cdef extern from "stdlib.h":
    ctypedef unsigned long size_t
    void *malloc(size_t n_bytes)
    void free(void *ptr)

import cython
import time

cdef int _wh_seed_x, _wh_seed_y, _wh_seed_z

cdef void wh_init(cython.ulong seed):
    """Initialize internal state from hashable object.
    
    None or no argument seeds from current time or from an operating
    system specific randomness source if available.
    
    If a is not None or an int or long, hash(a) is used instead.
    
    If a is an int or long, a is used directly.  Distinct values between
    0 and 27814431486575L inclusive are guaranteed to yield distinct
    internal states (this guarantee is specific to the default
    Wichmann-Hill generator).
    """
    global _wh_seed_x, _wh_seed_y, _wh_seed_z
    # arbitrarily, statically chosen for this eval7 version.
    cdef cython.ulong a = seed
    _wh_seed_x = a % 30268; a = a / 30268 
    _wh_seed_y = a % 30306; a = a / 30306
    _wh_seed_z = a % 30322

cdef cython.double wh_random():
    """Get the next random number in the range [0.0, 1.0)."""
    # Wichman-Hill random number generator.
    #
    # Wichmann, B. A. & Hill, I. D. (1982)
    # Algorithm AS 183:
    # An efficient and portable pseudo-random number generator
    # Applied Statistics 31 (1982) 188-190
    #
    # see also:
    #        Correction to Algorithm AS 183
    #        Applied Statistics 33 (1984) 123
    #
    #        McLeod, A. I. (1985)
    #        A remark on Algorithm AS 183
    #        Applied Statistics 34 (1985),198-200
    global _wh_seed_x, _wh_seed_y, _wh_seed_z
    # This part is thread-unsafe:
    # BEGIN CRITICAL SECTION
    _wh_seed_x = (171 * _wh_seed_x) % 30269
    _wh_seed_y = (172 * _wh_seed_y) % 30307
    _wh_seed_z = (170 * _wh_seed_z) % 30323
    # END CRITICAL SECTION
    # Note:  on a platform using IEEE-754 double arithmetic, this can
    # never return 0.0 (asserted by Tim; proof too long for a comment).
    return (_wh_seed_x/30269.0 + _wh_seed_y/30307.0 + _wh_seed_z/30323.0) % 1.0

cdef cython.int wh_randint(cython.int range):
    # wh_random() is 0.0 < x <= 1.0
    # 1 - wh_random() is 0.0 <= x < 1.0
    # (1 - wh_random()) * range is 0.0 <= x < range
    # <cython.int>((1 - wh_random()) * range) is a fairly evenly distributed integer 0 <= x < range
    return <cython.int>((1 - wh_random()) * range)

def py_wh_randint(range):
    return wh_randint(range)

wh_init(time.time())  # Python code, but done only once

# https://groups.google.com/d/msg/cython-users/cq0y7A4GEYI/COpObK6kp3YJ
cdef cython.ushort n_bits_table[8192]
cdef cython.ushort straight_table[8192]
cdef cython.uint top_five_cards_table[8192]
cdef cython.ushort top_card_table[8192]
cdef cython.ulonglong card_masks_table[52]
cdef cython.char *singular_table[52]
cdef cython.char *plural_table[52]

def load_tables(py_n_bits_table, py_straight_table, py_top_five_cards_table, py_top_card_table, py_card_masks_table):
    for i in range(8192):
        n_bits_table[i] = <cython.ushort>py_n_bits_table[i]
        straight_table[i] = <cython.ushort>py_straight_table[i]
        top_five_cards_table[i] = <cython.uint>py_top_five_cards_table[i]
        top_card_table[i] = <cython.ushort>py_top_card_table[i]
    for i in range(52):
        card_masks_table[i] = <cython.ulonglong>py_card_masks_table[i]

def init_card_names():
    cdef cython.char **src_s = [
        "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace",
        "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace",
        "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace",
        "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace",
    ]
    cdef cython.char **src_p = [
        "Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights", "Nines", "Tens", "Jacks", "Queens", "Kings", "Aces",
        "Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights", "Nines", "Tens", "Jacks", "Queens", "Kings", "Aces",
        "Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights", "Nines", "Tens", "Jacks", "Queens", "Kings", "Aces",
        "Twos", "Threes", "Fours", "Fives", "Sixes", "Sevens", "Eights", "Nines", "Tens", "Jacks", "Queens", "Kings", "Aces"
    ]
    for i in range(52):
        singular_table[i] = src_s[i]
        plural_table[i] = src_p[i]

cdef cython.int Spades = 3
cdef cython.int Hearts = 2
cdef cython.int Diamonds = 1
cdef cython.int Clubs = 0

cdef cython.int SPADE_OFFSET = 13 * Spades
cdef cython.int CLUB_OFFSET = 13 * Clubs
cdef cython.int DIAMOND_OFFSET = 13 * Diamonds
cdef cython.int HEART_OFFSET = 13 * Hearts

cdef cython.int HANDTYPE_SHIFT = 24
cdef cython.int TOP_CARD_SHIFT = 16
cdef cython.uint TOP_CARD_MASK = 0x000F0000
cdef cython.int SECOND_CARD_SHIFT = 12
cdef cython.uint SECOND_CARD_MASK = 0x0000F000
cdef cython.int THIRD_CARD_SHIFT = 8
cdef cython.int FOURTH_CARD_SHIFT = 4
cdef cython.int FIFTH_CARD_SHIFT = 0
cdef cython.uint FIFTH_CARD_MASK = 0x0000000F
cdef cython.int CARD_WIDTH = 4
cdef cython.uint CARD_MASK = 0x0F
cdef cython.int NUMBER_OF_CARDS = 52

cdef cython.uint HANDTYPE_STRAIGHTFLUSH = (<cython.uint>8)
cdef cython.uint HANDTYPE_FOUR_OF_A_KIND = (<cython.uint>7)
cdef cython.uint HANDTYPE_FULLHOUSE = (<cython.uint>6)
cdef cython.uint HANDTYPE_FLUSH = (<cython.uint>5)
cdef cython.uint HANDTYPE_STRAIGHT = (<cython.uint>4)
cdef cython.uint HANDTYPE_TRIPS = (<cython.uint>3)
cdef cython.uint HANDTYPE_TWOPAIR = (<cython.uint>2)
cdef cython.uint HANDTYPE_PAIR = (<cython.uint>1)
cdef cython.uint HANDTYPE_HIGHCARD = (<cython.uint>0)

cdef cython.uint HANDTYPE_VALUE_STRAIGHTFLUSH = ((<cython.uint>8) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_FOUR_OF_A_KIND = ((<cython.uint>7) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_FULLHOUSE = ((<cython.uint>6) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_FLUSH = ((<cython.uint>5) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_STRAIGHT = ((<cython.uint>4) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_TRIPS = ((<cython.uint>3) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_TWOPAIR = ((<cython.uint>2) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_PAIR = ((<cython.uint>1) << HANDTYPE_SHIFT)
cdef cython.uint HANDTYPE_VALUE_HIGHCARD = ((<cython.uint>0) << HANDTYPE_SHIFT)

cdef cython.uint evaluate(cython.ulonglong cards):
    """
    7-card evaluation function based on Keith Rule's port of PokerEval.
    Pure Python: 20000 calls in 0.176 seconds (113636 calls/sec)
    Cython: 20000 calls in 0.044 seconds (454545 calls/sec)
    """
    cdef cython.uint retval = 0, four_mask, three_mask, two_mask
    
    cdef cython.uint sc = <cython.uint>((cards >> (CLUB_OFFSET)) & 0x1fffUL)
    cdef cython.uint sd = <cython.uint>((cards >> (DIAMOND_OFFSET)) & 0x1fffUL)
    cdef cython.uint sh = <cython.uint>((cards >> (HEART_OFFSET)) & 0x1fffUL)
    cdef cython.uint ss = <cython.uint>((cards >> (SPADE_OFFSET)) & 0x1fffUL)
    
    cdef cython.uint ranks = sc | sd | sh | ss
    cdef cython.uint n_ranks = n_bits_table[ranks]
    cdef cython.uint n_dups = <cython.uint>(7 - n_ranks)
    
    cdef cython.uint st, t, kickers, second, tc, top
    
    if n_ranks >= 5:
        if n_bits_table[ss] >= 5:
            if straight_table[ss] != 0:
                return HANDTYPE_VALUE_STRAIGHTFLUSH + <cython.uint>(straight_table[ss] << TOP_CARD_SHIFT)
            else:
                retval = HANDTYPE_VALUE_FLUSH + top_five_cards_table[ss]
        elif n_bits_table[sc] >= 5:
            if straight_table[sc] != 0:
                return HANDTYPE_VALUE_STRAIGHTFLUSH + <cython.uint>(straight_table[sc] << TOP_CARD_SHIFT)
            else:
                retval = HANDTYPE_VALUE_FLUSH + top_five_cards_table[sc]
        elif n_bits_table[sd] >= 5:
            if straight_table[sd] != 0:
                return HANDTYPE_VALUE_STRAIGHTFLUSH + <cython.uint>(straight_table[sd] << TOP_CARD_SHIFT)
            else:
                retval = HANDTYPE_VALUE_FLUSH + top_five_cards_table[sd]
        elif n_bits_table[sh] >= 5:
            if straight_table[sh] != 0:
                return HANDTYPE_VALUE_STRAIGHTFLUSH + <cython.uint>(straight_table[sh] << TOP_CARD_SHIFT)
            else:
                retval = HANDTYPE_VALUE_FLUSH + top_five_cards_table[sh]
        else:
            st = straight_table[ranks]
            if st != 0:
                retval = HANDTYPE_VALUE_STRAIGHT + (st << TOP_CARD_SHIFT)

        if retval != 0 and n_dups < 3:
            return retval

    if n_dups == 0:
        return HANDTYPE_VALUE_HIGHCARD + top_five_cards_table[ranks]
    elif n_dups == 1:
        two_mask = ranks ^ (sc ^ sd ^ sh ^ ss)
        retval = <cython.uint>(HANDTYPE_VALUE_PAIR + (top_card_table[two_mask] << TOP_CARD_SHIFT))
        t = ranks ^ two_mask
        kickers = (top_five_cards_table[t] >> CARD_WIDTH) & ~FIFTH_CARD_MASK
        retval += kickers
        return retval
    elif n_dups == 2:
        two_mask = ranks ^ (sc ^ sd ^ sh ^ ss)
        if two_mask != 0:
            t = ranks ^ two_mask
            retval = <cython.uint>(HANDTYPE_VALUE_TWOPAIR
                + (top_five_cards_table[two_mask]
                & (TOP_CARD_MASK | SECOND_CARD_MASK))
                + (top_card_table[t] << THIRD_CARD_SHIFT))
            return retval
        else:
            three_mask = ((sc & sd) | (sh & ss)) & ((sc & sh) | (sd & ss))
            retval = <cython.uint>(HANDTYPE_VALUE_TRIPS + (top_card_table[three_mask] << TOP_CARD_SHIFT))
            t = ranks ^ three_mask
            second = top_card_table[t]
            retval += (second << SECOND_CARD_SHIFT)
            t ^= (1U << <cython.int>second)
            retval += <cython.uint>(top_card_table[t] << THIRD_CARD_SHIFT)
            return retval
    else:
        four_mask = sh & sd & sc & ss
        if four_mask != 0:
            tc = top_card_table[four_mask]
            retval = <cython.uint>(HANDTYPE_VALUE_FOUR_OF_A_KIND
                + (tc << TOP_CARD_SHIFT)
                + ((top_card_table[ranks ^ (1U << <cython.int>tc)]) << SECOND_CARD_SHIFT))
            return retval
        two_mask = ranks ^ (sc ^ sd ^ sh ^ ss)
        if n_bits_table[two_mask] != n_dups:
            three_mask = ((sc & sd) | (sh & ss)) & ((sc & sh) | (sd & ss))
            retval = HANDTYPE_VALUE_FULLHOUSE
            tc = top_card_table[three_mask]
            retval += (tc << TOP_CARD_SHIFT)
            t = (two_mask | three_mask) ^ (1U << <cython.int>tc)
            retval += <cython.uint>(top_card_table[t] << SECOND_CARD_SHIFT)
            return retval
        if retval != 0:
            return retval
        else:
            retval = HANDTYPE_VALUE_TWOPAIR
            top = top_card_table[two_mask]
            retval += (top << TOP_CARD_SHIFT)
            second = top_card_table[two_mask ^ (1 << <cython.int>top)]
            retval += (second << SECOND_CARD_SHIFT)
            retval += <cython.uint>((top_card_table[ranks ^ (1U << <cython.int>top) ^ (1 << <cython.int>second)]) << THIRD_CARD_SHIFT)
            return retval

cdef cython.ulonglong hand_to_mask(py_hand):
    cards = list(py_hand)
    card0 = cards[0]
    card1 = cards[1]
    mask0 = card0.to_mask()
    mask1 = card1.to_mask()
    return mask0 | mask1

def py_hand_to_mask(py_hand):
    return hand_to_mask(py_hand)
    
cdef cython.ulonglong many_to_mask(py_board):
    cdef cython.ulonglong board = 0
    for py_card in py_board:
        board |= py_card.to_mask()
    return board

def py_evaluate(py_cards):
    cdef cython.ulonglong mask = many_to_mask(py_cards)
    cdef cython.uint strength = evaluate(mask)
    return strength

cdef cython.uint filter_options(cython.ulonglong *source, cython.ulonglong *target, cython.uint num_options, cython.ulonglong dead):
    """
    Removes all options that share a dead card
    Returns total number of options kept
    """
    cdef cython.ulonglong options
    cdef cython.uint total = 0
    for 0 <= s < num_options:
        option = source[s]
        if option & dead == 0:
            target[total] = option
            total += 1
    return total

cdef cython.ulonglong deal_card(cython.ulonglong dead):
    cdef cython.uint cardex
    cdef cython.ulonglong card
    while True:
        cardex = wh_randint(52)
        card = card_masks_table[cardex]
        if dead & card == 0:
            return card

cdef cython.float hand_vs_range_monte_carlo(cython.ulonglong hand,
                                            cython.ulonglong *options, cython.int num_options,
                                            cython.ulonglong start_board, cython.int num_board,
                                            cython.int iterations):
    """
    Return equity of hand vs range.
    Note that only unweighted ranges are supported.
    Note that only heads-up evaluations are supported.
    
    hand is a two-card hand mask
    options is an array of num_options options for opponent's two-card hand
    board is a hand mask of the board; num_board says how many cards are in it
    """
    cdef cython.uint count = 0
    cdef cython.uint option_index = 0
    cdef cython.ulonglong option
    cdef cython.ulonglong dealt
    cdef cython.uint hero
    cdef cython.uint villain
    cdef cython.ulonglong board
    for 0 <= i < iterations:
        # choose an option for opponent's hand
        option = options[option_index]
        option_index += 1
        if option_index >= num_options:
            option_index = 0
        # deal the rest of the board
        dealt = hand | option
        board = start_board
        for j in range(5 - num_board):
            board |= deal_card(board | dealt)
        hero = evaluate(board | hand)
        villain = evaluate(board | option)
        if hero > villain:
            count += 2
        elif hero == villain:
            count += 1
    return 0.5 * <cython.double>count / <cython.double>iterations

def py_hand_vs_range_monte_carlo(py_hand, py_villain, py_board, py_iterations):
    py_options = py_villain.generate_options()
    cdef cython.ulonglong hand = hand_to_mask(py_hand)
    cdef cython.int num_options = len(py_options)
    cdef cython.ulonglong *options = <cython.ulonglong*>malloc(sizeof(cython.ulonglong) * num_options)
    cdef cython.ulonglong start_board = many_to_mask(py_board)
    cdef cython.int num_board = len(py_board)
    cdef cython.int iterations = py_iterations
    cdef cython.float equity  # DuplicatedSignature
    cdef cython.ulonglong mask
    for index, option in enumerate(py_options):
        options[index] = hand_to_mask(list(option))
        num_options
    num_options = filter_options(options, options, num_options, start_board | hand)
    equity = hand_vs_range_monte_carlo(hand, options, num_options, start_board, num_board, iterations)
    free(options)
    return equity

cdef cython.float hand_vs_range_exact(cython.ulonglong hand,
                                      cython.ulonglong *options, cython.int num_options,
                                      cython.ulonglong complete_board):
    # I think it might be okay (good) not to randomly sample options, but
    # instead to evenly sample them. (Still with a randomly sampled board, of
    # course.) This'll make the results converge faster. We can only do this
    # because we know that every option is equally likely (unlike, for example,
    # range vs. range equity calculation).
    cdef cython.uint wins = 0
    cdef cython.uint ties = 0
    cdef cython.ulonglong option  # @DuplicatedSignature
    cdef cython.uint hero = evaluate(complete_board | hand)
    cdef cython.uint villain  # @DuplicatedSignature
    for i in range(num_options):
        # choose an option for opponent's hand
        option = options[i]
        villain = evaluate(complete_board | option)
        if hero > villain:
            wins += 1
        elif hero == villain:
            ties += 1
    return (wins + 0.5 * ties) / <cython.double>num_options

def py_hand_vs_range_exact(py_hand, py_villain, py_board):
    py_options = py_villain.generate_options()
    cdef cython.ulonglong hand = hand_to_mask(py_hand)  # @DuplicatedSignature
    cdef cython.int num_options = len(py_options)  # @DuplicatedSignature
    cdef cython.ulonglong *options = <cython.ulonglong*>malloc(sizeof(cython.ulonglong) * num_options)  # @DuplicatedSignature
    cdef cython.ulonglong complete_board = many_to_mask(py_board)
    cdef cython.float equity
    cdef cython.ulonglong mask  # @DuplicatedSignature
    cdef cython.ulonglong dead = complete_board | hand  
    for index, option in enumerate(py_options):
        options[index] = hand_to_mask(list(option))
        num_options
    num_options = filter_options(options, options, num_options, complete_board | hand)
    equity = hand_vs_range_exact(hand, options, num_options, complete_board)
    free(options)
    return equity

cdef void all_hands_vs_range(cython.ulonglong *hands, cython.uint num_hands,
                                    cython.ulonglong *all_options, cython.uint num_options,
                                    cython.ulonglong board, cython.uint num_board,
                                    cython.long iterations,cython.float *result):
    """
    Return equity of each hand, versus range.
    Note that only unweighted ranges are supported.
    Note that only heads-up evaluations are supported.
    
    hands are two-card hand mask; num_hands is how many
    options is an array of num_options options for opponent's two-card hand
    board is a hand mask of the board; num_board says how many cards are in it
    iterations is iterations to perform
    result is a preallocated array in which to put results (order corresponds
        to order of hands)
    """
    cdef cython.float equity  # @DuplicatedSignature
    cdef cython.ulonglong hand
    cdef cython.uint current_num_options
    cdef cython.ulonglong *options = <cython.ulonglong *>malloc(sizeof(cython.ulonglong) * num_options)
    for 0 <= i < num_hands:
        hand = hands[i]
        # Have to do card removal effects at this point - on a hand by hand basis.
        current_num_options = filter_options(all_options, options, num_options, board | hand)
        if current_num_options == 0:
            result[i] = -1  # Villain's range makes this hand impossible for hero.
            continue
        if num_board == 5 and current_num_options <= iterations:
            equity = hand_vs_range_exact(hand, options, current_num_options, board)
        else:
            equity = hand_vs_range_monte_carlo(hand, options, current_num_options, board, num_board, iterations)
        result[i] = equity
    free(options)
        
def py_all_hands_vs_range(py_hero, py_villain, py_board, py_iterations):
    """
    Return dict mapping hero's hand to equity against villain's range on this board.
    
    hero and villain are ranges.
    board is a list of cards.
    
    TODO: consider randomising the order of opponent's hands at this point
    so that the evenly distributed sampling in hand_vs_range is unbiased.
    """
    hero_hands = py_hero.generate_options(py_board)
    villain_hands = py_villain.generate_options(py_board)
    cdef cython.ulonglong *hands = <cython.ulonglong *>malloc(sizeof(cython.ulonglong) * len(hero_hands))
    cdef cython.uint num_hands
    cdef cython.ulonglong *options = <cython.ulonglong *>malloc(sizeof(cython.ulonglong) * len(villain_hands))
    cdef cython.uint num_options
    cdef cython.ulonglong board  # @DuplicatedSignature
    cdef cython.uint num_board
    cdef cython.long iterations = <cython.long>py_iterations
    cdef cython.float *result = <cython.float *>malloc(sizeof(cython.float) * len(hero_hands))
    
    num_hands = 0
    for hand in hero_hands:
        hands[num_hands] = hand_to_mask(hand)
        num_hands += 1
        
    num_options = 0
    for option in villain_hands:
        options[num_options] = hand_to_mask(option)
        num_options += 1
        
    board = many_to_mask(py_board)
    num_board = len(py_board)

    all_hands_vs_range(hands, num_hands, options, num_options, board, num_board, iterations, result)
    
    py_result = {}
    for i in range(num_hands):
        if result[i] != -1:
            py_result[hero_hands[i]] = result[i]
    
    free(hands)
    free(options)
    free(result)
    
    return py_result

cdef cython.uint hand_type(cython.uint hand_value):
    return hand_value >> HANDTYPE_SHIFT

cdef cython.uint first_card(cython.uint hv):
    return (hv >> TOP_CARD_SHIFT) & CARD_MASK

cdef cython.uint second_card(cython.uint hv):
    return (hv >> SECOND_CARD_SHIFT) & CARD_MASK

cdef cython.uint third_card(cython.uint hv):
    return (hv >> THIRD_CARD_SHIFT) & CARD_MASK

cdef cython.uint fourth_card(cython.uint hv):
    return (hv >> FOURTH_CARD_SHIFT) & CARD_MASK

cdef cython.uint fifth_card(cython.uint hv):
    return (hv >> FIFTH_CARD_SHIFT) & CARD_MASK

cdef value_to_description(cython.uint hand_value):
    cdef cython.uint type = hand_type(hand_value)
    # Of course, some of these won't be meaningful sometimes, but it won't break
    cdef cython.uint first = first_card(hand_value)
    cdef cython.uint second = second_card(hand_value)
    if type == HANDTYPE_HIGHCARD:
        return "high card, %s" % (singular_table[first], )
    elif type == HANDTYPE_PAIR:
        return "a pair of %s" % (plural_table[first], )
    elif type == HANDTYPE_TWOPAIR:
        return "two pair, %s and %s" % (plural_table[first], plural_table[second])
    elif type == HANDTYPE_TRIPS:
        return "three of a kind, %s" % (plural_table[first], )
    elif type == HANDTYPE_STRAIGHT:
        return "a straight, %s-high" % (singular_table[first], )
    elif type == HANDTYPE_FLUSH:
        return "a flush, %s-high" % (singular_table[first], )
    elif type == HANDTYPE_FULLHOUSE:
        return "a full house, %s full of %s" % (plural_table[first], plural_table[second])
    elif type == HANDTYPE_FOUR_OF_A_KIND:
        return "four of a kind, %s" % (plural_table[first], )
    elif type == HANDTYPE_STRAIGHTFLUSH:
        return "a straight flush, %s-high" % (singular_table[first], )
    return "(HAND DESCRIPTION ERROR!)"

def py_value_to_description(py_value):
    cdef cython.uint value = py_value
    return value_to_description(value)
