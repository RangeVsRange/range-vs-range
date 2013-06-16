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
    
    def games(self, **criteria):
        #pylint:disable=C0322
        """
        Return games filtered to given criteria. Criteria kwargs supported are:
          path - preflop or postflop
          situationid - situation ID
          texture - flop texture, only valid for postflop situations
        If a kwarg value is None, it will be ignored
        """
        criteria = {k: v for k, v in criteria.iteritems() if v is not None}
        expr = lambda g: True
        if criteria.has_key('path'):
            path = criteria.pop('path')
            expr = lambda g, expr=expr:  \
                expr(g) and g.path == path
        if criteria.has_key('situationid'):
            situationid = criteria.pop('situationid')
            expr = lambda g, expr=expr:  \
                expr(g) and g.situation.id == situationid
        if criteria.has_key('textureid'):
            textureid = criteria.pop('textureid')
            expr = lambda g, expr=expr:  \
                expr(g) and g.texture.id == textureid
        if criteria:
            return ValueError('Invalid game selection criteria: "%s"' %
                (criteria.keys()[0],))
        return [g for g in self.all_games() if expr(g)]
        #pylint:enable=C0322

    def count(self, **criteria):
        """
        Return count of filtered games. See games() for details.
        """
        return len(self.games(**criteria))