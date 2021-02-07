def create_situation():
    """
    Single raised flop, HJ opens 2.5bb, BB calls. Aggressor in position.
    """
    # pylint:disable=undefined-variable
    bb = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="BB",
        stack=195,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='99-22,AJs-ATs,A8s-A6s,A3s-A2s,K9s-K6s,K4s-K2s,Q9s-Q5s,J9s-J7s,T9s-T7s,98s-96s,87s-85s,76s-74s,64s-63s,53s,43s,AQo-A9o,KQo-KTo,QJo-QTo,JTo')
    hj = dtos.SituationPlayerDetails(  # @UndefinedVariable
        name="HJ",
        stack=195,
        contributed=0,  # so far this betting round
        left_to_act=True,
        range_raw='AA-55,AKs-A2s,KQs-K6s,QJs-Q8s,JTs-J9s,T9s,98s,87s,76s,AKo-ATo,KQo-KTo,QJo-QTo')
    situation = dtos.SituationDetails(  # @UndefinedVariable
        situationid=None,
        description="Flop: HJ opened, BB called",
        players=[bb, hj],  # BB acts first in future rounds
        current_player=0,  # BB acts first this round
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=cards.FLOP,  # @UndefinedVariable
        pot_pre=11,  # antes, pot at end of last betting round, other players
        increment=2,  # minimum raise amount right now
        bet_count=0)
    return situation
