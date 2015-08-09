from rvr.poker.cards import Card, RIVER
from rvr.poker.handrange import HandRange, unweighted_options_to_description,\
    remove_board_from_range, NOTHING
from rvr.poker.showdown import showdown_equity
from sqlalchemy.orm.session import object_session
from rvr.core.dtos import line_description, ActionResult, UserDetails
from rvr.poker.action import range_contains_hand
from numpy.core.multiarray import concatenate
from rvr.db import tables

class InvalidComboForTree(Exception):
    """
    While attempting to calculate the EV of a combo at a point in the game tree,
    it turns out that some branches of the sub-tree are not possible while
    holding this combo, so there's no meaningful answer to the EV question.
    """
    pass

class GameTreeNode(object):
    """
    Partial or full game tree or node, with summary details of current node.
    """
    def __init__(self, street, board, actor, action, parent,
            ranges_by_userid, total_contrib=None, winners=None, final_pot=None):
        self.street = street
        self.board = board  # raw, string
        self.actor = actor
        self.action = action  # ActionResult
        self.parent = parent  # GameTreeNode
        self.children = []  # list of GameTreeNode
        self.ranges_by_userid = {k: HandRange(v)
                                 for k, v in ranges_by_userid.items()}
        # total chips put in
        self.total_contrib = dict(total_contrib)
        self.winners = set(winners) if winners else None  # set of userid
        self.final_pot = final_pot
        self.combo_evs = {}

    def __repr__(self):
        child_actions = [child.action.to_action() for child in self.children]
        return "GameTreeNode(street=%r, board=%r, actor=%r, action='%s', "  \
            "betting_line=%r, child_actions=%r, ranges_by_userid=%r, "  \
            "total_contrib=%r, winners=%r, final_pot=%r)" %  \
            (self.street, self.board, self.actor, self.action,
             line_description(self.betting_line),
             child_actions, self.ranges_by_userid, self.total_contrib,
             self.winners, self.final_pot)

    def get_betting_line(self):
        """
        Calculate betting line. Same format results as calculate_betting_line.
        """
        if self.parent is None:
            return {}
        partial = self.parent.get_betting_line()
        partial.setdefault(self.street, []).append(self.action.to_action())
        return partial
    betting_line = property(get_betting_line)

    def all_combos_ev(self, userid, local=False):
        """
        Return a mapping of combo to EV at this point in the game tree, for each
        combo in the user's range at this point.

        Recall that a combo is a frozenset of two cards.
        """
        user_range = self.ranges_by_userid[userid]
        combos = user_range.generate_options(Card.many_from_text(self.board))
        results = {}
        for combo in combos:
            try:
                results[combo] = self.combo_ev(combo, userid, local)
            except InvalidComboForTree:
                pass
        return results

    def calculate_combo_ev(self, combo, userid):
        """
        Calculate EV for a combo at this point in the game tree.
        """
        if self.children:
            # intermediate node, EV is combination of children's
            # oh, each child needs a weight / probability
            # oh, it's combo specific... "it depends" ;)

            # EV of combo is:
            # weighted sum of EV of children, but only for children where the
            # combo is present (where combo isn't present, probability is zero)

            # to assess probability:
            # - if this node's children are performed by this user:
            #   - EV is the EV of the action that contains this combo
            # - otherwise:
            #   - remove combo from the children's actor's current range
            #   - consider how many combo's of children's actor's current range
            #     proceed to each child
            #   - voila
            # This conveniently works even in a multi-way pot. It's a very good
            # approximation of the true probabilities. And note that truly
            # calculating the true probabilities is not possible.
            actor = self.children[0].actor
            if actor == userid:
                # EV is the EV of the action that contains this combo
                for node in self.children:
                    if range_contains_hand(node.ranges_by_userid[userid],
                                           combo):
                        return node.combo_ev(combo, userid)
                raise InvalidComboForTree('Combo not in child ranges for userid'
                    ' %d at line %s.' %
                    (userid, line_description(self.betting_line)))
            else:
                # probabilistic weighting of child EVs
                # size of bucket is probability of this child
                buckets = {child: child.ranges_by_userid[actor]  \
                    .generate_options(Card.many_from_text(child.board) +
                                      list(combo))
                    for child in self.children}
                total = len(concatenate(buckets.values()))
                probabilities = {child: 1.0 * len(buckets[child]) / total
                                 for child in self.children}
                ev = sum(probabilities[child] * child.combo_ev(combo, userid)
                    for child in self.children
                    if range_contains_hand(child.ranges_by_userid[userid],
                        combo))
                return ev
                # Invalid combos are ignored / not calculated or aggregated.
        elif userid not in self.winners:
            # they folded
            return 0.0 - self.total_contrib[userid]
        elif len(self.winners) == 1:
            # uncontested pot
            return 0.0 + self.final_pot - self.total_contrib[userid]
        else:
            # showdown
            ranges = {userid: range_
                      for userid, range_ in self.ranges_by_userid.items()}
            combos = set([combo])
            description = unweighted_options_to_description(combos)
            ranges[userid] = HandRange(description)
            equities, _iteration =  \
                showdown_equity(ranges, Card.many_from_text(self.board),
                    hard_limit=10000)  # TODO: 1: this is not good enough
            equity = equities[userid]
            return equity * self.final_pot - self.total_contrib[userid]

    def combo_ev(self, combo, userid, local=False):
        """
        EV for a combo at this point in the game tree, potentially
        pre-calculated.
        """
        key = (combo, userid)
        if not self.combo_evs.has_key(key):
            self.combo_evs[key] = self.calculate_combo_ev(combo, userid)
        if local:
            # To their true EV for the whole game at this point, add back their
            # total contributions so far. This yields their EV compared to
            # folding at this point. Basically, you don't want this ever to
            # be negative.
            return self.combo_evs[key] + self.total_contrib[userid]
        else:
            return self.combo_evs[key]

    @classmethod
    def _merge(cls, node, partial):
        """
        Merge this partial tree into this node.

        Also creates child nodes and merges partial's nodes into new children.
        """
        if node.street != partial.street:
            raise ValueError('Inconsistent streets')
        if node.action != partial.action:
            raise ValueError('Inconsistent actions')
        for template in partial.children:
            # look for a child with this action
            for child in node.children:
                if child.action.to_action() == template.action.to_action():
                    break
            else:
                # create a new one, a copy of template, without children yet
                # (because this line is in the other, but not in this)
                descriptions = {k: v.description
                    for k, v in template.ranges_by_userid.items()}
                child = cls(template.street, template.board,
                            template.actor, template.action, node,
                            descriptions, template.total_contrib,
                            template.winners, template.final_pot)
                node.children.append(child)
            cls._merge(child, template)

    @classmethod
    def from_game(cls, game):
        """
        Create a partial game tree from a single game. Note that this still
        creates branches (multi-child nodes) due to non-terminal folds and
        showdowns.
        """
        # TODO: REVISIT: Blackbox testing? Unit testing? Something!
        # Any error in any of this logic will create some obscure bug in some
        # game tree.
        # TODO: 4: A general purpose replayer. How many times do we have to
        # write this code before we refactor it into something reusable... and
        # demonstrably correct!
        actual_ranges = {}
        for rgp, player in zip(game.rgps, game.situation.players):
            new_range = remove_board_from_range(player.range,
                game.situation.board)
            actual_ranges[rgp.userid] = new_range.description
        board_raw = game.situation.board_raw
        session = object_session(game)
        # We need to look for:
        # - GameHistoryActionResult, to find actions that happened
        # - GameHistoryRangeAction, to find folds
        # - GameHistoryShowdown, to find showdown calls
        # - GameHistoryBoard, to know its the river, because then three-handed
        #   folds can be terminal
        history = []
        for table in [tables.GameHistoryActionResult,
                      tables.GameHistoryRangeAction,
                      tables.GameHistoryShowdown,
                      tables.GameHistoryBoard]:
            history.extend(session.query(table)  \
                .filter(table.gameid == game.gameid).all())
        history.sort(key=lambda row: row.order)
        current_round = game.situation.current_round
        stacks = {rgp.userid: player.stack
                  for rgp, player in zip(game.rgps, game.situation.players)}
        contrib = {rgp.userid: player.contributed
                   for rgp, player in zip(game.rgps, game.situation.players)}
        total_contrib = dict(contrib)
        to_act = {rgp.userid
                  for rgp, player in zip(game.rgps, game.situation.players)
                  if player.left_to_act}
        pot = game.situation.pot_pre +  \
            sum(p.contributed for p in game.situation.players)
        raise_total = max(p.contributed for p in game.situation.players)
        remain = {rgp.userid for rgp in game.rgps}
        root = cls(game.situation.current_round, board_raw, None,
                   None, None, actual_ranges, total_contrib)
        node = root  # where we're adding actions
        prev_range_action = None
        for item in history:
            # reset game state for new round
            if isinstance(item, tables.GameHistoryBoard):
                current_round = item.street
                board_raw = item.cards
                to_act = set(remain)
                contrib = {rgp.userid: 0 for rgp in game.rgps}
                raise_total = 0
                for userid, old_range in actual_ranges.iteritems():
                    new_range = remove_board_from_range(HandRange(old_range),
                        Card.many_from_text(item.cards))
                    actual_ranges[userid] = new_range.description
            if isinstance(item, tables.GameHistoryShowdown):
                # add call
                call_cost = raise_total - contrib[prev_range_action.userid]
                action = ActionResult.call(call_cost)
                ranges = dict(actual_ranges)
                ranges[prev_range_action.userid] =  \
                    prev_range_action.passive_range
                showdown_contrib = dict(total_contrib)
                showdown_contrib[prev_range_action.userid] += call_cost
                showdown_pot = pot + call_cost
                child = cls(current_round, board_raw,
                            prev_range_action.userid, action,
                            node, ranges,
                            total_contrib=showdown_contrib, winners=remain,
                            final_pot=showdown_pot)
                node.children.append(child)
            # Only if the fold is terminal is it part of the tree.
            # Folds are terminal when:
            # - two-handed; or,
            # - three-handed when:
            #   - all other players have acted on the river; or,
            #   - are all in before the river; or,
            # - they fold 100%
            if isinstance(item, tables.GameHistoryRangeAction):
                prev_range_action = item
                if item.fold_ratio is None:
                    has_fold = item.fold_range != NOTHING
                else:
                    has_fold = item.fold_ratio != 0.0
                is_final_round = current_round == RIVER or  \
                    not all(stacks.values())
                heads_up = len(remain) == 2
                final_action = len(to_act) == 1 and is_final_round
                # There's no (implicit) fold when multi-way and play continues.
                if has_fold and (final_action or heads_up):
                    # Play would not continue with a fold here, so there will be
                    # no actual fold action.
                    # TODO: 3: use game_continues?
                    # Add a non-played fold. We keep the folded player's range
                    # in here, because it is relevant to consider the EV of each
                    # folded combo.
                    winners = set(remain)
                    winners.remove(item.userid)
                    # winners may be one (HU) or multiple (multiway)
                    ranges = actual_ranges
                    ranges[item.userid] = item.fold_range
                    child = cls(current_round, board_raw, item.userid,
                                ActionResult.fold(), node, ranges,
                                total_contrib=total_contrib, winners=winners,
                                final_pot=pot)
                    node.children.append(child)
            if isinstance(item, tables.GameHistoryActionResult):
                # maintain game state
                if item.is_passive:
                    actual_ranges[item.userid] = prev_range_action.passive_range
                    stacks[item.userid] -= item.call_cost
                    contrib[item.userid] += item.call_cost
                    total_contrib[item.userid] += item.call_cost
                    pot += item.call_cost
                    action = ActionResult.call(item.call_cost)
                if item.is_aggressive:
                    actual_ranges[item.userid] =  \
                        prev_range_action.aggressive_range
                    chips = item.raise_total - contrib[item.userid]
                    stacks[item.userid] -= chips
                    contrib[item.userid] += chips
                    total_contrib[item.userid] += chips
                    pot += chips
                    raise_total = item.raise_total
                    to_act = set(remain)
                    action = ActionResult.raise_to(raise_total, item.is_raise)
                if item.is_fold:
                    remain.remove(item.userid)
                    action = ActionResult.fold()
                    # and yes, we still traverse in (multi-way)
                to_act.remove(item.userid)
                # add fold, check, call, raise or bet, and traverse in
                child = cls(current_round, board_raw, item.userid, action, node,
                            actual_ranges, total_contrib)
                node.children.append(child)
                # traverse down
                node = child
        return root

    @classmethod
    def from_games(cls, games):
        """
        Create merged game tree from all games in a group.
        """
        first, others = games[0], games[1:]
        root = cls.from_game(first)
        for game in others:
            cls._merge(root, cls.from_game(game))
        return root

class GameTree(object):
    """
    Game tree root node, and additional details
    """
    # TODO: 1.1: efficient exhaustive equity for hands-vs-range pre-river
    # TODO: 1.0: record whether nodes have complete subtree or not
    # (i.e. exclude nodes with unplayed children, incomplete children, or
    # pre-river non-all-in)
    def __init__(self, groupid, users, root):
        self.groupid = groupid
        self.users = users  # list of UserDetails
        self.root = root

    def __repr__(self):
        return "GameTree(groupid=%r, users=%r, root=%r)" %  \
            (self.groupid, self.users, self.root)

    @classmethod
    def from_games(cls, games):
        """
        Create merged game tree from all games in a group.
        """
        root = GameTreeNode.from_games(games)
        groupid = games[0].spawn_group
        users = [UserDetails.from_user(rgp.user) for rgp in games[0].rgps]
        return cls(groupid, users, root)
