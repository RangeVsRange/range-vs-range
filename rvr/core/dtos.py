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
from rvr.poker.cards import FLOP, TURN, RIVER, PREFLOP, Card, FINISHED
from sqlalchemy.orm.session import object_session

#pylint:disable=R0903,R0913,R0902

# Note: We do not log the user in until they have chosen a unique screenname
# But also note that we only know if their screenname is unique by trying.
class LoginRequest(object):
    """
    Details to record (or ensure) a user in the database.
    """
    def __init__(self, identity, email):
        """
        Note that we default screenname to "Player N"
        """
        self.identity = identity
        self.email = email

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
    Userid and screenname for user, as recorded in database.
    """
    def __init__(self, userid, screenname):
        self.userid = userid
        self.screenname = screenname

    def __repr__(self):
        return "UserDetails(userid=%r, screenname=%r)" %  \
            (self.userid, self.screenname)

    def __str__(self):
        return self.screenname

    @classmethod
    def from_user(cls, user):
        """
        Create object from tables.User
        """
        return cls(user.userid, user.screenname)

class LoginResponse(UserDetails):
    """
    Response from a LoginRequest. Note that the screenname may change because
    the user has chosen a different one.

    If response has a different screenname to request, it means that the user
    has previously chosen to have a different screenname, possibly because their
    name was taken.

    If response has the same screenname, it means either that the user has
    logged in previously, or they were created with that screenname.
    """
    def __init__(self, userid, screenname, existed):
        UserDetails.__init__(self, userid, screenname)
        self.existed = existed

    def __repr__(self):
        return "LoginResponse(userid=%r, screenname=%r, existed=%r)" %  \
            (self.userid, self.screenname, self.existed)

    @classmethod
    def from_user(cls, user, existed):  # pylint:disable=W0221
        """
        Create object from tables.User
        """
        return cls(user.userid, user.screenname, existed)

class SituationPlayerDetails(object):
    """
    Player-specific information for a situation.
    """
    def __init__(self, name, stack, contributed, left_to_act, range_raw):
        self.name = name
        self.stack = stack
        self.contributed = contributed
        self.left_to_act = left_to_act
        self.range_raw = range_raw

    def __repr__(self):
        return ("SituationPlayerDetails(name=%r, stack=%r, contributed=%r, "
            "left_to_act=%r, range=%r)") % (self.name, self.stack,
            self.contributed, self.left_to_act, self.range_raw)

class SituationDetails(object):
    """
    A training situation. If we ever allow custom situations, this should be
    enough to specify a new one.
    """
    def __init__(self, situationid, description, players, current_player,
                 is_limit, big_blind, board_raw, current_round, pot_pre,
                 increment, bet_count):
        """
        Note that board_raw can contain fewer cards than current_round would
        suggest (e.g. to allow flop situations with random flops), but it can't
        contain more.

        players is a list of SituationPlayerDetails.

        current_player is an index into the players list.
        """
        self.situationid = situationid
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
        return ("SituationDetails(situationid=%r, description=%r, players=%r, "
            "current_player=%r, is_limit=%r, big_blind=%r, board_raw=%r, "
            "current_round=%r, pot_pre=%r, increment=%r, bet_count=%r)") %  \
            (self.situationid, self.description, self.players,
             self.current_player, self.is_limit, self.big_blind, self.board_raw,
             self.current_round, self.pot_pre, self.increment, self.bet_count)

    @classmethod
    def from_situation(cls, situation):
        """
        Create instance from tables.Situation
        """
        ordered = sorted(situation.players, key=lambda p: p.order)
        players = [SituationPlayerDetails(name=player.name,
                                          stack=player.stack,
                                          contributed=player.contributed,
                                          left_to_act=player.left_to_act,
                                          range_raw=player.range_raw)
                   for player in ordered]
        return cls(situationid=situation.situationid,
                   description=situation.description,
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
    def __init__(self, gameid, public_ranges, users, situation):
        self.gameid = gameid
        self.public_ranges = public_ranges
        self.users = users
        self.situation = situation

    def __repr__(self):
        return "OpenGameDetails(gameid=%r, public_ranges=%r, users=%r, "  \
            "situation=%r)" % (self.gameid, self.public_ranges, self.users,
            self.situation)

    @classmethod
    def from_open_game(cls, open_game):
        """
        Create object from table.OpenGame
        """
        users = [UserDetails.from_user(o.user) for o in open_game.ogps]
        situation = SituationDetails.from_situation(open_game.situation)
        return cls(open_game.gameid, open_game.public_ranges, users, situation)

FOLD = 'fold'
CHECK = 'check'
CALL = 'call'
RAISE = 'raise'
BET = 'bet'

SHORTENING = {
    FOLD: 'F',
    CHECK: 'X',
    CALL: 'C',
    RAISE: 'R',
    BET: 'B'}

def calculate_betting_line(game):
    """
    Calculate betting line for game.

    E.g. {'flop': ['check', 'fold', 'bet', 'call'], 'turn': ['bet']} ...
    ... would mean: on the flop, Player A checks , Player B folds, Player C
    bets, Player A calls; on the turn, Player A donks all in. There is nothing
    else because we only return non-terminal actions. (Which is what constitutes
    a game on RvR.)
    """
    session = object_session(game)
    actions = session.query(tables.GameHistoryActionResult).filter(
        tables.GameHistoryActionResult.gameid == game.gameid).all()
    boards = session.query(tables.GameHistoryBoard).filter(
        tables.GameHistoryBoard.gameid == game.gameid).all()
    combined = sorted(actions + boards, key=lambda a: a.order)
    current_round = game.situation.current_round
    results = {}
    for item in combined:
        if isinstance(item, tables.GameHistoryBoard):
            current_round = item.street
        else:
            if item.is_fold:
                entry = FOLD
            elif item.is_passive and item.call_cost == 0:
                entry = CHECK
            elif item.is_passive:
                entry = CALL
            elif item.is_raise:
                entry = RAISE
            else:
                entry = BET
            results.setdefault(current_round, []).append(entry)
    return results

ROUND_ORDER = [PREFLOP, FLOP, TURN, RIVER]
LINE_STREET_SEPARATOR = ' - '

def line_description(line):
    """ e.g. 'XBC - XBRC - B' """
    # Maybe not the best place for this, but the line is not currently used
    # anywhere else.
    results = []
    for street in ROUND_ORDER:
        if street not in line:
            continue
        results.append(''.join([SHORTENING[verb] for verb in line[street]]))
    return LINE_STREET_SEPARATOR.join(results)

def game_line_key(game):
    """
    Key for sorting game's betting lines: fold < check < call < bet < raise.
    """
    map_number = {'F': 0, 'X': 1, 'C': 2, 'B': 3, 'R': 4}
    return [[map_number[c] for c in token]
            for token in game.line.split(LINE_STREET_SEPARATOR)]

class RunningGameSummary(object):
    """
    list of users in game, and details of situation
    """
    def __init__(self, gameid, public_ranges, users, situation,
                 is_on_me, is_finished, is_waiting, is_analysed, rgp_details,
                 spawn_group, spawn_factor, line):
        self.gameid = gameid
        self.public_ranges = public_ranges
        self.users = users  # TODO: REVISIT: replace this with rgp_details
        self.situation = situation
        self.is_on_me = is_on_me
        self.is_analysed = is_analysed
        self.is_finished = is_finished
        self.is_waiting = is_waiting
        self.rgp_details = rgp_details
        self.spawn_group = spawn_group
        self.spawn_factor = spawn_factor
        self.line = line

    def __repr__(self):
        return "RunningGameSummary(gameid=%r, public_ranges=%r, users=%r, "  \
            "situation=%r, is_on_me=%r, is_finished=%r, is_waiting=%r, "  \
            "is_analysed=%r, "  \
            "rgp_details=%r, spawn_group=%r, spawn_factor=%r, line=%r)" %  \
            (self.gameid, self.users, self.public_ranges, self.situation,
             self.is_on_me, self.is_finished, self.is_waiting, self.is_analysed,
             self.rgp_details, self.spawn_group, self.spawn_factor, self.line)

    @classmethod
    def from_running_game(cls, running_game, userid):
        """
        Create object from tables.RunningGame
        """
        rgps = sorted(running_game.rgps, key=lambda r:r.order)
        users = [UserDetails.from_user(r.user) for r in rgps]
        situation = SituationDetails.from_situation(running_game.situation)
        rgp_details = [RunningGameParticipantDetails.from_rgp(rgp)
                       for rgp in running_game.rgps]
        line = calculate_betting_line(running_game)  # {street: [action]}
        line = line_description(line)  # e.g. "XBC | XBRC | B"
        return cls(running_game.gameid, running_game.public_ranges, users,
                   situation, running_game.current_userid == userid,
                   running_game.game_finished, running_game.game_waiting,
                   running_game.analysis_performed, rgp_details,
                   running_game.spawn_group, running_game.spawn_factor, line)

class RunningGameParticipantDetails(object):
    """
    details of a user and their participation in a game
    """
    def __init__(self, user, order, stack, contributed, range_raw, left_to_act,
                 folded, results):
        self.user = user  # UserDetails
        self.order = order  # 0 is first to left of dealer
        self.stack = stack
        self.contributed = contributed
        self.range_raw = range_raw
        self.left_to_act = left_to_act
        self.folded = folded
        self.results = results

    def __repr__(self):
        return ("RunningGameParticipantDetails(user=%r, order=%r, stack=%r, "
                "contributed=%r, range=%r, left_to_act=%r, folded=%r, "
                "results=%r)") %  \
            (self.user, self.order, self.stack, self.contributed,
             self.range_raw, self.left_to_act, self.folded, self.results)

    @classmethod
    def from_rgp(cls, rgp):
        """
        Create object from tables.RunningGameParticipant
        """
        user = UserDetails.from_user(rgp.user)
        results = {rgpr.scheme: rgpr.result for rgpr in rgp.results}
        return cls(user, rgp.order, rgp.stack, rgp.contributed, rgp.range_raw,
                   rgp.left_to_act, rgp.folded, results)

class RunningGroup(object):
    """
    Summary of a spawn group
    """
    def __init__(self, groupid, is_finished, is_on_me, is_analysed,
                 description, situationid, users):
        self.groupid = groupid
        self.is_finished = is_finished
        self.is_on_me = is_on_me
        self.is_analysed = is_analysed
        self.description = description
        self.situationid = situationid
        self.users = users

    def __repr__(self):
        return ("RunningGroup(groupid=%r, is_finished=%r, is_on_me=%r, "
                "is_analysed=%r, description=%r, situationid=%r, users=%r)") % \
            (self.groupid, self.is_finished, self.is_on_me, self.is_analysed,
             self.description, self.situationid, self.users)

    @classmethod
    def from_rgps(cls, groupid, is_finished, is_on_me, games):
        is_analysed = sum(game.spawn_factor for game in games
                          if game.analysis_performed)
        users = {rgp.userid: {'screenname': rgp.user.screenname, 'result': 0.0}
                 for rgp in games[0].rgps}
        for game in games:
            for rgp in game.rgps:
                for result in rgp.results:
                    if result.scheme == tables.RunningGameParticipantResult.SCHEME_EV:
                        users[rgp.userid]['result'] +=  \
                            result.result * game.spawn_factor
        users = [users[rgp.userid] for rgp in games[0].rgps]
        situationid = games[0].situation.situationid
        return cls(groupid, is_finished, is_on_me, is_analysed,
                   games[0].situation.description, situationid, users)

class SituationResult(object):
    """
    Everything a user might want to know about their results for a situation.
    """
    def __init__(self, situationid, name, average, positions):
        self.situationid = situationid
        self.name = name
        self.average = average
        self.positions = positions

    def __repr__(self):
        return "SituationResult(situationid=%r, name=%r, average=%r, "  \
            "positions=%r)" % (self.situationid, self.name, self.average,
                               self.positions)

class PositionResult(object):
    """
    Everything a user might want to know about their results for a position.
    """
    def __init__(self, situationid, order, name, ev, played, total,
                 redline, blueline, average, stddev, confidence):
        self.situationid = situationid
        self.order = order
        self.name = name
        self.ev = ev
        self.played = played
        self.total = total
        self.redline = redline
        self.blueline = blueline
        self.average = average
        self.stddev = stddev
        self.confidence = confidence

    def __repr__(self):
        return "PositionResult(situationid=%r, order=%r, name=%r, ev=%r, "  \
            "played=%r, total=%r, redline=%r, blueline=%r, average=%r, "  \
            "stddev=%r, confidence=%r)" %  \
            (self.situationid, self.order, self.name, self.ev, self.played,
             self.total, self.redline, self.blueline, self.average, self.stddev,
             self.confidence)

class LeaderboardEntry(object):
    """
    a player's entry on a leaderboard:
    screenname, average, redline, blueline, confidence, #games
    """
    def __init__(self, screenname, average, redline, blueline, confidence,
                 played):
        self.screenname = screenname
        self.average = average
        self.redline = redline
        self.blueline = blueline
        self.confidence = confidence
        self.played = played

    def __repr__(self):
        return "LeaderboardEntry(screenname=%r, average=%r, redline=%r, "  \
            "blueline=%r, confidence=%r, played=%r)" %  \
            (self.screenname, self.average, self.redline, self.blueline,
             self.confidence, self.played)

class UsersGameDetails(object):
    """
    lists of open game details, running game details, for a specific user
    """
    def __init__(self, userid, running_details, finished_details,
                 running_groups, finished_groups,
                 c_less, c_more, o_less, o_more):
        self.userid = userid
        self.running_details = running_details
        self.finished_details = finished_details
        self.running_groups = running_groups
        self.finished_groups = finished_groups
        self.c_less = c_less
        self.c_more = c_more
        self.o_less = o_less
        self.o_more = o_more

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
        class_ = child.__class__
        if class_ in MAP_TABLE_DTO:
            return MAP_TABLE_DTO[class_].from_history_item(child)
        raise TypeError("Object is not a GameHistoryItem associated object")

    def should_include_for(self, userid, all_userids, is_finished,
                           public_ranges):
        """
        Should this item be included in the hand history for user <userid>,
        in a game with users <all_userids> and finished status <is_finished>?
        """
        # pylint:disable=unused-argument
        return True

class GameItemUserRange(GameItem):
    """
    user has range
    """
    def __init__(self, order, factor, user, range_raw):
        """
        user is a UserDetails
        range is a string describing the range
        """
        self.order = order
        self.factor = factor
        self.user = user
        self.range_raw = range_raw

    def __repr__(self):
        return "GameItemUserRange(order=%r, factor=%r, user=%r, range=%r)" %  \
            (self.order, self.factor, self.user, self.range_raw)

    def __str__(self):
        return "%s's range is: %s" %  \
            (self.user.screenname, self.range_raw)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryUserRange
        """
        user_details = UserDetails.from_user(item.user)
        return cls(item.order, item.factor, user_details, item.range_raw)

    def should_include_for(self, userid, all_userids, is_finished,
                           public_ranges):
        """
        Ranges are only shown to the current user, while the game is running -
        at least in competition mode.
        """
        # pylint:disable=unused-argument
        return public_ranges or is_finished or self.user.userid == userid

class GameItemRangeAction(GameItem):
    """
    user folds fold_range, checks or calls passive_range, bets or raises
    aggressive_range
    """
    def __init__(self, order, factor, user, range_action, is_check, is_raise,
                 fold_ratio, passive_ratio, aggressive_ratio):
        """
        user is a UserDetails
        """
        self.order = order
        self.factor = factor
        self.user = user
        self.range_action = range_action
        self.is_check = is_check
        self.is_raise = is_raise
        self.fold_ratio = fold_ratio
        self.passive_ratio = passive_ratio
        self.aggressive_ratio = aggressive_ratio

    def __repr__(self):
        return ("GameItemRangeAction(order=%r, factor=%r, user=%r,"
                " range_action=%r, is_check=%r, is_raise=%r,"
                " fold_ratio=%r, passive_ratio=%r, aggressive_ratio=%r)") %  \
            (self.order, self.factor, self.user, self.range_action,
             self.is_check, self.is_raise,
             self.fold_ratio, self.passive_ratio, self.aggressive_ratio)

    def __str__(self):
        return "%s performs range-based action: %s" % (self.user,
                                                       self.range_action)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryRangeAction
        """
        user_details = UserDetails.from_user(item.user)
        range_action = ActionDetails(fold_raw=item.fold_range,
            passive_raw=item.passive_range,
            aggressive_raw=item.aggressive_range,
            raise_total=item.raise_total)
        return cls(item.order, item.factor, user_details, range_action,
                   item.is_check, item.is_raise,
                   item.fold_ratio, item.passive_ratio, item.aggressive_ratio)

    def should_include_for(self, userid, all_userids, is_finished,
                           public_ranges):
        """
        Range actions are only shown to the user who makes them, while the game
        is running - at least in competition mode.
        """
        # pylint:disable=unused-argument
        return public_ranges or is_finished or self.user.userid == userid

class GameItemActionResult(GameItem):
    """
    User's range action results in an action
    """
    def __init__(self, order, factor, user, action_result):
        """
        user is a UserDetails
        """
        self.order = order
        self.factor = factor
        self.user = user
        self.action_result = action_result

    def __repr__(self):
        return ("GameItemActionResult(order=%r, factor=%r, user=%r, " +
                "action_result=%r)") %  \
            (self.order, self.factor, self.user, self.action_result)

    def __str__(self):
        return "%s performs action: %s" % (self.user,
                                           self.action_result)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryActionResult
        """
        user_details = UserDetails.from_user(item.user)
        action_result = ActionResult(is_fold=item.is_fold,
                                     is_passive=item.is_passive,
                                     is_aggressive=item.is_aggressive,
                                     call_cost=item.call_cost,
                                     raise_total=item.raise_total,
                                     is_raise=item.is_raise)
        return cls(item.order, item.factor, user_details, action_result)

