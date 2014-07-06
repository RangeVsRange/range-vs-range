"""
Central analysis logic such as the "re/analyse all games" function.

The paradigm here is that DTOs contain all the information the previous
verion's objects did, and the database objects contain a relational version
of the same.
"""
import logging
from rvr.infrastructure.util import concatenate
from rvr.db.tables import GameHistoryActionResult, GameHistoryRangeAction, \
    GameHistoryUserRange, AnalysisFoldEquity, GameHistoryBoard,\
    AnalysisFoldEquityItem
from rvr.poker.handrange import HandRange
from rvr.poker.cards import Card

# pylint:disable=R0902,R0913,R0914,R0903

# TODO: 0: unit tests for analysis; i.e. that the analysis is correct
# This is quite important, because coming back to it later, finding that it's
# subtly wrong, and then having to tell everyone that would be quite bad.

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
    def __init__(self, gameid, order, street, board, bettor, bettor_range,
                 raise_total, is_raise, pot_before_bet, bet_cost, pot_if_called,
                 potential_folders):
        logging.debug("FEA, gameid %d, order %d, initialising",
                      gameid, order)
        self.gameid = gameid
        self.order = order
        self.street = street
        self.board = Card.many_from_text(board)
        self.bettor = bettor
        self.bettor_range = HandRange(bettor_range)
        self.raise_total = raise_total
        self.is_raise = is_raise
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
        logging.debug("FEA, gameid %d, adding folder: userid %d",
                      self.gameid, ghra.userid)
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
        afe.is_raise = self.is_raise
        afe.bet_cost = self.bet_cost
        afe.raise_total = self.raise_total
        afe.pot_if_called = self.pot_if_called
        return afe
    
    def _create_afei(self, combo):
        """
        Create an AnalaysisFoldEquityItem for a particular combo in Hero's range
        """
        afei = AnalysisFoldEquityItem()
        afei.gameid = self.gameid
        afei.order = self.order
        lower_card, higher_card = sorted(combo)
        afei.higher_card = higher_card.to_mnemonic()
        afei.lower_card = lower_card.to_mnemonic()
        afei.fold_ratio = 1.0
        for _folder, fold_range, nonfold_range in self.folds:
            fold_size = len(fold_range.generate_options_unweighted(
                self.board + list(combo)))
            nonfold_size = len(nonfold_range.generate_options_unweighted(
                self.board + list(combo)))
            folder_fold_ratio = 1.0 * fold_size / (fold_size + nonfold_size)
            afei.fold_ratio *= folder_fold_ratio 
            # product of everyone's fold ratios
        nonfold_ratio = 1.0 - afei.fold_ratio
        afei.immediate_result = afei.fold_ratio * self.pot_before_bet -  \
            nonfold_ratio * self.bet_cost
        if nonfold_ratio:
            afei.semibluff_ev = -afei.immediate_result / nonfold_ratio
        else:
            afei.semibluff_ev = float('Inf')
        afei.semibluff_equity = afei.semibluff_ev / self.pot_if_called
        return afei
    
    def finalise(self, session):
        """
        Assuming complete, return an AnalysisFoldEquity
        """
        logging.debug("FEA, gameid %d, finalising", self.gameid)
        assert len(self.potential_folders) == 0
        afe = self._create_afe()
        session.add(afe)
        for combo in self.bettor_range.generate_options_unweighted(self.board):
            afei = self._create_afei(combo)
            session.add(afei)
        return afe
        # TODO: 3: need a supplementary table for individual folders
        # (to store userid, fold_ratio combos, in order, for later display)

class AnalysisReplayer(object):
    """
    Plays through a hand, performs analysis, and creates analysis items in
    database.
    """
    #pylint:disable=W0201
    def __init__(self, session, game):
        logging.debug("AnalysisReplayer, gameid %d, initialising",
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
        self.board = self.game.situation.board_raw
        self.fea = None  # current fold equity accumulator
        self.prev_range_action = None

    def process_board(self, item):
        """
        Process a GameHistoryBoard
        """
        self.contrib = {u:0 for u in self.remaining_userids}
        assert self.fea is None
        self.street = item.street
        self.board = item.cards

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
            self.fea = None
            self.ranges[item.userid] = self.prev_range_action.passive_range
        if item.is_aggressive:
            amount_raised = item.raise_total - max(self.contrib.values())
            bet_cost = item.raise_total - self.contrib[item.userid]
            is_raise = any(self.contrib.values())
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
                bettor_range=self.ranges[item.userid],  # range before bet
                raise_total=item.raise_total, 
                is_raise=is_raise, 
                pot_before_bet=self.pot, 
                bet_cost=bet_cost, 
                pot_if_called=pot_if_called, 
                potential_folders=[u for u in self.remaining_userids if 
                    u is not item.userid])
            self.pot += bet_cost
            self.ranges[item.userid] = self.prev_range_action.aggressive_range

    def process_range_action(self, item):
        """
        Process a GameItemRangeAction
        """
        if self.fea is not None:
            # We have a folder (assuming this fea qualifies).
            # We don't care if that final person raises or not; the
            # important point is that we know their fold range.
            fea_complete = self.fea.folder(item)
            if fea_complete:
                self.fea.finalise(self.session)
                self.fea = None

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
        gameid = self.game.gameid
        logging.debug("AnalysisReplayer, gameid %d, analyse", gameid)
        items = [self.session.query(table)
                 .filter(table.gameid == gameid).all()
                 for table in [GameHistoryBoard,
                               GameHistoryUserRange,
                               GameHistoryActionResult,
                               GameHistoryRangeAction]]
        child_items = sorted(concatenate(items),
                             key=lambda c: c.order)
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
        for item in child_items:
            self.process_child_item(item)
