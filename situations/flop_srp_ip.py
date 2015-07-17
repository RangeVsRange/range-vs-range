def create_situation():
    """
    Single raised flop, BTN opens 3bb, BB calls. Aggressor in position.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=194,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='TsTd,TsTc,ThTc,9s9h,9s9c,9h9d,9d9c,8s8h,8s8d,8h8d,8h8c,8d8c,7s7d,7s7c,7h7d,7h7c,7d7c,6s6h,6s6d,6s6c,6h6c,6d6c,55-22,AdJd,AcJc,AsTs,AhTh,A9s-A2s,KTs+,Ks9s,Kd9d,Ks8s,Kc8c,Kh7h,Kc7c,Ks6s,Kh6h,Kh5h,Kd5d,Q8s+,Qd7d,Qc7c,Qh6h,Qc6c,Qs5s,Qd5d,J8s+,Jh7h,Jc7c,T8s+,97s+,87s,76s,65s,54s,AhJs,AdJs,AdJh,AcJs,AcJh,AcJd,AsTh,AsTd,AsTc,AhTd,AhTc,AdTc,A9o-A2o,KTo+,Ks9d,Ks9c,Kh9d,Kh9c,Ks8h,Kh8s,Kd8c,Kc8d,Ks7d,Ks7c,Kh7d,Kh7c,Ks6h,Kh6s,Kd6c,Kc6d,Kd5s,Kd5h,Kc5s,Kc5h,QTo+,Qd9s,Qd9h,Qc9s,Qc9h,Qs8h,Qh8s,Qd8c,Qc8d,Qd7s,Qd7h,Qc7s,Qc7h,Qs6d,Qs6c,Qh6d,Qh6c,Qs5h,Qh5s,Qd5c,Qc5d,JTo,Js9h,Jh9s,Jd9c,Jc9d,Js8d,Js8c,Jh8d,Jh8c,Js7h,Jh7s,Jd7c,Jc7d,Ts9d,Ts9c,Th9d,Th9c,Td8s,Td8h,Tc8s,Tc8h,9s8h,9h8s,9d8c,9c8d,9s7d,9s7c,9h7d,9h7c,8d7s,8d7h,8c7s,8c7h,7d6s,7d6h,7c6s,7c6h,6s5d,6s5c,6h5d,6h5c,5s4h,5h4s,5d4c,5c4d')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=194,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='22+,A2s+,K5s+,Kh4h,Kd4d,Kd3d,Kc3c,Ks2s,Kh2h,Q7s+,Qs6s,Qd6d,Qs5s,Qc5c,Qc4c,Qs3s,Qd2d,J8s+,Jh7h,Jc7c,Js6s,Jh5h,Jd4d,Jc3c,Js2s,T7s+,Ts6s,Th6h,Ts5s,Th4h,Td3d,Tc2c,96s+,9d5d,9c5c,9s4s,9h3h,9d2d,85s+,8s4s,8c4c,8s3s,8h2h,74s+,7s3s,7c2c,63s+,6s2s,52s+,42s+,32s,A2o+,K5o+,Kd4s,Kd4h,Kd4c,Kh3s,Kh3d,Kh3c,Ks2h,Ks2d,Ks2c,Q8o+,Qs7h,Qs7d,Qs7c,Qh7s,Qh7d,Qh7c,Qh6s,Qd6s,Qd6h,Qc6s,Qc6h,Qc6d,Qs5h,Qs5d,Qs5c,Qh5d,Qh5c,Qd5c,J8o+,Jd7s,Jd7h,Jd7c,Jc7s,Jc7h,Jc7d,T8o+,Tc7s,Tc7h,Tc7d,98o,9s7h,9h7s,9d7s,9d7h,9c7s,9c7h,9s6c,9h6c,9d6c,87o,8s6d,8h6d,8c6d,7s6d,7s6c,7h6d,7h6c,7d6c,7c6d,7s5h,7d5h,7c5h,6s5h,6s5d,6h5d,6d5h,6c5h,6c5d,6h4s,6d4s,6c4s,5s4c,5h4s,5h4c,5d4s,5d4c,5c4s,5s3c,5h3d,5c3h')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="2bet, aggressor IP (BTN opens to 3bb, BB calls)",
        players=[bb, btn],  # BB acts first in future rounds
        current_player=0,  # BB acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=13,  # pot at start of this betting round
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation
