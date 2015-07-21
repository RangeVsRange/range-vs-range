"""
Showdown functionality - pre-river all in, and river
"""
#pylint:disable=R0913,R0914,R0904
from rvr.infrastructure.util import concatenate, stddev_one
import operator
from rvr.poker import cards
from rvr.poker.evaluate import BestHandEval7
import unittest
import random

def _impossible_deal(fixed):
    """
    fixed is a list of hands
    return true if it contains a duplicate
    """
    cards_ = concatenate(fixed)  # a hand is two cards, so concatenate hands
    return len(cards_) != len(set(cards_))

def __showdown_equity(wins_by_player, fixed, options_by_player, board, memo):
    """
    fixed maps player to fixed option
    range maps player to range
    board is the board, obv.

    returns a dict mapping player to number of pots won (may be fractional)
    """
    # if this ever needs to be more efficient, the solution is equivalence
    # groups
    remain = [p for p in options_by_player.keys() if p not in fixed.keys()]
    if not remain:
        # terminal case: do a single showdown
        _shown_down, winners = showdown(board, fixed, memo)
        for player in fixed.keys():
            if player in winners:
                wins_by_player[player] += 1.0 / len(winners)
        return 1
    else:
        # iterate over one range and recurse with one fewer range
        player = remain.pop()
        # we can remove options that are excluded by the board at this point...
        # but not options that are excluded by fixed
        options = [o for o in options_by_player[player]
                   if not o.intersection(board)]
        iterations = 0
        for hand in options:
            fixed_ = dict(fixed)
            fixed_[player] = hand
            # don't need board for this, already removed above:
            if _impossible_deal(fixed_.values()):
                continue  # trim tree early
            iterations += __showdown_equity(wins_by_player, fixed_,
                                            options_by_player, board, memo)
        return iterations

def _simulate_showdown(wins_by_player, options_by_player, board, memo):
    """
    Run one simulated showdown based on ranges.
    """
    selected = {}
    while True:
        for player, options in options_by_player.iteritems():
            selected[player] = random.choice(options)
        fixed = {player: hand for player, hand in selected.iteritems()}
        if not _impossible_deal(fixed.values() + [board]):
            break
    excluded = concatenate(fixed.values())
    fixed_board = []
    for i in range(5):
        if i < len(board):
            card = board[i]
            excluded.append(card)
        else:
            card = cards.deal_card(excluded)  # extends excluded
        fixed_board.append(card)
    _shown_down, winners = showdown(fixed_board, fixed, memo)
    for player in selected.keys():
        if player in winners:
            wins_by_player[player] += 1.0 / len(winners)

def _estimate_showdown_equity(options_by_player, board, iterations):
    """
    options_by_player: iterable of (option, weight)
    board: iterable of Card
    returns: wins_by_player
    """
    wins_by_player = {player: 0.0 for player in options_by_player.keys()}
    memo = {}
    i = 0
    while i < iterations:
        _simulate_showdown(wins_by_player, options_by_player, board, memo)
        i += 1
    return wins_by_player

MAX_ITERATIONS = 10000

def showdown_equity(ranges, board, hard_limit=MAX_ITERATIONS):
    """
    ranges: maps player to range
    board: community cards (may have Nones if not river)

    returns a dict mapping player to equity (between 0.0 and 1.0)
    """
    options_by_player = {player: range_.generate_options(board)
                         for player, range_ in ranges.iteritems()}
    total_combos = reduce(operator.mul,
                          [len(o) for o in options_by_player.values()])
    if total_combos <= hard_limit and len(board) == 5:
        # We only do exact equity for river showdowns
        # (Because we don't yet have functionality to iterate over all combos
        # of turn, river etc.)
        wins_by_player = {player: 0.0 for player in ranges.keys()}
        iterations = __showdown_equity(wins_by_player, {}, options_by_player,
                                       board, {})
    else:
        wins_by_player = _estimate_showdown_equity(options_by_player, board,
                                                   hard_limit)
        iterations = hard_limit
    total = sum(wins_by_player.values())
    return {player: wins / total
            for player, wins in wins_by_player.iteritems()}, iterations

def showdown(board, players_cards, memo=None):
    """
    board is a list of five board cards

    players_cards is a dict of {player: cards}
    order of this list is the order in which players will show down

    returns a list of tuples: (player, hand shown down), and a list of winners

    will return a hand for every player, with None representing a fold (because
    the player did not show down a hand)
    """
    shown_down = []  # list of: (player, hand or None)
    best = None  # best hand shown down so far
    total_cards = board + concatenate(
        [c for _p, c in players_cards.iteritems()])
    if len(set(total_cards)) != len(total_cards):
        assert False
    for player, cards_ in players_cards.iteritems():
        all_cards = frozenset(board + list(cards_))
        if memo is None:
            hand = BestHandEval7(all_cards)
        elif memo.has_key(all_cards):
            hand = memo[all_cards]
        else:
            hand = BestHandEval7(all_cards)
            memo[all_cards] = hand
        # They fold if it's worse than best, otherwise they show
        if best is None or hand >= best:
            best = hand
            shown_down.append((player, hand))
        else:
            shown_down.append((player, None))
    winners = [player for player, hand in shown_down if hand == best]
    return shown_down, winners

class Test(unittest.TestCase):
    #pylint:disable=C0111
    def assert_equity_almost_equal(self, first, second):
        self.assertEqual(first.keys(), second.keys())
        for key in first.keys():
            self.assertAlmostEqual(first[key], second[key], places=5)

    def _test_calculate_equity(self, ranges_txt, board_txt, expect,
                               expect_iters):
        from rvr.poker.handrange import HandRange
        from rvr.poker.cards import Card
        ranges = {"Player %d" % i: HandRange(ranges_txt[i])
                  for i in range(len(ranges_txt))}
        board = Card.many_from_text(board_txt)
        expected_results = {"Player %d" % i: expect[i]
                            for i in range(len(expect))}
        results, iterations = showdown_equity(ranges, board, 20000)
        self.assertEqual(iterations, expect_iters)
        self.assert_equity_almost_equal(results, expected_results)

    def test_calculate_equity(self):
        """
        ranges, board -> results
        ranges: maps player to range
        board: community cards at river
        results: a dict mapping player to equity (between 0.0 and 1.0)
        """
        # Vanilla: 2-player, unweighted, tastes good
        self._test_calculate_equity(["AhAc", "KhKc"],
                                    "AdKdKs2c2s",
                                    [0.0, 1.0],
                                    1)
        self._test_calculate_equity(["AhAc,QhQc", "KhKc"],
                                    "JhJdThTd9h",
                                    [0.5, 0.5],
                                    2)
        self._test_calculate_equity(["AhAc,QhQc", "KhKc,QdQs"],
                                    "JhJdThTd9h",
                                    [0.625, 0.375],
                                    4)
        self._test_calculate_equity(["AhKh,JhTh", "QhJh"],
                                    "2h3d4s5d7c",
                                    [1.0, 0.0],
                                    1)
        self._test_calculate_equity(["TT+,AKs", "KK-99,AQs+,AKo"],
                                    "4sQd8dJh6d",
                                    [0.71296, 0.28704],
                                    972)
        # a medium-strength wide range against a polarised range
        self._test_calculate_equity(
            ["TT-88,AQs-ATs,KTs+,QTs+,AJo+,KQo",
             "JJ+,77-22,AKs,A9s,K9s,Q9s,J9s+,T9s,98s,87s,76s,65s,ATo,KJo,QJo"],
            "5sKd7dJh6d",
            [0.44846, 0.55154],
            7994)
        # three-handed
        self._test_calculate_equity(
            ["KK+,AKs,QJs",
             "QQ,AQs,KQs,KQo",
             "AA,99,J9s,T9s,AQo"],
            "5sKd7dJh6d",
            [0.73854, 0.10820, 0.15326],
            5259)
        self._test_calculate_equity(
            ["KdKs,AsKd,KsQs",
             "JdJs,QsJs,JhTd",
             "TcTd,9c9d,Ks2d"],
            "2h2c3h3c4s",
            [0.31250, 0.25000, 0.43750],
            16)
        # Non-intersecting ranges
        self._test_calculate_equity(
            ["JJ+,AJs+,KJs+,QJs,AJo+,KJo+,QJo",
             "TT-77,T7s+,97s+,87s,T7o+,97o+,87o"],
            "KcQsTd8d7s",
            [0.68428, 0.31572],
            7098)

    def assert_wins_almost_equal(self, first, second, delta):
        self.assertEqual(first.keys(), second.keys())
        for key in first.keys():
            self.assertAlmostEqual(first[key], second[key], delta=delta[key])

    def _test_estimate_showdown_equity(self, ranges_txt, board_txt, expect,
                                       delta, iterations):
        from rvr.poker.handrange import HandRange
        from rvr.poker.cards import Card
        ranges = {"Player %d" % i: HandRange(ranges_txt[i])
                  for i in range(len(ranges_txt))}
        board = Card.many_from_text(board_txt)
        expected_results = {"Player %d" % i: expect[i]
                            for i in range(len(expect))}
        delta_by_player = {"Player %d" % i: delta[i]
                           for i in range(len(expect))}
        options_by_player = {p: r.generate_options(board)
                             for p, r in ranges.iteritems()}
        wins_by_player = _estimate_showdown_equity(options_by_player,
                                                   board, iterations)
        print "\nwins_by_player: %r\n" % wins_by_player
        self.assert_wins_almost_equal(wins_by_player, expected_results,
                                      delta_by_player)

    def _test_estimate_showdown_equity2(self, ranges_txt, board_txt, expect,
                                        sds, iterations):
        from rvr.poker.handrange import HandRange
        from rvr.poker.cards import Card
        ranges = {"Player %d" % i: HandRange(ranges_txt[i])
                  for i in range(len(ranges_txt))}
        board = Card.many_from_text(board_txt)
        sdev = [stddev_one(prob) for prob in expect]  # e.g. p=0.05, sdev=0.2179
        expected_results = {"Player %d" % i: expect[i] * iterations
                            for i in range(len(expect))}
        delta_by_player = {"Player %d" % i: sds * sdev[i] * (iterations ** 0.5)
                           for i in range(len(expect))}
        options_by_player = {p: r.generate_options(board)
                             for p, r in ranges.iteritems()}
        wins_by_player = _estimate_showdown_equity(options_by_player,
                                                   board, iterations)
        print "\nwins_by_player: %r\n" % wins_by_player
        self.assert_wins_almost_equal(wins_by_player, expected_results,
                                      delta_by_player)

    def test_estimate_showdown_equity(self):
        # if the code under test is wrong, 5 sds will fail once every
        # 1,744,278 runs
        # for 5%, 100000 runs, 5 sigma = 345
        # i.e. 5% -> 5000 +/- 345
        # for larger percentage 5 sigma will be higher but so will total
        self._test_estimate_showdown_equity2(
            ["KK-TT,AQs-AJs,KQs",
             "TT+,AQs+",
             "TT-88,A9s-A6s,KJs-KTs,QTs+,ATo,KJo",
             "33,A5s,T9s,98s,K8o,Q9o"],
            "AsJd9h6c",
            [0.29478, 0.42389, 0.22910, 0.05222],
            5,
            100000)
        self._test_estimate_showdown_equity2(
            ["AA,QsQc",
             "KK"],
            "AhKhQhKd",
            [0.017, 0.983],
            5,
            100000)
        self._test_estimate_showdown_equity2(
            ["KK-TT,AQs-AJs,KQs",
             "TT+,AQs+",
             "TT-88,A9s-A6s,KJs-KTs,QTs+,ATo,KJo",
             "33,A5s,T9s,98s,K8o,Q9o"],
            "AsJd9h6c4s",
            [0.298100, 0.454200, 0.222600, 0.025100],
            5,
            100000)
        self._test_estimate_showdown_equity2(
            ["AdAs,AcKc",
             "AdAs,JhTh,Js9s"],
            "AsJd9h6c4s",
            [0.5, 0.5],
            5,
            100000)
        self._test_estimate_showdown_equity2(
            ["AdAs,AhAs,AcKc,AhKh",
             "AdAs,JhTh,Js9s,JdTh,JhTs"],
            "AsJd9h6c4s",
            [0.6667, 0.3333],
            5,
            100000)
        self._test_estimate_showdown_equity2(
            ["AcAh,AcAs,AdAh,AdAs,AhAs,AcKc,AhKh,AsKs",
             "AdAs,Jc9c,Jd9d,Js9s,JcTh,JcTs,JdTc,JdTh,"
                "JdTs,JhTc,JhTd,JhTs,JsTc,JsTd,JsTh"],
            "AsJd9h6c4s",
            [0.9000, 0.1000],
            5,
            100000)

if __name__ == "__main__":
    # 262 seconds at 2013-02-10 (old version)
    # 175 seconds at 2014-12-19 (fewer tests though, because no weighted ranges)
    unittest.main()
