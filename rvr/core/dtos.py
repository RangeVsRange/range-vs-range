"""
Data transfer objects:
- login, with OpenID, OpenID identity, email address, screenname
- user, with userid for user, system generated
- gameid for open, running or finished game
- range-based action
- open game, with list of users registered and details of situation
- general game, with status (open/running/finished), whose turn?, details of
  situation as per open game list
- hand history(!)
"""
from rvr.db import tables

#pylint:disable=R0903,R0913,R0902

# Note: We do not log the user in until they have chosen a unique screenname
# But also note that we only know if their screenname is unique by trying.
class LoginRequest(object):
    """
    Details to record (or ensure) a user in the database.
    """
    def __init__(self, identity, email, screenname):
        """
        If the screenname is already taken, then error, ask user for new
        screenname, and try again.
        
        Response will be an error only when BOTH:
         - this user doesn't exist, AND
         - another user has this screenname
        """
        self.identity = identity
        self.email = email
        self.screenname = screenname

class ChangeScreennameRequest(object):
    """
    When the initial automatic login fails, the user gets a chance to choose a
    different screenname and try again. All is well, and this class is not
    needed.
    
    When the initial automatic login succeeds, the user may still want to change
    their screenname, and we give them that option. When they do so, this
    request object is sent to the backend to change their name.
    """
    def __init__(self, userid, screenname):
        self.userid = userid
        self.screenname = screenname

class DetailedUser(object):
    """
    OpenID identity, email address, screenname
    """
    def __init__(self, userid, identity, email, screenname):
        self.userid = userid
        self.identity = identity
        self.email = email
        self.screenname = screenname

class UserDetails(object):
    """
    Response from a LoginRequest. Note that the screenname may change because
    the user has chosen a different one.
    
    If response has a different screenname to request, it means that the user
    has previously chosen to have a different screenname, possibly because their
    name was taken.
    
    If response has the same screenname, it means either that the user has
    logged in previously, or they were created with that screenname.
    """
    def __init__(self, userid, screenname):
        self.userid = userid
        self.screenname = screenname
        
    @classmethod
    def from_user(cls, user):
        """
        Create object from tables.User
        """
        return cls(user.userid, user.screenname)
    
    def __repr__(self):
        return "UserDetails(%r, id=%r)" % (self.screenname, self.userid)

class SituationPlayerDetails(object):
    """
    Player-specific information for a situation.
    """
    def __init__(self, stack, contributed, left_to_act, range_):
        self.stack = stack
        self.contributed = contributed
        self.left_to_act = left_to_act
        self.range = range_

    def __repr__(self):
        return ("SituationPlayerDetails(stack=%r, contributed=%r, " +  \
            "left_to_act=%r, range=%r)") % (self.stack, self.contributed,
            self.left_to_act, self.range)

class SituationDetails(object):
    """
    A training situation. If we ever allow custom situations, this should be
    enough to specify a new one.
    """
    def __init__(self, description, players, current_player, is_limit,
                 big_blind, board, current_round, pot_pre, increment,
                 bet_count):
        """
        Note that board can contain fewer cards than current_round would
        suggest (e.g. to allow flop situations with random flops), but it can't
        contain more.
        
        players is a list of SituationPlayerDetails.
        
        current_player is an index into the players list.
        """
        self.description = description
        self.players = players
        self.current_player = current_player
        self.is_limit = is_limit
        self.big_blind = big_blind
        self.board = board
        self.current_round = current_round
        self.pot_pre = pot_pre
        self.increment = increment
        self.bet_count = bet_count
        
    @classmethod
    def from_situation(cls, situation):
        """
        Create instance from tables.Situation
        """
        ordered = sorted(situation.players, key=lambda p: p.order)
        players = [SituationPlayerDetails(stack=player.stack,
                                          contributed=player.contributed,
                                          left_to_act=player.left_to_act,
                                          range_=player.range)
                   for player in ordered]
        return cls(description=situation.description,
                   players=players,
                   current_player=situation.current_player_num,
                   is_limit=situation.is_limit,
                   big_blind=situation.big_blind,
                   board=situation.board,
                   current_round=situation.current_round,
                   pot_pre=situation.pot_pre,
                   increment=situation.increment,
                   bet_count=situation.bet_count)
    
    def left_to_act(self):
        """
        From (but excluding) current_player, all players who are left to
        act, including those players before current_player, after the others.
        
        E.g. if the players are 1,2,3,4,5 and 3 is current, and only 4 and 2
        have left_to_act=True, then this function returns [4, 2].
        """
        potential = self.players[self.current_player + 1:] +  \
            self.players[:self.current_player]
        return [p for p in potential if p.left_to_act]
    
    def __repr__(self):
        return ("SituationDetails(description=%r, players=%r, " +
            "current_player=%r, is_limit=%r, big_blind=%r, board=%r, " + 
            "current_round=%r, pot_pre=%r, increment=%r, bet_count=%r)") %  \
            (self.description, self.players, self.current_player, self.is_limit,
             self.big_blind, self.board, self.current_round, self.pot_pre,
             self.increment, self.bet_count)

class RangeBasedActionDetails(object):
    """
    range-based action request object
    """
    def __init__(self, fold_range, passive_range, aggressive_range):
        """
        fold_range is the part of their range they fold here
        passive_range is the part of their range they check or call here
        aggressive_range is the part of their range the bet or raise here
        """
        self.fold_range = fold_range
        self.passive_range = passive_range
        self.aggressive_range = aggressive_range

class OpenGameDetails(object):
    """
    list of users in game, and details of situation
    """
    def __init__(self, gameid, users, situation):
        self.gameid = gameid
        self.users = users
        self.situation = situation

    def __repr__(self):
        return "OpenGameDetails(gameid=%r, users=%r, situation=%r)" %  \
            (self.gameid, self.users, self.situation)
    
    @classmethod
    def from_open_game(cls, open_game):
        """
        Create object from table.OpenGame
        """
        users = [UserDetails.from_user(o.user) for o in open_game.ogps]
        situation = SituationDetails.from_situation(open_game.situation)
        return cls(open_game.gameid, users, situation)

class RunningGameDetails(object):
    """
    list of users in game, and details of situation
    """
    def __init__(self, gameid, users, situation, current_user_details):
        self.gameid = gameid
        self.users = users
        self.situation = situation
        self.current_user_details = current_user_details

    def __repr__(self):
        return ("RunningGameDetails(gameid=%r, users=%r, situation=%r, " +
                "current_user_details=%r)") %  \
            (self.gameid, self.users, self.situation, self.current_user_details)

    @classmethod
    def from_running_game(cls, running_game):
        """
        Create object from tables.RunningGame
        """ 
        rgps = sorted(running_game.rgps, key=lambda r:r.order)
        users = [UserDetails.from_user(r.user) for r in rgps]
        situation = SituationDetails.from_situation(running_game.situation)
        user_details = UserDetails.from_user(running_game.current_user)
        return cls(running_game.gameid, users, situation, user_details)

class UsersGameDetails(object):
    """
    lists of open game details, running game details, for a specific user
    """
    def __init__(self, userid, running_details):
        self.userid = userid
        self.running_details = running_details

class GameItem(object):
    """
    base class for hand history item DTOs
    """
    @classmethod
    def from_game_history_child(cls, child):
        """
        Child is a GameHistoryUserRange, etc.
        Construct a GameItemUserRange, etc. 
        """
        if isinstance(child, tables.GameHistoryUserRange):
            return GameItemUserRange.from_history_item(child)
        else:
            raise TypeError("Object is not a GameHistoryItem associated object")
    
    def should_include_for(self, _userid):
        """
        Should this item be included in the hand history for user <userid>?
        """
        # pylint:disable=R0201
        return True

class GameItemUserRange(GameItem):
    """
    user has range
    """
    def __init__(self, user, range_):
        """
        user is a UserDetails
        range is a string describing the range
        """
        self.user = user
        self.range = range_

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryUserRange
        """
        user_details = UserDetails.from_user(item.user)
        return cls(user_details, item.range)
        
    def should_include_for(self, userid):
        """
        Ranges are only shown to the current user (while the game is running).
        """
        return self.user.userid == userid
    
    def __repr__(self):
        return "GameItemUserRange(user=%r, range=%r)" %  \
            (self.user, self.range)
    
    def __str__(self):
        if self.range:
            range_ = self.range
        else:
            range_ = 'anything'
        return "%s's range is: %s" % (self.user.screenname, range_)

class GameItemRangeAction(GameItem):
    """
    user folds fold_range, checks or calls passive_range, bets or raises
    aggressive_range
    """
    def __init__(self, user, range_action):
        """
        user is a UserDetails
        """
        self.user = user
        self.range_action = range_action
    
    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryRangeAction
        """        
        user_details = UserDetails.from_user(item.user)
        range_action = RangeBasedActionDetails(item.fold_range,
            item.passive_range, item.aggressive_range)
        return cls(user_details, range_action)
    
    def should_include_for(self, userid):
        """
        Range actions are only shown to the user who makes them
        (while the game is running)
        """
        return self.user.userid == userid
    
    def __repr__(self):
        return ("GameItemRangeAction(user=%r, range_action=%r)") %  \
            (self.user, self.range_action)

class RunningGameHistory(object):
    """
    Everything about a running game.
    
    This will contain range data for both players if the game is finished, for
    one player if that user is requesting this object, or for no one if this is
    a public view of a running game.
    
    It will contain analysis only if the game is finished.
    """
    def __init__(self, game_details, history_items):
        self.game_details = game_details
        self.history = history_items
        
    def __repr__(self):
        return "RunningGameHistory(game_details=%r, history=%r)" %  \
            (self.game_details, self.history)