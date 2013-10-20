from rvr.core.dtos import LoginDetails
from rvr.db.creation import SESSION
from rvr.db.tables import User
class API(object):
    """
    A reference to the backend. You can have more than one reference to the same
    backend. You can also have references to multiple backends, but I don't
    expect that to happen.
    """
    def __init__(self):
        """
        Initialises a connection to the backend
        """
        pass
    
    def login(self, request):
        """
        1. Create or validate OpenID-based account
        inputs: provider, email, screenname
        outputs: userid
        """
        if request.userid is not None:
            raise Exception("don't specify a userid when logging in")
        session = SESSION()
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
            session.commit()
            return LoginDetails(userid=user.userid,
                                provider=user.provider,
                                email=user.email,
                                screenname=user.screenname)
    
    def open_games(self):
        """
        2. Retrieve open games including registered users
        inputs: (none)
        outputs: list of open games. for each game, users in game, details of game
        """
    
    def user_games(self):
        """
        3. Retrieve user's games and their statuses
        inputs: userid
        outputs: list of user's games. each may be open game, running (not our turn),
        running (our turn), finished. no more details of each game.
        """

    def leave_game(self):
        """
        4. Leave/cancel game we're in
        inputs: userid, gameid
        outputs: (none)
        """
    
    def join_game(self):
        """
        5. Join/start game we're not in
        inputs: userid, gameid
        outputs: (none)
        """

    def perform_action(self):
        """
        6. Perform action in game we're in
        inputs: userid, gameid, action
        outputs: (none)
        """
    
    def get_public_game(self):
        """
        7. Retrieve game history without current player's ranges
        inputs: gameid
        outputs: hand history populated with ranges iff finished
        """

    def get_user_game(self):
        """
        8. Retrieve game history with current player's ranges
        inputs: userid, gameid
        outputs: hand history partially populated with ranges for userid only
        """    