"""
A mock for what open games are available
"""

from rvr.infrastructure.ioc import IocComponent, LateResolvedSingleton

# pylint:disable=C0103,R0201,R0903

class OpenGameDetails(object):
    """
    Details about an open (joinable) game
    """
    def __init__(self, path, gameid, s):
        self.path = path
        self.gameid = gameid
        self.situation = s

class OpenPostflop(OpenGameDetails):
    """
    Details of an open postflop game
    """
    def __init__(self, gameid, s, t):
        super(OpenPostflop, self).__init__('postflop', gameid, s)
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
        super(OpenPreflop, self).__init__('preflop', gameid, s)
    
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
            OpenPostflop("0", all_post["0"], all_t["random"]),
            OpenPostflop("1", all_post["0"], all_t["wet"]),
            OpenPostflop("2", all_post["1"], all_t["random"]),
            OpenPostflop("3", all_post["2"], all_t["random"]),
            OpenPreflop("4", all_pre["100"]),
            OpenPreflop("5", all_pre["101"]),
            OpenPreflop("6", all_pre["102"])
        ]
        
    def preflop_games(self):
        """
        All open preflop games
        """
        return [g for g in self.all_games() if g.path == 'preflop']
    
    def postflop_games(self):
        """
        All open postflop games
        """
        return [g for g in self.all_games() if g.path == 'postflop']
    
    def situation_games(self, situationid):
        """
        All open games with given situationid
        """
        return [g for g in self.all_games() if g.situation.id == situationid]
        
    def postflop_texture_games(self, situationid, textureid):
        """
        All open postflop games with given situationid, textureid
        """
        return [g for g in self.all_games() if g.path == 'postflop' and  \
            g.situation.id == situationid and g.texture.id == textureid]