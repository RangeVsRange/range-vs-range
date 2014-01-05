"""
action functionality, imported from the previous versions
"""
from rvr.poker.cards import Card
import unittest
from rvr.poker.handrange import HandRange,  \
    _cmp_weighted_options, _cmp_options, weighted_options_to_description
from rvr.infrastructure.util import concatenate
from rvr.core.dtos import ActionOptions, ActionDetails, ActionResult
import logging

PREFLOP = "preflop"
FLOP = "flop"
TURN = "turn"
RIVER = "river"

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
    options = range_.generate_options()  # of the form [(hand, weight)]
    unweighted = [weighted[0] for weighted in options]
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
        return ActionOptions(call_amount)

def range_action_to_action(range_action, hand, current_options):
    """
    range_action is a ActionDetails, ranges have text descriptions
    hand is a list of two Card
    returns a new range, and an action
    """
    # Note that this gives incorrect results if an option is in two ranges
    if range_contains_hand(range_action.fold_range, hand):
        return range_action.fold_range, ActionResult.fold()
    elif range_contains_hand(range_action.passive_range, hand):
        return range_action.passive_range, \
            ActionResult.call(current_options.call_cost)
    elif range_contains_hand(range_action.aggressive_range, hand):
        return range_action.aggressive_range, \
            ActionResult.raise_to(range_action.raise_total)
    else:
        raise ValueError("hand is %s, range_action is invalid: %r" %
                         (hand, range_action))

def re_deal(range_action, cards_dealt, dealt_key, board, can_fold, can_call):
    """
    This function is for when we're not letting them fold (sometimes not even
    call).
    
    We reassign their hand so that it's not a fold (or call). If possible.
    Changes cards_dealt[dealt_key] to a new hand from one of the other ranges
    (unless they're folding 100%, of course).
    
    Returns fold ratio, passive ratio, aggressive ratio.
    
    In the case of can_fold and can_call, we calculate these ratios but don't
    re_deal.
    """
    # pylint:disable=R0913,R0914
    # Choose between passive and aggressive probabilistically
    # But do this by re-dealing, to account for card removal effects (other
    # hands, and the board)
    # Note that in a range vs. range situation, it's VERY HARD to determine the
    # probability that a player will raise cf. calling. But very luckily, we
    # can work around that, by using the fact that all other players are
    # currently dealt cards with a probability appropriate to their ranges, so
    # when we use their current cards as dead cards, we achieve the
    # probabilities we need here, without knowing exactly what those
    # probabilities are. (But no, I haven't proven this mathematically.)
    dead_cards = [card for card in board if card is not None]
    dead_cards.extend(concatenate([v for k, v in cards_dealt.iteritems()
                                   if k is not dealt_key]))
    fold_options = range_action.fold_range.generate_options(dead_cards)
    passive_options = range_action.passive_range.generate_options(dead_cards)
    aggressive_options =  \
        range_action.aggressive_range.generate_options(dead_cards)
    terminate = False
    if not can_fold:
        if can_call:
            allowed_options = passive_options + aggressive_options
        else:
            # On the river, heads-up, if we called it would end the hand
            # (like a fold elsewhere)
            allowed_options = aggressive_options
            if not allowed_options:
                # The hand must end. Now.
                # They have no bet/raise range, so they cannot raise.
                # They cannot call, because the cost and benefit of calling is
                # already handled as a partial showdown payment
                # They cannot necessarily fold, because they might not have a
                # fold range.
                terminate = True
        # Edge case: It's just possible that there will be no options here. This
        # can happen when the player's current hand is in their fold range, and
        # due to cards dealt to the board and to other players, they can't have
        # any of the hands in their call or raise ranges.
        # Example: The board has AhAd, and an opponent has AsAc, and all hand in
        # the player's passive and aggressive ranges contain an Ace, and the
        # only options that don't contain an Ace are in the fold range.
        # Resolution: In this case, we let them fold. They will find this
        # astonishing, but... I think we have to.
        if allowed_options:
            description = weighted_options_to_description(allowed_options)
            allowed_range = HandRange(description)
            cards_dealt[dealt_key] = allowed_range.generate_hand()
    # Note that we can't use RelativeSizes for this. Because that doesn't
    # account for card removal effects. I.e. for the opponent's range. But this
    # way indirectly does. Yes, sometimes this strangely means that Hero
    # surprisingly folds 100%. Yes, sometimes this strangely means that Hero
    # folds 0%. And that's okay, because those things really do happen some
    # times. (Although neither might player might know Hero is doing it!)
    fol = len(fold_options)
    pas = len(passive_options)
    agg = len(aggressive_options)
    total = fol + pas + agg
    return (terminate,
        float(fol) / total,
        float(pas) / total,
        float(agg) / total)

def _fold(rgp):
    """
    Fold rgp
    """
    rgp.folded = True
    rgp.left_to_act = False
    
def _passive(rgp, call_cost):
    """
    Check or call rgp
    """
    rgp.stack -= call_cost
    rgp.contributed += call_cost
    rgp.left_to_act = False
    
def _aggressive(game, rgp, raise_total):
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

def _apply_action_result(game, rgp, action_result):
    """
    Change game and rgp state. Add relevant hand history items. Possibly
    finish hand.
    """
    if action_result.is_fold:
        _fold(rgp)
    elif action_result.is_passive:
        _passive(rgp, action_result.call_cost)
    elif action_result.is_aggressive:
        _aggressive(game, rgp, action_result.raise_total)
    else:
        raise ValueError("Invalid action result")
    left_to_act = [p for p in game.rgps if p.left_to_act]
    remain = [p for p in game.rgps if not p.left_to_act and not p.folded]
    if len(left_to_act) == 1 and not remain:
        # BB got a walk, or everyone folded to the button postflop
        # TODO: finish game, left_to_act[0] is the winner
        game.is_finished = True
    elif not left_to_act:
        # TODO: if one remains, they win; otherwise, deal cards or show down
        game.is_finished = True
    else:
        # Who's up next? And not someone named Who, but the pronoun.
        later = [p for p in left_to_act if p.order > rgp.order]
        earlier = [p for p in left_to_act if p.order < rgp.order]
        chosen = later if later else earlier
        next_rgp = min(chosen, key=lambda p: p.order)
        game.current_rgp = next_rgp
        logging.debug("Next to act in game %d: userid %d, order %d",
                      game.gameid, next_rgp.userid, next_rgp.order)

def perform_action(game, rgp, range_action, current_options):
    """
    Determine result of range action, and apply it.
    
    Assumes validation is already done!
    """
    # pylint:disable=R0914
    left_to_act = [r for r in game.rgps if r.left_to_act]
    remain = [r for r in game.rgps if not r.folded]
    # no play on when 3-handed
    can_fold = len(remain) > 2
    # same condition hold for calling of course, also:
    # preflop, flop and turn, you can call
    # if there's someone else who hasn't acted yet, you can check to them
    can_call = can_fold or game.current_round != RIVER  \
        or len(left_to_act) > 1
    cards_dealt = {rgp: rgp.cards_dealt for rgp in game.rgps}
    terminate, f_ratio, _p_ratio, a_ratio = re_deal(range_action,
        cards_dealt, rgp, game.board, can_fold, can_call)
    # this redeals rgp's cards in the dict, so we need to re-apply to rgp
    rgp.cards_dealt = cards_dealt[rgp]
    # TODO: record sizes of range_action (subjective, not actual)
    # TODO: 1: add range action and result to hand history
    # TODO: partial payments
    if not can_fold and can_call:
        game.current_factor *= 1 - f_ratio
    elif not can_fold and not can_call:
        game.current_factor *= a_ratio
    rgp.range, action_result = range_action_to_action(range_action,
        rgp.cards_dealt, current_options)
    # TODO: need final showdown sometimes (rarely) ...
    # this equates to bettinground.complete in the old version
    _apply_action_result(game, rgp, action_result)
    # TODO: note, it might not be their turn at the point we commit, okay?
    return action_result    

class Test(unittest.TestCase):
    """
    Unit tests for action functionality
    """
    # pylint:disable=R0904
    def do_test_re_deal(self, action, dealt, key, board, result, re_dealt,
                        iterations=1, delta=0.0):
        """
        Worker function for testing re_deal
        """
        # pylint:disable=R0913,R0914
        action2 = ActionDetails(HandRange(action[0]),
                                HandRange(action[1]),
                                HandRange(action[2]), 2)
        board2 = Card.many_from_text(board)
        re_dealt2 = [(HandRange(text).generate_options(board2), ratio)
                     for text, ratio in re_dealt]
        counts = [0 for _ in re_dealt2]
        for _ndx in xrange(iterations):
            dealt2 = {k: Card.many_from_text(val) for k, val in dealt.items()}
            _te, fpct, _pp, _ap = re_deal(action2, dealt2, key, board2, False,
                                        True)
            continue_ratio = 1.0 - fpct
            self.assertEqual(continue_ratio, result,
                msg="Expected continue ratio %0.3f but got %0.3f" %
                    (result, continue_ratio))
            for ndx, (options, ratio) in enumerate(re_dealt2):
                if (frozenset(dealt2[key]), 1) in options:
                    counts[ndx] += 1
                    break
            else:
                self.fail("dealt[key]=%r not in expected re_dealt2 ranges: %r" %
                          (dealt2[key], re_dealt2))
        for ndx, val in enumerate(counts):
            expected = re_dealt[ndx][1] * iterations
            self.assertAlmostEqual(val, expected, delta=delta,
                msg=("Expected count %0.0f but got count %0.0f" +  \
                " for re_dealt item %s") % (expected, val, re_dealt[ndx][0]))
    
    def test_re_deal(self):
        """
        Test re_deal
        """
        # Returns 0.0 when they choose to fold 100%, and doesn't re-deal
        # "QQ,KK,AA"/""/"", {0:JJ,1:KK}, 1, "2h3c4d" => 0.0, no re-deal
        self.do_test_re_deal(action=["QQ,KK,AA", "nothing", "nothing"],
                             dealt={0:"JsJh", 1:"KsKh"},
                             key=1,
                             board="2h3c4d",
                             result=0.0,
                             re_dealt=[("KsKh", 1.0)])
        
        # Returns 0.0 when they choose not to fold 100% but end up doing it
        # anyway, and doesn't re-deal
        # "KK"/"AA"/"", {0:AA,1:KK}, 1, "As2h3c" => 0.0; no re-deal
        self.do_test_re_deal(action=["KK", "AA", "nothing"],
                             dealt={0:"AdAh", 1:"KdKh"},
                             key=1,
                             board="As2h3c",
                             result=0.0,
                             re_dealt=[("KdKh", 1.0)])
        
        # Generates a new hand with the appropriate ratio/probability,
        # accounting for card removal effects
        # "QQ"/"KK"/"AA", {0:QQ,1:KK}, 1, "As2h3c" => 9.0 / 12.0;
        # re-dealing AA 33.3%, KK 66.7%
        self.do_test_re_deal(action=["QQ", "KK", "AA"],
                             dealt={0:"QsQh", 1:"KsKh"},
                             key=1,
                             board="As2h3c",
                             result=9.0/10.0,
                             re_dealt=[("AA", 1.0/3), ("KK", 2.0/3)],
                             iterations=10000,
                             delta=333)
    
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
    
    def test_range_action_to_action(self):
        """
        Test range_action_to_action
        """
        # pylint:disable=R0914,R0915

        # will test:
        # - act fold,
        # - act check,
        # - act call,
        # - act raise,
        # - act case where hand is in no range (although invalid)
        # won't test:
        # - act case where hand is in all ranges (because the result is
        #   undefined)
        
        options_with_check = ActionOptions(0, False, 2, 196) 
        options_with_call = ActionOptions(10, True, 20, 196)
        options_without_raise = ActionOptions(196)

        range_aa = HandRange("AA")
        range_72o = HandRange("72o")
        range_22_72o = HandRange("22,72o")
        range_empty = HandRange("nothing")
        range_22_weighted = HandRange("22(3)")

        hand_72o = Card.many_from_text("7h2c")
        hand_22 = Card.many_from_text("2h2c")
        hand_aa = Card.many_from_text("AhAc")
        hand_72s = Card.many_from_text("7h2h")

        action_with_raise = ActionDetails(range_72o, range_22_weighted,
                                          range_aa, 40)

        rng, act = range_action_to_action(action_with_raise,
                                          hand_72o, options_with_check)
        self.assert_(act.is_fold)
        self.assertEqual("72o", rng.description)
        rng, act = range_action_to_action(action_with_raise,
                                          hand_22, options_with_check)
        self.assert_(act.is_passive)
        self.assertEqual(act.call_cost, 0)
        rng, act = range_action_to_action(action_with_raise,
                                          hand_aa, options_with_check)
        self.assert_(act.is_aggressive)
        self.assertEqual(act.raise_total, 40)
        try:
            act = range_action_to_action(action_with_raise,
                                         hand_72s, options_with_check)
            self.assertTrue(False)
        except ValueError:
            pass

        rng, act = range_action_to_action(action_with_raise,
                                          hand_72o, options_with_call)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_with_raise,
                                          hand_22, options_with_call)
        self.assert_(act.is_passive)
        self.assertEqual(act.call_cost, 10)
        rng, act = range_action_to_action(action_with_raise,
                                          hand_aa, options_with_call)
        self.assert_(act.is_aggressive)
        self.assertEqual(act.raise_total, 40)
        try:
            act = range_action_to_action(action_with_raise,
                                         hand_72s, options_with_call)
            self.assertTrue(False)
        except ValueError:
            pass

        action_without_raise = ActionDetails(range_22_72o, range_aa,
                                             range_empty, 0)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_72o, options_with_check)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_22, options_with_check)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_aa, options_with_check)
        self.assert_(act.is_passive)
        self.assertEqual(act.call_cost, 0)
        try:
            act = range_action_to_action(action_without_raise,
                                         hand_72s, options_with_check)
            self.assertTrue(False)
        except ValueError:
            pass

        rng, act = range_action_to_action(action_without_raise,
                                          hand_72o, options_with_call)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_22, options_with_call)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_aa, options_with_call)
        self.assert_(act.is_passive)
        self.assertEqual(act.call_cost, 10)
        try:
            act = range_action_to_action(action_without_raise,
                                         hand_72s, options_with_call)
            self.assertTrue(False)
        except ValueError:
            pass

        rng, act = range_action_to_action(action_without_raise,
                                          hand_72o, options_without_raise)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_22, options_without_raise)
        self.assert_(act.is_fold)
        rng, act = range_action_to_action(action_without_raise,
                                          hand_aa, options_without_raise)
        self.assert_(act.is_passive)
        self.assertEqual(act.call_cost, 196)
        try:
            rng, act = range_action_to_action(action_without_raise,
                hand_72s, options_without_raise)
            self.assertTrue(False)
        except ValueError:
            pass

if __name__ == '__main__':
    # 9.7s 20130205 (client-server)
    # 9.0s 20140102 (web)
    unittest.main()