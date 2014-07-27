"""
action functionality, imported from the previous versions
"""
from rvr.poker.cards import Card, FLOP, PREFLOP, RIVER, TURN
import unittest
from rvr.poker.handrange import HandRange,  \
    _cmp_weighted_options, _cmp_options
from rvr.infrastructure.util import concatenate
from rvr.core.dtos import ActionOptions, ActionDetails, ActionResult
import random
from collections import namedtuple
import logging

NEXT_ROUND = {PREFLOP: FLOP, FLOP: TURN, TURN: RIVER}
TOTAL_COMMUNITY_CARDS = {PREFLOP: 0, FLOP: 3, TURN: 4, RIVER: 5}

def _option_to_text(option):
    """
    option is set of two Card
    return something like "AhAd" (highest card first)
    """
    return "".join([o.to_mnemonic() for o in sorted(option, reverse=True)])

def range_sum_equal(fold_range, passive_range, aggressive_range,
                    original_range):
    """
    Returns validity (boolean), and reason (string, or None if valid)
    """
    # pylint:disable=R0914
    all_ranges = [fold_range, passive_range, aggressive_range]
    original_hand_options = original_range.generate_options()
    all_ranges_hand_options = concatenate([r.generate_options()
                                           for r in all_ranges])
    original_hand_options.sort(cmp=_cmp_weighted_options)
    all_ranges_hand_options.sort(cmp=_cmp_weighted_options)
    prev = (None, -1)
    # pylint:disable=W0141
    for ori, new in map(None, original_hand_options, all_ranges_hand_options):
        # we compare two hands, each of which is a set of two Card
        if ori != new:
            # actually three scenarios:
            # hand is in multiple action ranges
            # (new is the same as the previous new) 
            # hand is in action ranges but not original range
            # (new < ori means new is not in original range)
            # hand is in original range but not action ranges
            # (new > ori means ori is not in action ranges)
            if new is None:
                message =  \
                    "hand in original range but not in action ranges: %s" %  \
                    _option_to_text(ori[0])
            elif ori is None:
                message =  \
                    "hand in action ranges but not in original range: %s" %  \
                    _option_to_text(new[0])
            else:
                newh, neww = new
                orih, oriw = ori
                if newh == prev[0]:
                    message = "hand in multiple ranges: %s" %  \
                        _option_to_text(newh)
                elif _cmp_options(newh, orih) > 0:
                    message = "hand in original range but not in " +  \
                        "action ranges: %s" % _option_to_text(orih)
                elif _cmp_options(newh, orih) < 0:
                    message = "hand in action ranges but not in " +  \
                        "original range: %s" % _option_to_text(newh)
                elif neww != oriw:
                    message = "weight changed from %d to %d for hand %s" %  \
                        (oriw, neww, _option_to_text(orih))
                else:
                    raise RuntimeError("hands not equal, but can't " +  \
                                       "figure out why: %s, %s" % \
                                       (_option_to_text(orih),
                                        _option_to_text(newh)))
            return False, message
        prev = new
    return True, None

def range_action_fits(range_action, options, original_range):
    """
    is range_action a valid response to options, original_range?
    meaning:
    - every hand in original_range is in exactly one range in range_action
    - weights for each option are the same as original
    - raise size should be within the band specified in options
    - if there is no aggressive option, the raise range should be empty, and the raise size will be ignored
    (also, weights can be ignored here - we don't support weighted actions yet
    this means that carving AA(2) up into AA(1) and AA(1) is not valid)
    """
    # Four possible reasons to fail validity checks:
    # 1. hand W is in both X and Y
    # 2. hand W is in original, but is not in X, Y, or Z
    # 3. raise size is 0, but raise range is not
    # 4. raise size is not between min and max
    fold_range = range_action.fold_range
    passive_range = range_action.passive_range
    aggressive_range = range_action.aggressive_range
    raise_total = range_action.raise_total
    try:
        valid, reason = range_sum_equal(fold_range,
                                        passive_range,
                                        aggressive_range,
                                        original_range)
    except RuntimeError as err:
        return False, err.message
    if not valid:
        return False, reason
    # we require that if there is a raise range, there is a raise size
    # but if there is an empty raise range, raise size is irrelevant
    if aggressive_range.is_empty():
        return True, None
    # and last, their raise size isn't wrong
    if not options.can_raise():
        return (False,
            "there was a raising range, but raising was not an option")
    valid = raise_total >= options.min_raise  \
        and raise_total <= options.max_raise
    reason = None if valid else ("raise total must be between %d and %d" %
                                 (options.min_raise, options.max_raise))
    return valid, reason

def range_contains_hand(range_, hand):
    """
    Is hand in range?
    """
    options = range_.generate_options()
    unweighted = [option[0] for option in options]
    return set(hand) in unweighted

def calculate_current_options(game, rgp):
    """
    Determines what options the current player has in a running game.
    
    Returns a dtos.ActionOptions instance.
    """
    raised_to = max([p.contributed for p in game.rgps])
    call_amount = min(rgp.stack, raised_to - rgp.contributed)
    bet_lower = raised_to + game.increment  # min-raise
    bet_higher = rgp.stack + rgp.contributed  # shove
    if bet_higher < bet_lower:  # i.e. all in
        bet_lower = bet_higher
    if game.situation.is_limit:
        bet_higher = bet_lower  # minraise is only option for limit
    can_raise = bet_lower > raised_to  # i.e. there is a valid bet
    is_capped = (game.situation.is_limit and  # No limit is never capped
        game.bet_count >= 4)  # Not capped until 4 bets in
    can_raise = can_raise and not is_capped
    if can_raise:
        return ActionOptions(call_cost=call_amount,
                             is_raise=raised_to != 0,
                             min_raise=bet_lower,
                             max_raise=bet_higher)
    else:
        return ActionOptions(call_amount, is_raise=raised_to != 0)

def act_fold(rgp):
    """
    Fold rgp
    """
    rgp.folded = True
    rgp.left_to_act = False
    
def act_passive(rgp, call_cost):
    """
    Check or call rgp
    """
    rgp.stack -= call_cost
    rgp.contributed += call_cost
    rgp.left_to_act = False
    
def act_aggressive(game, rgp, raise_total):
    """
    Bet or raise rgp
    """
    rgp.stack = rgp.stack - (raise_total - rgp.contributed)
    raised_to = max(rgp.contributed for rgp in game.rgps)
    game.increment = max(game.increment, raise_total - raised_to)
    rgp.contributed = raise_total
    game.bet_count += 1
    rgp.left_to_act = False
    # everyone who hasn't folded is now left to act again
    for other in game.rgps:
        if other is not rgp and not other.folded:
            other.left_to_act = True

def act_terminate(game, rgp):
    """
    Handle game termination when a range action results in termination.
    """
    rgp.left_to_act = False
    game.is_finished = True

def finish_game(game):
    """
    Game is finished. Calculate results, record in hand history,
    perform analysis.
    """
    # TODO: RESULTS: finish game
    # There may be a winner: one person with left_to_act True. Or there may be a
    # range-based showdown (river, or all in)
    # TODO: RESULTS: need final showdown sometimes (rarely) ...
    return game

# TODO: EQUITY PAYMENT: fold equity
# TODO: EQUITY PAYMENT: (controversial!) redeal equity (call vs. raise)
# TODO: STRATEGY: profitable float
# - hero bets one flop (etc.), villain calls
# - hero checks turn (etc.), villain bets
# - if hero doesn't bet big enough on the flop (etc.), checks too much
#   on the turn (etc.), and folds too much to the bet, villain has
#   a profitable float
# (villain will often have a profitable float anyway due to equity,
#  i.e. a semi-float, but that's impossible to quantify.) 
# (it's also okay to be profitably floated sometimes, e.g. when a
#  flush draw comes off, because that doesn't happen 100% of the
#  time.)

Branch = namedtuple("Branch",  # pylint:disable=C0103
                    ["is_continue",  # For this option, does play continue?
                     "options",  # Combos that lead to this option
                     "action",  # Action that results from this option
                     "range"])  # Range for player making the action

class WhatCouldBe(object):
    """
    Determine how to handle current range action.
    """
    def __init__(self, game, rgp, range_action, current_options):
        self.game = game
        self.rgp = rgp
        self.range_action = range_action
        self.current_options = current_options
        
        self.all_in = any([player.stack == 0 for player in game.rgps])
        self.bough = []  # list of Branch
        self.action_result = None

    def game_continues(self, will_remain, will_act):
        """
        Given a list of players remaining in the hand, and a list of players
        remaining to act, will the game continue? (Or is it over, contested or
        otherwise.)
        """
        if self.game.current_round == RIVER or self.all_in:
            # On the river, game continues if there are at least two players,
            # and at least one left to act.
            # Similarly, if one player is all in, game continues if there are
            # at least two players, and at least one left to act.
            return len(will_remain) >= 2 and len(will_act) >= 1
        else:
            # Pre-river, game continues if there are at least two players
            return len(will_remain) >= 2

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
        fold_options = self.range_action.fold_range  \
            .generate_options_unweighted(dead_cards)
        passive_options = self.range_action.passive_range  \
            .generate_options_unweighted(dead_cards)
        aggressive_options = self.range_action.aggressive_range  \
            .generate_options_unweighted(dead_cards)
        # Consider fold
        fold_action = ActionResult.fold()
        if len(fold_options) > 0:
            self.bough.append(Branch(self.fold_continue(),
                                     fold_options,
                                     fold_action,
                                     self.range_action.fold_range))
        # Consider call
        passive_action = ActionResult.call(self.current_options.call_cost)
        if len(passive_options) > 0:
            self.bough.append(Branch(self.passive_continue(),
                                     passive_options,
                                     passive_action,
                                     self.range_action.passive_range))
        # Consider raise
        aggressive_action = ActionResult.raise_to(
            self.range_action.raise_total, self.current_options.is_raise)
        if len(aggressive_options) > 0:
            self.bough.append(Branch(self.aggressive_continue(),
                                     aggressive_options,
                                     aggressive_action,
                                     self.range_action.aggressive_range))

    def re_range(self, branch):
        """
        Assign new range to rgp, and redeal their hand
        """
        # branch.options excludes cards dealt, branch.range does not
        self.rgp.range_raw = branch.range.description
        self.rgp.cards_dealt = random.choice(branch.options)
        logging.debug("gameid %d, new range for userid %d, new range %r, " +
                      "new cards_dealt %r", self.rgp.gameid, self.rgp.userid,
                      self.rgp.range_raw, self.rgp.cards_dealt)

    def calculate_what_will_be(self):
        """
        Choose one of the non-terminal actions, or return termination if they're
        all terminal. Also update game's current_factor. 
        """
        # reduce current factor by the ratio of non-terminal-to-terminal options
        non_terminal = []
        terminal = []
        for branch in self.bough:
            if not branch.options:
                continue
            if branch.is_continue:
                logging.debug("gameid %d, potential action %r would continue",
                              self.game.gameid, branch.action)
                non_terminal.extend(branch.options)
            else:
                logging.debug("gameid %d, potential action %r would terminate",
                              self.game.gameid, branch.action)
                terminal.extend(branch.options)
        total = len(non_terminal) + len(terminal)
        reduction = float(len(non_terminal)) / total
        logging.debug("gameid %d, with %d non-terminal and %d terminal, " +
                      "multiplying current factor by %0.2f from %0.2f to %0.2f",
                      self.game.gameid, len(non_terminal), len(terminal),
                      reduction, self.game.current_factor,
                      self.game.current_factor * reduction)
        # the more non-terminal, the less effect on current factor
        self.game.current_factor *= reduction
        if non_terminal:
            chosen_option = random.choice(non_terminal)
            # but which action was chosen?
            for branch in self.bough:
                if chosen_option in branch.options:
                    logging.debug("gameid %d, chosen %r for action %r",
                        self.game.gameid, chosen_option, branch.action)
                    self.action_result = branch.action
                    self.re_range(branch)
        else:
            logging.debug("gameid %d, what will be is to terminate",
                          self.game.gameid)
            self.action_result = ActionResult.terminate()
        return self.action_result    

class Test(unittest.TestCase):
    """
    Unit tests for action functionality
    """
    # pylint:disable=R0904    
    def test_cmp_options(self):
        """
        Test _cmp_options
        """
        cqh = Card.from_text("Qh")
        ckh = Card.from_text("Kh")
        cah = Card.from_text("Ah")
        cks = Card.from_text("Ks")
        ckc = Card.from_text("Kc")
        kh_qh = set([ckh, cqh])
        ah_kh = set([ckh, cah])
        ks_kh = set([ckh, cks])
        kh_kc = set([ckh, ckc])
        self.assertEqual(-1, _cmp_options(kh_qh, ah_kh))
        self.assertEqual(-1, _cmp_options(kh_qh, ks_kh))
        self.assertEqual(-1, _cmp_options(kh_qh, kh_kc))
        self.assertEqual(1, _cmp_options(ah_kh, kh_qh))
        self.assertEqual(1, _cmp_options(ah_kh, ks_kh))
        self.assertEqual(1, _cmp_options(ah_kh, kh_kc))
        self.assertEqual(1, _cmp_options(ks_kh, kh_qh))
        self.assertEqual(-1, _cmp_options(ks_kh, ah_kh))
        self.assertEqual(1, _cmp_options(ks_kh, kh_kc))
        self.assertEqual(1, _cmp_options(kh_kc, kh_qh))
        self.assertEqual(-1, _cmp_options(kh_kc, ah_kh))
        self.assertEqual(-1, _cmp_options(kh_kc, ks_kh))
    
    def test_range_action_fits(self):
        """
        Test range_action_fits
        """
        # pylint:disable=R0915
        
        # will test that:
        # - hand in original but not action should fail
        # - hand not in original but in action should fail
        # - hand in two or more ranges should fail
        # - raise size within band should succeed
        # - raise size outside band should fail
        # - should work the same with weights as without
        range_original = HandRange("AA(5),22,72o")
        range_aa = HandRange("AA(5)")
        range_kk = HandRange("KK")
        range_22 = HandRange("22")
        range_72o = HandRange("72o")
        range_22_72o = HandRange("22,72o")
        range_aa_22 = HandRange("AA(5),22")
        range_empty = HandRange("nothing")
        range_22_weighted = HandRange("22(3)")
        
        #options = [FoldOption(), CheckOption(), RaiseOption(2, 194)]
        options = ActionOptions(0, False, 2, 194)
        
        # invalid, raise size too small
        range_action = ActionDetails(range_72o, range_22, range_aa, 1)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn, "raise total must be between 2 and 194")

        # valid, minraise
        range_action = ActionDetails(range_72o, range_22, range_aa, 2)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)

        # valid, never folding when we can check
        range_action = ActionDetails(range_empty, range_22_72o, range_aa, 2)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)

        # valid, max raise
        range_action = ActionDetails(range_72o, range_22, range_aa, 194)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)

        # invalid, raise size too big
        range_action = ActionDetails(range_72o, range_22, range_aa, 195)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn, "raise total must be between 2 and 194")

        # invalid, AA in original but not action
        range_action = ActionDetails(range_72o, range_22, range_empty, 2)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn,
            "hand in original range but not in action ranges: AdAc")
        
        # invalid, KK in action but not original
        range_action = ActionDetails(range_72o, range_aa_22, range_kk, 2)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn,
            "hand in action ranges but not in original range: KdKc")

        # invalid, AA in multiple ranges
        range_action = ActionDetails(range_72o, range_aa_22, range_aa, 2)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn, "hand in multiple ranges: AdAc")
        
        #options = [FoldOption(), CallOption(10), RaiseOption(20, 194)]
        options = ActionOptions(10, True, 20, 194)
        
        # invalid, re-weighted
        range_action = ActionDetails(range_72o, range_22_weighted, range_aa, 20)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn, "weight changed from 1 to 3 for hand 2d2c")

        # valid, empty raise range (still has a raise size, which is okay)
        range_action = ActionDetails(range_aa, range_22_72o, range_empty, 20)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)

        # invalid, raise too big
        range_action = ActionDetails(range_72o, range_22, range_aa, 195)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn, "raise total must be between 20 and 194")

        #options = [FoldOption(), CallOption(194)]
        options = ActionOptions(194)
        
        # valid, 0 raise size is okay if empty raise range
        range_action = ActionDetails(range_22_72o, range_aa, range_empty, 0)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)
        
        # valid, 200 raise size is okay if empty raise range
        range_action = ActionDetails(range_22_72o, range_aa, range_empty, 200)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)

        # valid, has raise size but raise range is empty
        range_action = ActionDetails(range_original, range_empty, range_empty,
                                     20)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertTrue(val)

        # invalid, has raise range
        range_action = ActionDetails(range_72o, range_22, range_aa, 20)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn,
            "there was a raising range, but raising was not an option")
        
        range_action = ActionDetails(range_72o, range_22, range_aa, 0)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn,
            "there was a raising range, but raising was not an option")

        # invalid, doesn't equal original
        range_action = ActionDetails(range_empty, range_aa, range_empty, 0)
        val, rsn = range_action_fits(range_action, options, range_original)
        self.assertFalse(val)
        self.assertEqual(rsn,
            "hand in original range but not in action ranges: 2d2c")

    def test_range_contains_hand(self):
        """
        Test range_contains_hand
        """
        from rvr.poker import cards
        range_ = HandRange("AA(5),KK")
        hands_in = [
            [Card(cards.ACE, cards.SPADES), Card(cards.ACE, cards.HEARTS)],
            [Card(cards.KING, cards.CLUBS), Card(cards.KING, cards.DIAMONDS)]
            ]
        hands_out = [
            [Card(cards.ACE, cards.SPADES), Card(cards.KING, cards.HEARTS)],
            [Card(cards.DEUCE, cards.CLUBS), Card(cards.DEUCE, cards.DIAMONDS)]
            ]
        for hand_in in hands_in:
            self.assertTrue(range_contains_hand(range_, hand_in))
        for hand_out in hands_out:
            self.assertFalse(range_contains_hand(range_, hand_out))

if __name__ == '__main__':
    # 9.7s 20130205 (client-server)
    # 9.0s 20140102 (web)
    unittest.main()