"""
Core API for Range vs. Range backend.
"""
from rvr.core.dtos import OpenGameDetails, UserDetails, \
    RunningGameDetails, FinishedGameDetails, UsersGameDetails, DetailedUser
from rvr.db.creation import BASE, ENGINE, create_session
from rvr.db.tables import User, Situation, OpenGame, OpenGameParticipant, \
    RunningGame, RunningGameParticipant, FinishedGameParticipant
from functools import wraps
import logging
import random
from sqlalchemy.exc import IntegrityError

#pylint:disable=R0903

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
        # pylint:enable=W0703
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
        situation = Situation()
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
        matches = self.session.query(User)  \
            .filter(User.identity == request.identity)  \
            .filter(User.email == request.email).all()
        if matches:
            # return user from database
            user = matches[0]
            return UserDetails.from_user(user)
        else:
            # create user in database
            user = User()
            user.identity = request.identity
            user.email = request.email
            user.screenname = request.screenname
            self.session.add(user)
            try:
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                # special error if it's just screenname (most likely cause)
                matches = self.session.query(User)  \
                    .filter(User.screenname == request.screenname).all()
                if matches:
                    return self.ERR_LOGIN_DUPLICATE_SCREENNAME
                else:
                    raise
            logging.debug("Created user %d with screenname '%s'",
                          user.userid, user.screenname)
            return UserDetails.from_user(user)
            
    @api
    def change_screenname(self, request):
        """
        Change user's screenname
        """
        self.session.query(User).filter(User.userid == request.userid)  \
            .one().screenname = request.screenname
    
    @api
    def get_user(self, userid):
        """
        Get user's LoginDetails
        """
        matches = self.session.query(User)  \
            .filter(User.userid == userid).all()
        if not matches:
            return self.ERR_NO_SUCH_USER
        user = matches[0]
        return DetailedUser(userid=user.userid,
                            identity=user.identity,
                            email=user.email,
                            screenname=user.screenname)
    
    @api
    def delete_user(self, userid):
        """
        Delete user if not playing any games.
        """
        matches = self.session.query(User).filter(User.userid == userid).all()
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
        matches = self.session.query(User)  \
            .filter(User.screenname == screenname).all()
        if matches:
            user = matches[0]
            return UserDetails.from_user(user)
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
        all_open_games = self.session.query(OpenGame).all()
        results = [OpenGameDetails.from_open_game(game)
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
        all_running_games = self.session.query(RunningGame).all()
        results = [RunningGameDetails.from_running_game(game)
                   for game in all_running_games]
        return results
    
    @api
    def get_user_games(self, userid):
        """
        3. Retrieve user's games and their statuses
        inputs: userid
        outputs: list of user's games. each may be open game, running (not our turn),
        running (our turn), finished. no more details of each game.
        
        Note: we don't validate that userid is a real userid!
        """
        rgps = self.session.query(RunningGameParticipant)  \
            .filter(RunningGameParticipant.userid == userid).all()
        running_games = [RunningGameDetails.from_running_game(rgp.game)
                         for rgp in rgps]
        fgps = self.session.query(FinishedGameParticipant)  \
            .filter(FinishedGameParticipant.userid == userid).all()
        finished_games = [FinishedGameDetails.from_finished_game(fgp.game)
                          for fgp in fgps]
        return UsersGameDetails(userid, running_games, finished_games)
    
    def _start_game(self, open_game):
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
        running_game = RunningGame()
        running_game.gameid = open_game.gameid
        running_game.situationid = open_game.situationid
        running_game.current_userid = random.choice(open_game.ogps).userid
        self.session.delete(open_game)
        self.session.add(running_game)
        for order, ogp in enumerate(open_game.ogps):
            rgp = RunningGameParticipant()
            rgp.game = running_game
            rgp.userid = ogp.userid  # haven't loaded users, so just copy userid
            rgp.order = order
            self.session.delete(ogp)
            self.session.add(rgp)
        logging.debug("Started game %d", open_game.gameid)
        return running_game
    
    @api
    def join_game(self, userid, gameid):
        # TODO: call this from the front end (join_game)
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
        games = self.session.query(OpenGame)  \
            .filter(OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = self.session.query(User).filter(User.userid == userid).all()
        if not users:
            return self.ERR_NO_SUCH_USER
        user = users[0]
        if any(ogp.userid == userid for ogp in game.ogps):
            return self.ERR_JOIN_GAME_ALREADY_IN
        game.participants += 1
        if game.participants > game.situation.participants:
            return self.ERR_JOIN_GAME_GAME_FULL
        
        # add user to game
        ogp = OpenGameParticipant()
        ogp.game = game
        ogp.user = user
        self.session.add(ogp)
    
        # start game?
        start_game = game.participants == game.situation.participants
        if start_game:
            self.session.flush()
            running_game = self._start_game(game)
        else:
            running_game = None
            
        try:
            # This commits both the add, and the start game if present.
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
        # TODO: call this from the front end (leave_game)
        """
        4. Leave/cancel game we're in
        inputs: userid, gameid
        outputs: (none)
        """
        # check error conditions
        games = self.session.query(OpenGame)  \
            .filter(OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = self.session.query(User).filter(User.userid == userid).all()
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
    def perform_action(self):
        """
        6. Perform action in game we're in
        inputs: userid, gameid, action
        outputs: (none)
        """
        # TODO: perform_action
    
    @api
    def get_public_game(self):
        """
        7. Retrieve game history without current player's ranges
        inputs: gameid
        outputs: hand history populated with ranges iff finished
        """
        # TODO: get_public_game
        # To start with, just return basic details of the game
    
    @api
    def get_private_game(self):
        """
        8. Retrieve game history with current player's ranges
        inputs: userid, gameid
        outputs: hand history partially populated with ranges for userid only
        """
        # TODO: get_private_game
        # To start with, just do what get_public_game does
    
    @api
    def ensure_open_games(self):
        """
        Ensure there is exactly one empty open game for each situation in the
        database.
        """
        for situation in self.session.query(Situation).all():
            empty_open = self.session.query(OpenGame)  \
                .filter(Situation.situationid == situation.situationid)  \
                .filter(OpenGame.participants == 0).all()
            if len(empty_open) > 1:
                # delete all except one
                for game in empty_open[:-1]:
                    logging.debug("Deleted open game %d for situation %d",
                                  game.gameid, situation.situationid)
                    self.session.delete(game)
            elif len(empty_open) == 0:
                # add one!
                new_game = OpenGame()
                new_game.situationid = situation.situationid
                new_game.participants = 0
                self.session.add(new_game)
                self.session.flush()  # get gameid
                logging.debug("Created open game %d for situation %d",
                              new_game.gameid, situation.situationid)
