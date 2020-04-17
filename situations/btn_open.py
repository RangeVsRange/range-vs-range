def create_situation():
    """
    BTN raises, folds to BB.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=198,
        contributed=2,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)  # @UndefinedVariable
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=195,
        contributed=5,  # so far this betting round
        left_to_act=False,
        range_raw='22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,85s+,75s+,64s+,54s,Jh6h,Jc6c,Td6d,Ts6s,Qh4h,Qc4c,7s4s,5d3d,5s3s,5c3c,4h3h,A4o+,K9o+,Q9o+,J9o+,T9o,Kd8s,Ks8c,Kc8h,9d8h,9d8c,9h8d,9h8s,9h8c,9s8h,9c8d,9c8s')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="BB facing BTN open",
        players=[bb, btn],  # BB acts first in future rounds
        current_player=0,  # BB acts next this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=1,  # antes, pot at end of last round, or folded players
        increment=3,  # minimum raise amount right now
        bet_count=2)
    return situation
