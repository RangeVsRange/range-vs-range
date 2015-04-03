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
    GameHistoryShowdownEquity, GAME_HISTORY_TABLES, GameHistoryBase
from rvr.poker.handrange import HandRange
from rvr.poker.cards import Card, RIVER, PREFLOP
import unittest
from rvr.poker.action import game_continues
from rvr.poker.showdown import showdown_equity
import datetime

# pylint:disable=R0902,R0913,R0914,R0903

def _range_desc_to_size(range_description):
    """
    Given a range description, determine the number of combos it represents.
    """
    return len(HandRange(range_description).generate_options()) 

def already_analysed(session, game):
    """
    Is this game already analysed?
    """
    feas = session.query(AnalysisFoldEquity)  \
        .filter(AnalysisFoldEquity.gameid == game.gameid).all()
    equities = session.query(GameHistoryShowdownEquity)  \
        .filter(GameHistoryShowdownEquity.gameid == game.gameid).all()
    return bool(feas) or bool(equities)

def _make_space(session, game, order):
    """
    Move all history items by one, to make space for a new one 
    """
    update_items = []
    update_bases = []
    for table in GAME_HISTORY_TABLES:
        items = session.query(table)  \
            .filter(table.gameid == game.gameid)  \
            .filter(table.order >= order).all()
        for item in items:
            base = session.query(GameHistoryBase)  \
                .filter(GameHistoryBase.gameid == game.gameid)  \
                .filter(GameHistoryBase.order == item.order).one()
            update_items.append(item)
            update_bases.append(base)
    # process these without an intermediate flush
    update_items.sort(key=lambda i:i.order, reverse=True)
    update_bases.sort(key=lambda i:i.order, reverse=True)
    for item, base in zip(update_items, update_bases):
        item.order += 1
        base.order += 1
        session.commit()
    game.next_hh += 1
    session.commit()
    # now there is a gap in the history

def _record_showdown(session, game, order, is_passive, pot, factor):
    """
    Similar to API._record_showdown, but in the middle of the history

    Requires that a gap has been created by _make_space
    """
    base = GameHistoryBase()
    base.gameid = game.gameid
    base.order = order
    base.factor = factor
    base.time = datetime.datetime.utcnow()
    # TODO: REVISIT: out-of-order history items (chronologically)
    
    showdown = GameHistoryShowdown()
    showdown.is_passive = is_passive
    showdown.pot = pot
    showdown.gameid = base.gameid
    showdown.order = base.order
    
    session.add(base)
    session.add(showdown)
    return showdown

