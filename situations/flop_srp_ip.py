def create_situation():
    """
    Single raised flop, BTN opens 3bb, BB calls. Aggressor in position.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=195,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='44-22,7d7s,7d7c,7h7c,6d6s,6d6c,6h6c,5d5s,5d5c,5h5c,A9s-A6s,K9s-K2s,Q9s-Q2s,J8s-J2s,T7s-T4s,96s-95s,86s-85s,75s-74s,64s-63s,52s+,42s+,32s,KdTd,KsTs,QhTh,QcTc,Jd9d,Ts8s,9h7h,9c7c,7c6c,6h5h,6c5c,ATo-A3o,KJo-K9o,Q9o+,J9o+,T9o,98o,87o,76o,AdJs,AdJc,AhJd,AhJs,AsJh,AsJc,AcJd,AcJh,KdQs,KdQc,KhQd,KhQs,KsQh,KsQc,KcQd,KcQh,Td8h,Th8c,Ts8d,Tc8s,6d5s,6d5c,6h5d,6h5s,6s5h,6s5c,6c5d,6c5h')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=195,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,85s+,75s+,64s+,54s,Jh6h,Jc6c,Td6d,Ts6s,Qh4h,Qc4c,7s4s,5d3d,5s3s,5c3c,4h3h,A4o+,K9o+,Q9o+,J9o+,T9o,Kd8s,Ks8c,Kc8h,9d8h,9d8c,9h8d,9h8s,9h8c,9s8h,9c8d,9c8s')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="Flop: BB called BTN open",
        players=[bb, btn],  # BB acts first in future rounds
        current_player=0,  # BB acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=11,  # antes, pot at end of last betting round, other players
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation
