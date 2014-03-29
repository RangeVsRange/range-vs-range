"""
Temporary mixin for refactoring: new version
"""
from rvr.poker.action import finish_game
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

    def fold_continue(self):
        remain = [r for r in self.game.rgps if not r.folded]
        return len(remain) > 2
    
    def passive_continue(self):
        remain = [r for r in self.game.rgps if not r.folded]
        left_to_act = [r for r in self.game.rgps if r.left_to_act]
        return len(remain) > 2 or self.game.current_round != RIVER  \
            or len(left_to_act) > 1
    
    def aggressive_continue(self):
        # Always true because, like the other two of these, we assume there is
        # at least on option that results in this action, because otherwise the
        # question itself doesn't make sense.
        return True
        
    def consider_all(self):
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

class PA2:
    """
    New implementation of play on. As mixin, for refactoring purposes.
    """        
    def _play_all(self, game, rgp, range_action, current_options):
        """
        Plays every action in range_action, except the zero-weighted ones.
        If the game can continue, this will return an appropriate action_result.
        If not, it will return a termination. The game will continue if any
        action results in at least two players remaining in the hand, and at
        least one player left to act. (Whether or not that includes this
        player.)
        
        Inputs: as per _perform_action, below
        
        Outputs: an ActionResult: fold, passive, aggressive, or terminate
        
        Side effects:
         - reduce current factor based on non-playing ranges
         - redeal rgp's cards based on new range
         - (later) equity payments and such
        """
        # Why not:
        #  - perform each possible action,
        #  - see if the hand ends,
        #  - record results if it does (and determine the appropriate factor)
        #  - if there are both terminal and non-terminal options, re-deal
        #  - if there are no terminal options, use current hand (could re-deal,
        #    but as an efficiency
        #  - if there are only terminal options, they all play, but the hand is
        #    finished
        # In summary:
        #  - the terminal options play, with appropriate weight
        #  - current factor is reduced by the ratio of non-terminal-to-terminal
        #    options (between 0 to 1)
        #  - the hand either:
        #    - terminates, because all options are terminal
        #    - continues with one of the non-terminal options
        # So in terms of domain model, we need:
        #  - a basic poker hand class that:
        #    - generates options
        #    - applies actions
        #    - knows if the hand has ended
        #  - and a play-on class that:
        #    - maintains a current hand
        #    - copies current hand and applies all options
        #    - determines which options terminate and which don't
        #    - re-deals if there is a terminal option and multiple non-terminal
        #      options
        #    - records results of terminal options
        #    - tracks current factor
        what_could_be = WhatCouldBe(game, rgp, range_action, current_options)
        what_could_be.consider_all()
        what_could_be.calculate_what_will_be()
        return what_could_be.action_result

    def _perform_action(self, game, rgp, range_action, current_options):
        """
        Inputs:
         - game, tables.RunningGame object, from database
         - rgp, tables.RunningGameParticipant object, == game.current_rgp
         - range_action, action to perform
         - current_options, options user had here (re-computed)
         
        Outputs:
         - An ActionResult, what *actually* happened
         
        Side effects:
         - Records range action in DB (purely copying input to DB)
         - Records action result in DB
         - Records resulting range for rgp in DB
         - Applied the resulting action to the game, i.e. things like:
           - removing folded player from game
           - putting chips in the pot
           - starting the next betting round, if betting round finishes
           - determining who is next to act, if still same betting round
         - If the game is finished:
           - flag that the game is finished
           
        It's as simple as that. Now we just need to do / calculate as described,
        but instead of redealing based on can_call and can_fold, we'll play out
        each option, and terminate only when all options are terminal.
        """
        self._record_range_action(rgp, range_action)
        action_result = self._play_all(game, rgp, range_action,
                                       current_options)
        if action_result.is_terminate:
            game.is_finished = True
            rgp.left_to_act = False
        else:
            self._record_action_result(rgp, action_result)
            self._record_rgp_range(rgp, rgp.range_raw)
            self.apply_action_result(game, rgp, action_result)
        if game.is_finished:
            finish_game(game)
        action_result.game_over = game.is_finished  # let the user know
        return action_result
    