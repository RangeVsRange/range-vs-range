def create_situation():
    """
    3bet flop, CO opens 3bb, BTN raises to 9bb, CO to act. Aggressor in position.
    """
    # pylint:disable=undefined-variable
    co = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="CO",
        stack=194,
        contributed=6,  # so far this betting round
        left_to_act=True,
        range_raw='AA-22,ATo+,KJo+,QJo,A2s+,K6s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,64s+,54s')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=182,
        contributed=18,  # so far this betting round
        left_to_act=False,
        range_raw='JJ+,AKs,A7s-A2s,AsKh,AsKc,AhKd,AdKs,AdKc,AcKh,ATo,KJo,QJo')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="3bet, aggressor IP (CO opens to 3bb, BTN 3bets to 9bb, CO to act) (alpha)",
        players=[co, btn],  # CO acts first in future rounds
        current_player=0,  # CO acts next this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=3,  # antes, or pot at end of last betting round
        increment=12,  # minimum raise amount right now
        bet_count=3)
    return situation
