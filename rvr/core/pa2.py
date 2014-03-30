"""
Temporary mixin for refactoring: new version
"""
from rvr.core.dtos import ActionResult
from collections import namedtuple
from rvr.poker.cards import RIVER
from rvr.infrastructure.util import concatenate
import random

# pylint:disable=R0903,W0232,R0201,W0613,C0111

# Additional TODOs around this stuff, not specifically to do with refactoring:
# TODO: HAND HISTORY: record (subjective) sizes of range_action
# TODO: EQUITY PAYMENT: fold equity
# TODO: EQUITY PAYMENT: (controversial!) redeal equity (call vs. raise)
# TODO: 1: notice when they get all in
# TODO: RESULTS: need final showdown sometimes (rarely) ...
# TODO: REVISIT: it might not be their turn at the point we commit, ok?
# TODO: STRATEGY: profitable float
# - hero bets one flop (etc.), villain calls
# - hero checks turn (etc.), villain bets
# - if hero doesn't bet enough on the flop (etc.), checks too much
#   on the turn (etc.), and folds too much to the bet, villain has
#   a profitable float
# (villain will often have a profitable float anyway due to equity,
#  i.e. a semi-float, but that's impossible to quantify.) 
# (it's also okay to be profitably floated sometimes, e.g. when a
#  flush draw comes off, because that doesn't happen 100% of the
#  time.)

Branch = namedtuple("is_continue",  # For this option, does play continue?
                    "options",  # Combos that lead to this option
                    "action")  # Action that results from this option

class WhatCouldBe(object):
    def __init__(self, game, rgp, range_action, current_options):
        self.game = game
        self.rgp = rgp
        self.range_action = range_action
        self.current_options = current_options
        
        self.bough = []  # list of Branch
        self.action_result = None

    def game_continues(self, will_remain, will_act):
        """
        Given a list of players remaining in the hand, and a list of players
        remaining to act, will the game continue? (Or is it over, contested or
        otherwise.)
        """
        if self.game.current_round != RIVER:
            # Pre-river, game continues if there are at least two players
            return len(will_remain) >= 2
        else:
            # On the river, game continues if there are at least two players,
            # and at least one left to act
            return len(will_remain) >= 2 and len(will_act) >= 1

    def fold_continue(self):
        """
        If current player folds here, will the hand continue?
        """
        # remain is everyone who else who hasn't folded
        will_remain = [r for r in self.game.rgps
                       if not r.folded and r is not self.rgp]
        # to act is everyone else who's to act
        will_act = [r for r in self.game.rgps
                    if r.left_to_act and r is not self.rgp]
        return self.game_continues(will_remain, will_act)
    
    def passive_continue(self):
        """
        If a passive action is taken here, will the hand continue?
        """
        # remain is everyone who hasn't folded
        will_remain = [r for r in self.game.rgps if not r.folded]
        # to act is everyone else who's to act
        will_act = [r for r in self.game.rgps
                    if r.left_to_act and r is not self.rgp]
        return self.game_continues(will_remain, will_act)
    
    def aggressive_continue(self):
        """
        If an aggressive action is taken here, will the hand continue?

        Actually, this will always return True.
        """
        # remain is everyone who hasn't folded
        will_remain = [r for r in self.game.rgps if not r.folded]
        # to act is everyone else who hasn't folded
        will_act = [r for r in self.game.rgps
                    if not r.folded and r is not self.rgp]
        return self.game_continues(will_remain, will_act)
        
    def consider_all(self):
        """
        Plays every action in range_action, except the zero-weighted ones.
        If the game can continue, this will return an appropriate action_result.
        If not, it will return a termination. The game will continue if any
        action results in at least two players remaining in the hand, and at
        least one player left to act. (Whether or not that includes this
        player.)
        
        Inputs: see __init__
        
        Outputs: an ActionResult: fold, passive, aggressive, or terminate
        
        Side effects:
         - reduce current factor based on non-playing ranges
         - redeal rgp's cards based on new range
         - (later) equity payments and such
        """
        # note that we only consider the possible
        # mostly copied from the old re_deal
        cards_dealt = {rgp: rgp.cards_dealt for rgp in self.game.rgps}
        dead_cards = [card for card in self.game.board if card is not None]
        dead_cards.extend(concatenate([v for k, v in cards_dealt.iteritems()
                                   if k is not self.rgp]))
        fold_options =  \
            self.range_action.fold_range.generate_options(dead_cards)
        passive_options =  \
            self.range_action.passive_range.generate_options(dead_cards)
        aggressive_options =  \
            self.range_action.aggressive_range.generate_options(dead_cards)
        # Consider fold
        fold_action = ActionResult.fold()
        if len(self.fold_options) > 0:
            self.bough.append(Branch(self.fold_continue(),
                                     fold_options,
                                     fold_action))
        # Consider call
        passive_action = ActionResult.call(self.current_options.call_cost)
        if len(self.passive_options) > 0:
            self.bough.append(Branch(self.passive_continue(),
                                     passive_options,
                                     passive_action))
        # Consider raise
        aggressive_action = ActionResult.raise_to(
            self.current_options.raise_total, self.current_options.is_raise)
        if len(self.aggressive_options) > 0:
            self.bough.append(Branch(self.aggressive_continue(),
                                     aggressive_options,
                                     aggressive_action))

    def calculate_what_will_be(self):
        """
        Choose one of the non-terminal actions, or return termination if they're
        all terminal. Also update game's current_factor. 
        """
        # reduce current factor by the ratio of non-terminal-to-terminal options
        non_terminal = []
        terminal = []
        for branch in self.bough:
            if branch.is_continue:
                terminal.extend(branch.options)
            else:
                non_terminal.extend(branch.options)
        total = len(non_terminal) + len(terminal)
        # the more non-terminal, the less effect on current factor
        self.game.current_factor *= float(len(non_terminal)) / total
        if non_terminal:
            chosen_option = random.choice(non_terminal)
            # but which action was chosen?
            for branch in self.bough:
                if chosen_option in branch.options:
                    self.action_result = branch.action
        else:
            self.action_result = ActionResult.terminate()
        return self.action_result

    