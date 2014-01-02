"""
action functionality, imported from the previous versions
"""

from twisted.spread import pb
import logging
from rvr.poker.cards import Card
import unittest
from rvr.poker.handrange import HandRange,  \
    _cmp_weighted_options, _cmp_options, weighted_options_to_description
from rvr.infrastructure.util import concatenate
from rvr.core.dtos import ActionOptions, ActionResponse, ActionDetails

# TODO: fix this lint, instead of ignoring
# pylint:disable=R0903,C0111,R0201,W0141,C0301,W0110,C0103,W0201,R0914,W0703,R0913,W0613,R0904,C0324,R0915

class Option:
    OPTION_FOLD = "fold"
    OPTION_CHECK = "check"
    OPTION_CALL = "call"
    OPTION_RAISE = "bet/raise"
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name

class FoldOption(Option, pb.Copyable, pb.RemoteCopy):
    def __init__(self):
        Option.__init__(self, Option.OPTION_FOLD)
    def __eq__(self, other):
        return isinstance(other, self.__class__)
    def __hash__(self):
        return 0
    def __repr__(self):
        return "<FoldOption>"
pb.setUnjellyableForClass(FoldOption, FoldOption)

class CheckOption(Option, pb.Copyable, pb.RemoteCopy):
    def __init__(self):
        Option.__init__(self, Option.OPTION_CHECK)
    def __eq__(self, other):
        return isinstance(other, self.__class__)
    def __hash__(self):
        return 0
    def __repr__(self):
        return "<CheckOption>"
pb.setUnjellyableForClass(CheckOption, CheckOption)

class CallOption(Option, pb.Copyable, pb.RemoteCopy):
    def __init__(self, cost):
        Option.__init__(self, Option.OPTION_CALL)
        self.cost = cost
    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.cost == other.cost
    def __hash__(self):
        return hash(self.cost)
    def __str__(self):
        return self.name + " " + str(self.cost)
    def __repr__(self):
        return "<CallOption cost=%d>" % self.cost
pb.setUnjellyableForClass(CallOption, CallOption)

class RaiseOption(Option, pb.Copyable, pb.RemoteCopy):
    def __init__(self, min_, max_):
        Option.__init__(self, Option.OPTION_RAISE)
        self.min = min_
        self.max = max_
    def __eq__(self, other):
        return isinstance(other, self.__class__) and  \
            self.min == other.min and  \
            self.max == other.max
    def __hash__(self):
        return hash((self.min, self.max))
    def __str__(self):
        word = "bet" if self.min == 0 else "raise"
        return (word + " to between " + str(self.min) +
                " and " + str(self.max))
    def __repr__(self):
        return "<RaiseOption min=%d max=%d>" % (self.min, self.max)
pb.setUnjellyableForClass(RaiseOption, RaiseOption)

class Action():
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return self.name
    def full_hand_history_format(self, player, plain, bold):
        # pylint:disable=E1101
        return self.hand_history_format(player, plain, bold)
        
class FoldAction(Action, pb.Copyable, pb.RemoteCopy):
    def __init__(self):
        Action.__init__(self, Option.OPTION_FOLD)
    def __eq__(self, other):
        return isinstance(other, self.__class__)
    def __hash__(self):
        return 0
    def hand_history_format(self, player, plain, bold):
        bold(player)
        plain(" folds")
pb.setUnjellyableForClass(FoldAction, FoldAction)

class CheckAction(Action, pb.Copyable, pb.RemoteCopy):
    def __init__(self):
        Action.__init__(self, Option.OPTION_CHECK)
    def __eq__(self, other):
        return isinstance(other, self.__class__)
    def __hash__(self):
        return 0
    def hand_history_format(self, player, plain, bold):
        bold(player)
        plain(" checks")
pb.setUnjellyableForClass(CheckAction, CheckAction)

class CallAction(Action, pb.Copyable, pb.RemoteCopy):
    def __init__(self, cost):
        Action.__init__(self, Option.OPTION_CALL)
        self.cost = cost
    def __eq__(self, other):
        return isinstance(other, self.__class__) and  \
            self.cost == other.cost
    def __hash__(self):
        return hash(self.cost)
    def __repr__(self):
        return self.name + " " + str(self.cost)
    def hand_history_format(self, player, plain, bold):
        bold(player)
        plain(" calls for %d chips" % self.cost)
pb.setUnjellyableForClass(CallAction, CallAction)

class RaiseAction(Action, pb.Copyable, pb.RemoteCopy):
    def __init__(self, total):
        Action.__init__(self, Option.OPTION_RAISE)
        self.total = total
    def __eq__(self, other):
        return isinstance(other, self.__class__) and  \
            self.total == other.total
    def __hash__(self):
        return hash(self.total)
    def __repr__(self):
        return self.name + " to " + str(self.total)
    def hand_history_format(self, player, plain, bold):
        bold(player)
        plain(" bets/raises to %d chips" % self.total)
pb.setUnjellyableForClass(RaiseAction, RaiseAction)

class RangeSizes(pb.Copyable, pb.RemoteCopy):
    """
    Not jellyable, because we don't believe the client.
    """
    def __init__(self, fold_ratio, call_ratio, raise_ratio):
        self.fold_ratio = fold_ratio
        self.call_ratio = call_ratio
        self.raise_ratio = raise_ratio

pb.setUnjellyableForClass(RangeSizes, RangeSizes)

class RangeAction(pb.Copyable, pb.RemoteCopy):
    def __init__(self, fold_range, passive_range, aggressive_range, raise_total):
        self.fold_range = fold_range
        self.passive_range = passive_range
        self.aggressive_range = aggressive_range
        self.raise_total = raise_total
        self.can_check = False
        self.sizes = None
    def __repr__(self):
        return "<fold '%r', call '%r', bet '%r', size %r>" %  \
            (self.fold_range, self.passive_range, self.aggressive_range,
             self.raise_total)
    def clear_sizes(self):
        self.sizes = None
    def set_sizes(self, f, p, a):
        self.sizes = RangeSizes(f, p, a)
    def get_sizes(self):
        return self.sizes
    def hand_history_format(self, player, plain, bold):
        relative_sizes = self.get_sizes()
        fold_pct = 100.0 * relative_sizes.fold_ratio
        call_pct = 100.0 * relative_sizes.call_ratio
        raise_pct = 100.0 * relative_sizes.raise_ratio  
        bold(player)
        parts = []
        if fold_pct:
            parts.append("folds %d%%" % fold_pct)
        if call_pct:
            parts.append("%s %d%%" % ("checks" if self.can_check else "calls", call_pct))
        if raise_pct:
            parts.append("%s (to %d) %d%%" %
                         ("bets" if self.can_check else "raises",
                          self.raise_total, raise_pct))
        plain(" %s" % ", ".join(parts))
    def full_hand_history_format(self, player, plain, bold):
        relative_sizes = self.get_sizes()
        fold_pct = 100.0 * relative_sizes.fold_ratio
        call_pct = 100.0 * relative_sizes.call_ratio
        raise_pct = 100.0 * relative_sizes.raise_ratio
        bold(player)
        parts = []
        if fold_pct:
            parts.append("folds %d%% (%s)" %
                         (fold_pct, self.fold_range.description))
        if call_pct:
            parts.append("%s %d%% (%s)" %
                         ("checks" if self.can_check else "calls",
                          call_pct, self.passive_range.description))
        if raise_pct:
            parts.append("%s (to %d) %d%% (%s)" %
                         ("bets" if self.can_check else "raises",
                          self.raise_total, raise_pct,
                          self.aggressive_range.description))
        plain(" %s" % "\n... ".join(parts))
    def postUnjelly(self):
        self.relative_sizes = None  # No trust. But it's not jellyable anyway.

pb.setUnjellyableForClass(RangeAction, RangeAction)

def action_fits(action, options):
    if action is None:
        logging.info("invalid action: None")
        return False
    similar = filter(lambda o: o.name == action.name, options)
    if len(similar) == 0:
        logging.info("invalid action, no options of this type: %s", action)
        return False
    if len(similar) > 1:
        raise ValueError("Invalid option list, " +
                         "containing multiple entries for type " +
                         str(type(action)))
    option, = similar
    if isinstance(action, FoldAction) or isinstance(action, CheckAction):
        return True
    if isinstance(action, CallAction):
        val = action.cost == option.cost
        if not val:
            logging.info("CallAction is invalid: %s", action)
        return val
    if isinstance(action, RaiseAction):
        val = action.total >= option.min and action.total <= option.max
        if not val:
            logging.info("RaiseAction is invalid: %s", action)
            logging.info("min = %d, max = %d", option.min, option.max)
        return val
    raise ValueError("Unknown action type " + str(type(action)))

def _option_to_text(option):
    """
    option is set of two Card
    return something like "AhAd" (highest card first)
    """
    return "".join([o.to_mnemonic() for o in sorted(option, reverse=True)])

def range_sum_equal(fold_range, passive_range, aggressive_range, original_range):
    """
    Returns validity (boolean), and reason (string, or None if valid)
    """
    all_ranges = [fold_range, passive_range, aggressive_range]
    original_hand_options = original_range.generate_options()
    all_ranges_hand_options = concatenate([r.generate_options() for r in all_ranges])
    original_hand_options.sort(cmp=_cmp_weighted_options)
    all_ranges_hand_options.sort(cmp=_cmp_weighted_options)
    prev = (None, -1)
    for ori, new in map(None, original_hand_options, all_ranges_hand_options):
        # we compare two hands, each of which is a set of two Card
        if ori != new:
            # actually three scenarios:
            # hand is in multiple action ranges (new is the same as the previous new) 
            # hand is in action ranges but not original range (new < ori means new is not in original range)
            # hand is in original range but not action ranges (new > ori means ori is not in action ranges)
            if new is None:
                message = "hand in original range but not in action ranges: %s" % _option_to_text(ori[0])
            elif ori is None:
                message = "hand in action ranges but not in original range: %s" % _option_to_text(new[0])
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
    except Exception as err:
        return False, err.message
    if not valid:
        return False, reason
    # we require that if there is a raise range, there is a raise size
    # but if there is an empty raise range, raise size is irrelevant
    if aggressive_range.is_empty():
        return True, None
    # and last, their raise size isn't wrong
    if not options.can_raise():
        return False, "there was a raising range, but raising was not an option"  # they specified a raise range, but had no such option!
    valid = raise_total >= options.min_raise and raise_total <= options.max_raise
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

def range_action_to_action(range_action, original, hand, current_options):
    """
    range_action is a RangeAction, ranges have text descriptions
    hand is a list of two Card
    returns a new range, and an action
    """
    # Note that this gives incorrect results if an option is in two ranges
    if range_contains_hand(range_action.fold_range, hand):
        return range_action.fold_range, FoldAction()
    elif range_contains_hand(range_action.passive_range, hand):
        if filter(lambda o: isinstance(o, CheckOption), current_options):
            return range_action.passive_range, CheckAction()
        else:
            call_option, = filter(lambda o: isinstance(o, CallOption), current_options)
            return range_action.passive_range, CallAction(call_option.cost)
    elif range_contains_hand(range_action.aggressive_range, hand):
        return range_action.aggressive_range, RaiseAction(range_action.raise_total)
    else:
        raise ValueError("hand is %s, range_action is invalid: %r" % (hand, range_action))

def range_action_to_action2(range_action, original, hand, current_options):
    """
    range_action is a RangeAction, ranges have text descriptions
    hand is a list of two Card
    returns a new range, and an action
    """
    # Note that this gives incorrect results if an option is in two ranges
    if range_contains_hand(range_action.fold_range, hand):
        return range_action.fold_range, FoldAction()
    elif range_contains_hand(range_action.passive_range, hand):
        if current_options.can_check():
            return range_action.passive_range, CheckAction()
        else:
            return range_action.passive_range, CallAction(current_options.call_cost)
    elif range_contains_hand(range_action.aggressive_range, hand):
        return range_action.aggressive_range, RaiseAction(range_action.raise_total)
    else:
        raise ValueError("hand is %s, range_action is invalid: %r" % (hand, range_action))

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
    aggressive_options = range_action.aggressive_range.generate_options(dead_cards)
    terminate = False
    if not can_fold:
        if can_call:
            allowed_options = passive_options + aggressive_options
        else:
            # On the river, heads-up, if we called it would end the hand (like a
            # fold elsewhere)
            allowed_options = aggressive_options
            if not allowed_options:
                # The hand must end. Now.
                # They have no bet/raise range, so they cannot raise.
                # They cannot call, because the cost and benefit of calling is already handled as a partial showdown payment
                # They cannot necessarily fold, because they might not have a fold range.
                terminate = True
        # Edge case: It's just possible that there will be no options here. This
        # can happen when the player's current hand is in their fold range, and due
        # to cards dealt to the board and to other players, they can't have any of
        # the hands in their call or raise ranges.
        # Example: The board has AhAd, and an opponent has AsAc, and all hand in
        # the player's passive and aggressive ranges contain an Ace, and the only
        # options that don't contain an Ace are in the fold range.
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
    f = len(fold_options)
    p = len(passive_options)
    a = len(aggressive_options)
    total = f + p + a
    return (terminate,
        float(f) / total,
        float(p) / total,
        float(a) / total)

class Test(unittest.TestCase):
    def do_test_re_deal(self, action, dealt, key, board, result, re_dealt, iterations=1, delta=0.0):
        action2 = ActionDetails(HandRange(action[0]),
                              HandRange(action[1]),
                              HandRange(action[2]), 2)
        board2 = Card.many_from_text(board)
        re_dealt2 = [(HandRange(text).generate_options(board2), ratio) for text, ratio in re_dealt]
        counts = [0 for _ in re_dealt2]
        for _i in xrange(iterations):
            dealt2 = {k: Card.many_from_text(v) for k, v in dealt.items()}
            _t, f, _p, _a = re_deal(action2, dealt2, key, board2, False, True)
            continue_ratio = 1.0 - f
            self.assertEqual(continue_ratio, result,
                msg="Expected continue ratio %0.3f but got %0.3f" %
                    (result, continue_ratio))
            for i, (options, ratio) in enumerate(re_dealt2):
                if (frozenset(dealt2[key]), 1) in options:
                    counts[i] += 1
                    break
            else:
                self.fail("dealt[key]=%r not in expected re_dealt2 ranges: %r" %
                          (dealt2[key], re_dealt2))
        for i, v in enumerate(counts):
            expected = re_dealt[i][1] * iterations
            self.assertAlmostEqual(v, expected, delta=delta,
                msg="Expected count %0.0f but got count %0.0f for re_dealt item %s" %
                    (expected, v, re_dealt[i][0]))
    
    def test_re_deal(self):
        # Returns 0.0 when they choose to fold 100%, and doesn't re-deal
        # "QQ,KK,AA"/""/"", {0:JJ,1:KK}, 1, "2h3c4d" => 0.0, no re-deal
        self.do_test_re_deal(action=["QQ,KK,AA","nothing","nothing"],
                             dealt={0:"JsJh", 1:"KsKh"},
                             key=1,
                             board="2h3c4d",
                             result=0.0,
                             re_dealt=[("KsKh", 1.0)])
        
        # Returns 0.0 when they choose not to fold 100% but end up doing it anyway, and doesn't re-deal
        # "KK"/"AA"/"", {0:AA,1:KK}, 1, "As2h3c" => 0.0; no re-deal
        self.do_test_re_deal(action=["KK","AA","nothing"],
                             dealt={0:"AdAh", 1:"KdKh"},
                             key=1,
                             board="As2h3c",
                             result=0.0,
                             re_dealt=[("KdKh", 1.0)])
        
        # Generates a new hand with the appropriate ratio/probability, accounting for card removal effects
        # "QQ"/"KK"/"AA", {0:QQ,1:KK}, 1, "As2h3c" => 9.0 / 12.0; re-dealing AA 33.3%, KK 66.7%
        self.do_test_re_deal(action=["QQ","KK","AA"],
                             dealt={0:"QsQh", 1:"KsKh"},
                             key=1,
                             board="As2h3c",
                             result=9.0/10.0,
                             re_dealt=[("AA", 1.0/3),("KK", 2.0/3)],
                             iterations=10000,
                             delta=333)
    
    def test_cmp_options(self):
        Qh = Card.from_text("Qh")
        Kh = Card.from_text("Kh")
        Ah = Card.from_text("Ah")
        Ks = Card.from_text("Ks")
        Kc = Card.from_text("Kc")
        KhQh = set([Kh, Qh])
        AhKh = set([Kh, Ah])
        KsKh = set([Kh, Ks])
        KhKc = set([Kh, Kc])
        self.assertEqual(-1, _cmp_options(KhQh, AhKh))
        self.assertEqual(-1, _cmp_options(KhQh, KsKh))
        self.assertEqual(-1, _cmp_options(KhQh, KhKc))
        self.assertEqual(1, _cmp_options(AhKh, KhQh))
        self.assertEqual(1, _cmp_options(AhKh, KsKh))
        self.assertEqual(1, _cmp_options(AhKh, KhKc))
        self.assertEqual(1, _cmp_options(KsKh, KhQh))
        self.assertEqual(-1, _cmp_options(KsKh, AhKh))
        self.assertEqual(1, _cmp_options(KsKh, KhKc))
        self.assertEqual(1, _cmp_options(KhKc, KhQh))
        self.assertEqual(-1, _cmp_options(KhKc, AhKh))
        self.assertEqual(-1, _cmp_options(KhKc, KsKh))
    
    def test_range_action_fits(self):
        # will test that:
        # - hand in original but not action should fail
        # - hand not in original but in action should fail
        # - hand in two or more ranges should fail
        # - raise size within band should succeed
        # - raise size outside band should fail
        # - should work the same with weights as without
        range_original = HandRange("AA(5),22,72o")
        range_AA = HandRange("AA(5)")
        range_KK = HandRange("KK")
        range_22 = HandRange("22")
        range_72o = HandRange("72o")
        range_22_72o = HandRange("22,72o")
        range_AA_22 = HandRange("AA(5),22")
        range_empty = HandRange("nothing")
        range_22_weighted = HandRange("22(3)")
        
        #options = [FoldOption(), CheckOption(), RaiseOption(2, 194)]
        options = ActionOptions(0, False, 2, 194)
        
        # invalid, raise size too small
        range_action = ActionDetails(range_72o, range_22, range_AA, 1)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "raise total must be between 2 and 194")

        # valid, minraise
        range_action = ActionDetails(range_72o, range_22, range_AA, 2)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)

        # valid, never folding when we can check
        range_action = ActionDetails(range_empty, range_22_72o, range_AA, 2)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)

        # valid, max raise
        range_action = ActionDetails(range_72o, range_22, range_AA, 194)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)

        # invalid, raise size too big
        range_action = ActionDetails(range_72o, range_22, range_AA, 195)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "raise total must be between 2 and 194")

        # invalid, AA in original but not action
        range_action = ActionDetails(range_72o, range_22, range_empty, 2)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "hand in original range but not in action ranges: AdAc")
        
        # invalid, KK in action but not original
        range_action = ActionDetails(range_72o, range_AA_22, range_KK, 2)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "hand in action ranges but not in original range: KdKc")

        # invalid, AA in multiple ranges
        range_action = ActionDetails(range_72o, range_AA_22, range_AA, 2)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "hand in multiple ranges: AdAc")
        
        #options = [FoldOption(), CallOption(10), RaiseOption(20, 194)]
        options = ActionOptions(10, True, 20, 194)
        
        # invalid, re-weighted
        range_action = ActionDetails(range_72o, range_22_weighted, range_AA, 20)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "weight changed from 1 to 3 for hand 2d2c")

        # valid, empty raise range (still has a raise size, which is okay)
        range_action = ActionDetails(range_AA, range_22_72o, range_empty, 20)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)

        # invalid, raise too big
        range_action = ActionDetails(range_72o, range_22, range_AA, 195)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "raise total must be between 20 and 194")

        #options = [FoldOption(), CallOption(194)]
        options = ActionOptions(194)
        
        # valid, 0 raise size is okay if empty raise range
        range_action = ActionDetails(range_22_72o, range_AA, range_empty, 0)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)
        
        # valid, 200 raise size is okay if empty raise range
        range_action = ActionDetails(range_22_72o, range_AA, range_empty, 200)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)

        # valid, has raise size but raise range is empty
        range_action = ActionDetails(range_original, range_empty, range_empty, 20)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertTrue(v)

        # invalid, has raise range
        range_action = ActionDetails(range_72o, range_22, range_AA, 20)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "there was a raising range, but raising was not an option")
        
        range_action = ActionDetails(range_72o, range_22, range_AA, 0)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "there was a raising range, but raising was not an option")

        # invalid, doesn't equal original
        range_action = ActionDetails(range_empty, range_AA, range_empty, 0)
        v, r = range_action_fits(range_action, options, range_original)
        self.assertFalse(v)
        self.assertEqual(r, "hand in original range but not in action ranges: 2d2c")

    def test_range_contains_hand(self):
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
    
    def test_range_action_to_action22(self):
        # will test:
        # - a fold,
        # - a check,
        # - a call,
        # - a raise,
        # - a case where hand is in no range (although invalid)
        # won't test:
        # - a case where hand is in all ranges (because the result is undefined)
        
        options_with_check = ActionOptions(0, False, 2, 196)  # [FoldOption(), CheckOption(), RaiseOption(2, 196)] 
        options_with_call = ActionOptions(10, True, 20, 196)  # [FoldOption(), CallOption(10), RaiseOption(20, 196)]
        options_without_raise = ActionOptions(196)  # [FoldOption(), CallOption(196)]

        range_AA = HandRange("AA")
        range_72o = HandRange("72o")
        range_22_72o = HandRange("22,72o")
        range_empty = HandRange("nothing")
        range_22_weighted = HandRange("22(3)")

        hand_72o = Card.many_from_text("7h2c")
        hand_22 = Card.many_from_text("2h2c")
        hand_AA = Card.many_from_text("AhAc")
        hand_72s = Card.many_from_text("7h2h")
        
        range_original = HandRange("AA,22,72o")

        action_with_raise = ActionDetails(range_72o, range_22_weighted, range_AA, 40)

        r, a = range_action_to_action2(action_with_raise, range_original, hand_72o, options_with_check)
        self.assertIsInstance(a, FoldAction)
        self.assertEqual("72o", r.description)
        r, a = range_action_to_action2(action_with_raise, range_original, hand_22, options_with_check)
        self.assertIsInstance(a, CheckAction)
        r, a = range_action_to_action2(action_with_raise, range_original, hand_AA, options_with_check)
        self.assertIsInstance(a, RaiseAction)
        self.assertEqual(a.total, 40)
        try:
            a = range_action_to_action2(action_with_raise, range_original, hand_72s, options_with_check)
            self.assertTrue(False)
        except ValueError:
            pass

        r, a = range_action_to_action2(action_with_raise, range_original, hand_72o, options_with_call)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_with_raise, range_original, hand_22, options_with_call)
        self.assertIsInstance(a, CallAction)
        self.assertEqual(a.cost, 10)
        r, a = range_action_to_action2(action_with_raise, range_original, hand_AA, options_with_call)
        self.assertIsInstance(a, RaiseAction)
        self.assertEqual(a.total, 40)
        try:
            a = range_action_to_action2(action_with_raise, range_original, hand_72s, options_with_call)
            self.assertTrue(False)
        except ValueError:
            pass

        action_without_raise = ActionDetails(range_22_72o, range_AA, range_empty, 0)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_72o, options_with_check)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_22, options_with_check)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_AA, options_with_check)
        self.assertIsInstance(a, CheckAction)
        try:
            a = range_action_to_action2(action_without_raise, range_original, hand_72s, options_with_check)
            self.assertTrue(False)
        except ValueError:
            pass

        r, a = range_action_to_action2(action_without_raise, range_original, hand_72o, options_with_call)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_22, options_with_call)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_AA, options_with_call)
        self.assertIsInstance(a, CallAction)
        self.assertEqual(a.cost, 10)
        try:
            a = range_action_to_action2(action_without_raise, range_original, hand_72s, options_with_call)
            self.assertTrue(False)
        except ValueError:
            pass

        r, a = range_action_to_action2(action_without_raise, range_original, hand_72o, options_without_raise)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_22, options_without_raise)
        self.assertIsInstance(a, FoldAction)
        r, a = range_action_to_action2(action_without_raise, range_original, hand_AA, options_without_raise)
        self.assertIsInstance(a, CallAction)
        self.assertEqual(a.cost, 196)
        try:
            r, a = range_action_to_action2(action_without_raise, range_original, hand_72s, options_without_raise)
            self.assertTrue(False)
        except ValueError:
            pass

if __name__ == '__main__':
    # 9.7s 20130205 (client-server)
    # 9.0s 20140102 (web)
    unittest.main()