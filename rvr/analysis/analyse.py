"""
Central analysis logic such as the "re/analyse all games" function.

The paradigm here is that DTOs contain all the information the previous
verion's objects did, and the database objects contain a relational version
of the same.
"""
import logging
from rvr.infrastructure.util import concatenate
from rvr.db.tables import GameHistoryActionResult, GameHistoryRangeAction, \
    GameHistoryUserRange, AnalysisFoldEquity, GameHistoryBoard
from rvr.poker.handrange import HandRange

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
    def __init__(self, gameid, order, street, bettor, raise_total,
                 is_raise, pot_before_bet, bet_cost, pot_if_called,
                 potential_folders):
        logging.debug("FEA, gameid %d, order %d, initialising",
                      gameid, order)
        self.gameid = gameid
        self.order = order
        self.street = street
        self.bettor = bettor
        self.raise_total = raise_total
        self.is_raise = is_raise
        self.pot_before_bet = pot_before_bet
        self.bet_cost = bet_cost
        self.pot_if_called = pot_if_called
        self.potential_folders = potential_folders  # userids
        self.total_fold_ratio = 1.0  # reduces for each potential caller
        self.folds = []  # list of (userid, fold_ratio)
    
    def folder(self, ghra):
        """
        ghra is a GameHistoryRangeAction, who we consider to be a folder.
        
        Returns True if this fea is complete.
        """
        logging.debug("FEA, gameid %d, adding folder: userid %d",
                      self.gameid, ghra.userid)
        self.potential_folders.remove(ghra.userid)
        fold_options = _range_desc_to_size(ghra.fold_range)
        all_options = fold_options +  \
            _range_desc_to_size(ghra.passive_range) +  \
            _range_desc_to_size(ghra.aggressive_range)
        fold_ratio = 1.0 * fold_options / all_options
        self.total_fold_ratio *= fold_ratio
        self.folds.append((ghra.userid, fold_ratio))
        return len(self.potential_folders) == 0
    
    def finalise(self):
        """
        Assuming complete, return an AnalysisFoldEquity
        """
        logging.debug("FEA, gameid %d, finalising", self.gameid)
        assert len(self.potential_folders) == 0
        other_ratio = 1.0 - self.total_fold_ratio
        afe = AnalysisFoldEquity()
        afe.gameid = self.gameid
        afe.order = self.order
        afe.street = self.street
        afe.pot_before_bet = self.pot_before_bet
        afe.is_raise = self.is_raise
        afe.bet_cost = self.bet_cost
        afe.raise_total = self.raise_total
        afe.pot_if_called = self.pot_if_called
        afe.immediate_result = self.total_fold_ratio * self.pot_before_bet -  \
            other_ratio * self.bet_cost
        afe.semibluff_ev = -afe.immediate_result / other_ratio
        afe.semibluff_equity = afe.semibluff_ev / self.pot_if_called
        return afe
        # TODO: 0: need a supplementary table for individual folders
        # (to store userid, fold_ratio combos, in order, for later display)

class AnalysisReplayer(object):
    """
    Plays through a hand, performs analysis, and creates analysis items in
    database.
    """
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
        self.fea = None  # current fold equity accumulator

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
        stacks = {self.game.rgps[i].userid:
                  self.game.situation.players[i].stack
                  for i in range(len(self.game.situation.players))}
        contrib = {self.game.rgps[i].userid:
                   self.game.situation.players[i].contributed 
                   for i in range(len(self.game.situation.players))}
        remaining_userids = [rgp.userid for rgp in self.game.rgps]
        for item in child_items:
            if isinstance(item, GameHistoryBoard):
                contrib = {u: 0 for u in remaining_userids}
                assert self.fea is None
                self.street = item.street
            if isinstance(item, GameHistoryActionResult):
                if item.is_fold:
                    remaining_userids.remove(item.userid)
                if item.is_passive:
                    self.pot += item.call_cost
                    contrib[item.userid] += item.call_cost
                    stacks[item.userid] -= item.call_cost 
                    self.fea = None
                if item.is_aggressive:
                    amount_raised = item.raise_total - max(contrib.values())
                    bet_cost = item.raise_total - contrib[item.userid]
                    is_raise = any(contrib.values())
                    contrib[item.userid] = item.raise_total
                    stacks[item.userid] -= bet_cost
                    # we assume the person who has contributed the most calls
                    pot_if_called = self.pot + bet_cost + amount_raised
                    self.fea = FoldEquityAccumulator(
                        gameid=self.game.gameid,
                        order=item.order,
                        street=self.street,
                        bettor=item.userid,
                        raise_total=item.raise_total,
                        is_raise=is_raise,
                        pot_before_bet=self.pot,
                        bet_cost=bet_cost,
                        pot_if_called=pot_if_called,
                        potential_folders=[u for u in remaining_userids
                                           if u is not item.userid])
                    self.pot += bet_cost
            if isinstance(item, GameHistoryRangeAction)  \
                    and self.fea is not None:
                # We have a folder (assuming this fea qualifies).
                # We don't care if that final person raises or not; the
                # important point is that we know their fold range.
                fea_complete = self.fea.folder(item)
                if fea_complete:
                    self.session.add(self.fea.finalise())
                    self.fea = None                
