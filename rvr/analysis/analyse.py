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
    AnalysisFoldEquityItem
from rvr.poker.handrange import HandRange
from rvr.poker.cards import Card, RIVER, PREFLOP
import unittest
from rvr.poker.action import game_continues

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
    return bool(session.query(AnalysisFoldEquity)  \
        .filter(AnalysisFoldEquity.gameid == game.gameid).all())

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
        self.current_factor = 1.0  # TODO: 0: get rid of this eventually
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
        for _folder, fold_range, nonfold_range in self.folds:
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
    def __init__(self, session, game):
        logging.debug("gameid %d, AnalysisReplayer, initialising",
                      game.gameid)
        if not game.is_finished:
            raise ValueError("Can't analyse game until finished.")
        if already_analysed(session, game):
            raise ValueError("Game is already analysed.")
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
                logging.debug("gameid %d, FEA %d, canceling",
                              self.fea.gameid, self.fea.order)
            self.fea = None
            self.ranges[item.userid] = self.prev_range_action.passive_range
            if not self.fold_continues:
                fold_size = len(
                    HandRange(self.prev_range_action.fold_range)
                    .generate_options(self.board))
                passive_size = len(
                    HandRange(self.prev_range_action.passive_range)
                    .generate_options(self.board))
                aggressive_size = len(
                    HandRange(self.prev_range_action.aggressive_range)
                    .generate_options(self.board))
                all_size = fold_size + passive_size + aggressive_size
                fold_ratio = 1.0 * fold_size / all_size
                self._reduce_current_factor(1.0 - fold_ratio)
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
            if not self.passive_continues:
                fold_size = len(
                    HandRange(self.prev_range_action.fold_range)
                    .generate_options(self.board))
                passive_size = len(
                    HandRange(self.prev_range_action.passive_range)
                    .generate_options(self.board))
                aggressive_size = len(
                    HandRange(self.prev_range_action.aggressive_range)
                    .generate_options(self.board))
                all_size = fold_size + passive_size + aggressive_size
                aggressive_ratio = 1.0 * (aggressive_size) / all_size
                self._reduce_current_factor(aggressive_ratio)
            elif not self.fold_continues:
                fold_size = len(
                    HandRange(self.prev_range_action.fold_range)
                    .generate_options(self.board))
                passive_size = len(
                    HandRange(self.prev_range_action.passive_range)
                    .generate_options(self.board))
                aggressive_size = len(
                    HandRange(self.prev_range_action.aggressive_range)
                    .generate_options(self.board))
                all_size = fold_size + passive_size + aggressive_size
                fold_ratio = 1.0 * fold_size / all_size
                self._reduce_current_factor(1.0 - fold_ratio)
            
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

    def create_showdown(self, order, factor, userids):
        """
        Create a showdown with given userids. Pre-river if pre-river.
        """
        # TODO: 1: create showdown with given userids.
        
        # TODO: 1: record current factor against showdown, for results
        # (Shit, where do we get current factor from?! We should have been
        #  recording it against the history - specifically range actions and
        #  action results.)
        # (Well, conceptually it's pretty simple - current factor goes down when
        #  there are terminal options that are avoided and play on is forced.)
        # (But the *right* thing to do is to change the database to include
        #  current factor for all game history items, and to retrospectively
        #  calculate and inject that data for running and finished games.)
        # (Perhaps this is a candidate for making a nullable column, then using
        #  the code here to backfill the data, then make the column
        #  non-nullable.)
        # TODO: 1: note that showdown results must be scaled down by the...
        # ... current factor and by the unlikeliness of the action...
        # ... being chosen from the range action.
        # If possible, handle pre-river and river showdowns together.
        # (perhaps river showdown is a special case of pre-river showdown?)
        logging.debug('gameid %d, order %d, factor %0.8f, creating showdown '
                      'with userids: %r',
                      self.game.gameid, order, factor, userids)
    
    def _reduce_current_factor(self, factor):
        """
        Factor is the proportion of combos that were allowed to continue play
        """
        new_current_factor = self.current_factor * factor
        logging.debug(
            'analysis gameid %d, reducing factor from %0.8f by %0.4f to %0.8f',
            self.game.gameid, self.current_factor, factor, new_current_factor)
        self.current_factor = new_current_factor
    
    def _get_current_factor(self, item):
        """
        Return or calculate current factor
        """
        if item.factor is None:
            logging.debug('gameid %d, order %d, updating factor to %r',
                          item.gameid, item.order, self.current_factor)
            item.factor = self.current_factor
            self.session.commit()
        if item.factor != self.current_factor:
            logging.error('INCONSISTENCY: gameid %d, cf %r; order %d, cf %r',
                          item.gameid, self.current_factor, item.order,
                          item.factor)
            item.factor = self.current_factor
            self.session.commit()
        return item.factor
    
    def range_action_showdown(self, item):
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
                return
            if prev_contrib is not None and  \
                    self.contrib[userid] != prev_contrib:
                return
            prev_contrib = self.contrib[userid]
            last_stack = self.stacks[userid]
        if last_stack > 0 and self.street != RIVER:
            # end of betting round, but not showdown
            return
        size_fold = _range_desc_to_size(item.fold_range)
        size_passive = _range_desc_to_size(item.passive_range)
        size_aggressive = _range_desc_to_size(item.aggressive_range)
        size_all = size_fold + size_passive + size_aggressive
        if len(self.remaining_userids) > 2:
            # this player folds, but the pot is contested, so we have a showdown
            factor = self._get_current_factor(item) * size_fold / size_all
            self.create_showdown(order=item.order,
                factor=factor,
                userids=[userid for userid in self.remaining_userids
                         if userid != item.userid])
        factor = self._get_current_factor(item) * size_passive / size_all
        self.create_showdown(order=item.order,
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
        

        # TODO: 1: range actions create showdowns
        
        # TODO: 1: track who remains
        # -> self.remaining_userids
        # TODO: 1: track who has acted (note that situation has 'left to act')
        # -> self.left_to_act
        # TODO: 1: track how much each player have contributed
        # -> self.contrib
        
        # Consider the fold option, the passive option, the aggressive option.
        # An aggressive option can't create a showdown, but the other two can.
        # It's also possible for both fold and passive to create showdowns.
        # A showdown is when the option terminates a betting round with two or
        # more players remaining. An option terminates when it is non-aggressive
        # and all players have either folded or put in the same amount of money
        # and all players have had a chance to act. The showdown is between all
        # players who have not folded.
        
        # The above applies on any street, but it's only a showdown if they are
        # all in - or on the river.
        
        


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
        self.current_factor = 1.0

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
            self._get_current_factor(item)
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