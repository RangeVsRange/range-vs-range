def create_situation():
    """
    3bet flop, BTN opens 3bb, BB raises to 10bb, BTN calls. Aggressor out of position.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=180,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='JJ+,TsTh,ThTd,TdTc,9s9d,9h9c,8s8c,7s7h,6h6d,AQs+,AsJs,AhJh,AdTd,AcTc,Kh9h,Kc9c,Kh8h,Kd8d,Ks7s,Kd7d,Kd6d,Kc6c,Ks5s,Kc5c,Qs7s,Qh7h,Qs6s,Qd6d,Qh5h,Qc5c,Js7s,Jd7d,Th7h,Td7d,9h6h,9c6c,8s6s,8h6h,8h5h,8d5d,7d5d,7c5c,7s4s,7c4c,6h4h,6d4d,6s3s,6d3d,5s3s,5h3h,5h2h,5c2c,4d3d,4c3c,4s2s,4c2c,3h2h,3d2d,AQo+,AsJh,AsJd,AsJc,AhJd,AhJc,AdJc,AhTs,AdTs,AdTh,AcTs,AcTh,AcTd')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=180,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='JJ-22,AQs-A2s,KJs+,KsTs,KhTh,Kd9d,QJs,QdTd,QcTc,Qh9h,JTs,Jh9h,Jd9d,Jd8d,T9s,Ts8s,Tc8c,Tc7c,98s,9s7s,87s,8h6h,76s,7d5d,65s,6c4c,54s,5s3s,4h3h,AQo-AJo,AsTh,AsTd,AsTc,AhTd,AhTc,AdTc,Ad9h,Ac9s,Ac9d,Ah8s,Ad8s,Ac8h,As7c,Ah7d,Ad7c,As6h,As6d,Ah6c,Ah5s,Ad5h,Ac5s,Ad4s,Ac4h,Ac4d,As3c,Ah3d,Ac3h,As2d,Ad2h,Ac2s,KQo,KhJs,KdJs,KdJh,KcJs,KcJh,KcJd,KsTh,KsTd,KhTc,QhJs,QdJs,QcJh,JsTc,JhTd,JdTc')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="3bet, aggressor OOP (BTN opens to 3bb, BB 3bets to 10, BTN calls)",
        players=[bb, btn],  # BB acts first in future rounds
        current_player=0,  # BB acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=41,  # pot at start of this betting round
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation
