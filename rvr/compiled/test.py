"""
Unit tests for eval7
"""
import unittest
from rvr.poker.handrange import HandRange
from rvr.poker.cards import Card
from rvr.poker import cards
from rvr.compiled.eval7 import py_hand_vs_range_exact  # @UnresolvedImport
from rvr.compiled.eval7 import py_hand_vs_range_monte_carlo  # @UnresolvedImport
from rvr.compiled.eval7 import py_all_hands_vs_range  # @UnresolvedImport
from rvr.compiled.eval7 import py_wh_randint  # @UnresolvedImport
from rvr.compiled.eval7 import py_hand_to_mask  # @UnresolvedImport
from rvr.compiled import eval7

#pylint:disable=C0301,C0103,E1101,C0111,R0904

CLUB_OFFSET = 13 * 0
DIAMOND_OFFSET = 13 * 1
HEART_OFFSET = 13 * 2
SPADE_OFFSET = 13 * 3

map_suit_to_offset = {
    cards.SPADES: SPADE_OFFSET,
    cards.HEARTS: HEART_OFFSET,
    cards.DIAMONDS: DIAMOND_OFFSET,
    cards.CLUBS: CLUB_OFFSET}

map_rank_to_offset = {
    cards.DEUCE: 0,
    cards.TREY: 1,
    cards.FOUR: 2,
    cards.FIVE: 3,
    cards.SIX: 4,
    cards.SEVEN: 5,
    cards.EIGHT: 6,
    cards.NINE: 7,
    cards.TEN: 8,
    cards.JACK: 9,
    cards.QUEEN: 10,
    cards.KING: 11,
    cards.ACE: 12}

def non_py_just_eval(cards_):
    mask = 0
    for card in cards_:
        mask |= 1L << (map_suit_to_offset[card.suit] +
                       map_rank_to_offset[card.rank])
    return eval7.non_py_evaluate(mask)  # @UndefinedVariable
            
class TestEval7(unittest.TestCase):
    def test_wh_random(self):
        # 0.9s
        result = {n: 0 for n in range(52)}
        for i in xrange(1900000):
            result[py_wh_randint(52)] += 1
        for i in range(52):
            self.assertAlmostEqual(result[i], 36500, delta=1000)    
    
    def test_hand_to_mask(self):
        # Highest and lowest cards
        result = py_hand_to_mask(Card.many_from_text("As2c"))
        self.assertEqual(result, 2251799813685249)

    def test_hand_vs_range_exact(self):
        hand = Card.many_from_text("AcAh")
        villain = HandRange("AA")
        board = Card.many_from_text("KhJd8c5d2s")
        equity = py_hand_vs_range_exact(hand, villain, board)
        self.assertEqual(equity, 0.5)

        hand = Card.many_from_text("AcAh")
        villain = HandRange("AsAd")
        board = Card.many_from_text("KhJd8c5d2s")
        equity = py_hand_vs_range_exact(hand, villain, board)
        self.assertEqual(equity, 0.5)

        hand = Card.many_from_text("AsAd")
        villain = HandRange("AA,A3o,32s")
        board = Card.many_from_text("KhJd8c5d2s")
        equity = py_hand_vs_range_exact(hand, villain, board)
        self.assertAlmostEqual(equity, 0.95, places=7)

    def test_hand_vs_range_monte_carlo(self):
        hand = Card.many_from_text("AsAd")
        villain = HandRange("AA,A3o,32s")
        board = []
        equity = py_hand_vs_range_monte_carlo(
            hand, villain, board, 10000000)
        self.assertAlmostEqual(equity, 0.85337, delta=0.002)

    def test_all_hands_vs_range(self):
        hero = HandRange("AsAd,3h2c")
        villain = HandRange("AA,A3o,32s")
        board = []
        equity_map = py_all_hands_vs_range(hero, villain, board, 10000000)
        self.assertEqual(len(equity_map), 2)
        hand1 = frozenset(Card.many_from_text("AsAd"))
        hand2 = frozenset(Card.many_from_text("3h2c"))
        self.assertAlmostEqual(equity_map[hand1], 0.85337, delta=0.002)
        self.assertAlmostEqual(equity_map[hand2], 0.22865, delta=0.002)
        
        # Hero has an impossible hand in his range.
        hero = HandRange("JsJc,QsJs")
        villain = HandRange("JJ")
        board = Card.many_from_text("KhJd8c")
        equity_map = py_all_hands_vs_range(hero, villain, board, 10000000)
        hand = frozenset(Card.many_from_text("QsJs"))
        self.assertAlmostEqual(equity_map[hand], 0.03687, delta=0.0002)
        self.assertEqual(len(equity_map), 1)

if __name__ == '__main__':
    # 2013-02-09 28 seconds (old version)
    # 2014-12-29 28 seconds
    unittest.main()