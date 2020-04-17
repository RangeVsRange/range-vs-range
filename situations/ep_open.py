def create_situation():
    """
    UTG raises, folds to BB.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=198,
        contributed=2,  # so far this betting round
        left_to_act=True,
        range_raw=ANYTHING)  # @UndefinedVariable
    utg = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="UTG",
        stack=195,
        contributed=5,  # so far this betting round
        left_to_act=False,
        range_raw='55+,4h4s,4d4c,A4s+,K9s+,Q9s+,J9s+,T9s,98s,Td8d,Tc8c,8s7s,8c7c,7h6h,7s6s,6d5d,6h5h,AJo+,KQo')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="BB facing UTG open",
        players=[bb, utg],  # BB acts first in future rounds
        current_player=0,  # BB acts next this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.PREFLOP,  # @UndefinedVariable
        pot_pre=1,  # antes, pot at end of last round, or folded players
        increment=3,  # minimum raise amount right now
        bet_count=2)
    return situation
