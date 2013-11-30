"""
Core API for Range vs. Range backend.
"""
from rvr.db.creation import BASE, ENGINE, create_session
from rvr.db import tables
from rvr.core import dtos
from functools import wraps
import logging
import random
from sqlalchemy.exc import IntegrityError
import itertools

#pylint:disable=R0903

GAME_HISTORY_TABLES = [tables.GameHistoryUserRange]

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
        situation = tables.Situation()
        situation.description = "Heads-up preflop, 100 BB"
        situation.participants = 2
        self.session.add(situation)
    
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
        results = [dtos.RunningGameDetails.from_running_game(game)
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
        running_games = [dtos.RunningGameDetails.from_running_game(rgp.game)
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
        running_game = tables.RunningGame()
        running_game.next_hh = 0
        running_game.game = open_game
        running_game.situation = open_game.situation
        running_game.current_userid = random.choice(open_game.ogps).userid
        self.session.add(running_game)
        self.session.flush()  # get gameid from database
        for order, ogp in enumerate(open_game.ogps + [final_ogp]):
            rgp = tables.RunningGameParticipant()
            rgp.gameid = running_game.gameid
            rgp.userid = ogp.userid  # haven't loaded users, so just copy userid
            rgp.order = order
            self.session.add(rgp)
            self.session.flush()  # populate game
            self._set_rgp_range(rgp, "")
        self.session.delete(open_game)  # cascades to ogps
        logging.debug("Started game %d", open_game.gameid)
        return running_game
    
    def _set_rgp_range(self, rgp, range_):
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
        range_element.range_ = range_
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
    
    ERR_LEAVE_GAME_NOT_IN = APIError("User was not registered")
    
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
            return self.ERR_LEAVE_GAME_NOT_IN
        game.participants -= 1        
        # I don't know why, but flush here causes ensure_open_games to fail.
        # Failure to merge appropriately?
        self.session.commit()
        logging.debug("User %d left game %d", userid, gameid)
        self.ensure_open_games()        
    
    @api
    def perform_action(self, gameid, userid, range_action):
        """
        Performs range_action for specified user in specified game.
        
        Fails if:
         - game is not a running game with user in it
         - it's not user's turn
         - range_action does not sum to user's current range
        """
        # TODO: perform_action
        
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
        filtered_dtos = [dto for dto in child_dtos
                         if is_finished or dto.should_include_for(userid)]
        return filtered_dtos
        
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
        return dtos.RunningGameHistory(game_details, history_items)
    
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