class FoldEquityAccumulator(object):
    """
    Holds the data needed to calculate and create an AnalysisFoldEquity.
    """
    def __init__(self, gameid, order, street, board, bettor, range_action,
                 raise_total, pot_before_bet, bet_cost,
                 pot_if_called, potential_folders):
        logging.debug("gameid %d, FEA %d, initialising",
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
        logging.debug("gameid %d, FEA %d, finalised", self.gameid, self.order)
        return afe

class AnalysisReplayer(object):
    """
    Plays through a hand, performs analysis, and creates analysis items in
    database.
    """
    #pylint:disable=W0201
    def __init__(self, api, session, game):
        logging.debug("gameid %d, AnalysisReplayer, initialising",
                      game.gameid)
        if not game.is_finished:
            raise ValueError("Can't analyse game until finished.")
        if already_analysed(session, game):
            raise ValueError("Game is already analysed.")
        self.api = api
        self.session = session
        self.game = game
        self.pot = self.game.situation.pot_pre +  \
            sum([p.contributed for p in self.game.situation.players])
        self.street = self.game.situation.current_round
        self.board = Card.many_from_text(self.game.situation.board_raw)
        self.fea = None  # current fold equity accumulator
        self.prev_range_action = None

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
        if item.is_fold:
            self.remaining_userids.remove(item.userid)
            self.ranges[item.userid] = self.prev_range_action.fold_range
        if item.is_passive:
            self.pot += item.call_cost
            self.contrib[item.userid] += item.call_cost
            self.stacks[item.userid] -= item.call_cost
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
                    u is not item.userid])
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

    def create_showdown(self, ranges, order, is_passive, pot, factor, userids):
        """
        Create a showdown with given userids. Pre-river if pre-river.
        """
        # TODO: 2: showdown results
        # TODO: 2: note that showdown results must be scaled down by the...
        # ... current factor and by the unlikeliness of the action...
        # ... being chosen from the range action.
        # If possible, handle pre-river and river showdowns together.
        # (perhaps river showdown is a special case of pre-river showdown?)
        showdowns = self.session.query(GameHistoryShowdown)  \
            .filter(GameHistoryShowdown.gameid == self.game.gameid)  \
            .filter(GameHistoryShowdown.order == order)  \
            .filter(GameHistoryShowdown.is_passive == is_passive).all()
        if len(showdowns) == 0:
            _make_space(self.session, self.game, order)
            showdown = _record_showdown(self.session, self.game, order,
                                        is_passive, pot, factor)
            logging.debug("gameid %d, order %d, created showdown",
                          self.game.gameid, order)
            self.session.commit()
        else:
            assert len(showdowns) == 1
            assert showdowns[0].pot == pot and showdowns[0].factor == factor
            logging.debug("gameid %d, order %d, confirmed existing showdown",
                          self.game.gameid, order)
            showdown = showdowns[0]
        # TODO: REVISIT: this ignores ranges of folded players
        # it might make a difference in situations where a player has (for
        # example) limited their range to Ax and later folded, hence surely
        # removing an ace from the deck for the other players (significantly
        # changing their equities)
        range_map = {k: v for k, v in ranges.iteritems() if k in userids}
        equity_map, iterations = showdown_equity(range_map, self.game.board)
        logging.debug('gameid %d, order %d, is_passive %r, factor %0.8f, '
                      'showdown with userids: %r, equity: %r '
                      '(iterations %d)',
                      self.game.gameid, order, is_passive, factor, userids,
                      equity_map, iterations)
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
                participant.gameid = self.game.gameid
                participant.order = order
                participant.is_passive = is_passive
                participant.showdown_order = showdown_order
                participant.userid = userid
            participant.equity = equity_map[userid]
        # TODO: 1: payments - with detailed explanations!
        # - generic payment to user: raw payment, factor, resultant payment
        # Each payment will link to a history item (i.e. gameid and order),
        # being one of:
        #  - fold equity payment / range action
        #  - board equity payment / board
        #  - choice equity payment / range action
        #  - showdown equity payment / showdown
        #  (note that winning a pot uncontested is covered by fold equity)
        # Each payment will be made to all players
    
    def _calculate_call_cost(self, userid):
        """
        It would have been convenient if this was stored in
        GameHistoryRangeAction... but it's easy enough to calculate based on
        this object's state.
        """
        return max(self.contrib.values()) - self.contrib[userid]
    
    def range_action_showdown(self, item):
        """
        Consider showdowns based on this range action resulting in a fold, and
        another based on this resulting in a check or call.
        """
        # TODO: 2: recreate this functionality mid-game, with create-if-needed,
        # then delete this eventually. (In the mean time, we will actually
        # change following items order, to recreate as if injected initially!) 
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
        size_fold = _range_desc_to_size(item.fold_range)
        size_passive = _range_desc_to_size(item.passive_range)
        size_aggressive = _range_desc_to_size(item.aggressive_range)
        size_all = size_fold + size_passive + size_aggressive
        pot = self.pot
        order = item.order
        # Note that fold is arbitrarily considered to be before call
        if len(self.remaining_userids) > 2:
            order += 1
            # this player folds, but the pot is contested, so we have a showdown
            factor = item.factor * size_fold / size_all
            ranges = {key: HandRange(txt)
                      for key, txt in self.ranges.iteritems()}
            # They (temporarily) fold
            ranges.pop(item.userid)
            self.create_showdown(ranges=ranges,
                order=order,
                is_passive=False,
                pot=pot,
                factor=factor,
                userids=[userid for userid in self.remaining_userids
                         if userid != item.userid])
        factor = item.factor * size_passive / size_all
        ranges = {key: HandRange(txt)
                  for key, txt in self.ranges.iteritems()}
        pot += self._calculate_call_cost(item.userid)
        # They (temporarily) call
        ranges[item.userid] = HandRange(item.passive_range)
        if not ranges[item.userid].is_empty():
            order += 1
            # It's a real call, not folding 100%
            self.create_showdown(ranges=ranges,
                                 order=order,
                                 is_passive=True,
                                 pot=pot,
                                 factor=factor,
                                 userids=self.remaining_userids)

    def process_range_action(self, item):
        """
        Process a GameItemRangeAction
        """
        self.range_action_fea(item)
        self.range_action_showdown(item)
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
            self.process_action_result(item)
        if isinstance(item, GameHistoryRangeAction):
            self.process_range_action(item)
            self.prev_range_action = item

    def analyse(self):
        """
        Perform all analysis on game that has not been done.
        
        If you need to reanalyse the game, delete the existing analysis first.
        """
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