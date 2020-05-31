"""
Central analysis logic such as the "re/analyse all games" function.

The paradigm here is that DTOs contain all the information the previous
verion's objects did, and the database objects contain a relational version
of the same.
"""
import logging
from rvr.infrastructure.util import concatenate
from rvr.db.tables import GameHistoryActionResult, GameHistoryRangeAction,  \
    GameHistoryUserRange, AnalysisFoldEquity, GameHistoryBoard,  \
    AnalysisFoldEquityItem, GameHistoryShowdown,  \
    GameHistoryShowdownEquity, \
    PaymentToPlayer, RunningGameParticipantResult
from rvr.poker.handrange import HandRange, unweighted_options_to_description
from rvr.poker.cards import Card, RIVER, PREFLOP
import unittest
from rvr.poker.action import game_continues
from rvr.poker.showdown import showdown_equity, all_combos_ev
from rvr.mail.notifications import notify_finished

# pylint:disable=R0902,R0913,R0914,R0903

def _range_desc_to_size(range_description):
    """
    Given a range description, determine the number of combos it represents.
    """
    return len(HandRange(range_description).generate_options())

class FoldEquityAccumulator(object):
    """
    Holds the data needed to calculate and create an AnalysisFoldEquity.
    """
    def __init__(self, gameid, order, street, board, bettor, range_action,
                 raise_total, pot_before_bet, bet_cost,
                 pot_if_called, potential_folders):
        logging.debug("gameid %d, order %d, FEA initialising",
                      gameid, order)
        self.gameid = gameid
        self.order = order
        self.street = street
        self.board = board
        self.bettor = bettor
        self.range_action = range_action
        self.raise_total = raise_total
        self.pot_before_bet = pot_before_bet
        self.bet_cost = bet_cost
        self.pot_if_called = pot_if_called
        self.potential_folders = potential_folders  # userids
        self.folds = []  # list of (userid, fold_ratio)

    def folder(self, ghra):
        """
        ghra is a GameHistoryRangeAction, who we consider to be a folder.

        Returns True if this fea is complete.
        """
        logging.debug("gameid %d, FEA %d, adding folder: userid %d",
                      self.gameid, self.order, ghra.userid)
        self.potential_folders.remove(ghra.userid)
        fold_range = HandRange(ghra.fold_range)
        pas = HandRange(ghra.passive_range)
        agg = HandRange(ghra.aggressive_range)
        nonfold_range = pas.add(agg, self.board)
        self.folds.append((ghra.userid, fold_range, nonfold_range))
        return len(self.potential_folders) == 0

    def _create_afe(self):
        """
        Create the AnalysisFoldEquity
        """
        afe = AnalysisFoldEquity()
        afe.gameid = self.gameid
        afe.order = self.order
        afe.street = self.street
        afe.pot_before_bet = self.pot_before_bet
        afe.is_raise = self.range_action.is_raise
        afe.is_check = self.range_action.is_check
        afe.bet_cost = self.bet_cost
        afe.raise_total = self.raise_total
        afe.pot_if_called = self.pot_if_called
        return afe

    def _create_afei(self, combo, is_agg=False, is_pas=False, is_fol=False):
        """
        Create an AnalaysisFoldEquityItem for a particular combo in Hero's range
        """
        afei = AnalysisFoldEquityItem()
        afei.gameid = self.gameid
        afei.order = self.order
        lower_card, higher_card = sorted(combo)
        afei.higher_card = higher_card.to_mnemonic()
        afei.lower_card = lower_card.to_mnemonic()
        afei.is_aggressive = is_agg
        afei.is_passive = is_pas
        afei.is_fold = is_fol
        afei.fold_ratio = 1.0
        for _, fold_range, nonfold_range in self.folds:
            fold_size = len(fold_range.generate_options(
                self.board + list(combo)))
            nonfold_size = len(nonfold_range.generate_options(
                self.board + list(combo)))
            folder_fold_ratio = 1.0 * fold_size / (fold_size + nonfold_size)
            afei.fold_ratio *= folder_fold_ratio
            # product of everyone's fold ratios = how often we take it down
        nonfold_ratio = 1.0 - afei.fold_ratio
        afei.immediate_result = afei.fold_ratio * self.pot_before_bet -  \
            nonfold_ratio * self.bet_cost
        if nonfold_ratio and self.street != RIVER:
            afei.semibluff_ev = -afei.immediate_result / nonfold_ratio
            afei.semibluff_equity = afei.semibluff_ev / self.pot_if_called
        else:
            afei.semibluff_ev = None
            afei.semibluff_equity = None
        return afei

    def finalise(self, session):
        """
        Assuming complete, return an AnalysisFoldEquity
        """
        logging.debug("gameid %d, FEA %d, calculating...", self.gameid,
                      self.order)
        logging.debug("actually, not bothering!")
        return  # TODO: 5: reintroduce this (fold equity analysis)
        #pylint:disable=unreachable
        assert len(self.potential_folders) == 0
        afe = self._create_afe()
        session.add(afe)
        for combo in HandRange(self.range_action.aggressive_range)  \
                .generate_options(self.board):
            afei = self._create_afei(combo, is_agg=True)
            session.add(afei)
        for combo in HandRange(self.range_action.passive_range)  \
                .generate_options(self.board):
            afei = self._create_afei(combo, is_pas=True)
            session.add(afei)
        for combo in HandRange(self.range_action.fold_range)  \
                .generate_options(self.board):
            afei = self._create_afei(combo, is_fol=True)
            session.add(afei)
        logging.debug("gameid %d, FEA %d, finalised",
                      self.gameid, self.order)
        return afe

class ComboOrderAccumulator(object):
    """
    Calculates combo EV for a point in the hand, as it's replayed.

    The convention is that this number represents the EV before the event
    recorded at the given order. This really only makes a difference for vpip,
    but it's per user expectations. It doesn't make sense for it to be a 0 ev
    call in the case that I later fold.

    Note that some combos that are accumulated end up with invalid results.
    These are the combos that don't get played out. E.g. I have a raise range,
    but I happen to call. In Optimisation Mode, these will have valid evs in
    another betting line.

    Ideally we would delete these when a non-terminal betting line is not played
    out.
    """
    # TODO: 0: delete combos when non-terminal betting lines are not played out
    def __init__(self, userid, combo, order):
        self.userid = userid
        self.combo = combo
        self.order = order
        self.ev = 0.0
        self.factor = 1.0

    def vpip(self, contribution):
        """
        Combo voluntarily puts money in pot, to bet or call
        """
        self.ev -= contribution * self.factor

    def _terminal_outcome(self, result, weight):
        """
        With a likelihood of weight, result happens.
        Play continues if weight < 1.0, but factor reduces accordingly.
        """
        self.ev += result * weight * self.factor
        self.factor *= (1.0 - weight)

    def fold_equity(self, pot, weight):
        """
        Combo got folds and so wins pot (some of the time, at least)
        """
        self._terminal_outcome(pot, weight)

    def showdown(self, winnings, weight):
        """
        Combo goes to showdown (some of the time, at least)
        """
        self._terminal_outcome(winnings, weight)

class AnalysisReplayer(object):
    """
    Plays through a hand, performs analysis, and creates analysis items in
    database.
    """
    #pylint:disable=W0201
    def __init__(self, session, game):
        logging.debug("gameid %d, AnalysisReplayer, initialising",
                      game.gameid)
        if not game.game_finished:
            raise ValueError("Can't analyse game until finished.")
        if game.analysis_performed:
            raise ValueError("Game is already analysed.")
        self.session = session
        self.game = game
        self.pot = self.game.situation.pot_pre +  \
            sum([p.contributed for p in self.game.situation.players])
        self.starting_pot = self.pot
        self.street = self.game.situation.current_round
        self.board = self.game.situation.board
        self.fea = None  # current fold equity accumulator
        self.prev_range_action = None
        self.ranges = {self.game.rgps[i].userid:
                       self.game.situation.players[i].range_raw
                       for i in range(len(self.game.situation.players))}
        self.stacks = {self.game.rgps[i].userid:
                       self.game.situation.players[i].stack
                       for i in range(len(self.game.situation.players))}
        self.contrib = {self.game.rgps[i].userid:
                        self.game.situation.players[i].contributed
                        for i in range(len(self.game.situation.players))}
        self.remaining_userids = [rgp.userid for rgp in self.game.rgps]
        self.left_to_act = [self.game.rgps[i].userid
                            for i in range(len(self.game.situation.players))
                            if self.game.situation.players[i].left_to_act]
        # map of userid to (map of combo to (set of ComboOrderAccumulator))
        self.combo_orders = {
            self.game.rgps[i].userid: {
                combo: set([ComboOrderAccumulator(self.game.rgps[i].userid,
                                                  combo,
                                                  None)])  # for the whole game
                for combo in HandRange(self.ranges[self.game.rgps[i].userid])  \
                    .generate_options(self.board)
            }
            for i in range(len(self.game.situation.players))
        }
        # TODO: 0: maybe this time we can do it, and put it in the database, and be done with oh god please.
        #
        # Create new 0.0 for every order that could be shown to user in history:
        # - range action
        # - action result
        # - showdown
        #
        # Then update all combo orders (including the new ones) when we find a:
        # - (tick) bet (Hero gets a vpip)
        # - (tick) call (Hero gets a vpip)
        # - (tick) showdown call (Hero gets a vpip)
        # - (tick) fold (Villain gets a fold equity)
        # - showdown (everyone gets a showdown)
        #
        # I.e. any time there's a payment.

    def _new_combo_evs(self, userid, range_, order):
        """
        Add new ComboOrderAccumulator items for new game node
        """
        combo_map = self.combo_orders[userid]
        combos = range_.generate_options(self.board)
        for combo in combos:
            evs = combo_map.setdefault(combo, set())
            evs.add(ComboOrderAccumulator(userid, combo, order))

    def _combo_vpips(self, userid, range_, contribution):
        """
        Apply vpip to Hero's combos
        """
        combo_map = self.combo_orders[userid]
        combos = range_.generate_options(self.board)
        for combo in combos:
            for ev in combo_map[combo]:
                ev.vpip(contribution)

    def _combo_fold_equity(self, userid, combo, pot, weight):
        """
        Apply a fold equity payment for a combo
        """
        for ev in self.combo_orders[userid][combo]:
            ev.fold_equity(pot, weight)

    def _fold_ratio(self, hero_combos, fold_combos, villain_combo):
        """
        How often does hero fold when Villain holds combo?
        """
        count_all = 0
        count_folds = 0
        for combo in hero_combos:
            if len(combo.union(villain_combo)) == 4:
                count_all += 1
                if combo in fold_combos:
                    count_folds += 1
        if count_all:
            return 1.0 * count_folds / count_all
        else:
            return None

    def _all_combos_fold_equity(self, range_action, folder, nonfolder):
        """
        Unique fold equity payment for each combo *of Villain's range*.

        Note that folding has no effect on Heros's combo ev.
        """
        villain = HandRange(self.ranges[nonfolder])
        hero = HandRange(self.ranges[folder])
        fold = HandRange(range_action.fold_range)
        villain_combos = villain.generate_options(self.board)
        hero_combos = hero.generate_options(self.board)
        fold_combos = fold.generate_options(self.board)
        for combo in villain_combos:
            fold_ratio = self._fold_ratio(hero_combos, fold_combos, combo)
            if fold_ratio is not None:
                self._combo_fold_equity(nonfolder, combo, self.pot, fold_ratio)

    def _combo_showdown(self, userid, combo, winnings, weight):
        """
        Apply a showdown payment for a combo
        """
        for ev in self.combo_orders[userid][combo]:
            ev.showdown(winnings, weight)

    def _combo_showdown_weight(self):
        pass

    def _all_combos_showdown(self, pot, board, ranges):
        """
        Showdown payments for every combo of every player's range
        """
        # The hardest spot to deal with is this:
        # Player A bets
        # Player B calls
        # Player C folds some, calls some, and raises some
        # To evaluate Player C's combos is easy. They are all considered to have
        # 100% weight, because from their perspective Player A's and Player B's
        # bet and call happen 100% of the time.
        # But to evaluate Player A's combos, or Player B's combos is harder.
        # We have to respect that the three-player showdown only happens some of
        # the time, because Player C could have folded (a terminal option) or
        # raise (a non-terminal option). So Player A or Player B's EV for the
        # three-player showdown is weighted. The weight of Player C's folds
        # don't contribute to this - instead they contribute to the weight of
        # a different showdown, between Player A and Player B.
        #
        # So I guess it goes like this:
        #
        # Player A bets.
        # Player B calls, but we don't have a showdown yet.
        # Player C folds some, calls some, and raises some.
        # The EV of a combo of Player A is a combination of the EV from the
        # showdown that happens when Player C folds, and the EV from the
        # showdown that happens when Player C calls, and the EV of whatever
        # happens when Player C raises.
        # So it is very important that we know how likely Player C's fold, call
        # and raise are.
        # Player A or Player B's EV will be:
        # - two-player showdown EV * (fold_ratio for this combo)
        # - three-player showdown EV * (call_ratio for this combo)
        # - and a reduction of weight equal to (fold_ratio + call_ratio)
        # This will mimic what happens in-game, where both showdowns are handled
        # together, with each given a weight appropriate to the action ratios,
        # and then a total factor reduction of (non_terminal / total).
        # It'll work exactly the same when the range is a single combo, of
        # course.
        #
        # So finally we realise how complicated this is. For every combo of each
        # player (except the last player), we must:
        # - calculate the fold_ratio, call_ratio, raise ratio of the last player
        # - calculate the EV of the showdown when they fold
        # - calculate the EV of the showdown when they call
        # - reduce the factor by (f+c)/(f+c+r)
        # And this kind of needs to be done atomically.
        userids_combo_evs = all_combos_ev(board=board,
                                          userids=ranges.keys(),
                                          pot=pot,
                                          ranges=ranges)
        for userid, combo_evs in userids_combo_evs:
            for description, ev in combo_evs:
                combo = Card.many_from_text(description)
                weight = 1#self._combo_showdown_weight()  # impossible to calculate here
                if weight is not None:
                    self._combo_showdown(userid, combo, ev, weight)

    def process_board(self, item):
        """
        Process a GameHistoryBoard
        """
        self.contrib = {u:0 for u in self.remaining_userids}
        self.left_to_act = self.remaining_userids[:]
        assert self.fea is None
        self.street = item.street
        self.board = Card.many_from_text(item.cards)

    def process_action_result(self, item):
        """
        Process a GameHistoryActionResult
        """
        self._new_combo_evs(userid=item.userid,
                            range_=HandRange(self.ranges[item.userid]),
                            order=item.order)
        if item.is_fold:
            self.remaining_userids.remove(item.userid)
            self.ranges[item.userid] = self.prev_range_action.fold_range
        if item.is_passive:
            self.pot += item.call_cost
            self.contrib[item.userid] += item.call_cost
            self.stacks[item.userid] -= item.call_cost
            self.pot_payment(item, item.call_cost)
            if self.fea is not None:
                # because they call, we will never know how much the other
                # players would have folded
                logging.debug("gameid %d, FEA %d, canceling",
                              self.fea.gameid, self.fea.order)
            self.fea = None
            self.ranges[item.userid] = self.prev_range_action.passive_range
        if item.is_aggressive:
            self.left_to_act = self.remaining_userids[:]
            amount_raised = item.raise_total - max(self.contrib.values())
            bet_cost = item.raise_total - self.contrib[item.userid]
            self.contrib[item.userid] = item.raise_total
            self.stacks[item.userid] -= bet_cost
            self.pot_payment(item, bet_cost)
            # we assume the person who has contributed the most calls
            pot_if_called = self.pot + bet_cost + amount_raised
            self.fea = FoldEquityAccumulator(
                gameid=self.game.gameid,
                order=item.order,
                street=self.street,
                board=self.board,
                bettor=item.userid,
                range_action=self.prev_range_action,  # ranges before bet
                raise_total=item.raise_total,
                pot_before_bet=self.pot,
                bet_cost=bet_cost,
                pot_if_called=pot_if_called,
                potential_folders=[u for u in self.remaining_userids if
                    u != item.userid])
            self.pot += bet_cost
            self.ranges[item.userid] = self.prev_range_action.aggressive_range
        self.left_to_act.remove(item.userid)

    def range_action_fea(self, item):
        """
        Apply range action to fold equity analysis.
        """
        if self.fea is not None:
            # We have a folder (assuming this fea qualifies).
            # We don't care if that final person raises or not; the
            # important point is that we know their fold range.
            fea_complete = self.fea.folder(item)
            if fea_complete:
                self.fea.finalise(self.session)
                self.fea = None

    def pot_payment(self, action_item, contribution):
        """
        A simple payment from a player to the pot.
        """
        if contribution == 0:
            return
        self._combo_vpips(action_item.userid,
                          HandRange(self.ranges[action_item.userid]),
                          contribution)
        amount = -action_item.factor * contribution
        logging.debug('gameid %d, order %d, userid %d, pot payment: '
                      'factor %0.4f * contribution %d = amount %0.8f',
                      action_item.gameid, action_item.order, action_item.userid,
                      action_item.factor, contribution, amount)
        payment = PaymentToPlayer()
        payment.reason = PaymentToPlayer.REASON_POT
        payment.gameid = action_item.gameid
        payment.order = action_item.order
        payment.userid = action_item.userid
        payment.amount = amount
        self.session.add(payment)

    def fold_equity_payments(self, range_action, fold_ratio):
        """
        Fold equity payment occurs for every range action with only two players
        remaining, and is a payment equal to the current pot multiplied by the
        current factor multiplied by the fold ratio (up to and including 100% of
        the pot, e.g. when in a HU situation BTN open folds 100%).

        This is not a payment from one player to the other. It is a payment from
        the pot to the player who bet. The bettor gains a portion of the pot
        equal to the fold ratio, and the pot loses this by virtue of a reduction
        in the current factor.
        """
        if len(self.remaining_userids) != 2:
            return
        # Note that this includes the bet amount from the betting player, an as-
        # yet unmatched bet. This is correct, because this is (for example) the
        # amount the betting player will win if this player folds 100% - no
        # more, no less.
        if not fold_ratio:
            logging.debug('gameid %d, order %d, fold ratio 0.0, '
                          'skipping fold equity payments',
                          range_action.gameid, range_action.order)
            return
        amount = self.pot * range_action.factor * fold_ratio
        assert range_action.userid in self.remaining_userids
        if self.remaining_userids[0] == range_action.userid:
            nonfolder = self.remaining_userids[1]
        else:
            nonfolder = self.remaining_userids[0]
        logging.debug('gameid %d, order %d, userid %d, fold equity payment: '
                      'pot %d * factor %0.4f * fold ratio %0.4f = amount %0.8f',
                      range_action.gameid, range_action.order,
                      nonfolder,
                      self.pot, range_action.factor, fold_ratio, amount)
        nonfolder_payment = PaymentToPlayer()
        nonfolder_payment.reason = PaymentToPlayer.REASON_FOLD_EQUITY
        nonfolder_payment.gameid = range_action.gameid
        nonfolder_payment.order = range_action.order
        nonfolder_payment.userid = nonfolder
        nonfolder_payment.amount = amount
        self.session.add(nonfolder_payment)
        self._all_combos_fold_equity(range_action,
                                     folder=range_action.userid,
                                     nonfolder=nonfolder)

    def showdown_payments(self, showdown, equities):
        """
        Create showdown payments for all participants of this showdown.
        """
        logging.debug('gameid %d, order %d, creating showdown payments',
                      showdown.gameid, showdown.order)
        for participant in equities:
            payment = PaymentToPlayer()
            payment.reason = PaymentToPlayer.REASON_SHOWDOWN
            payment.gameid = showdown.gameid
            payment.order = showdown.order
            payment.userid = participant.userid
            payment.amount = showdown.factor * showdown.pot * participant.equity
            logging.debug('gameid %d, order %d, userid %d, showdown payment: '
                          'factor %0.4f * pot %d * equity %0.4f = '
                          'amount %0.8f',
                          showdown.gameid, showdown.order, participant.userid,
                          showdown.factor, showdown.pot, participant.equity,
                          payment.amount)
            self.session.add(payment)
            # and redline and blueline
            total_contrib = showdown.factor *  \
                (showdown.pot - self.starting_pot) / len(equities)
            payment = PaymentToPlayer()
            payment.reason = PaymentToPlayer.REASON_REDLINE
            payment.gameid = showdown.gameid
            payment.order = showdown.order
            payment.userid = participant.userid
            payment.amount = total_contrib
            logging.debug('gameid %d, order %d, userid %d, redline payment: '
                          'factor %0.4f * (pot %d - start %d) / people %d = '
                          'amount %0.8f',
                          showdown.gameid, showdown.order, participant.userid,
                          showdown.factor, showdown.pot, self.starting_pot,
                          len(equities), payment.amount)
            self.session.add(payment)
            payment = PaymentToPlayer()
            payment.reason = PaymentToPlayer.REASON_BLUELINE
            payment.gameid = showdown.gameid
            payment.order = showdown.order
            payment.userid = participant.userid
            payment.amount = -total_contrib
            logging.debug('gameid %d, order %d, userid %d, blueline payment: '
                          '-factor %0.4f * (pot %d - start %d) / people %d = '
                          'amount %0.8f',
                          showdown.gameid, showdown.order, participant.userid,
                          showdown.factor, showdown.pot, self.starting_pot,
                          len(equities), payment.amount)
            self.session.add(payment)

    def showdown_call(self, gameid, order, caller, call_cost, call_ratio,
                      factor, range_):
        """
        This is a call that doesn't really happen (it's not in the game tree
        main branch), but it's terminal (like a fold), and we pay out showdowns,
        but to do so we also need to charge for the call that doesn't happen.
        """
        self._combo_vpips(caller, range_, call_cost)
        payment = PaymentToPlayer()
        payment.reason = PaymentToPlayer.REASON_SHOWDOWN_CALL
        payment.gameid = gameid
        payment.order = order
        payment.userid = caller
        payment.amount = -call_cost * factor * call_ratio
        logging.debug('gameid %d, order %d, userid %d, showdown call payment: '
            'call cost %d * factor %0.4f * call ratio %0.4f = '
            'amount %0.8f',
            gameid, order, caller, call_cost, factor, call_ratio,
            payment.amount)
        self.session.add(payment)

    def analyse_showdown(self, ranges, order, is_passive, userids):
        """
        Create a showdown with given userids. Pre-river if pre-river.
        """
        for userid, range_ in ranges.iteritems():
            if userid in userids:
                self._new_combo_evs(userid, range_, order)
        showdowns = self.session.query(GameHistoryShowdown)  \
            .filter(GameHistoryShowdown.gameid == self.game.gameid)  \
            .filter(GameHistoryShowdown.order == order)  \
            .filter(GameHistoryShowdown.is_passive == is_passive).all()
        if len(showdowns) != 1:
            logging.warning("gameid %d, order %d, has %d showdowns",
                            self.game.gameid, order, len(showdowns))
            return
        logging.debug("gameid %d, order %d, confirmed existing showdown",
                      self.game.gameid, order)
        showdown = showdowns[0]
        # TODO: REVISIT: this ignores ranges of folded players
        # It might make a difference in situations where a player has (for
        # example) limited their range to Ax and later folded, hence surely
        # removing an ace from the deck for the other players (significantly
        # changing their equities)
        # Actually, where it makes a difference, it would be really neat to see
        # it. Imagine someone saying "hey, this stupid site says I made a bad
        # call here with 23% equity when really I had 32% equity and it was a
        # great call!" Well no actually, the card removal effects of the folded
        # players change your equity, and you suck at poker.
        range_map = {k: v for k, v in ranges.iteritems() if k in userids}
        assert self.board == self.game.board
        equity_map, iterations = showdown_equity(range_map, self.game.board)
        logging.debug('gameid %d, order %d, is_passive %r, factor %0.8f, '
                      'showdown with userids: %r, equity: %r '
                      '(iterations %d)',
                      self.game.gameid, order, is_passive, showdown.factor,
                      userids, equity_map, iterations)
        existing_equities = {p.showdown_order: p
            for p in showdown.participants}  #pylint:disable=no-member
        for showdown_order, userid in enumerate(userids):
            # create if not exist, otherwise update
            if showdown_order in existing_equities:
                participant = existing_equities[showdown_order]
            else:
                # TODO: REVISIT: this is ordered by situation player order,
                # not showdown order
                participant = GameHistoryShowdownEquity()
                self.session.add(participant)
                existing_equities[showdown_order] = participant
                participant.gameid = self.game.gameid
                participant.order = order
                participant.is_passive = is_passive
                participant.showdown_order = showdown_order
                participant.userid = userid
            participant.equity = equity_map[userid]
        self.showdown_payments(showdown=showdown,
                               equities=existing_equities.values())
        self._all_combos_showdown(showdown.pot, self.game.board, range_map)

    def _calculate_call_cost(self, userid):
        """
        It would have been convenient if this was stored in
        GameHistoryRangeAction... but it's easy enough to calculate based on
        this object's state.
        """
        return max(self.contrib.values()) - self.contrib[userid]

    def range_action_showdowns(self, item, fold_ratio, call_ratio):
        """
        Consider showdowns based on this range action resulting in a fold, and
        another based on this resulting in a check or call.
        """
        prev_contrib = None
        last_stack = None
        for userid in self.remaining_userids:
            if userid == item.userid:
                continue
            if userid in self.left_to_act:
                # no showdowns because the betting round hasn't finished
                return
            if prev_contrib is not None and  \
                    self.contrib[userid] != prev_contrib:
                # no showdowns because the betting round hasn't finished
                return
            prev_contrib = self.contrib[userid]
            last_stack = self.stacks[userid]
        # betting round is over
        if last_stack > 0 and self.street != RIVER:
            # end of betting round, but not showdown
            return
        order = item.order
        # Note that fold is arbitrarily considered to be before call
        if len(self.remaining_userids) > 2 and fold_ratio > 0.0:
            # this player folds, but the pot is contested, so we have a showdown
            order += 1
            ranges = {key: HandRange(txt)
                      for key, txt in self.ranges.iteritems()}
            # They (temporarily) fold
            ranges.pop(item.userid)
            self.analyse_showdown(ranges=ranges,
                order=order,
                is_passive=False,
                userids=[userid for userid in self.remaining_userids
                         if userid != item.userid])
        ranges = {key: HandRange(txt)
                  for key, txt in self.ranges.iteritems()}
        # They (temporarily) call
        ranges[item.userid] = HandRange(item.passive_range)
        if call_ratio > 0.0:
            # It's a real call, not folding 100%
            order += 1
            call_cost = self._calculate_call_cost(item.userid)
            if call_cost != 0:
                self.showdown_call(gameid=item.gameid, order=order,
                    caller=item.userid, call_cost=call_cost,
                    call_ratio=call_ratio, factor=item.factor,
                    range_=ranges[item.userid])
            self.analyse_showdown(ranges=ranges,
                order=order,
                is_passive=True,
                userids=self.remaining_userids)

    def process_range_action(self, item):
        """
        Process a GameHistoryRangeAction
        """
        self._new_combo_evs(userid=item.userid,
                            range_=HandRange(self.ranges[item.userid]),
                            order=item.order)
        legacy_fol = len(HandRange(item.fold_range).generate_options(self.board))
        legacy_pas = len(HandRange(item.passive_range).generate_options(self.board))
        legacy_agg = len(HandRange(item.aggressive_range).generate_options(self.board))
        total = legacy_fol + legacy_pas + legacy_agg
        fold_ratio = item.fold_ratio if item.fold_ratio is not None  \
            else 1.0 * legacy_fol / total
        call_ratio = item.passive_ratio if item.passive_ratio is not None  \
            else 1.0 * legacy_pas / total
        self.fold_equity_payments(range_action=item, fold_ratio=fold_ratio)
        self.range_action_fea(item)
        self.range_action_showdowns(item, fold_ratio=fold_ratio,
                                    call_ratio=call_ratio)
        will_act = set(self.left_to_act).difference({item.userid})
        fold_will_remain = set(self.remaining_userids).difference({item.userid})
        all_in = any([stack == 0 for stack in self.stacks.values()])
        self.fold_continues = game_continues(
            current_round=self.street,
            all_in=all_in,
            will_remain=fold_will_remain,
            will_act=will_act)
        passive_will_remain = set(self.remaining_userids)
        self.passive_continues = game_continues(
            current_round=self.street,
            all_in=all_in,
            will_remain=passive_will_remain,
            will_act=will_act)

    def process_child_item(self, item):
        """
        Process a single history item, as part of the broader analysis.
        """
        if isinstance(item, GameHistoryBoard):
            self.process_board(item)
        if isinstance(item, GameHistoryActionResult):
            # self.equity_payments(item)
            self.process_action_result(item)
        if isinstance(item, GameHistoryRangeAction):
            self.process_range_action(item)
            self.prev_range_action = item

    def finalise_results(self):
        """
        Calculate RunningGameParticipant's result, under each scheme
        """
        for rgp in self.game.rgps:
            payments = self.session.query(PaymentToPlayer)  \
                .filter(PaymentToPlayer.gameid == self.game.gameid)  \
                .filter(PaymentToPlayer.userid == rgp.userid).all()
            for scheme, include in  \
                    RunningGameParticipantResult.SCHEME_DETAILS.iteritems():  # @UndefinedVariable
                rgpr = RunningGameParticipantResult()
                rgpr.gameid = rgp.gameid
                rgpr.userid = rgp.userid
                rgpr.scheme = scheme
                rgpr.result = sum(payment.amount for payment in payments
                                  if payment.reason in include)
                self.session.add(rgpr)
                logging.debug("gameid %d, userid %d, scheme %s: result %0.4f",
                    rgpr.gameid, rgpr.userid, rgpr.scheme, rgpr.result)

    def analyse(self):
        """
        Perform all analysis on game that has not been done.

        If you need to reanalyse the game, delete the existing analysis first.
        """
        gameid = self.game.gameid

        logging.debug("gameid %d, AnalysisReplayer, analyse", gameid)
        items = [self.session.query(table)
                 .filter(table.gameid == gameid).all()
                 for table in [GameHistoryBoard,
                               GameHistoryUserRange,
                               GameHistoryActionResult,
                               GameHistoryRangeAction]]
        child_items = sorted(concatenate(items),
                             key=lambda c: c.order)
        for item in child_items:
            self.process_child_item(item)

        self.finalise_results()

    def finalise(self):
        """
        Commit, send out notification
        """
        self.game.analysis_performed = True
        self.session.commit()  # ensure it can only notify once
        logging.debug("gameid %d, notifying", self.game.gameid)
        notify_finished(self.game)
        self.session.commit()  # also a reasonable time to commit

