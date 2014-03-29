"""
Temporary refactoring mixin.
"""
from rvr.poker.action import finish_game, range_action_to_action, re_deal
from rvr.core.dtos import ActionResult
from rvr.poker.cards import RIVER

# pylint:disable=E1101,R0914,W0232,R0903,C0103

class PA1_2:
    """
    Old implementation of play on. As mixin, for refactoring purposes.
    
    What was wrong with this version? It runs.
    """
    def _play_on(self, game, rgp, range_action, current_options):
        """
        Determines range action and affects side effects.
        """
        left_to_act = [r for r in game.rgps if r.left_to_act]
        remain = [r for r in game.rgps if not r.folded]
        # pylint:disable=C0301
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
        # terminate means the hand is over, and also means no action is needed.
        # The above redeals rgp's cards in the dict, so we need to re-apply to
        # rgp.
        rgp.cards_dealt = cards_dealt[rgp]
        if not can_fold and can_call:
            game.current_factor *= 1 - f_ratio
        elif not can_fold and not can_call:
            game.current_factor *= a_ratio        
        if not terminate:
            rgp.range, action_result = range_action_to_action(range_action,
                rgp.cards_dealt, current_options)
        else:
            action_result = ActionResult.terminate()
        return action_result
    
    def _perform_action(self, game, rgp, range_action, current_options):
        """
        Determine result of range action, and apply it.
        
        Assumes validation is already done.
        """
        self._record_range_action(rgp, range_action)
        action_result = self._play_on(game, rgp, range_action, current_options)
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
