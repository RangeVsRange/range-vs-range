def create_situation():
    """
    Create deep HU situation.
    """
    # pylint:disable=undefined-variable
    sb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="SB",
        stack=199,
        contributed=1,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=198,
        contributed=2,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)
    utg = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="UTG",
        stack=200,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=200,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="4-handed, 100 BB deep",
        players=[sb, bb, utg, btn],  # SB acts first in future rounds
        current_player=2,  # UTG acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=0,  # antes, or pot at end of last betting round
        increment=2,  # minimum raise amount right now
        bet_count=1)
    return situation
