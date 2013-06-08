"""
A mock for determining available situations
"""

from collections import namedtuple
from rvr.infrastructure.ioc import IocComponent

# pylint:disable=C0103,R0201
SituationDetails = namedtuple("SituationDetails", "type, name, players, id")
TextureDetails = namedtuple("TextureDetails", "name, cards, id")

# for SituationDetails.type
TYPE_PREFLOP = 0
TYPE_POSTFLOP = 1

class MockSituationProvider(IocComponent):
    """
    Mocks out getting lists of available situations.
    """
    def all_postflop(self):
        """
        All postflop situations
        """
        return [
            SituationDetails(TYPE_POSTFLOP, "BB vs. a steal", 2, "1"),
            SituationDetails(TYPE_POSTFLOP, "CO vs. a re-steal", 2, "2"),
            SituationDetails(TYPE_POSTFLOP, "BTN cold call", 2, "3")
        ]
        
    def all_textures(self):
        """
        Standard textures: dry, wet, semi-wet, random
        """
        return [
            TextureDetails("Random Flop", "", "random"),
            TextureDetails("Dry Flop", "Kh 8d 3c", "dry"),
            TextureDetails("Semi-Wet Flop", "As Jc 8c", "semiwet"),
            TextureDetails("Wet Flop", "9h 8h 6d", "wet")
        ]

    def all_preflop(self):
        """
        All preflop situations
        """
        return [
            SituationDetails(TYPE_PREFLOP, "Heads-up", 2, "1"),
            SituationDetails(TYPE_PREFLOP, "Blind vs. blind", 2, "2"),
            SituationDetails(TYPE_PREFLOP, "BTN vs. both blinds", 2, "3"),
            SituationDetails(TYPE_PREFLOP, "6-max preflop", 2, "4")
        ]

    def get_postflop(self, situationid):
        """
        Return a PostflopSituationDetails for the given situationid
        """
        d = {details.id: details for details in self.all_postflop()}
        return d[situationid]