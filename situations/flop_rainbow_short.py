def create_situation():
    """
    Create HU rainbow flop situation.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=65,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='66-22,A8s-A2s,KTs-K2s,Q2s+,J3s+,T4s+,95s+,85s+,74s+,64s+,53s+,43s,ATo-A2o,KJo-K2o,Q6o+,J7o+,T7o+,97o+,87o,76o,65o,54o')
    sb_btn = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BTN",
        stack=65,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='55+,A2s+,K7s+,Q8s+,J8s+,T8s+,97s+,86s+,76s,A7o+,K9o+,QTo+,JTo,T9o,98o')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="654 rainbow flop, BTN vs. BB, 35 BB deep, 2.5x open, with antes",
        players=[bb, sb_btn],  # BB acts first in future rounds
        current_player=0,  # BB acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='6s5h4d',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=13,  # antes, or pot at end of last betting round
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation