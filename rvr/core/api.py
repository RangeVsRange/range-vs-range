from rvr.core.dtos import LoginDetails, OpenGameDetails, UserDetails,\
    RunningGameDetails
from rvr.db.creation import BASE, ENGINE, with_session
from rvr.db.tables import User, Situation, OpenGame, OpenGameParticipant,\
    RunningGame, RunningGameParticipant, FinishedGame, FinishedGameParticipant
from functools import wraps
import logging
import random

hack = False

def exception_mapper(fun):
    """
    Converts database exceptions to APIError
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        Catch exceptions and return API.ERR_UNKNOWN
        """
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
        @with_session
        
    Used to ensure exception_mapper and with_session are applied in the correct
    order.
    """
    @wraps(fun)
    @exception_mapper
    @with_session
    def inner(*args, **kwargs):
        return fun(*args, **kwargs)
    return inner

class APIError(object):
    def __init__(self, description):
        self.description = description
    
    def __str__(self):
        return self.description

class API(object):
    """
    A reference to the backend. You can have more than one reference to the same
    backend. You can also have references to multiple backends, but I don't
    expect that to happen.
    """
    ERR_UNKNOWN = APIError("Internal error")
    ERR_NO_SUCH_USER = APIError("No such user")
    ERR_NO_SUCH_OPEN_GAME = APIError("No such open game")
    
    def __init__(self):
        """
        Initialises a connection to the backend
        """
        pass
    
    @api
    def create_db(self, session):
        """
        Create and seed the database
        """
        BASE.metadata.create_all(ENGINE)
        
    @api
    def initialise_db(self, session):
        """
        Create initial data for database
        """
        situation = Situation()
        situation.description = "Heads-up preflop, 100 BB"
        situation.participants = 2
        session.add(situation)
    
    @api
    def login(self, request, session):
        """
        1. Create or validate OpenID-based account
        inputs: provider, email, screenname
        outputs: userid
        """
        if request.userid is not None:
            raise Exception("don't specify a userid when logging in")
        matches = session.query(User)  \
            .filter(User.provider == request.provider)  \
            .filter(User.email == request.email)  \
            .filter(User.screenname == request.screenname).all()
        if matches:
            # return user from database
            user = matches[0]
            return LoginDetails(userid=user.userid,
                                provider=user.provider,
                                email=user.email,
                                screenname=user.screenname)
        else:
            # create user in database
            user = User()
            session.add(user)
            user.provider = request.provider
            user.email = request.email
            user.screenname = request.screenname
            return LoginDetails(userid=user.userid,
                                provider=user.provider,
                                email=user.email,
                                screenname=user.screenname)
    
    @api
    def get_user_by_screenname(self, screenname, session):
        """
        Return list of all users userid, screenname
        """
        matches = session.query(User)  \
            .filter(User.screenname == screenname).all()
        if matches:
            user = matches[0]
            return UserDetails(user.userid, user.screenname)
        else:
            return None
    
    @api
    def get_open_games(self, session):
        """
        2. Retrieve open games including registered users
        inputs: (none)
        outputs: List of open games. For each game, users in game, details of
                 game
        """
        all_open_games = session.query(OpenGame).all()
        results = [OpenGameDetails.from_open_game(game)
                   for game in all_open_games]
        return results
    
    @api
    def get_running_games(self, session):
        """
        Retrieve running games including registered users
        input: (none)
        outputs: List of running games. For each game, users in game, details
                 of game
        """
        all_running_games = session.query(RunningGame).all()
        results = [RunningGameDetails.from_running_game(game)
                   for game in all_running_games]
        return results
    
    @api
    def get_user_games(self, session, userid):
        """
        3. Retrieve user's games and their statuses
        inputs: userid
        outputs: list of user's games. each may be open game, running (not our turn),
        running (our turn), finished. no more details of each game.
        """
        # TODO:
        
    def _start_game(self, session, open_game):
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
        session.delete(open_game)
        session.add(running_game)
        for ogp in open_game.ogps:
            rgp = RunningGameParticipant()
            rgp.game = running_game
            rgp.userid = ogp.userid  # haven't loaded users, so just copy userid
            session.delete(ogp)
            session.add(rgp)
        return running_game

    ERR_JOIN_GAME_ALREADY_IN = APIError("User is already registered")
    ERR_JOIN_GAME_GAME_FULL = APIError("Game is full")

    @api
    def join_game(self, userid, gameid, session):
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
        games = session.query(OpenGame)  \
            .filter(OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = session.query(User).filter(User.userid == userid).all()
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
        session.add(ogp)

        # start game?
        start_game = game.participants == game.situation.participants
        if start_game:
            session.flush()
            running_game = self._start_game(session, game)
        else:
            running_game = None
            
        try:
            # This commits both the add, and the start game if present.
            # This is important so that there are never duplicate game ids.
            session.commit()  # explicitly check that it commits okay
        except Exception as _ex:
            # An error will occur if game no longer exists, or user no longer
            # exists, or user has already been added to game, or game has
            # already been filled, or problems with starting the game!
            session.rollback()
            # Complete fail, okay, here we just try again!
            running_game = self.join_game(userid, gameid, session)

        self.ensure_open_games(session)

        # it's committed, so we will have the id
        if running_game is not None:
            return running_game.gameid

    ERR_LEAVE_GAME_NOT_IN = APIError("User was not registered")

    @api
    def leave_game(self, userid, gameid, session):
        """
        4. Leave/cancel game we're in
        inputs: userid, gameid
        outputs: (none)
        """
        # check error conditions
        games = session.query(OpenGame)  \
            .filter(OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = session.query(User).filter(User.userid == userid).all()
        if not users:
            return self.ERR_NO_SUCH_USER
        for ogp in game.ogps:
            if ogp.userid == userid:
                session.delete(ogp)
                break
        else:
            return self.ERR_LEAVE_GAME_NOT_IN
        game.participants -= 1        
        # I don't know why, but flush here causes
        # ensure_open_games to fail.
        session.commit()  # TODO: Why won't flush work?
        self.ensure_open_games(session)        

    @api
    def perform_action(self, session):
        """
        6. Perform action in game we're in
        inputs: userid, gameid, action
        outputs: (none)
        """
        # TODO:
    
    @api
    def get_public_game(self, session):
        """
        7. Retrieve game history without current player's ranges
        inputs: gameid
        outputs: hand history populated with ranges iff finished
        """
        # TODO:
        # To start with, just return basic details of the game

    @api
    def get_private_game(self, session):
        """
        8. Retrieve game history with current player's ranges
        inputs: userid, gameid
        outputs: hand history partially populated with ranges for userid only
        """
        # TODO:
        # To start with, just do what get_public_game does
    
    @api
    def ensure_open_games(self, session):
        """
        Ensure there is exactly one empty open game for each situation in the
        database.
        """
        for situation in session.query(Situation).all():
            empty_open = session.query(OpenGame)  \
                .filter(Situation.situationid == situation.situationid)  \
                .filter(OpenGame.participants == 0).all()
            if len(empty_open) > 1:
                # delete all except one
                for game in empty_open[:-1]:
                    logging.debug("Deleted open game %d for situation %d",
                                  game.gameid, situation.situationid)
                    session.delete(game)
            elif len(empty_open) == 0:
                # add one!
                new_game = OpenGame()
                new_game.situationid = situation.situationid
                new_game.participants = 0
                session.add(new_game)
                session.flush()  # get gameid
                logging.debug("Created open game %d for situation %d",
                              new_game.gameid, situation.situationid)
                