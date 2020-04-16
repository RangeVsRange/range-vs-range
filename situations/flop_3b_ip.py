def create_situation():
    """
    3bet flop, CO opens 2.5bb, BTN raises to 8bb, CO to act. Aggressor in position.
    """
    # pylint:disable=undefined-variable
    co = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="CO",
        stack=195,
        contributed=5,  # so far this betting round
        left_to_act=True,
        range_raw='22+,A2s+,K4s+,Q7s+,J8s+,T8s+,97s+,86s+,76s,65s,Td7d,Tc7c,9d6d,9c6c,7h5h,7s5s,5h4h,5s4s,A9o+,KTo+,QTo+,JTo,Ad8h,Ah8d,Ah8s,Ah8c,As8h,As8c,Ac8d,Ac8s')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=184,
        contributed=16,  # so far this betting round
        left_to_act=False,
        range_raw='JJ+,TdTh,ThTs,TsTc,9d9h,9s9c,AJs+,A8s,A3s-A2s,K8s,Q8s,J8s,KhQh,KsQs,Qd9d,Qc9c,Jh9h,Js9s,Ad7d,Ac7c,Td7d,Th7h,9s7s,9c7c,As6s,Ac6c,9d6d,9h6h,8s6s,8c6c,7h6h,7s6s,7d5d,7c5c,6d5d,6h5h,6s4s,6c4c,5d4d,5s4s,AQo+,AdJh,AdJs,AhJd,AhJs,AsJh,AsJc,AcJh,AcJs,KdQh,KdQs,KdQc,KhQd,KhQs,KhQc,KsQd,KsQc,KcQh,KcQs')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="CO facing BTN 3bet",
        players=[co, btn],  # CO acts first in future rounds
        current_player=0,  # CO acts next this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=3,  # antes, or pot at end of last betting round
        increment=11,  # minimum raise amount right now
        bet_count=3)
    return situation
