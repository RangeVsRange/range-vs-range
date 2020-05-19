def create_situation():
    """
    CO opens 2.5bb, SB raises to 10bb, CO to act.
    """
    # pylint:disable=undefined-variable
    sb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="SB",
        stack=180,
        contributed=20,  # so far this betting round
        left_to_act=False,
        range_raw='88+,7d7h,7d7s,7h7c,7s7c,6h6s,6d6c,A9s+,A5s-A4s,KTs+,QTs+,JTs,T9s,Kh9h,Kc9c,Jd9d,Js9s,9h8h,8s7s,8c7c,7d6d,7h6h,6s5s,Ah3h,As3s,AQo+,AdJs,AhJs,AhJc,AsJd,AcJd,AcJh,KdQh,KdQc,KhQd,KsQh,KsQc,KcQs')
    co = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="CO",
        stack=195,
        contributed=5,  # so far this betting round
        left_to_act=True,
        range_raw='22+,A2s+,K4s+,Q7s+,J8s+,T8s+,97s+,86s+,76s,65s,Td7d,Tc7c,9d6d,9c6c,7h5h,7s5s,5h4h,5s4s,A9o+,KTo+,QTo+,JTo,Ad8h,Ah8d,Ah8s,Ah8c,As8h,As8c,Ac8d,Ac8s')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="CO facing SB 3bet",
        players=[sb, co],  # SB acts first in future rounds
        current_player=1,  # CO acts next this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=2,  # antes, pot at end of last betting round, or dead money
        increment=15,  # minimum raise amount right now
        bet_count=3)
    return situation
