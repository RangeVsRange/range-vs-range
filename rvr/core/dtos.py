"""
Data transfer objects:
- login, with OpenID, OpenID provider, email address, screenname
- user, with userid for user, system generated
- gameid for open, running or finished game
- range-based action
- open game, with list of users registered and details of situation
- general game, with status (open/running/finished), whose turn?, details of
  situation as per open game list
- hand history(!)
"""

class LoginDetails(object):
    """
    OpenID provider, email address, screenname
    """
    def __init__(self, userid, provider, email, screenname):
        self.userid = userid
        self.provider = provider
        self.email = email
        self.screenname = screenname

class UserDetails(object):
    """
    userid
    """
    pass

class RangeBasedActionDetails(object):
    """
    range-based action
    """
    pass

class OpenGameDetails(object):
    """
    list of users registered and details of situation
    """
    pass

class GameDetails(object):
    """
    general game, with status (open/running/finished), whose turn?, details of
    situation as per open game list
    """
    pass

class HandHistoryDetails(object):
    """
    sufficient to show a completed game, analysis etc. to user
    sufficient for the user to choose their new range-based action
    """
    pass