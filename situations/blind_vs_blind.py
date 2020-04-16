def create_situation():
    """
    Create blind vs. blind situation.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=198,
        contributed=2,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)  # @UndefinedVariable
    sb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="SB",
        stack=199,
        contributed=1,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)  # @UndefinedVariable
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="Blind vs. blind",
        players=[sb, bb],  # SB acts first in future rounds
        current_player=0,  # SB acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=0,  # antes, or pot at end of last betting round
        increment=2,  # minimum raise amount right now
        bet_count=1)
    return situation
