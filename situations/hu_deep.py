def create_situation():
    """
    Create deep HU situation.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=1998,
        contributed=2,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)
    btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=1999,
        contributed=1,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="Heads-up 1000 BB ultra deep",
        players=[bb, btn],  # BB acts first in future rounds
        current_player=1,  # BTN acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=0,  # antes, or pot at end of last betting round
        increment=2,  # minimum raise amount right now
        bet_count=1)
    return situation
