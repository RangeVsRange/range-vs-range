"""
range-specific functionality
"""
import re
import random
import logging
from rvr.poker.cards import Card, RANK_MAP, SUIT_MAP, Rank,  \
    RANK_INVERT, Suit, SPADES, ACE, RANKS_HIGH_TO_LOW, RANKS_LOW_TO_HIGH
import unittest

# pylint:disable=C0103

ANYTHING = "anything"
NOTHING = "nothing"

ALL_RANKS = "23456789TJQKA"
ALL_SUITS = "cdhs"
# In future, I may allow defining entirely different ranges with
# separate probabilities. E.g.:
#    (AKo-AJo,KQo-KJo)50;(AKo-ATo,KQo-KTo)50
# is equivalent to:
#    AKo-AJo(2),KQo-KJo(2),ATo,KTo
# I've created RE_RANGE for this. It can be used by first splitting on ";",
# then applying the regex, or if there's no ";", surround the text with
# "(" and ")1" and try the regex.
RE_RANGE = re.compile(r"^\(([^()]*(\(\d+\)|))+\)(\d+)$")
RE_SUBRANGE = re.compile(r"^([^(]*)(\((\d+)\)|)$")
RE_TWOCARDS = re.compile(r"^([2-9TJQKA][shdc])(?!\1)([2-9TJQKA][shdc])$")
RE_PAIR = re.compile(r"^([2-9TJQKA])\1$")
RE_UNPAIRED = re.compile(r"^([2-9TJQKA])(?!\1)([2-9TJQKA])(o|s|)$")
RE_CLOSED_PAIRS = re.compile(r"^([2-9TJQKA])\1-([2-9TJQKA])\2$")
RE_OPEN_PAIRS = re.compile(r"^([2-9TJQKA])\1\+$")
RE_CLOSED_UNPAIRED = re.compile(r"^([2-9TJQKA])([2-9TJQKA])(o|s|)-"
                                 + r"\1([2-9TJQKA])\3$")
RE_OPEN_UNPAIRED = re.compile(r"^([2-9TJQKA])(?!\1)([2-9TJQKA])(o|s|)\+$")

def between(rank1, rank2):
    """
    Returns a list of all ranks between rank1 and rank2, inclusive.
    rank2 can be higher or lower or the same as rank1.
    """
    indeces = sorted([ALL_RANKS.find(rank1), ALL_RANKS.find(rank2)])
    if -1 in indeces:
        raise ValueError("Bad cards for between(): " + rank1 + "," + rank2)
    return [ALL_RANKS[i] for i in range(indeces[0], indeces[1] + 1)]

def weighted_choice(items):
    """items is a list in the form [(option, weight), ...]"""
    weight_total = sum((item[1] for item in items))
    invalids = [item[1] for item in items if item[1] < 0]
    if invalids:
        raise ValueError("weighted_choice() invalid weights: " + str(invalids))
    if weight_total < 1:
        raise ValueError("weighted_choice() needs at least"
                         "one positive weight")
    count = random.randint(0, weight_total - 1)
    for item, weight in items:
        if count < weight:
            return item
        count = count - weight
    return item

def subrange(part):
    """
    Interprets a weighted subrange, e.g. 'AQo+(3)' -> ('AQo+', 3)
    """
    match = RE_SUBRANGE.match(part)
    if not match:
        raise ValueError('Hand range part ' + part + ' is invalid')
    if match.group(3) is not None:
        weight = int(match.group(3))
        if weight <= 0:
            raise ValueError('Hand range part ' + part
                             + ' is invalid. Bad weight: '
                             + match.group(3))
    else:
        weight = 1
    cards = match.group(1)
    return (cards, weight)

def hands_in_subrange(cards):
    """
    Return a list of the specific hands in this subrange
    e.g. Kh7c - but not both Kh7c and 7cKh
    """
    # pylint:disable=R0911
    if cards == NOTHING:
        return []
    if cards == ANYTHING:
        return [rank1 + suit1 + rank2 + suit2
                for rank1 in ALL_RANKS
                for rank2 in ALL_RANKS
                for suit1 in ALL_SUITS
                for suit2 in ALL_SUITS
                if rank1 + suit1 < rank2 + suit2]
    # Check for two specific cards
    match = RE_TWOCARDS.match(cards)
    if match:
        card1, card2 = match.groups()
        return [card1 + card2]
    # Check for pair
    match = RE_PAIR.match(cards)
    if match:
        rank1, = match.groups()
        return [rank1 + suit1 + rank1 + suit2
                for suit1 in ALL_SUITS
                for suit2 in ALL_SUITS
                if suit1 < suit2]
    # Check for unpaired hand
    match = RE_UNPAIRED.match(cards)
    if match:
        rank1, rank2, qual = match.groups()
        return [rank1 + suit1 + rank2 + suit2
                for suit1 in ALL_SUITS
                for suit2 in ALL_SUITS
                if ((qual != "o" and suit1 == suit2) or
                    (qual != "s" and suit1 != suit2))]
    # Check for closed range of pairs
    match = RE_CLOSED_PAIRS.match(cards)
    if match:
        rank1, rank2 = match.groups()
        return [rank + suit1 + rank + suit2
                for suit1 in ALL_SUITS
                for suit2 in ALL_SUITS
                if suit1 < suit2
                for rank in between(rank1, rank2)]
    # Check for open range of pairs
    match = RE_OPEN_PAIRS.match(cards)
    if match:
        rank1, = match.groups()
        return [rank + suit1 + rank + suit2
                for rank in between("A", rank1)
                for suit1 in ALL_SUITS
                for suit2 in ALL_SUITS
                if suit1 < suit2]
    # Check for closed unpaired range, e.g. AKo-ATo
    match = RE_CLOSED_UNPAIRED.match(cards)
    if match:
        rank1, rank2, qual, rank3 = match.groups()
        if not rank1 in between(rank2, rank3):
            return [rank1 + suit1 + rank + suit2
                    for suit1 in ALL_SUITS
                    for suit2 in ALL_SUITS
                    if (qual != "o" and suit1 == suit2
                        or qual != "s" and suit1 != suit2)
                    for rank in between(rank2, rank3)]
    # Check for open unpaired range,
    # e.g 82o+ means 82o, 83o, 84o, 85o, 86o, 87o
    match = RE_OPEN_UNPAIRED.match(cards)
    if match:
        rank1, rank2, qual = match.groups()
        return [rank1 + suit1 + rank + suit2
                for suit1 in ALL_SUITS
                for suit2 in ALL_SUITS
                if (qual != "o" and suit1 == suit2
                    or qual != "s" and suit1 != suit2)
                for rank in between(rank1, rank2)[:-1]]
    raise ValueError('Hand range part ' + cards + ' is invalid')

def _order_option(o):
    """
    o is something like         ["Ah","Ad"] or ["Ad","Ah"] or ["Ks","Ad"]
    returns something more like ["Ah","Ad"] or ["Ah","Ad"] or ["Ad","Ks"]
    """
    m1, m2 = o
    r1 = RANK_MAP[m1[0]]
    r2 = RANK_MAP[m2[0]]
    rc = cmp(r1, r2)
    if rc < 0:
        return [m2, m1]
    if rc > 0:
        return [m1, m2]
    s1 = SUIT_MAP[m1[1]]
    s2 = SUIT_MAP[m2[1]]
    sc = cmp(s1, s2)
    if sc < 0:
        return [m2, m1]
    if sc > 0:
        return [m1, m2]
    raise RuntimeError("option is the same card twice: %s" % o)

def _odds_and_evens(mnemonics):
    """
    takes a list of things like "Ah","Kh" (each ordered)
    return a list of odds (e.g. "AhKh")
    and a list of evens (e.g. "AKo")
    """
    mnemonics = set([tuple(o) for o in mnemonics])  # remove duplicates
    potential = {}
    for m1, m2 in mnemonics:
        r1 = m1[0]
        s1 = m1[1]
        r2 = m2[0]
        s2 = m2[1]
        if r1 == r2:  # pair
            key = r1 * 2
        else:  # non-pair
            qualifier = "s" if s1 == s2 else "o"
            key = "%s%s%s" % (r1, r2, qualifier)
        if not potential.has_key(key):
            potential[key] = []
        potential[key].append([m1, m2])
    # potential is now mnemonics grouped by potential even
    # now we convert the true evens to evens, and leave the odds
    odds = []
    evens = []
    for key, value in potential.iteritems():
        if len(key) == 2:
            include = (len(value) == 6)
        elif key[2] == "s":
            include = (len(value) == 4)
        else:
            include = (len(value) == 12)
        if include:
            evens.append(key)
        else:
            odds.extend(value)
    return odds, evens

def _group_hands(preflop_hands):
    """
    takes a list of preflop hands (not individual combos)
    return a triple:
    - a list of pairs
    - a list of lists of suited hands, grouped by primary rank
    - a list of lists of offsuit hands, grouped by primary rank
    - e.g. 72o,73o,54o,54s,AA,22 -> [AA,22], [[54s]], [[72o,73o],[54o]]
    """
    pairs = []
    suited = {}  # maps primary to list
    offsuit = {}  # ditto
    for hand in preflop_hands:
        if len(hand) == 2:
            pairs.append(hand)
        else:
            target = suited if hand[2] == "s" else offsuit
            primary = hand[0]
            if not target.has_key(primary):
                target[primary] = []
            target[primary].append(hand)
    return pairs, suited.values(), offsuit.values()

def _colate_group(g):
    """
    takes a list of hands that share a primary rank
    may be pairs, suited, or offsuit
    returns a list of range parts, e.g. ["AA", "TT", "99"] -> ["AA", "TT-99"]
    """
    # pylint:disable=R0912
    # I know this code reads weird
    if not g:
        return []
    is_pairs = (g[0][0] == g[0][1])
    prefix = g[0][0]  # only means anything for non-pair hands
    # only means anything for non-pair hands
    primary = Rank.from_mnemonic(prefix)
    postfix = g[0][2:]  # only means anything for non-pair hands
    secondaries = [text[1] for text in g]
    ranks = [Rank.from_mnemonic(ch) for ch in secondaries]
    ranks.sort(reverse=True)
    all_ranks = RANKS_HIGH_TO_LOW[:]
    # so we have:
    # ranks =     [A, T, 9]
    # all_ranks = [A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2] 
    # and we want [A, T-9]
    # or as an interim result: [[A], [T, 9]] (we will call this list groups)
    groups = []
    # algorithm:
    # - run down all_ranks until we find a card that matches head of ranks
    # - add a new group, and add this rank to the current group
    # - keep running down while cards match, adding them to the current group
    # - when one doesn't match, set current group to None, as per we started
    current_group = None
    for rank in all_ranks:
        if not ranks:
            break
        if current_group is None:
            if rank == ranks[0]:
                current_group = [rank]
                del ranks[0]
                groups.append(current_group)
        else:
            if rank == ranks[0]:
                current_group.append(rank)
                del ranks[0]
            else:
                current_group = None
    results = []
    for group in groups:
        if len(group) == 1:
            if is_pairs:
                results.append(RANK_INVERT[group[0]] * 2)
            else:
                results.append("%s%s%s" % (prefix, RANK_INVERT[group[0]],
                                           postfix))
        else:
            if is_pairs:
                if group[0] == ACE:
                    results.append("%s+" % (RANK_INVERT[group[-1]] * 2))
                else:
                    results.append("-".join([RANK_INVERT[group[0]] * 2,
                                             RANK_INVERT[group[-1]] * 2]))
            else:
                # this now may be a "AJs-ATs" type hand or "ATs+" type hand
                # the condition is: the secondary of the second element is the
                # next lowest rank than the secondary of the first.
                if RANKS_LOW_TO_HIGH.index(primary)  \
                    - RANKS_LOW_TO_HIGH.index(group[0]) == 1:
                    results.append("%s%s%s+" %
                                   (prefix, RANK_INVERT[group[-1]], postfix))
                else:
                    results.append("%s%s%s-%s%s%s" %
                                   (prefix, RANK_INVERT[group[0]], postfix,
                                    prefix, RANK_INVERT[group[-1]], postfix))
    return results

