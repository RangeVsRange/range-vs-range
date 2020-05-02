def create_situation():
    """
    Single raised flop, MP opens 2.5bb, BTN calls. Aggressor out of position.
    """
    # pylint:disable=undefined-variable
    hj = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="HJ",
        stack=195,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='55+,4d4h,4d4s,4h4c,4s4c,3d3c,2h2s,A2s+,K8s+,Q8s+,J9s+,T8s+,98s,Js8s,Kh7h,Ks7s,9h7h,9s7s,8d7d,8h7h,8s7s,Kd6d,Kc6c,8d6d,8s6s,7h6h,7s6s,7c6c,7s5s,6d5d,6s5s,6c5c,6d4d,5d4d,5h4h,5c4c,ATo+,KJo+,Ah9c,Ac9s,KhTc,KsTd,KsTc,KcTh,QdJh,QdJc,QhJd,QhJs,QhJc,QsJd,QsJc,QcJh,QcJs')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=195,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='TT-44,3d3h,3h3s,3s3c,2d2s,2h2c,ATs-A8s,KJs-K9s,Q9s+,J9s+,T9s,98s,87s,76s,Td8d,Tc8c,9s7s,6d5d,6h5h,5s4s,AJo,KQo,AdQh,AhQc,AsQd,AcQs')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="Flop: HJ opened, BTN called, flop is Kc 8d 3h",
        players=[hj, btn],  # HJ acts first in future rounds
        current_player=0,  # HJ acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='Kc8d3h',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=13,  # antes, or pot at end of last betting round
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation
