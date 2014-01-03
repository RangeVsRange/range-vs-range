"""
Core API for Range vs. Range backend.
"""
from rvr.db.creation import BASE, ENGINE, create_session
from rvr.db import tables
from rvr.core import dtos
from functools import wraps
import logging
from sqlalchemy.exc import IntegrityError
import itertools
from rvr.poker.handrange import deal_from_ranges
from rvr.poker.action import range_action_fits, calculate_current_options,  \
    PREFLOP, RIVER, re_deal, range_action_to_action

#pylint:disable=R0903

GAME_HISTORY_TABLES = [tables.GameHistoryUserRange]

# def validate_action(action, options, range_raw):
#     """
#     Check that action is valid and return any error.
#     """
#     action.raise_total = int(action.raise_total)
#     if options.can_raise() and (action.raise_total < options.min_raise or
#                                 action.raise_total > options.max_raise):
#         return API.ERR_INVALID_RAISE_TOTAL
#     fold_range = HandRange(action.fold_range)
#     passive_range = HandRange(action.passive_range)
#     aggressive_range = HandRange(action.aggressive_range)
#     original_range = HandRange(range_raw)
#     # todo: port the old range_action_fits, because this is not enough.
#     # E.g. we don't recognise that it's invalid to have a raising range when
#     # there's no option to raise.
#     # todo: also, port the unit tests!
#     is_valid, _reason = range_sum_equal(fold_range, passive_range,
#                                         aggressive_range, original_range)
#     if is_valid:
#         return None
#     else:
#         return API.ERR_INVALID_RANGES

def exception_mapper(fun):
    """
    Converts database exceptions to APIError
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        Catch exceptions and return API.ERR_UNKNOWN
        """
        # pylint:disable=W0703
        try:
            return fun(*args, **kwargs)
        except Exception as ex:
            logging.debug(ex)
            return API.ERR_UNKNOWN
    return inner

def api(fun):
    """
    Equivalent to:
        @exception_mapper
        @create_session
        
    Used to ensure exception_mapper and create_session are applied in the
    correct order.
    """
    @wraps(fun)
    @exception_mapper
    @create_session
    def inner(*args, **kwargs):
        """
        No additional functionality
        """
        return fun(*args, **kwargs)
    return inner

class APIError(object):
    """
    These objects will be returned by @exception_mapper
    """
    def __init__(self, description):
        self.description = description
    
    def __str__(self):
        return self.description

class API(object):
    """
    Core Range vs. Range API, which may be called by:
     - a website
     - an admin console or command line
     - a thick client
    """
    
    ERR_UNKNOWN = APIError("Internal error")
    ERR_NO_SUCH_USER = APIError("No such user")
    ERR_NO_SUCH_OPEN_GAME = APIError("No such open game")
    ERR_NO_SUCH_RUNNING_GAME = APIError("No such running game")
    ERR_LOGIN_DUPLICATE_SCREENNAME = APIError("Duplicate screenname")
    ERR_JOIN_GAME_ALREADY_IN = APIError("User is already registered")
    ERR_JOIN_GAME_GAME_FULL = APIError("Game is full")
    ERR_DELETE_USER_PLAYING = APIError("User is playing")
    ERR_USER_NOT_IN_GAME = APIError("User is not in the specified game")
    
    def __init__(self):
        self.session = None  # required for @create_session
    
    @exception_mapper
    def create_db(self):
        """
        Create and seed the database
        """
        #pylint:disable=R0201
        BASE.metadata.create_all(ENGINE)
        
    @api
    def initialise_db(self):
        """
        Create initial data for database
        """
        bb = dtos.SituationPlayerDetails(  # pylint:disable=C0103
            stack=198,
            contributed=2,
            left_to_act=True,
            range_raw='anything')
        btn = dtos.SituationPlayerDetails(
            stack=199,
            contributed=1,
            left_to_act=True,
            range_raw='anything')
        situation = dtos.SituationDetails(
            description="Heads-up preflop, 100 BB",
            players=[bb, btn],  # bb acts first in future rounds
            current_player=1,  # btn acts next (this round)
            is_limit=False,
            big_blind=2,
            board_raw='',
            current_round=PREFLOP,
            pot_pre=0,
            increment=2,
            bet_count=1)
        return self._add_situation(situation)
    
    @api
    def login(self, request):
        """
        1. Create or validate OpenID-based account
        inputs: identity, email, screenname
        outputs: userid
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.identity == request.identity)  \
            .filter(tables.User.email == request.email).all()
        if matches:
            # return user from database
            user = matches[0]
            return dtos.UserDetails.from_user(user)
        else:
            # create user in database
            user = tables.User()
            user.identity = request.identity
            user.email = request.email
            user.screenname = request.screenname
            self.session.add(user)
            try:
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                # special error if it's just screenname (most likely cause)
                matches = self.session.query(tables.User)  \
                    .filter(tables.User.screenname == request.screenname).all()
                if matches:
                    return self.ERR_LOGIN_DUPLICATE_SCREENNAME
                else:
                    raise
            logging.debug("Created user %d with screenname '%s'",
                          user.userid, user.screenname)
            return dtos.UserDetails.from_user(user)
            
    @api
    def change_screenname(self, request):
        """
        Change user's screenname
        """
        self.session.query(tables.User)  \
            .filter(tables.User.userid == request.userid)  \
            .one().screenname = request.screenname
    
    @api
    def get_user(self, userid):
        """
        Get user's LoginDetails
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not matches:
            return self.ERR_NO_SUCH_USER
        user = matches[0]
        return dtos.DetailedUser(userid=user.userid,
                                 identity=user.identity,
                                 email=user.email,
                                 screenname=user.screenname)
    
    @api
    def delete_user(self, userid):
        """
        Delete user if not playing any games.
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not matches:
            return self.ERR_NO_SUCH_USER
        user = matches[0]
        if user.rgps or user.fgps:
            return self.ERR_DELETE_USER_PLAYING
        for ogp in user.ogps:
            self.session.delete(ogp)
        self.session.delete(user)
        return True
    
    @api
    def get_user_by_screenname(self, screenname):
        """
        Return userid, screenname
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.screenname == screenname).all()
        if matches:
            user = matches[0]
            return dtos.UserDetails.from_user(user)
        else:
            return None
    
    def _add_situation(self, dto):
        """
        Add a dtos.SituationDetails to the database, as a tables.Situation and
        associated tables.SituationPlayer objects.
        """
        situation = tables.Situation()
        situation.description = dto.description
        situation.participants = len(dto.players)
        situation.is_limit = dto.is_limit
        situation.big_blind = dto.big_blind
        situation.board_raw = dto.board_raw
        situation.current_round = dto.current_round
        situation.pot_pre = dto.pot_pre
        situation.increment = dto.increment
        situation.bet_count = dto.bet_count
        situation.current_player_num = dto.current_player
        self.session.add(situation)
        for order, player in enumerate(dto.players):
            child = tables.SituationPlayer()
            child.situation = situation
            child.order = order
            child.stack = player.stack
            child.contributed = player.contributed
            child.range_raw = player.range_raw
            child.left_to_act = player.left_to_act
            self.session.add(child)
    
    @api
    def get_open_games(self):
        """
        2. Retrieve open games including registered users
        inputs: (none)
        outputs: List of open games. For each game, users in game, details of
                 game
        """
        all_open_games = self.session.query(tables.OpenGame).all()
        results = [dtos.OpenGameDetails.from_open_game(game)
                   for game in all_open_games]
        return results
    
    @api
    def get_running_games(self):
        """
        Retrieve running games including registered users
        input: (none)
        outputs: List of running games. For each game, users in game, details
                 of game
        """
        all_running_games = self.session.query(tables.RunningGame).all()
        results = [dtos.RunningGameSummary.from_running_game(game)
                   for game in all_running_games]
        return results
    
    @api
    def get_user_games(self, userid):
        """
        3. Retrieve user's games and their statuses
        inputs: userid
        outputs: list of user's games. each may be open game, running (not our
        turn), running (our turn), finished. no more details of each game.
        
        Note: we don't validate that userid is a real userid!
        """
        rgps = self.session.query(tables.RunningGameParticipant)  \
            .filter(tables.RunningGameParticipant.userid == userid).all()
        running_games = [dtos.RunningGameSummary.from_running_game(rgp.game)
                         for rgp in rgps]
        return dtos.UsersGameDetails(userid, running_games)
    
    def _start_game(self, open_game, final_ogp):
        """
        Takes the id of a full OpenGame, creates a new RunningGame from it,
        deletes the original and returns the id of the new RunningGame.
        
        This gets called when a game fills up, so that we can immediately tell
        the user that the game was started, and the new running game's id.
        
        Because adding a user to an open game happens in the same context as
        starting the game here, it's not possible for an open game to be left
        full.
        
        Returns RunningGame object, because there is no game id, because the
        object hasn't been committed yet, so the database hasn't created the id
        yet.
        """
        situation = open_game.situation
        all_ogps = open_game.ogps + [final_ogp]
        running_game = tables.RunningGame()
        running_game.next_hh = 0
        running_game.game = open_game
        running_game.situation = situation
        # we have to calculate current userid in advance so we can flush
        running_game.current_userid =  \
            all_ogps[situation.current_player_num].userid
        running_game.board_raw = situation.board_raw
        running_game.current_round = situation.current_round
        running_game.pot_pre = situation.pot_pre
        running_game.increment = situation.increment
        running_game.bet_count = situation.bet_count
        running_game.current_factor = 1.0
        situation_players = situation.ordered_players()
        self.session.add(running_game)
        self.session.flush()  # get gameid from database
        map_to_range = {p: p.range for p in situation.players}
        player_to_dealt = deal_from_ranges(map_to_range, running_game.board)
        for order, (ogp, s_p) in enumerate(zip(all_ogps, situation_players)):
            # create rgps in the order they will act in future rounds
            rgp = tables.RunningGameParticipant()
            rgp.gameid = running_game.gameid
            rgp.userid = ogp.userid  # haven't loaded users, so just copy userid
            rgp.order = order
            rgp.stack = s_p.stack
            rgp.contributed = s_p.contributed
            rgp.range_raw = s_p.range_raw
            rgp.left_to_act = s_p.left_to_act
            rgp.folded = False
            rgp.cards_dealt = player_to_dealt[s_p]
            if situation.current_player_num == order:
                assert running_game.current_userid == ogp.userid
            self.session.add(rgp)
            self.session.flush()  # populate game
            # Note that we do NOT create a range history item for them,
            # it is implied. But if we did, it would look like this:
            # self._set_rgp_range(rgp, "")
        self.session.delete(open_game)  # cascades to ogps
        logging.debug("Started game %d", open_game.gameid)
        return running_game
    
    def _set_rgp_range(self, rgp, range_raw):
        """
        Record that this user now has this range in this game, in the hand
        history.
        """
        base = tables.GameHistoryBase()
        base.gameid = rgp.gameid
        base.order = rgp.game.next_hh
        range_element = tables.GameHistoryUserRange()
        range_element.gameid = base.gameid
        range_element.order = base.order
        range_element.userid = rgp.userid
        range_element.range_raw = range_raw
        rgp.game.next_hh += 1
        self.session.add(base)
        self.session.add(range_element)

    @api
    def join_game(self, userid, gameid):
        """
        5. Join/start game we're not in
        inputs: userid, gameid
        outputs: - running game id if the game started
                 - otherwise nothing
        errors: - gameid doesn't exist
                - userid doesn't exist
                - game is full
                - user is already registered
        """
        # check error conditions
        games = self.session.query(tables.OpenGame)  \
            .filter(tables.OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not users:
            return self.ERR_NO_SUCH_USER
        user = users[0]
        if any(ogp.userid == userid for ogp in game.ogps):
            return self.ERR_JOIN_GAME_ALREADY_IN
        game.participants += 1
        if game.participants > game.situation.participants:
            return self.ERR_JOIN_GAME_GAME_FULL  # This can't happen.

        ogp = tables.OpenGameParticipant()
        ogp.gameid = game.gameid
        ogp.userid = user.userid
            
        # start game?
        start_game = game.participants == game.situation.participants
        if start_game:
            running_game = self._start_game(game, ogp)
        else:
            # add user to game
            self.session.add(ogp)
            running_game = None
            
        try:
            # This commits either the add or the start game.
            # This is important so that there are never duplicate game ids.
            self.session.commit()  # explicitly check that it commits okay
        except IntegrityError as _ex:
            # An error will occur if game no longer exists, or user no longer
            # exists, or user has already been added to game, or game has
            # already been filled, or problems with starting the game!
            self.session.rollback()
            # Complete fail, okay, here we just try again!
            running_game = self.join_game(userid, gameid)
    
        logging.debug("User %d joined game %d", userid, gameid)
    
        self.ensure_open_games()
    
        # it's committed, so we will have the id
        if running_game is not None:
            return running_game.gameid
        
    @api
    def leave_game(self, userid, gameid):
        """
        4. Leave/cancel game we're in
        inputs: userid, gameid
        outputs: (none)
        """
        # check error conditions
        games = self.session.query(tables.OpenGame)  \
            .filter(tables.OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not users:
            return self.ERR_NO_SUCH_USER
        for ogp in game.ogps:
            if ogp.userid == userid:
                self.session.delete(ogp)
                break
        else:
            return self.ERR_USER_NOT_IN_GAME
        game.participants -= 1        
        # I don't know why, but flush here causes ensure_open_games to fail.
        # Failure to merge appropriately?
        self.session.commit()
        logging.debug("User %d left game %d", userid, gameid)
        self.ensure_open_games()        

    ERR_NOT_USERS_TURN = APIError("It's not that user's turn.")
    ERR_INVALID_RAISE_TOTAL = APIError("Invalid raise total.")
    ERR_INVALID_RANGES = APIError("Invalid ranges.")

    def _perform_action(self, game, rgp, range_action, current_options):
        """
        Change game and rgp state. Add relevant hand history items. Possibly
        finish hand.
        
        Assumes validation is already done!
        """
        self.session.commit() # because if we don't we get some ...
        # ... weird circular dependency thing ...
        # ... but hold on, we haven't done anything yet!?! TODO
        left_to_act = [rgp for rgp in game.rgps if rgp.left_to_act]
        remain = [rgp for rgp in game.rgps if not rgp.folded]
        # no play on when 3-handed
        can_fold = len(remain) > 2
        # same condition hold for calling of course, also:
        # preflop, flop and turn, you can call
        # if there's someone else who hasn't acted yet, you can check to them
        can_call = can_fold or game.current_round != RIVER  \
            or len(left_to_act) > 1
        cards_dealt = {rgp: rgp.cards_dealt for rgp in game.rgps}
        terminate, f_ratio, p_ratio, a_ratio = re_deal(range_action,
            cards_dealt, rgp, game.board, can_fold, can_call)
        # TODO: use sizes somehow
        # TODO: add range action and resultant action and current factor changes to hand history
        # TODO: partial payments
        if can_fold:
            pass
        elif can_call:
            game.current_factor *= 1 - f_ratio
        else:
            game.current_factor *= a_ratio
        rgp.range, action_result = range_action_to_action(range_action,
            rgp.range, rgp.cards_dealt, current_options)
        # TODO: need final showdown sometimes (rarely)
        # TODO: update game and current rgp
        return action_result
        
#         range_action.set_sizes(f_ratio, p_ratio, a_ratio)
#         self.hand_history.add_range_action(
#             self.player_client_map[player].name, range_action)
#         self.do_partial_payments(range_action, player, can_fold, can_call, f_ratio, p_ratio, a_ratio)
#         # change current factor before the call or raise goes in because we
#         # re-dealt
#         if can_fold:
#             logging.debug("maintaining current_factor %0.4f", self.current_factor)
#         elif can_call:
#             logging.debug("reducing current_factor for folds from %0.4f by %0.4f to %0.4f", self.current_factor, 1 - f_ratio, self.current_factor * (1 - f_ratio))
#             self.current_factor *= 1 - f_ratio
#         else:
#             logging.debug("reducing current_factor for folds and calls from %0.4f by %0.4f to %0.4f", self.current_factor, a_ratio, self.current_factor * a_ratio)
#             self.current_factor *= a_ratio
#         new_range, action = range_action_to_action(range_action, self.ranges[player], self.cards_dealt[player], self.current_options)
#         logging.debug("changing player '%s' range from '%r' to '%r'", player.name, self.ranges[player], new_range)
#         self.ranges[player] = new_range
#         if isinstance(action, CallAction) and \
#                 self.left_to_act and \
#                 self.already_acted and \
#                 self.round == RIVER:
#             self.need_final_showdown = True
#         self.handleAction(action, terminate, player)
        
        # TO_DO: perform_action
        # TO_DO: NOTE: it might not be their turn any more!
        #return dtos.ActionResponse.call(current_options.call_cost)
        #return dtos.ActionResponse.fold()
        #return dtos.ActionResponse.raise_(range_action.raise_total)
    
    @api
    def perform_action(self, gameid, userid, range_action):
        """
        Performs range_action for specified user in specified game.
        
        Fails if:
         - game is not a running game with user in it
         - it's not user's turn
         - range_action does not sum to user's current range
         - range_action raise_total isn't appropriate
        """
        # check that game exists
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_RUNNING_GAME
        game = games[0]
        # check that they're in the game and it's their turn
        rgp = game.current_rgp
        if game.current_rgp.userid == userid:
            rgp = game.current_rgp
        else:
            return self.ERR_NOT_USERS_TURN
        current_options = calculate_current_options(game, rgp)
        # check that their range action is valid for their options + range
        is_valid, _err = range_action_fits(range_action, current_options,
                                           rgp.range)
        if not is_valid:
            return API.ERR_INVALID_RANGES

        return self._perform_action(game, rgp, range_action, current_options)
        
    def _get_history_items(self, game, userid=None):
        """
        Returns a list of game history items (tables.GameHistoryBase with
        additional details from child tables), with private data only for
        <userid>, if specified.
        """
        # pylint:disable=W0142
        is_finished = game.current_userid is None
        child_items = [self.session.query(table)
                       .filter(table.gameid == game.gameid).all()
                       for table in GAME_HISTORY_TABLES]
        child_dtos = [dtos.GameItem.from_game_history_child(child)
                      for child in itertools.chain(*child_items)]
        return [dto for dto in child_dtos
                if is_finished or dto.should_include_for(userid)]
    
    def _get_game(self, gameid, userid=None):
        """
        Return game <gameid>. If <userid> is not None, return private data for
        the specified user. If the game is finished, return all private data.
        Analysis items are considered private data, because they include both
        players' ranges.
        """
        if userid is not None:
            users = self.session.query(tables.User)  \
                .filter(tables.User.userid == userid).all()
            if not users:
                return self.ERR_NO_SUCH_USER
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_RUNNING_GAME
        game = games[0]
        game_details = dtos.RunningGameDetails.from_running_game(game)
        history_items = self._get_history_items(game, userid)
        if game.current_rgp is None:
            current_options = None
        else:
            current_options = calculate_current_options(game, game.current_rgp)
        return dtos.RunningGameHistory(game_details, history_items,
                                       current_options)        

    @api
    def get_public_game(self, gameid):
        """
        7. Retrieve game history without current player's ranges
        inputs: gameid
        outputs: hand history populated with ranges iff finished
        """
        return self._get_game(gameid)
    
    @api
    def get_private_game(self, gameid, userid):
        """
        8. Retrieve game history with current player's ranges
        inputs: userid, gameid
        outputs: hand history partially populated with ranges for userid only
        """
        return self._get_game(gameid, userid)
    
    @api
    def ensure_open_games(self):
        """
        Ensure there is exactly one empty open game for each situation in the
        database.
        """
        for situation in self.session.query(tables.Situation).all():
            empty_open = self.session.query(tables.OpenGame)  \
                .filter(tables.Situation.situationid ==
                        situation.situationid)  \
                .filter(tables.OpenGame.participants == 0).all()
            if len(empty_open) > 1:
                # delete all except one
                for game in empty_open[:-1]:
                    logging.debug("Deleted open game %d for situation %d",
                                  game.gameid, situation.situationid)
                    self.session.delete(game)
            elif len(empty_open) == 0:
                # add one!
                new_game = tables.OpenGame()
                new_game.situationid = situation.situationid
                new_game.participants = 0
                self.session.add(new_game)
                self.session.flush()  # get gameid
                logging.debug("Created open game %d for situation %d",
                              new_game.gameid, situation.situationid)
