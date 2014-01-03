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
from argparse import ArgumentError
from rvr.poker.handrange import HandRange

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
    
    def __repr__(self):
        return "UserDetails(%r, id=%r)" % (self.screenname, self.userid)
        
    @classmethod
    def from_user(cls, user):
        """
        Create object from tables.User
        """
        return cls(user.userid, user.screenname)

class SituationPlayerDetails(object):
    """
    Player-specific information for a situation.
    """
    def __init__(self, stack, contributed, left_to_act, range_raw):
        self.stack = stack
        self.contributed = contributed
        self.left_to_act = left_to_act
        self.range_raw = range_raw

    def __repr__(self):
        return ("SituationPlayerDetails(stack=%r, contributed=%r, " +  \
            "left_to_act=%r, range=%r)") % (self.stack, self.contributed,
            self.left_to_act, self.range_raw)

class SituationDetails(object):
    """
    A training situation. If we ever allow custom situations, this should be
    enough to specify a new one.
    """
    def __init__(self, description, players, current_player, is_limit,
                 big_blind, board_raw, current_round, pot_pre, increment,
                 bet_count):
        """
        Note that board_raw can contain fewer cards than current_round would
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
        self.board_raw = board_raw
        self.current_round = current_round
        self.pot_pre = pot_pre
        self.increment = increment
        self.bet_count = bet_count
    
    def __repr__(self):
        return ("SituationDetails(description=%r, players=%r, " +
            "current_player=%r, is_limit=%r, big_blind=%r, board_raw=%r, " + 
            "current_round=%r, pot_pre=%r, increment=%r, bet_count=%r)") %  \
            (self.description, self.players, self.current_player, self.is_limit,
             self.big_blind, self.board_raw, self.current_round, self.pot_pre,
             self.increment, self.bet_count)
        
    @classmethod
    def from_situation(cls, situation):
        """
        Create instance from tables.Situation
        """
        ordered = sorted(situation.players, key=lambda p: p.order)
        players = [SituationPlayerDetails(stack=player.stack,
                                          contributed=player.contributed,
                                          left_to_act=player.left_to_act,
                                          range_raw=player.range_raw)
                   for player in ordered]
        return cls(description=situation.description,
                   players=players,
                   current_player=situation.current_player_num,
                   is_limit=situation.is_limit,
                   big_blind=situation.big_blind,
                   board_raw=situation.board_raw,
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

class RunningGameSummary(object):
    """
    list of users in game, and details of situation
    """
    def __init__(self, gameid, users, situation, current_user_details):
        self.gameid = gameid
        self.users = users
        self.situation = situation
        self.current_user_details = current_user_details

    def __repr__(self):
        return ("RunningGameSummary(gameid=%r, users=%r, situation=%r, " +
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
        user_details = UserDetails.from_user(running_game.current_rgp.user)
        return cls(running_game.gameid, users, situation, user_details)

class RunningGameParticipantDetails(object):
    """
    details of a user and their participation in a game
    """
    def __init__(self, user, order, stack, contributed, range_raw, left_to_act,
                 folded):
        self.user = user  # UserDetails
        self.order = order  # 0 is first to left of dealer
        self.stack = stack
        self.contributed = contributed
        self.range_raw = range_raw
        self.left_to_act = left_to_act
        self.folded = folded
    
    def __repr__(self):
        return ("RunningGameParticipantDetails(user=%r, order=%r, stack=%r, " +
                "contributed=%r, range=%r, left_to_act=%r, folded=%r)") %  \
            (self.user, self.order, self.stack, self.contributed,
             self.range_raw, self.left_to_act, self.folded)
    
    @classmethod
    def from_rgp(cls, rgp):
        """
        Create object from tables.RunningGameParticipant
        """
        user = UserDetails.from_user(rgp.user)
        return cls(user, rgp.order, rgp.stack, rgp.contributed, rgp.range_raw,
                   rgp.left_to_act, rgp.folded)

class RunningGameDetails(object):
    """
    details of a game, including game state (more than RunningGameSummary)
    """
    def __init__(self, gameid, situation, current_player, board_raw,
                 current_round, pot_pre, increment, bet_count, rgp_details):
        self.gameid = gameid
        self.situation = situation  # SituationDetails
        self.current_player = current_player # RGPDetails
        self.board_raw = board_raw
        self.current_round = current_round
        self.pot_pre = pot_pre
        self.increment = increment
        self.bet_count = bet_count
        self.rgp_details = rgp_details  # RunningGameParticipantDetails
    
    def __repr__(self):
        return ("RunningGameDetails(gameid=%r, situation=%r, " +
                "current_player=%r, board_raw=%r, current_round=%r, " +  \
                "pot_pre=%r, increment=%r, bet_count=%r, rgp_details=%r") %  \
            (self.gameid, self.situation, self.current_player, self.board_raw,
             self.current_round, self.pot_pre, self.increment, self.bet_count,
             self.rgp_details)
    
    @classmethod
    def from_running_game(cls, game):
        """
        Create object from tables.RunningGame
        """
        situation = SituationDetails.from_situation(game.situation)        
        rgp_details = [RunningGameParticipantDetails.from_rgp(rgp)
                       for rgp in game.rgps]
        current_player = [r for r in rgp_details
                          if r.user.userid == game.current_rgp.userid][0]
        return cls(game.gameid, situation, current_player, game.board_raw,
                   game.current_round, game.pot_pre, game.increment,
                   game.bet_count, rgp_details)

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
    def __init__(self, user, range_raw):
        """
        user is a UserDetails
        range is a string describing the range
        """
        self.user = user
        self.range_raw = range_raw
    
    def __repr__(self):
        return "GameItemUserRange(user=%r, range=%r)" %  \
            (self.user, self.range_raw)
    
    def __str__(self):
        if self.range_raw:
            range_raw = self.range_raw
        else:
            range_raw = 'anything'
        return "%s's range is: %s" % (self.user.screenname, range_raw)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryUserRange
        """
        user_details = UserDetails.from_user(item.user)
        return cls(user_details, item.range_raw)
        
    def should_include_for(self, userid):
        """
        Ranges are only shown to the current user (while the game is running).
        """
        return self.user.userid == userid

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
    
    def __repr__(self):
        return ("GameItemRangeAction(user=%r, range_action=%r)") %  \
            (self.user, self.range_action)
    
    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryRangeAction
        """        
        user_details = UserDetails.from_user(item.user)
        range_action = ActionDetails(item.fold_range,
            item.passive_range, item.aggressive_range, item.raise_total)
        return cls(user_details, range_action)
    
    def should_include_for(self, userid):
        """
        Range actions are only shown to the user who makes them
        (while the game is running)
        """
        return self.user.userid == userid

class RunningGameHistory(object):
    """
    Everything about a running game.
    
    This will contain range data for both players if the game is finished, for
    one player if that user is requesting this object, or for no one if this is
    a public view of a running game.
    
    It will contain analysis only if the game is finished.
    """
    def __init__(self, game_details, history_items, current_options):
        self.game_details = game_details
        self.history = history_items
        self.current_options = current_options
        
    def __repr__(self):
        return ("RunningGameHistory(game_details=%r, history=%r, " +  \
                "current_options=%r)") %  \
            (self.game_details, self.history, self.current_options)
            
class ActionOptions(object):
    """
    Describes the options available to the current player, in general poker
    terms. E.g. fold, check, raise between X and Y chips, call Z chips.
    
    (Note that being allowed to fold is implied. You're always allowed to fold.)
    """
    def __init__(self, call_cost, is_raise=False,
                 min_raise=None, max_raise=None):
        """
        User can check if call_cost is 0. Otherwise, cost to call is call_cost.
        User can raise if min_raise and max_raise aren't None. If so, user can
        raise to between min_raise and max_raise. Note that each of these
        represents a raise total, not a contribution, and not what the amount of
        their raising.
        """
        self.call_cost = call_cost
        self.is_raise = is_raise
        if (min_raise is None) != (max_raise is None):
            raise ArgumentError(
                "specify both min_raise and max_raise, or neither")
        self.min_raise = min_raise
        self.max_raise = max_raise
        
    def __repr__(self):
        return "ActionOptions(call_cost=%r, min_raise=%r, max_raise=%r)" %  \
            (self.call_cost, self.min_raise, self.max_raise)
    
    def can_fold(self):
        """
        Does the user have the option to fold?
        """
        # pylint:disable=R0201
        return True
    
    def can_check(self):
        """
        Does the user have the option to check?
        """
        return self.call_cost == 0
    
    def can_raise(self):
        """
        Does the user have the option to raise? If so, minraise and max_raise
        will be available to express how much the user can raise to.
        """
        return self.min_raise is not None
    
class ActionDetails(object):
    """
    range-based action request object
    """
    def __init__(self, 
                 fold_range=None, passive_range=None, aggressive_range=None,
                 raise_total=None, 
                 fold_raw=None, passive_raw=None, aggressive_raw=None):
        """
        fold_range is the part of their range they fold here
        passive_range is the part of their range they check or call here
        aggressive_range is the part of their range the bet or raise here
        """
        if (fold_range is not None and fold_raw is not None) or  \
            (passive_range is not None and passive_raw is not None) or  \
            (aggressive_range is not None and aggressive_raw is not None):
            raise ValueError("Specified range and raw")
        if (fold_range is None and fold_raw is None) or  \
            (passive_range is None and passive_raw is None) or  \
            (aggressive_range is None and aggressive_raw is None):
            raise ValueError("Specified neither range or raw")
        if raise_total is None:
            if not aggressive_range.is_empty():
                raise ValueError(
                    "If aggressive_range is not nothing, must have raise_total")

        self.fold_range = fold_range  \
            if isinstance(fold_range, HandRange)  \
            else HandRange(fold_raw)
        self.passive_range = passive_range  \
            if isinstance(passive_range, HandRange)  \
            else HandRange(passive_raw)
        self.aggressive_range = aggressive_range  \
            if isinstance(aggressive_range, HandRange)  \
            else HandRange(aggressive_raw)
        self.raise_total = raise_total            

    def __repr__(self):
        return ("ActionDetails(fold_range=%r, passive_range=%r, " +
                "aggressive_range=%r, raise_total=%r)") %  \
            (self.fold_range, self.passive_range, self.aggressive_range,
             self.raise_total)

class ActionResponse(object):
    """
    response to a range-based action request, tells the user what happened
    """
    def __init__(self, is_fold=False, is_passive=False, 
                is_aggressive=False, call_cost=None, raise_total=None):
        if len([b for b in [is_fold, is_passive, is_aggressive] if b]) != 1:
            raise ValueError("Specify only one type of action for a response")
        if is_passive and call_cost is None:
            raise ValueError("Specify a call cost when is_passive")
        if is_aggressive and raise_total is None:
            raise ValueError("Specify a raise total when is_aggressive")
        self.is_fold = is_fold
        self.is_passive = is_passive
        self.is_aggressive = is_aggressive
        self.call_cost = call_cost
        self.raise_total = raise_total
        
    @classmethod
    def fold(cls):
        """
        User folded
        """
        return ActionResponse(is_fold=True)
    
    @classmethod
    def call(cls, call_cost):
        """
        User checked or called
        """
        return ActionResponse(is_passive=True, call_cost=call_cost)
    
    @classmethod
    def raise_to(cls, raise_total):
        """
        User bet or raised
        """
        return ActionResponse(is_aggressive=True, raise_total=raise_total)
    
    def __repr__(self):
        return ("ActionResponse(is_fold=%r, is_passive=%r, " +
                "is_aggressive=%r, call_cost=%r, raise_total=%r)") %  \
            (self.is_fold, self.is_passive, self.is_aggressive,
             self.call_cost, self.raise_total)
