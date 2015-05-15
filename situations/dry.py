def create_situation():
    """
    Create 6-max dry flop situation.
    """
    # pylint:disable=undefined-variable
    co = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="CO",
        stack=194,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='22+,A2s+,K2s+,Q6s+,J6s+,T6s+,96s+,86s+,75s+,64s+,53s+,43s,A2o+,K8o+,Q9o+,J9o+,T9o,98o,87o')
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=194,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='99-22,AJs-A6s,K8s+,Q8s+,J8s+,T8s+,97s+,86s+,75s+,64s+,53s+,43s,AJo-A2o,KTo+,QTo+,JT')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="Dry flop, CO opens, BTN calls",
        players=[co, btn],  # CO acts first in future rounds
        current_player=0,  # CO acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='Ks8h3d',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=15,  # pot at start of this betting round
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation