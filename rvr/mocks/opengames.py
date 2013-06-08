"""
A mock for what open games are available
"""

from rvr.infrastructure.ioc import IocComponent
from collections import namedtuple

# pylint:disable=C0103,R0201
OpenGameDetails = namedtuple("OpenGameDetails", "description, id")

class MockGameFilter(IocComponent):
    """
    Mocks out the calculation of how many matching games are available, based
    on the partial signup information entered by the user during signup.
    """    
    def count_all(self):
        """
        All open games
        """
        return 17
    
    def count_all_preflop(self):
        """
        All preflop situations
        """
        return 13
    
    def count_all_postflop(self):
        """
        All postflop situations
        """
        return 14
    
    def count_situation(self, _situationid):
        """
        Situations that match situation
        """
        return 12
    
    def all_games(self):
        """
        All open games
        """
        return [
            OpenGameDetails("Situation: BB vs. a steal; Random flop", "1"),
            OpenGameDetails("Situation: BB vs. a steal; Wet flop", "2"),
            OpenGameDetails("Situation: CO vs. a re-steal; Random flop", "3"),
            OpenGameDetails("Situation: BTN cold call; Random flop", "4"),
            OpenGameDetails("Preflop: Heads-up", "5"),
            OpenGameDetails("Preflop: Blind vs. blind", "6"),
            OpenGameDetails("Preflop: 6-max preflop", "7")
        ]
