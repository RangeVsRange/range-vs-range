"""
Python wrapper for (cython) eval7
"""
from rvr.poker.cards import Card
import unittest
from rvr.compiled import eval7

#pylint:disable=R0903,R0904

class BestHandEval7:
    """
    Wrapping class for eval7
    """
    def __init__(self, cards):
        self.value = eval7.py_evaluate(cards)
    def __cmp__(self, other):
        if other is None:
            return 1  # anything beats a fold
        # higher value is higher hand
        return cmp(self.value, other.value)
    def __hash__(self):
        return hash(self.value)
    def __str__(self):
        return eval7.py_value_to_description(self.value)

class Test(unittest.TestCase):
    """
    Unit tests for BestHandEval7
    """
    def test_description(self):
        """
        Test BestHandEval7 to string
        """
        cards = Card.many_from_text("AsTdTs5sAc5cQd")
        hand = BestHandEval7(cards)
        self.assertEqual(str(hand), "two pair, Aces and Tens")
        
    def test_compare(self):
        """
        Test BestHandEval7 compare
        """
        hand1 = BestHandEval7(Card.many_from_text("AsTdTs5sAc5cQd"))
        hand2 = BestHandEval7(Card.many_from_text("AsTdTs5sAc5cJd"))
        self.assertTrue(hand1 > hand2)  # Q kicker beats J kicker
        
if __name__ == '__main__':
    # 2013-02-10
    unittest.main()