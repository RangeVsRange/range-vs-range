"""
A mock for what open games are available
"""

from rvr.infrastructure.ioc import IocComponent, LateResolvedSingleton

# pylint:disable=C0103,R0201,R0903

class OpenGameDetails(object):
    """
    Details about an open (joinable) game
    """
    def __init__(self, gameid):
        self.gameid = gameid

class OpenPostflop(OpenGameDetails):
    """
    Details of an open postflop game
    """
    def __init__(self, gameid, s, t):
        super(OpenPostflop, self).__init__(gameid)
        self.situation = s
        self.texture = t
    
    @property
    def description(self):
        """
        A text representation of an open postflop game
        """
        return "Postflop: %s; %s" % (self.situation.name, self.texture.name)

class OpenPreflop(OpenGameDetails):
    """
    Details of an open preflop game
    """
    def __init__(self, gameid, s):
        super(OpenPreflop, self).__init__(gameid)
        self.situation = s
    
    @property
    def description(self):
        """
        A text representation of an open postflop game
        """
        return "Preflop: %s" % (self.situation.name,)

class MockGameFilter(IocComponent):
    """
    Mocks out the calculation of how many matching games are available, based
    on the partial signup information entered by the user during signup.
    """
    situation_provider = LateResolvedSingleton('SituationProvider')
    
    def count_all(self):
        """
        All open games
        """
        return 17
    
    def count_all_preflop(self):
        """
        All preflop games
        """
        return 13
    
    def count_all_postflop(self):
        """
        All postflop games
        """
        return 14
    
    def count_situation(self, _situationid):
        """
        Games that match situation
        """
        return 12
    
    def count_situation_texture(self, _situationid, _textureid):
        """
        Games that match situation and texture 
        """
        return 1
    
    def all_games(self):
        """
        All open games
        """
        all_post = {post.id: post for post in
            self.situation_provider.all_postflop()}
        all_pre = {pre.id: pre for pre in
            self.situation_provider.all_preflop()}
        all_t = {t.id: t for t in
            self.situation_provider.all_textures()}
        return [
            OpenPostflop(0, all_post["1"], all_t["random"]),
            OpenPostflop(1, all_post["1"], all_t["wet"]),
            OpenPostflop(2, all_post["2"], all_t["random"]),
            OpenPostflop(3, all_post["3"], all_t["random"]),
            OpenPreflop(4, all_pre["1"]),
            OpenPreflop(5, all_pre["2"]),
            OpenPreflop(6, all_pre["4"])
        ]