class GameItemBoard(GameItem):
    """
    The board at street is cards
    """
    def __init__(self, order, factor, street, cards):
        """
        they're both strings
        """
        self.order = order
        self.factor = factor
        self.street = street
        self.cards = cards

    def __repr__(self):
        return "GameItemBoard(order=%r, factor=%r, street=%r, cards=%r)" %  \
            (self.order, self.factor, self.street, self.cards)

    def __str__(self):
        if self.street == FLOP:
            return "%s: %s" % (self.street, self.cards)
        elif self.street == TURN:
            return "%s: %s %s" % (self.street, self.cards[0:6], self.cards[6:])
        elif self.street == RIVER:
            return "%s: %s %s %s" % (self.street, self.cards[0:6],
                                     self.cards[6:8], self.cards[8:10])
        else:
            # Unknown, but probably PREFLOP, but shouldn't happen.
            return "(unknown street) %s: %s" % (self.street, self.cards)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryBoard
        """
        return cls(item.order, item.factor, item.street, item.cards)

class GameItemTimeout(GameItem):
    """
    User has timed out.
    """
    def __init__(self, order, factor, user):
        """
        user is a UserDetails
        """
        self.order = order
        self.factor = factor
        self.user = user

    def __repr__(self):
        return ("GameItemTimeout(order=%r, factor=%r, user=%r)") %  \
            (self.order, self.factor, self.user)

    def __str__(self):
        return "%s has timed out" % (self.user,)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryTimeout
        """
        user_details = UserDetails.from_user(item.user)
        return cls(item.order, item.factor, user_details)

class GameItemChat(GameItem):
    """
    User chats message.
    """
    def __init__(self, order, factor, user, message):
        """
        user is a UserDetails
        """
        self.order = order
        self.factor = factor
        self.user = user
        self.message = message

    def __repr__(self):
        return "GameItemChat(order=%r, factor=%r, user=%r, message=%r)" %  \
            (self.order, self.factor, self.user, self.message)

    def __str__(self):
        return "%s chats: %s" % (self.user, self.message)

    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryChat
        """
        user_details = UserDetails.from_user(item.user)
        return cls(item.order, item.factor, user_details, item.message)

    def should_include_for(self, userid, all_userids, is_finished,
                           public_ranges):
        """
        Private to game, even when game is finished
        """
        # pylint:disable=unused-argument
        return userid in all_userids

class GameItemShowdown(GameItem):
    STREET_DESCRIPTIONS = {PREFLOP: "Preflop",
                           FLOP: "On the flop",
                           TURN: "On the turn",
                           RIVER: "On the river",
                           None: "After the hand"}
    """
    Showdown, including pot size, players, and equities.
    """
    def __init__(self, order, factor, is_passive, pot, equities):
        self.order = order
        self.factor = factor
        self.is_passive = is_passive
        self.pot = pot
        self.equities = equities

    def __repr__(self):
        return "GameItemShowdown(order=%r, factor=%r, is_passive=%r, "  \
            "pot=%r, equities=%r)" %  \
            (self.order, self.factor, self.is_passive, self.pot, self.equities)

    def __str__(self):
        return "Showdown between %s for %d chips" %  \
            (self.players_desc(), self.pot)

    def players_desc(self):
        """
        Return a string like "Player A, Player B and Player C".
        """
        if len(self.equities) == 0:
            return "(unknown players)"
        first_showdowners = ", ".join([str(eq.user)
                                       for eq in self.equities[:-1]])
        return " and ".join([first_showdowners,
                                    str(self.equities[-1].user)])


    @classmethod
    def from_history_item(cls, item):
        """
        Create from a GameHistoryShowdown, and its GameHistoryShowdownItems
        """
        # participants naturally sorted by showdown order
        equities = [GameItemShowdownEquity(participant)
                    for participant in item.participants]
        return cls(item.order, item.factor, item.is_passive, item.pot, equities)

    def should_include_for(self, userid, all_userids, is_finished,
                           public_ranges):
        """
        We should include showdowns in hand histories only once the hand is
        over.
        """
        # pylint:disable=unused-argument
        return is_finished

class GameItemShowdownEquity(object):
    """
    Equity for a player at showdown
    """
    def __init__(self, equity_item):
        """
        Create from a GameHistoryShowdownEquity
        """
        self.user = UserDetails.from_user(equity_item.user)
        self.equity = equity_item.equity

    def __repr__(self):
        return "GameItemShowdownEquity(user=%r, equity=%r)" %  \
            (self.user, self.equity)

class GamePayment(object):
    """
    A payment to a player
    """
    def __init__(self, payment_to_player):
        """
        Create from a PAymentToPlayer
        """
        self.user = UserDetails.from_user(payment_to_player.user)
        self.reason = payment_to_player.reason
        self.amount = payment_to_player.amount

    def __repr__(self):
        return "GamePayment(user=%r, reason=%r, amount=%r)" %  \
            (self.user, self.reason, self.amount)

class AnalysisItemFoldEquityItem(object):
    """
    All about the fold equity of betting a particular combo.
    """
    def __init__(self, cards, is_aggressive, is_passive, is_fold, fold_ratio,
                 immediate_result, semibluff_ev, semibluff_equity):
        self.cards = cards
        self.is_aggressive = is_aggressive
        self.is_passive = is_passive
        self.is_fold = is_fold
        self.fold_ratio = float(fold_ratio)
        self.immediate_result = float(immediate_result)
        self.semibluff_ev = float(semibluff_ev) if semibluff_ev else None
        self.semibluff_equity =  \
            float(semibluff_equity) if semibluff_equity else None

    def __repr__(self):
        return "AnalysisItemFoldEquityItem(cards=%r, fold_ratio=%r, "  \
            "immediate_result=%r, semibluff_ev=%r, semibluff_equity=%r)" %  \
            (self.cards, self.fold_ratio, self.immediate_result,
             self.semibluff_ev, self.semibluff_equity)

    @classmethod
    def from_afei(cls, afei):
        """
        Create from AnalysisFoldEquityItem
        """
        cards = [Card.from_text(afei.higher_card),
                 Card.from_text(afei.lower_card)]
        return cls(cards, afei.is_aggressive, afei.is_passive, afei.is_fold,
            afei.fold_ratio, afei.immediate_result,
            afei.semibluff_ev,
            afei.semibluff_equity)

class AnalysisItemFoldEquity(object):
    """
    All about the fold equity of a betting range.
    """
    STREET_DESCRIPTIONS = {PREFLOP: "Preflop",
                           FLOP: "On the flop",
                           TURN: "On the turn",
                           RIVER: "On the river",
                           None: "After the hand"}

    def __init__(self, bettor, street, pot_before_bet, is_raise, is_check,
                 bet_cost, raise_total, pot_if_called, items):
        # bettor is a UserDetails
        self.bettor = bettor
        self.street = street
        self.pot_before_bet = pot_before_bet
        self.is_raise = is_raise
        self.is_check = is_check
        self.bet_cost = bet_cost
        self.raise_total = raise_total
        self.pot_if_called = pot_if_called
        self.items = items

    def __repr__(self):
        return "AnalysisItemFoldEquity(bettor=%r, street=%r, "  \
            "pot_before_bet=%r, is_raise=%r, is_check=%r, bet_cost=%r, "  \
            "raise_total=%r, pot_if_called=%r, items=%r)" %  \
            (self.bettor, self.street, self.pot_before_bet, self.is_raise,
             self.is_check, self.bet_cost, self.raise_total, self.pot_if_called,
             self.items)

    @classmethod
    def from_afe(cls, afe):
        """
        Create from AnalysisFoldEquity
        """
        bettor = UserDetails.from_user(afe.action_result.user)
        items = [AnalysisItemFoldEquityItem.from_afei(item)
                 for item in afe.items]
        items.sort(key=lambda item: (-item.immediate_result, item.cards),
                   reverse=True)
        return cls(bettor, afe.street, afe.pot_before_bet, afe.is_raise,
                   afe.is_check, afe.bet_cost, afe.raise_total,
                   afe.pot_if_called, items)

MAP_TABLE_DTO = {tables.GameHistoryUserRange: GameItemUserRange,
                 tables.GameHistoryRangeAction: GameItemRangeAction,
                 tables.GameHistoryActionResult: GameItemActionResult,
                 tables.GameHistoryBoard: GameItemBoard,
                 tables.GameHistoryTimeout: GameItemTimeout,
                 tables.GameHistoryChat: GameItemChat,
                 tables.GameHistoryShowdown: GameItemShowdown}

class RunningGameDetails(object):
    """
    Details of a game, including game state.

    More info than RunningGameSummary. Included in a RunningGameHistory.
    """
    # TODO: REVISIT: Perhaps the 1:1 relationship between RunningGameDetails and
    # RunningGameHistory implies that they should be combined. But perhaps it
    # doesn't!
    def __init__(self, gameid, public_ranges, situation, current_player,
                 board_raw, current_round, pot_pre, increment, bet_count,
                 current_factor, spawn_factor, spawn_group, rgp_details):
        self.gameid = gameid
        self.public_ranges = public_ranges
        self.situation = situation  # SituationDetails
        self.current_player = current_player # RGPDetails
        self.board_raw = board_raw
        self.current_round = current_round
        self.pot_pre = pot_pre
        self.increment = increment
        self.bet_count = bet_count
        self.current_factor = current_factor
        self.spawn_factor = spawn_factor
        self.spawn_group = spawn_group
        self.rgp_details = rgp_details  # list of RunningGameParticipantDetails

    def __repr__(self):
        return ("RunningGameDetails(gameid=%r, public_ranges=%r, situation=%r, "
                "current_player=%r, board_raw=%r, current_round=%r, "
                "pot_pre=%r, increment=%r, bet_count=%r, current_factor=%r, "
                "spawn_factor=%r, spawn_group=%r, rgp_details=%r") %  \
            (self.gameid, self.public_ranges, self.situation,
             self.current_player, self.board_raw, self.current_round,
             self.pot_pre, self.increment, self.bet_count, self.current_factor,
             self.spawn_factor, self.spawn_group, self.rgp_details)

    @classmethod
    def from_running_game(cls, game):
        """
        Create object from tables.RunningGame
        """
        situation = SituationDetails.from_situation(game.situation)
        rgp_details = [RunningGameParticipantDetails.from_rgp(rgp)
                       for rgp in game.rgps]
        current_players = [r for r in rgp_details
                           if r.user.userid == game.current_userid]
        current_player = current_players[0] if current_players else None
        spawn_group = game.spawn_group if game.spawn_group is not None  \
            else game.gameid
        return cls(game.gameid, game.public_ranges, situation, current_player,
                   game.board_raw, game.current_round, game.pot_pre,
                   game.increment, game.bet_count, game.current_factor,
                   game.spawn_factor, spawn_group, rgp_details)

    def is_finished(self):
        """
        True when the game is finished.
        """
        return self.current_round == FINISHED

class RunningGameHistory(object):
    """
    Everything about a running game.

    This will contain range data for both players if the game is finished, for
    one player if that user is requesting this object, or for no one if this is
    a public view of a running game.

    It will contain analysis only if the game is finished.

    Includes a RunningGameDetails.
    """
    def __init__(self, game_details, current_options, history_items,
                 payment_items, analysis_items):
        self.game_details = game_details
        self.current_options = current_options
        self.history = history_items
        self.payments = payment_items
        self.analysis = analysis_items

    def __repr__(self):
        return "RunningGameHistory(game_details=%r, current_options=%r, "  \
            "history=%r, analysis=%r)" %  \
            (self.game_details, self.current_options, self.history,
             self.analysis)

    def is_finished(self):
        """
        True when the game is finished.
        """
        return self.game_details.is_finished()

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
        return "ActionOptions(call_cost=%r, is_raise=%r, min_raise=%r, "  \
            "max_raise=%r)" % (self.call_cost, self.is_raise, self.min_raise,
                               self.max_raise)

    def can_check(self):
        """
        Does the user have the option to check?
        """
        # Note that this is cost to call, not total contribution once called.
        # Which is why it works for checking in the big blind.
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
            raise ValueError("No raise total")

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
                "aggressive_range=%r, raise_total=%r") %  \
            (self.fold_range, self.passive_range, self.aggressive_range,
             self.raise_total)

    def __str__(self):
        return "folding %s, passive %s, aggressive (to %d) %s" %  \
            (self.fold_range.description, self.passive_range.description,
             self.raise_total, self.aggressive_range.description)

class ActionResult(object):
    """
    response to a range-based action request, tells the user what happened
    """
    def __init__(self, is_fold=False, is_passive=False,
                 is_aggressive=False, call_cost=None, raise_total=None,
                 is_terminate=False, is_raise=False):
        if len([b for b in [is_fold, is_passive, is_aggressive] if b]) != 1  \
            and not is_terminate:
            raise ValueError("Specify only one type of action for a response")
        if is_passive and call_cost is None:
            raise ValueError("Specify a call cost when is_passive")
        if is_aggressive and raise_total is None:
            raise ValueError("Specify a raise total when is_aggressive")
        if is_terminate and (is_fold or is_passive or is_aggressive or
                             call_cost is not None or raise_total is not None):
            raise ValueError("is_terminate only, or not at all")
        self.is_fold = is_fold
        self.is_passive = is_passive
        self.is_aggressive = is_aggressive
        self.call_cost = call_cost
        self.raise_total = raise_total
        self.is_terminate = is_terminate
        self.is_raise = is_raise

    @classmethod
    def fold(cls):
        """
        User folded
        """
        return ActionResult(is_fold=True)

    @classmethod
    def call(cls, call_cost):
        """
        User checked or called
        """
        return ActionResult(is_passive=True, call_cost=call_cost)

    @classmethod
    def raise_to(cls, raise_total, is_raise):
        """
        User bet or raised
        """
        return ActionResult(is_aggressive=True, raise_total=raise_total,
                            is_raise=is_raise)

    @classmethod
    def terminate(cls):
        """
        This action terminates the hand. No fold, passive or aggressive is
        recorded.
        """
        return ActionResult(is_terminate=True)

    def to_action(self):
        """
        Convert to game tree action code
        """
        if self.is_fold:
            return FOLD
        if self.is_passive:
            if self.call_cost:
                return CALL
            return CHECK
        if self.is_raise:
            return RAISE
        return BET

    def __str__(self):
        # pylint:disable=R0911
        if self.is_fold:
            return "fold"
        if self.is_passive:
            if self.call_cost:
                return "call %d" % (self.call_cost,)
            else:
                return "check"
        if self.is_aggressive:
            if self.is_raise:
                return "raise to %d" % (self.raise_total,)
            else:
                return "bet %d" % (self.raise_total,)
        if self.is_terminate:
            return "(terminate)"
        return "(inexplicable)"

    def __repr__(self):
        return ("ActionResult(is_fold=%r, is_passive=%r, " +
                "is_aggressive=%r, call_cost=%r, raise_total=%r, " +
                "is_terminate=%r, is_raise=%r)") %  \
            (self.is_fold, self.is_passive, self.is_aggressive,
             self.call_cost, self.raise_total, self.is_terminate, self.is_raise)

    def __eq__(self, other):
        return self.is_fold == other.is_fold and  \
               self.is_passive == other.is_passive and  \
               self.is_aggressive == other.is_aggressive and  \
               self.call_cost == other.call_cost and  \
               self.raise_total == other.raise_total and  \
               self.is_terminate == other.is_terminate and  \
               self.is_raise == other.is_raise

    def __ne__(self, other):
        return not self.__eq__(other)