class Test(unittest.TestCase):
    """
    Unit test class
    """
    # pylint:disable=W0212,C0103,R0904
    def test_create_afei_one_folder_bet(self):
        """ Test _create_afei for a bet against one player"""
        # bet 10 on a pot of 10
        # unprofitable bluff
        fea = FoldEquityAccumulator(
            gameid=0,
            order=0,
            street=PREFLOP,
            board=[],
            bettor=0,
            range_action=None,
            raise_total=10,
            pot_before_bet=10,
            bet_cost=10,
            pot_if_called=30,
            potential_folders=[])
        fold_range = HandRange("KK")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))
        afei = fea._create_afei(combo=Card.many_from_text("KsQh"), is_agg=True)
        self.assertAlmostEqual(afei.fold_ratio, 1.0 / 3.0)
        self.assertAlmostEqual(afei.immediate_result,
            1.0 / 3.0 * 10.0 + (2.0 / 3.0) * (-10))
        self.assertAlmostEqual(afei.semibluff_ev, 5.0)
        self.assertAlmostEqual(afei.semibluff_equity, 5.0 / 30.0)

    def test_create_afei_one_folder_raise(self):
        """ Test _create_afei for a raise against one player"""
        # raise from 10 to 30 on an original pot of 10
        # profitable bluff
        fea = FoldEquityAccumulator(
            gameid=0,
            order=0,
            street=PREFLOP,
            board=[],
            bettor=0,
            range_action=None,
            raise_total=30,
            pot_before_bet=20,
            bet_cost=30,
            pot_if_called=70,
            potential_folders=[])
        fold_range = HandRange("KK-JJ")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))
        afei = fea._create_afei(combo=Card.many_from_text("KsQh"), is_agg=True)
        self.assertAlmostEqual(afei.fold_ratio, 2.0 / 3.0)
        self.assertAlmostEqual(afei.immediate_result,
            2.0 / 3.0 * 20.0 + (1.0 / 3.0) * (-30.0))  # 3.33...
        self.assertAlmostEqual(afei.semibluff_ev, -10.0)
        self.assertAlmostEqual(afei.semibluff_equity, -10.0 / 70.0)

    def test_create_afei_one_folder_reraise(self):
        """ Test _create_afei for a reraise against one player"""
        # raise from 30 to 50 on an original pot of 10
        # unprofitable bluff
        fea = FoldEquityAccumulator(
            gameid=0,
            order=0,
            street=PREFLOP,
            board=[],
            bettor=0,
            range_action=None,
            raise_total=50,
            pot_before_bet=50,
            bet_cost=40,
            pot_if_called=110,
            potential_folders=[])
        fold_range = HandRange("QQ")
        nonfold_range = HandRange("AA-KK")
        fea.folds.append((1, fold_range, nonfold_range))
        afei = fea._create_afei(combo=Card.many_from_text("KsQh"), is_agg=True)
        self.assertAlmostEqual(afei.fold_ratio, 1.0 / 4.0)
        self.assertAlmostEqual(afei.immediate_result,
            1.0 / 4.0 * 50.0 + (3.0 / 4.0) * (-40.0))  # -17.5
        self.assertAlmostEqual(afei.semibluff_ev, 4.0 / 3.0 * 17.5)
        self.assertAlmostEqual(afei.semibluff_equity, 4.0 / 3.0 * 17.5 / 110.0)

    def test_create_afei_two_folders_bet(self):
        """ Test _create_afei for a bet against two players"""
        # bet 10 on a pot of 10
        # profitable bluff
        fea = FoldEquityAccumulator(
            gameid=0,
            order=0,
            street=RIVER,
            board=[],
            bettor=0,
            range_action=None,
            raise_total=10,
            pot_before_bet=10,
            bet_cost=10,
            pot_if_called=30,
            potential_folders=[])
        fold_range = HandRange("KK")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))
        fold_range = HandRange("KK")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))
        afei = fea._create_afei(combo=Card.many_from_text("AsQh"), is_agg=True)
        self.assertAlmostEqual(afei.fold_ratio, 4.0 / 9.0)
        self.assertAlmostEqual(afei.immediate_result,
            4.0 / 9.0 * 10.0 + (5.0 / 9.0) * (-10))
        self.assertEqual(afei.semibluff_ev, None)
        self.assertEqual(afei.semibluff_equity, None)

    def test_create_afei_two_folders_raise(self):
        """ Test _create_afei for a raise against two players"""
        # raise from 10 to 30 on an original pot of 10
        # unprofitable bluff
        fea = FoldEquityAccumulator(
            gameid=0,
            order=0,
            street=RIVER,
            board=[],
            bettor=0,
            range_action=None,
            raise_total=30,
            pot_before_bet=20,
            bet_cost=30,
            pot_if_called=70,
            potential_folders=[])
        fold_range = HandRange("KK")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))  # folds 2/3
        fold_range = HandRange("QQ")
        nonfold_range = HandRange("KK+")
        fea.folds.append((1, fold_range, nonfold_range))  # folds 1/4
        afei = fea._create_afei(combo=Card.many_from_text("AsQh"), is_agg=True)
        self.assertAlmostEqual(afei.fold_ratio, 1.0 / 6.0)
        self.assertAlmostEqual(afei.immediate_result,
            1.0 / 6.0 * 20.0 + (5.0 / 6.0) * (-30))  # -21.66...
        self.assertAlmostEqual(afei.semibluff_ev, None)
        self.assertAlmostEqual(afei.semibluff_equity, None)

    def test_create_afei_two_fodlers_reraise(self):
        """ Test _create_afei for a reraise against two players"""
        # raise from 30 to 50 on an original pot of 10
        # profitable bluff
        fea = FoldEquityAccumulator(
            gameid=0,
            order=0,
            street=RIVER,
            board=[],
            bettor=0,
            range_action=None,
            raise_total=50,
            pot_before_bet=50,
            bet_cost=50,
            pot_if_called=120,  # assumes called by the raiser, not the bettor
            potential_folders=[])
        fold_range = HandRange("KK")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))  # folds 2/3
        fold_range = HandRange("KK-JJ")
        nonfold_range = HandRange("AA")
        fea.folds.append((1, fold_range, nonfold_range))  # folds 5/6
        afei = fea._create_afei(combo=Card.many_from_text("AsQh"), is_agg=True)
        self.assertAlmostEqual(afei.fold_ratio, 10.0 / 18.0)
        self.assertAlmostEqual(afei.immediate_result,
            10.0 / 18.0 * 50.0 + 8.0 / 18.0 * (-50.0))  # 5.55...
        self.assertAlmostEqual(afei.semibluff_ev, None)
        self.assertAlmostEqual(afei.semibluff_equity, None)

if __name__ == '__main__':
    unittest.main()
