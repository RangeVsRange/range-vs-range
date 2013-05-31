"""
Mock objects, to be used with the IoC container: rvr.infrastructure.ioc.FEATURES
"""
from rvr.infrastructure.ioc import IocComponent
from collections import namedtuple

#pylint:disable=R0201,R0903,C0103
OpenGameDetails = namedtuple("OpenGameDetails", "description, id")
PostflopSituationDetails = namedtuple("PostflopSituationDetails",
    "description, players, id")
PreflopSituationDetails = namedtuple("PreflopSituationDetails",
    "description, players, id")
TextureDetails = namedtuple("TextureDetails", "name, cards, id")

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
    
    def count_all_situations(self):
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
        
    def all_postflop(self):
        """
        All postflop situations
        """
        return [
            PostflopSituationDetails("BB vs. a steal", 2, "1"),
            PostflopSituationDetails("CO vs. a re-steal", 2, "2"),
            PostflopSituationDetails("BTN cold call", 2, "3")
        ]

    def all_preflop(self):
        """
        All preflop situations
        """
        return [
            PreflopSituationDetails("Heads-up", 2, "1"),
            PreflopSituationDetails("Blind vs. blind", 2, "2"),
            PreflopSituationDetails("BTN vs. both blinds", 2, "3"),
            PreflopSituationDetails("6-max preflop", 2, "4")
        ]
        
    def all_textures(self):
        """
        Standard textures: dry, wet, semi-wet, random
        """
        return [
            TextureDetails("Random Flop", None, "random"),
            TextureDetails("Dry Flop", "Kh 8d 3c", "dry"),
            TextureDetails("Semi-Wet Flop", "As Jc 8c", "semiwet"),
            TextureDetails("Wet Flop", "9h 8h 6d", "wet")
        ]