def _unweighted_mnemonics_to_parts(mnemonics):
    """
    create description based on unweighted mnemonics
    
    input mnemonics should be a list of list of two card mnemonics, not necessarily in order (e.g. KhAh ok)
    return value is a list of sub-part descriptions (strings)
    """
    mnemonics = [_order_option(o) for o in mnemonics]
    # list of string, each is a subpart,
    # e.g. "AhKh", "AKs", "AKs-AQs", "AQs+", etc.
    results = []
    # step 1:
    # - group mnemonics that are the same preflop hand
    # - where the hand isn't full, move them to the result
    # - now all that remains is complete preflop hands (AA, AKs, 72o etc.)
    odds, preflop_hands = _odds_and_evens(mnemonics)
    results.extend(["".join(o) for o in odds])  # e.g. AhAd, AdKd, etc.
    # step 2:
    # - group into pairs, offsuits, suits
    # - for each list: pairs, Axs, Kxs, etc., Axo, Kxo, etc., perform step 3
    pairs, suited, offsuit = _group_hands(preflop_hands)
    # step 3:
    # - extract a sorted list of the second character
    # - scan through and group into contiguous ranges
    # - move each contiguous range to results
    results.extend(_colate_group(pairs))  # AA, TT-99, etc.
    for g in suited:
        results.extend(_colate_group(g))  # 72s, 86s-84s, etc.
    for g in offsuit:
        results.extend(_colate_group(g))  # AKo, AKo-AQo, etc.
    return results

def weighted_options_to_description(options):
    """
    convert options to a minimal description, a la PokerStove
    options is list of (hand, weight)
    where a hand is a set of two Card
    """
    # Okay, this isn't going to be easy.
    # First step: take weight out of the equation by grouping by weight and
    # then stripping weights and handling just the options for each group
    if not options:
        return NOTHING
    if set(options) == SET_ANYTHING_OPTIONS:
        return ANYTHING
    groups = {}
    for hand, weight in options:
        if not groups.has_key(weight):
            groups[weight] = []
        try:
            cards = list(hand)  # was set of two Card, now list of two Card
        except TypeError:
            pass
        groups[weight].append([cards[0].to_mnemonic(), cards[1].to_mnemonic()])
    parts = []
    for weight, group in groups.iteritems():
        for part in _unweighted_mnemonics_to_parts(group):
            if weight != 1:
                parts.append("%s(%d)" % (part, weight))
            else:
                parts.append(part)
    # sort them too, for standardisation
    def key_part(part):
        """
        returns a comparison key for a part
        """
        if part[1] in SUIT_MAP.keys():
            # odds
            is_pair = part[0] == part[2]
            is_suited = part[1] == part[3]
            key_rank1 = Rank.from_mnemonic(part[0])
            key_rank2 = Rank.from_mnemonic(part[2])
            key_suit1 = Suit.from_mnemonic(part[1])
            key_suit2 = Suit.from_mnemonic(part[3])
        else:
            # evens
            is_pair = part[0] == part[1]
            is_suited = len(part) > 2 and part[2] == "s"
            key_rank1 = Rank.from_mnemonic(part[0])
            key_rank2 = Rank.from_mnemonic(part[1])
            key_suit1 = SPADES # no way to compare, e.g. AA to AhAs
            key_suit2 = SPADES # ditto
        return [is_pair, is_suited, key_rank1, key_rank2, key_suit1, key_suit2]
    parts.sort(key=key_part, reverse=True)
    return ",".join(parts)

def remove_board_from_range(hand_range, board):
    """
    returns a new hand_range, with no options that contain any hand in board
    """
    options = hand_range.generate_options(board)
    description = weighted_options_to_description(options)
    return HandRange(description)

def _cmp_options(a, b):
    """
    compare unweighted options
    """
    return cmp(sorted(a), sorted(b))

def _cmp_weighted_options(a, b):
    """
    compare weighted options
    """
    return _cmp_options(a[0], b[0]) or cmp(a[1], b[1])

def reweight(new, old):
    """
    Give everything in new the weight it hand in old
    New and old are HandRange objects
    """
    # do this based on options for both
    # iterate through all options of new and set the weight of each to the
    # weight of the corresponding option in old
    options_new = new.generate_options()
    options_old = old.generate_options()
    options_new.sort(cmp=_cmp_weighted_options)
    options_old.sort(cmp=_cmp_weighted_options)
    results = []
    for o in options_old:
        if not options_new:
            break
        # o is of form (set([Card(),Card()], weight)
        if o[0] == options_new[0][0]:
            n = options_new.pop(0)
            results.append((n[0], o[1]))
    if options_new:
        raise RuntimeError("reweight: option in new that isn't in old: %s" %
                           str(options_new[0]))
    description = weighted_options_to_description(results)
    return HandRange(description)

class HandRange(object):
    """
    Represents a hand range! (Texas Hold'em only.)
    """
    def __init__(self, description, is_strict=True):
        self.description = str(description)
        self.is_strict = is_strict
        if description == NOTHING:
            self.subranges = []
        else:
            self.subranges = [subrange(part)
                              for part in self.description.split(',')]

    def __repr__(self):
        return "HandRange(description=%r)" % self.description
    
    def is_empty(self):
        """
        Is this hand range nothing? E.g. when facing an all in, your raising
        range will be nothing.
        """
        return not self.subranges
    
    def polarised(self, board = None):
        """
        Returns an unweighted equivalent of this hand range.
        """
        original = self.generate_options(board)
        maxweight = max([o[1] for o in original])
        results = []
        for o in original:
            if random.randrange(0, maxweight) < o[1]:
                results.append((o[0], 1))
        return HandRange(weighted_options_to_description(results))

    def generate_options(self, board=None):
        """
        option is a list of (hand, weight)
        """
        excluded_cards = board or []
        excluded_mnemonics = [card.to_mnemonic() for card in excluded_cards]
        # it's really nice for this to be a list, for self.polarise_weights
        options = []
        for part, weight in self.subranges:
            option_mnemonics = hands_in_subrange(part)  # list of e.g. "AhKh"
            not_excluded = lambda hand: (hand[0:2] not in excluded_mnemonics
                and hand[2:4] not in excluded_mnemonics)
            option_mnemonics = [o for o in option_mnemonics if not_excluded(o)]
            hands = [frozenset(Card.many_from_text(txt))
                     for txt in option_mnemonics]
            options.extend([(hand, weight) for hand in hands])
        if self.is_strict:
            return options
        else:
            return list(set(options))
    
    def generate_options_unweighted(self, board=None):
        """
        just hand, no weight
        error if weights are not all the same
        """
        excluded_cards = board or []
        excluded_mnemonics = [card.to_mnemonic() for card in excluded_cards]
        # it's really nice for this to be a list, for self.polarise_weights
        options = []
        first_weight = None
        for part, weight in self.subranges:
            if first_weight == None:
                first_weight = weight
            elif weight != first_weight:
                raise ValueError("range is not evenly weighted")
            option_mnemonics = hands_in_subrange(part)  # list of e.g. "AhKh"
            not_excluded = lambda hand: (hand[0:2] not in excluded_mnemonics
                and hand[2:4] not in excluded_mnemonics)
            option_mnemonics = [o for o in option_mnemonics if not_excluded(o)]
            hands = [frozenset(Card.many_from_text(txt))
                     for txt in option_mnemonics]
            options.extend(hands)
        if self.is_strict:
            return options
        else:
            return list(set(options))
        
    def generate_hand(self, board = None):
        """
        Generate a pair of pocket cards for Holdem, based on self.description
        and excluding board cards.
        
        Return hand that is a list of two Card
        
        Options are generated by this function, and not maintained, because:
         - ranges are defined without knowledge of board cards
         - we don't want to transmit options over the wire
        """
        options = self.generate_options(board)
        if not options:
            raise ValueError("No valid options to generate hand from")
        pick = list(weighted_choice(options))
        random.shuffle(pick)
        return pick
    
    def subtract(self, other):
        """
        Return a HandRange with all options from self that are not options in
        other.
        
        other should also be a HandRange. 
        """
        mine = self.generate_options()
        other = other.generate_options()
        # TODO: REVISIT: there's probably a more efficient way to do this.
        # Also note that this will only remove options with the same weight.
        for option in other:
            if option in mine:
                mine.remove(option)
        return HandRange(weighted_options_to_description(mine))
        
    def validate(self):
        """
        Check that this HandRange's description is valid.
        
        Throw ValueError if not.
        """
        options = self.generate_options()
        hands = [hand for hand, _weight in options]
        if len(hands) != len(set(hands)):
            raise ValueError("Duplicate hands in range: %s" % self.description)
    
    def is_valid(self):
        """
        Check that this HandRange's description is valid.
        
        Return True or False. Call validate() for more detailed error.
        """
        try:
            self.validate()
        except ValueError:
            return False
        return True

class IncompatibleRangesError(RuntimeError):
    """
    Occur when players in a game have incompatible ranges. E.g. my range is
    'AhAs' and your range is 'AcAs'.
    """
    pass

def deal_from_ranges(range_map, board):
    """
    takes a dict mapping arbitrary key to range
    return a dict mapping same keys to dealt hands from those ranges
    """
    count = 0
    while True:
        result = {k: r.generate_hand(board) for k, r in range_map.iteritems()}
        all_cards = [card for hand in result.values() for card in hand]
        all_cards.extend(board)
        if len(all_cards) == len(set(all_cards)):
            return result
        count += 1
        if count == 1000:
            logging.warning(
                "apparently incompatible set of ranges: %r (board is %r)",
                range_map, board)
        if count > 10000:
            raise IncompatibleRangesError(
                "apparently incompatible set of ranges: %r (board is %r)" %
                (range_map, board))

SET_ANYTHING_OPTIONS = set(HandRange(ANYTHING).generate_options())

class Test(unittest.TestCase):
    """
    Unit test class
    """
    # pylint:disable = R0904
    def test_order_option(self):
        """ Test _order_option """
        self.assertEqual(_order_option(["Ah", "Ad"]), ["Ah", "Ad"])
        self.assertEqual(_order_option(["Ad", "Ah"]), ["Ah", "Ad"])
        self.assertEqual(_order_option(["Ad", "Ks"]), ["Ad", "Ks"])
        self.assertEqual(_order_option(["Ks", "Ad"]), ["Ad", "Ks"])
        self.assertEqual(_order_option(["Ks", "As"]), ["As", "Ks"])
        self.assertEqual(_order_option(["As", "Ks"]), ["As", "Ks"])
        
    def test_create_group(self):
        """ Test _colate_group """
        self.assertEqual(_colate_group(["88", "TT", "AA", "99"]),
                         ["AA", "TT-88"])
        self.assertEqual(_colate_group(["A8", "AT", "AK", "A9"]),
                         ["AK", "AT-A8"])
        self.assertEqual(_colate_group(["A8s", "ATs", "AKs", "A9s"]),
                         ["AKs", "ATs-A8s"])
        self.assertEqual(_colate_group(["A8o", "ATo", "AKo", "A9o"]),
                         ["AKo", "ATo-A8o"])
        
    def test_unweighted_options_to_description(self):
        """ Test _unweighted_mnemonics_to_parts """
        options = [["Ah","Kh"], ["Kd","Ad"], ["Ac","Kc"], ["Ks","As"],
                   ["As","Ad"],
                   ["Kh","Kc"], ["Kc","Ks"], ["Ks","Kd"], ["Kd","Kh"],
                    ["Kh","Ks"], ["Kd","Kc"],
                   ["7h","2c"], ["7h","2s"], ["7h","2d"], ["7c","2h"],
                    ["7c","2s"], ["7c","2d"], ["7s","2h"], ["7s","2c"],
                    ["7s","2d"], ["7d","2h"], ["7d","2c"], ["2s","7d"]]
        parts = ["AKs", "AsAd", "KK", "72o"]
        self.assertEqual(set(_unweighted_mnemonics_to_parts(options)),
                         set(parts))
        
    def test_weighted_options_to_description(self):
        """ Test _weighted_options_to_description """
        valid = ["KK+(2),99,5s5h,5s5c,5h5c,5d5c,44,22,A4s,KJs,K8s-K6s," +
                    "Ks4s,Kh4h,Q4s,J4s,T4s+,94s,84s,74s,64s,54s,Q9o,T7o,Ts6h," +
                    "Ts6d,Ts6c,Th6s,Th6d,Th6c,Td6s,Td6c,Tc6s,Tc6h,T5o-T2o," +
                    "42o+,32o",
                 "AsKs(2),AhKh(2),AdKd,AcKc(2)"]
        for v in valid:
            handrange = HandRange(v)
            options = handrange.generate_options()
            final = weighted_options_to_description(options)
            self.assertEqual(v, final)
        convert = {
            "KK(1)": "KK",
            "AsKs(2),KcAc(2),KhAh(2),AdKd(2)": "AKs(2)",
            "AsKs(2),KcAc(2),KhAh(2),AdKd(1)": "AsKs(2),AhKh(2),AdKd,AcKc(2)"}
        for k, v in convert.iteritems():
            handrange = HandRange(k)
            options = handrange.generate_options()
            final = weighted_options_to_description(options)
            self.assertEqual(v, final, "expected '%s', got '%s" % (v, final))
    
    def test_generate_options_unweighted(self):
        """ Test HandRange.generate_options_unweighted """
        valid = HandRange("AA(3),AKo(3)")
        invalid = HandRange("AA(3),AKo(2)")
        options = valid.generate_options_unweighted()
        self.assertEqual(len(options), 18)
        try:
            options = invalid.generate_options_unweighted()
            self.assert_(False, "should raise ValueError")
        except ValueError as _ex:
            pass
    
    def test_reweight(self):
        """ Test reweight """
        # tuples of old, new, result
        inputs = [("AA", "AA", "AA"),
                  ("AA,KK", "KK", "KK"),
                  ("AA", "AA(2)", "AA"),
                  ("AA(2),KK(3)", "KK(2)", "KK(3)"),
                  ("AsKs(2),AhKh(3),AdKd(2),AcKc(2),72o(2)", "AKs",
                   "AsKs(2),AhKh(3),AdKd(2),AcKc(2)"),
                  ("AKs,72o", "AsKs(2),AhKh(3),AdKd(2),AcKc(2)", "AKs")]
        for old, new, result in inputs:
            self.assertEqual(reweight(HandRange(new),
                                      HandRange(old)).description, result)
    
    def test_subtract(self):
        """ Test subtract """
        data = [("anything", "nothing", "anything"),
                ("nothing", "nothing", "nothing"),
                ("anything", "anything", "nothing"),
                ("nothing", "anything", "nothing"),
                ("22+", "33", "44+,22"),
                ("33+", "33-22", "44+")]
        for minuend, subtrahend, difference in data:
            result = HandRange(minuend).subtract(HandRange(subtrahend))
            self.assertEqual(result.description, difference)

if __name__ == '__main__':
    # 0.035s in 20130205 (Eclipse 3.6.1)
    # 0.035s on 20131230 (Eclipse 4.2.2)
    unittest.main()
