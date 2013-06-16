"""
A mock for determining available situations
"""

from collections import namedtuple
from rvr.infrastructure.ioc import IocComponent

# pylint:disable=C0103,R0201
SituationDetails = namedtuple("SituationDetails",
    "type, name, players, id, order")
TextureDetails = namedtuple("TextureDetails", "name, cards, id, order")

# for SituationDetails.type
TYPE_PREFLOP = 0
TYPE_POSTFLOP = 1

class MockSituationProvider(IocComponent):
    """
    Mocks out getting lists of available situations.
    """
    #pylint:disable=C0301
    def all_postflop(self):
        """
        All postflop situations
        """
        return [
            SituationDetails(TYPE_POSTFLOP, "BB vs. a steal", 2, "0", 0),
            SituationDetails(TYPE_POSTFLOP, "CO vs. a re-steal", 2, "1", 1),
            SituationDetails(TYPE_POSTFLOP, "BTN cold call", 2, "2", 2)
        ]

    def all_preflop(self):
        """
        All preflop situations
        """
        return [
            SituationDetails(TYPE_PREFLOP, "Heads-up", 2, "100", 100),
            SituationDetails(TYPE_PREFLOP, "Blind vs. blind", 2, "101", 101),
            SituationDetails(TYPE_PREFLOP, "BTN vs. both blinds", 2, "102", 102),
            SituationDetails(TYPE_PREFLOP, "6-max preflop", 2, "103", 103)
        ]
        
    def all_textures(self):
        """
        Standard textures: dry, wet, semi-wet, random
        """
        return [
            TextureDetails("Random Flop", "", "random", 0),
            TextureDetails("Dry Flop", "Kh 8d 3c", "dry", 1),
            TextureDetails("Semi-Wet Flop", "As Jc 8c", "semiwet", 2),
            TextureDetails("Wet Flop", "9h 8h 6d", "wet", 3)
        ]
    #pylint:enable=C0301

    def get_situation_by_id(self, situationid):
        """
        Return a SituationDetails for the given situationid, whether preflop or
        postflop.
        """
        all_post = {p.id: p for p in self.all_postflop()}
        all_pre = {p.id: p for p in self.all_preflop()}
        return all_post.get(situationid, all_pre.get(situationid, None))
    
    def get_texture_by_id(self, textureid):
        """
        Return a TextureDetails
        """
        all_ = {t.id: t for t in self.all_textures()}
        return all_.get(textureid, None)