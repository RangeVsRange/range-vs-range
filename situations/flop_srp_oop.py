def create_situation():
    """
    Single raised flop, MP opens 3bb, BTN calls. Aggressor out of position.
    """
    # pylint:disable=undefined-variable
    mp = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="MP",
        stack=194,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='22+,A8s+,As7s,Ad7d,As6s,Ad6d,A5s-A2s,KTs+,Ks9s,QJs,QdTd,QcTc,Qh9h,JTs,Js9s,Jh9h,Jd8d,T9s,Ts8s,Tc8c,Tc7c,98s,9h7h,9d7d,9s6s,87s,8h6h,8c6c,8h5h,76s,7s5s,7d5d,7d4d,65s,6d4d,6c4c,6c3c,54s,5s3s,5h3h,43s,ATo+,KQo')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=194,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='JJ-22,AQs-A2s,KJs+,KsTs,KhTh,Kd9d,QJs,QdTd,QcTc,Qh9h,JTs,Jh9h,Jd9d,Jd8d,T9s,Ts8s,Tc8c,Tc7c,98s,9s7s,87s,8h6h,76s,7d5d,65s,6c4c,54s,5s3s,5d2d,4h3h,4c2c,3h2h,AQo-AJo,AsTh,AsTd,AsTc,AhTd,AhTc,AdTc,Ad9h,Ac9s,Ac9d,Ah8s,Ad8s,Ac8h,As7c,Ah7d,Ad7h,As6h,As6d,Ah6c,Ah5s,Ad5h,Ac5s,Ad4s,Ac4h,Ac4d,As3c,Ah3d,Ac3h,As2d,Ad2h,Ac2s,KQo,KhJs,KdJs,KdJh,KcJs,KcJh,KcJd,KsTh,KsTd,KhTc,QhJs,QdJs,QcJh,JsTc,JhTd,JdTc')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="2bet, aggressor OOP (MP opens to 3bb, BTN calls) (alpha)",
        players=[mp, btn],  # MP acts first in future rounds
        current_player=0,  # MP acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=15,  # antes, or pot at end of last betting round
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation
