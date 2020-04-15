"""
action functionality, imported from the previous versions
"""
from rvr.poker.cards import Card, FLOP, PREFLOP, RIVER, TURN
import unittest
from rvr.poker.handrange import HandRange, _cmp_options, deal_from_ranges,\
    NOTHING
from rvr.infrastructure.util import concatenate
from rvr.core.dtos import ActionOptions, ActionDetails, ActionResult
from collections import namedtuple
import logging
import numpy

NEXT_ROUND = {PREFLOP: FLOP, FLOP: TURN, TURN: RIVER}
TOTAL_COMMUNITY_CARDS = {PREFLOP: 0, FLOP: 3, TURN: 4, RIVER: 5}
WEIGHT_SAMPLES = 10

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
    original_hand_options.sort(cmp=_cmp_options)
    all_ranges_hand_options.sort(cmp=_cmp_options)
    prev = None
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
                    _option_to_text(ori)
            elif ori is None:
                message =  \
                    "hand in action ranges but not in original range: %s" %  \
                    _option_to_text(new)
            else:
                if new == prev:
                    message = "hand in multiple ranges: %s" %  \
                        _option_to_text(new)
                elif _cmp_options(new, ori) > 0:
                    message = "hand in original range but not in " +  \
                        "action ranges: %s" % _option_to_text(ori)
                elif _cmp_options(new, ori) < 0:
                    message = "hand in action ranges but not in " +  \
                        "original range: %s" % _option_to_text(new)
                else:
                    raise RuntimeError("hands not equal, but can't " +  \
                                       "figure out why: %s, %s" % \
                                       (_option_to_text(ori),
                                        _option_to_text(new)))
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
    return set(hand) in range_.generate_options()

def generate_excluded_cards(game, exclude=None):
    """
    calculate excluded cards, as if players had been dealt cards
    """
    # Yep, even if they're folded, we include them.
    map_to_range = {rgp: rgp.range for rgp in game.rgps}
    # We consider the future board. By doing this here, we make action
    # probabilities consistent with calculated range sizes.
    # Implications:
    #  - we're using an actual board for everything, except pre-river all in
    #  - i.e. call ratio will be determined by future board cards, even though
    #    future board cards are ignored for equity calculations
    #  - it's extremely counter-intuitive, but I think it's the right result
    # More broadly:
    #  - (good) we'll never end up in an impossible situation
    #    (e.g. Ax vs. Ax on board AAxAx)
    #  - (bad) (already possible?) sometimes one range just won't be played
    #    out (actually, good and correct?, for both competition and
    #    optimization mode?)
    #  - (bad) when you get all in pre-river, future cards will be excluded
    #    from the perspective of the probability of the action, but included
    #    from the perspective of the showdown ranges and equities (but this
    #    is still the most preferable option)
    board = game.total_board or game.board
    player_to_dealt = deal_from_ranges(map_to_range, board)
    # note: this catches cards dealt to folded RGPs - as it should!
    values = [dealt for rgp, dealt in player_to_dealt.iteritems()
              if rgp != exclude]
    excluded_cards = concatenate(values)
    excluded_cards.extend(board)
    return excluded_cards

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

def game_continues(current_round, all_in, will_remain, will_act):
    """
    Given a list of players remaining in the hand, and a list of players
    remaining to act, will the game continue? (Or is it over, contested or
    otherwise.)
    """
    if current_round == RIVER or all_in:
        # On the river, game continues if there are at least two players,
        # and at least one left to act.
        # Similarly, if one player is all in, game continues if there are
        # at least two players, and at least one left to act.
        return len(will_remain) >= 2 and len(will_act) >= 1
    else:
        # Pre-river, game continues if there are at least two players
        return len(will_remain) >= 2

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
    game.game_finished = True

# TODO: 5: test situations like P1 bet, P2 call, P3 fold/call/raise
# (P3's action triggers a P1+P2 showdown and a P1+P2+P3 showdown, and more.)
# TODO: 5: results weighted by size of ranges in starting situation?

Branch = namedtuple("Branch",  # pylint:disable=C0103
                    ["is_continue",  # For this option, does play continue?
                     "weight",  # Relative likelihood of this option
                     "action",  # Action that results from this option
                     "range"])  # Range for player making the action

OptionWeights = namedtuple("OptionWeights",  # pylint:disable=C0103
                           ['fold',
                            'passive',
                            'aggressive'])

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
        return game_continues(self.game.current_round, self.all_in,
                              will_remain, will_act)

    def passive_continue(self):
        """
        If a passive action is taken here, will the hand continue?
        """
        # remain is everyone who hasn't folded
        will_remain = [r for r in self.game.rgps if not r.folded]
        # to act is everyone else who's to act
        will_act = [r for r in self.game.rgps
                    if r.left_to_act and r is not self.rgp]
        return game_continues(self.game.current_round, self.all_in,
                              will_remain, will_act)

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
        return game_continues(self.game.current_round, self.all_in,
                              will_remain, will_act)

    def sample_weights(self):
        # Deal a hand, and then based on the hands dealt to the others,
        # calculate how likely each betting line would continue.
        # (If done infinite times, this would give an answer equivalent
        # to dealing infinite times, and counting how many deals go into each
        # betting line.)
        # (That would also be equivalent to considering all possible combos vs.
        # all possible combos, excluding those that share cards (card removal
        # effects), and counting how many combos lead to each betting line.)
        # (There is a bias from those Villain combos where Hero has more combos
        # and therefore these Villain combos are more likely to be selected, but
        # this is accounted for by the returned weights being divided by the
        # total number of Hero combos for the selected Villain combos.)
        dead_cards = generate_excluded_cards(self.game, exclude=self.rgp)
        fold = len(self.range_action.fold_range
                   .generate_options(dead_cards))
        passive = len(self.range_action.passive_range
                      .generate_options(dead_cards))
        aggressive = len(self.range_action.aggressive_range
                         .generate_options(dead_cards))
        # It's very important to divide through by the total here.
        # Okay I'm kidding, probably no one would ever notice the difference.
        # (Except the unit test I made to check that's it's correct.)
        # The above sampling over-represents Hero combos that are more common.
        # The reason is that generate_excluded_cards() perfectly samples all
        # possibilities equally, but then generate_options results in more
        # options being generated when the villains happened to be sampled
        # combos that give Hero more combos.
        # Dividing through by the total precisely counteracts that bias.
        total = fold + passive + aggressive
        return 1.0 * fold / total,  \
            1.0 * passive / total,  \
            1.0 * aggressive / total

    def calculate_weights(self):
        """
        Answers the question "Given player X continues with subrange A of
        original range B, while player Y holds range C, what is the probability
        that each line is taken?

        This is a VERY hard question to answer.

        The most accurate and correct way would be slow: consider all combos of
        each player multiplied by each other, then count the possibilities that
        fall in each of Hero's fold, passive and aggressive ranges.

        This estimates it through random sampling a few times instead.
        """
        # after much consideration, this is the best, most practical way:
        # - deal a hand (all players)
        # - holding other players' dealt card, calculate weights (range-vs-hand)
        # - these weights are unbiased estimators of true weights
        # - do this multiple times, and average them
        # this is two changes from the previous way:
        # 1) cards dealt reflect true card removal effects by including Hero
        # 2) average over multiple
        # 3) and therefore no longer really defines "which combos do what"
        samples = [self.sample_weights() for _ in xrange(WEIGHT_SAMPLES)]
        fold = sum(sample[0] for sample in samples) / len(samples)
        passive = sum(sample[1] for sample in samples) / len(samples)
        aggressive = sum(sample[2] for sample in samples) / len(samples)
        return fold, passive, aggressive

    def consider_all(self):
        # mostly copied from the old re_deal (originally!)
        """
        Plays every action in range_action, except the zero-weighted ones.
        If the game can continue, this will return an appropriate action_result.
        If not, it will return a termination. The game will continue if any
        action results in at least two players remaining in the hand, and at
        least one player left to act. (Whether or not that includes this
        player.)

        Inputs: see __init__

        Outputs: range ratios

        Side effects:
         - analyse effects of a fold, a passive play, or an aggressive play
        """
        # note that we only consider the possible
        fold_weight, passive_weight, aggressive_weight =  \
            self.calculate_weights()
        # Consider fold
        fold_action = ActionResult.fold()
        if fold_weight > 0.0:
            self.bough.append(Branch(self.fold_continue(),
                                     fold_weight,
                                     fold_action,
                                     self.range_action.fold_range))
        # Consider call
        passive_action = ActionResult.call(self.current_options.call_cost)
        if passive_weight > 0.0:
            self.bough.append(Branch(self.passive_continue(),
                                     passive_weight,
                                     passive_action,
                                     self.range_action.passive_range))
        # Consider raise
        aggressive_action = ActionResult.raise_to(
            self.range_action.raise_total, self.current_options.is_raise)
        if aggressive_weight > 0.0:
            self.bough.append(Branch(self.aggressive_continue(),
                                     aggressive_weight,
                                     aggressive_action,
                                     self.range_action.aggressive_range))
        return OptionWeights(fold=fold_weight,
                             passive=passive_weight,
                             aggressive=aggressive_weight)

    def calculate_what_will_be(self, auto_spawn):
        """
        Choose one of the non-terminal actions, or return termination if they're
        all terminal. Also update game's current_factor.

        Returns a weighted list of action results:
            [(weight, action_result), (weight, action_result)...]

        If auto_spawn, there may be multiple. If not, then only one.
        """
        # reduce current factor by the weighted ratio of
        # non-terminal-to-terminal lines
        non_terminal = 0.0
        terminal = 0.0
        for branch in self.bough:
            if not branch.weight:
                # specifically, this continue means that zero-weighted lines
                # won't be played, even when playing out all betting lines
                continue
            if branch.is_continue:
                logging.debug("gameid %d, potential action %r would continue",
                              self.game.gameid, branch.action)
                non_terminal += branch.weight
            else:
                logging.debug("gameid %d, potential action %r would terminate",
                              self.game.gameid, branch.action)
                terminal += branch.weight
        total = non_terminal + terminal
        reduction = non_terminal / total
        logging.debug("gameid %d, with %0.4f non-terminal and %0.4f " +
                      "terminal, multiplying current factor by %0.4f from " +
                      "%0.4f to %0.4f",
                      self.game.gameid, non_terminal, terminal,
                      reduction, self.game.current_factor,
                      self.game.current_factor * reduction)
        self.game.current_factor *= reduction
        if non_terminal == 0.0:
            logging.debug("gameid %d, what will be is to terminate",
                          self.game.gameid)
            return []
        elif not auto_spawn:
            # pick a branch that continues
            indices = [i for i, branch in enumerate(self.bough)
                       if branch.is_continue]
            weights = [self.bough[index].weight / non_terminal
                       for index in indices]
            # numpy.random.choice does not cope with a list of Branch
            # so we're picking from indices, and then converting to Branch
            index = numpy.random.choice(indices, p=weights)
            branch = self.bough[index]
            logging.debug("gameid %d, chosen action %r",
                self.game.gameid, branch.action)
            return [(1.0, branch.action, branch.range.description)]
        else:
            results = []
            for branch in self.bough:
                if branch.weight > 0.0 and branch.is_continue:
                    # dividing by non_terminal is actually scaling *up* so that
                    # all (non-terminal) weights add to 1.0
                    weight = branch.weight / non_terminal
                    logging.debug("gameid %d, action %r will happen or spawn,"
                                  " with weight %0.4f",
                                  self.game.gameid, branch.action, weight)
                    results.append(
                        (weight, branch.action, branch.range.description))
            return results

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
        range_original = HandRange("AA,22,72o")
        range_aa = HandRange("AA")
        range_kk = HandRange("KK")
        range_22 = HandRange("22")
        range_72o = HandRange("72o")
        range_22_72o = HandRange("22,72o")
        range_aa_22 = HandRange("AA,22")
        range_empty = HandRange("nothing")

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
        range_ = HandRange("AA,KK")
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

    class MockRGP:
        def __init__(self, stack, range, folded, left_to_act):
            self.stack = stack
            self.range = range
            self.folded = folded
            self.left_to_act = left_to_act

    class MockGame:
        def __init__(self, rgps, total_board, current_round, gameid,
                     current_factor):
            self.rgps = rgps
            self.total_board = total_board
            self.current_round = current_round
            self.gameid = gameid
            self.current_factor = current_factor

    def test_game_5643(self):
        """
        Board is Ts3sAh
        MP bets AsAd,AsAc,AdAc,KK-JJ,ThTd,ThTc,TdTc,99-44,3h3d,3h3c,3d3c,22,AsKs,AdKd,AcKc,AsQs,AdQd,AcQc,AsJs,AdJd,AcJc,AdTd,AcTc,As9s,Ad9d,Ac9c,As8s,Ad8d,Ac8c,As7s,Ad7d,As6s,Ad6d,As5s,Ad5d,Ac5c,As4s,Ad4d,Ac4c,Ad3d,Ac3c,As2s,Ad2d,Ac2c,KJs+,KhTh,KdTd,KcTc,Ks9s,QJs,QdTd,QcTc,Qh9h,JhTh,JdTd,JcTc,Js9s,Jh9h,Jd8d,Th9h,Td9d,Tc9c,Tc8c,Tc7c,98s,9h7h,9d7d,9s6s,87s,8h6h,8c6c,8h5h,76s,7s5s,7d5d,7d4d,65s,6d4d,6c4c,6c3c,54s,5h3h,4h3h,4d3d,4c3c,AsKh,AsKd,AsKc,AdKs,AdKh,AdKc,AcKs,AcKh,AcKd,AsQh,AsQd,AsQc,AdQs,AdQh,AdQc,AcQs,AcQh,AcQd,AsJh,AsJd,AsJc,AdJs,AdJh,AdJc,AcJs,AcJh,AcJd,AsTh,AsTd,AsTc,AdTh,AdTc,AcTh,AcTd,KQo
        BTN folds 99-66,22,Kd9d,Jd9d,Jd8d,Td9d,Tc9c,9d8d,9c8c,8d7d,8c7c,7d6d,7c6c,7d5d,6d5d,6c5c,6c4c
        BTN calls JJ,ThTd,ThTc,TdTc,55-44,3h3d,3h3c,3d3c,AsQs,AdQd,AcQc,AsJs,AdJd,AcJc,AdTd,AcTc,As9s,Ad9d,Ac9c,As8s,Ad8d,Ac8c,As7s,Ad7d,Ac7c,As6s,Ad6d,Ac6c,As5s,Ad5d,Ac5c,As4s,Ad4d,Ac4c,Ad3d,Ac3c,As2s,Ad2d,Ac2c,KJs+,KhTh,QJs,QdTd,QcTc,Qh9h,JhTh,JdTd,JcTc,Jh9h,Th9h,Tc8c,Tc7c,9s8s,9h8h,9s7s,8s7s,8h7h,8h6h,7s6s,7h6h,6s5s,6h5h,54s,5d2d,4h3h,4c2c,3h2h,AsQh,AsQd,AsQc,AdQs,AdQh,AdQc,AcQs,AcQh,AcQd,AsJh,AsJd,AsJc,AdJs,AdJh,AdJc,AcJs,AcJh,AcJd,AsTh,AsTd,AsTc,AdTc,Ad9h,Ac9s,Ac9d,Ad8s,Ac8h,As7c,Ad7h,As6h,As6d,Ad5h,Ac5s,Ad4s,Ac4h,Ac4d,As3c,Ac3h,As2d,Ad2h,Ac2s,KQo,KhJs,KdJs,KdJh,KcJs,KcJh,KcJd,KsTh,KsTd,KhTc,QhJs,QdJs,QcJh,JsTc,JhTd,JdTc

        MP is betting 1/3 pot.
        BTN calls more than 3 times in 4, yet MP makes a profit!
        """
        mp = self.MockRGP(
            189,
            HandRange("AsAd,AsAc,AdAc,KK-JJ,ThTd,ThTc,TdTc,99-44,3h3d,3h3c,3d3c,22,AsKs,AdKd,AcKc,AsQs,AdQd,AcQc,AsJs,AdJd,AcJc,AdTd,AcTc,As9s,Ad9d,Ac9c,As8s,Ad8d,Ac8c,As7s,Ad7d,As6s,Ad6d,As5s,Ad5d,Ac5c,As4s,Ad4d,Ac4c,Ad3d,Ac3c,As2s,Ad2d,Ac2c,KJs+,KhTh,KdTd,KcTc,Ks9s,QJs,QdTd,QcTc,Qh9h,JhTh,JdTd,JcTc,Js9s,Jh9h,Jd8d,Th9h,Td9d,Tc9c,Tc8c,Tc7c,98s,9h7h,9d7d,9s6s,87s,8h6h,8c6c,8h5h,76s,7s5s,7d5d,7d4d,65s,6d4d,6c4c,6c3c,54s,5h3h,4h3h,4d3d,4c3c,AsKh,AsKd,AsKc,AdKs,AdKh,AdKc,AcKs,AcKh,AcKd,AsQh,AsQd,AsQc,AdQs,AdQh,AdQc,AcQs,AcQh,AcQd,AsJh,AsJd,AsJc,AdJs,AdJh,AdJc,AcJs,AcJh,AcJd,AsTh,AsTd,AsTc,AdTh,AdTc,AcTh,AcTd,KQo"),
            False,
            False)
        btn = self.MockRGP(
            194,
            HandRange("JJ,ThTd,ThTc,TdTc,99-44,3h3d,3h3c,3d3c,22,AsQs,AdQd,AcQc,AsJs,AdJd,AcJc,AdTd,AcTc,As9s,Ad9d,Ac9c,As8s,Ad8d,Ac8c,As7s,Ad7d,Ac7c,As6s,Ad6d,Ac6c,As5s,Ad5d,Ac5c,As4s,Ad4d,Ac4c,Ad3d,Ac3c,As2s,Ad2d,Ac2c,KJs+,KhTh,Kd9d,QJs,QdTd,QcTc,Qh9h,JhTh,JdTd,JcTc,Jh9h,Jd9d,Jd8d,Th9h,Td9d,Tc9c,Tc8c,Tc7c,98s,9s7s,87s,8h6h,76s,7d5d,65s,6c4c,54s,5d2d,4h3h,4c2c,3h2h,AsQh,AsQd,AsQc,AdQs,AdQh,AdQc,AcQs,AcQh,AcQd,AsJh,AsJd,AsJc,AdJs,AdJh,AdJc,AcJs,AcJh,AcJd,AsTh,AsTd,AsTc,AdTc,Ad9h,Ac9s,Ac9d,Ad8s,Ac8h,As7c,Ad7h,As6h,As6d,Ad5h,Ac5s,Ad4s,Ac4h,Ac4d,As3c,Ac3h,As2d,Ad2h,Ac2s,KQo,KhJs,KdJs,KdJh,KcJs,KcJh,KcJd,KsTh,KsTd,KhTc,QhJs,QdJs,QcJh,JsTc,JhTd,JdTc"),
            False,
            True)

        game = self.MockGame([mp, btn],
                             Card.many_from_text("Ts3sAhQhAc"),
                             FLOP,
                             5643,
                             1.0)  # it's not 1.0, but doesn't matter

        range_action = ActionDetails(
            fold_range=HandRange("99-66,22,Kd9d,Jd9d,Jd8d,Td9d,Tc9c,9d8d,9c8c,8d7d,8c7c,7d6d,7c6c,7d5d,6d5d,6c5c,6c4c"),
            passive_range=HandRange("JJ,ThTd,ThTc,TdTc,55-44,3h3d,3h3c,3d3c,AsQs,AdQd,AcQc,AsJs,AdJd,AcJc,AdTd,AcTc,As9s,Ad9d,Ac9c,As8s,Ad8d,Ac8c,As7s,Ad7d,Ac7c,As6s,Ad6d,Ac6c,As5s,Ad5d,Ac5c,As4s,Ad4d,Ac4c,Ad3d,Ac3c,As2s,Ad2d,Ac2c,KJs+,KhTh,QJs,QdTd,QcTc,Qh9h,JhTh,JdTd,JcTc,Jh9h,Th9h,Tc8c,Tc7c,9s8s,9h8h,9s7s,8s7s,8h7h,8h6h,7s6s,7h6h,6s5s,6h5h,54s,5d2d,4h3h,4c2c,3h2h,AsQh,AsQd,AsQc,AdQs,AdQh,AdQc,AcQs,AcQh,AcQd,AsJh,AsJd,AsJc,AdJs,AdJh,AdJc,AcJs,AcJh,AcJd,AsTh,AsTd,AsTc,AdTc,Ad9h,Ac9s,Ac9d,Ad8s,Ac8h,As7c,Ad7h,As6h,As6d,Ad5h,Ac5s,Ad4s,Ac4h,Ac4d,As3c,Ac3h,As2d,Ad2h,Ac2s,KQo,KhJs,KdJs,KdJh,KcJs,KcJh,KcJd,KsTh,KsTd,KhTc,QhJs,QdJs,QcJh,JsTc,JhTd,JdTc"),
            aggressive_range=HandRange(NOTHING),
            raise_total=0)
        current_options = ActionOptions(
            call_cost=5,
            is_raise=True,
            min_raise=10,
            max_raise=194)
        wcb = WhatCouldBe(game, btn, range_action, current_options)
        weights = wcb.consider_all()
        f = weights.fold
        p = weights.passive
        a = weights.aggressive
        self.assertAlmostEqual(f + p + a, 1.0)
        self.assertEqual(a, 0.0)
        self.assertAlmostEqual(p, 0.734, delta=0.014)
        # also updates current_factor
        weighted_actions = wcb.calculate_what_will_be(False)
        self.assertTrue(weighted_actions)
        self.assertEqual(len(weighted_actions), 1)
        weight, action, _description = weighted_actions[0]
        self.assertEqual(weight, 1.0)
        self.assertTrue(action.is_passive)
        # also updates current_factor
        weighted_actions = wcb.calculate_what_will_be(True)
        self.assertTrue(weighted_actions)

    def test_game_5564(self):
        """
        Board is TcAdAcTh3h
        BTN jams As4s,Ah4h,As3s,As2s,Ah2h,As4h,As4d,As4c,Ah4s,Ah4d,Ah4c,As3d,As3c,Ah3s,Ah3d,Ah3c,As2h,As2d,As2c,Ah2s,Ah2d,Ah2c
        BB folds 3d3c,Ah9h,Ah8h,Ah7h,Ah6h,Ah5h,Ah4h,Ah2h,QsTs,QdTd,JsTs,JdTd,Td9d,Td8d,As9c,Ah9d,Ah9c,As8c,Ah8d,Ah8c,As7c,Ah7d,Ah7c,As6c,Ah6d,Ah6c,As5c,Ah5d,Ah5c,As4c,Ah4d,Ah4c,As2c,Ah2d,Ah2c,KsTd,KhTd,KcTd,QsTd,QhTd,QcTd,JsTd,JhTd,JcTd,Td8s,Td8h
        BB calls AhTd,As3c,Ah3d,Ah3c

        BB is calling 8% of his range, but with blockers, the call weight
        should be between 0% and 8%, but never 0%.
        """
        btn = self.MockRGP(
            0,
            # 22 jams
            HandRange("As4s,Ah4h,As3s,As2s,Ah2h,As4h,As4d,As4c,Ah4s,Ah4d,Ah4c,As3d,As3c,Ah3s,Ah3d,Ah3c,As2h,As2d,As2c,Ah2s,Ah2d,Ah2c"),
            False,
            False)
        bb = self.MockRGP(
            178,
            # 50 combos to act
            HandRange("3d3c,Ah9h,Ah8h,Ah7h,Ah6h,Ah5h,Ah4h,Ah2h,QsTs,QdTd,JsTs,JdTd,Td9d,Td8d,As9c,Ah9d,Ah9c,As8c,Ah8d,Ah8c,As7c,Ah7d,Ah7c,As6c,Ah6d,Ah6c,As5c,Ah5d,Ah5c,As4c,Ah4d,Ah4c,As2c,Ah2d,Ah2c,KsTd,KhTd,KcTd,QsTd,QhTd,QcTd,JsTd,JhTd,JcTd,Td8s,Td8h,AhTd,As3c,Ah3d,Ah3c"),
            False,
            True)

        game = self.MockGame([bb, btn],
                             Card.many_from_text("TcAdAcTh3h"),
                             RIVER,
                             5564,
                             0.00475263)

        range_action = ActionDetails(
            # 46 folds, 4 calls
            fold_range=HandRange("3d3c,Ah9h,Ah8h,Ah7h,Ah6h,Ah5h,Ah4h,Ah2h,QsTs,QdTd,JsTs,JdTd,Td9d,Td8d,As9c,Ah9d,Ah9c,As8c,Ah8d,Ah8c,As7c,Ah7d,Ah7c,As6c,Ah6d,Ah6c,As5c,Ah5d,Ah5c,As4c,Ah4d,Ah4c,As2c,Ah2d,Ah2c,KsTd,KhTd,KcTd,QsTd,QhTd,QcTd,JsTd,JhTd,JcTd,Td8s,Td8h"),
            passive_range=HandRange("AhTd,As3c,Ah3d,Ah3c"),
            aggressive_range=HandRange(NOTHING),
            raise_total=0)
        current_options = ActionOptions(
            call_cost=178,
            is_raise=True)
        wcb = WhatCouldBe(game, bb, range_action, current_options)
        weights = wcb.consider_all()
        f = weights.fold
        p = weights.passive
        a = weights.aggressive
        self.assertAlmostEqual(f + p + a, 1.0)
        self.assertEqual(a, 0.0)
        # call is about 0.0559
        # (733 total combos of combos)
        # (equals 41 calls, 692 folds)
        self.assertAlmostEqual(p, 41.0 / 733, 2)
        # also updates current_factor
        weighted_actions = wcb.calculate_what_will_be(False)
        self.assertFalse(weighted_actions)
        # also updates current_factor
        weighted_actions = wcb.calculate_what_will_be(True)
        self.assertFalse(weighted_actions)

if __name__ == '__main__':
    # 9.7s 20130205 (client-server)
    # 9.0s 20140102 (web)
    unittest.main()
