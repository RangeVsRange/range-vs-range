"""
Admin Cmd class for interacting with API
"""
from cmd import Cmd
import logging
from rvr.core.api import APIError, API
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest
#pylint:disable=R0201,R0904

class AdminCmd(Cmd):
    """
    Cmd class to make calls to an API instance
    """
    def __init__(self):
        Cmd.__init__(self)
        self.api = API()
    
    def do_createdb(self, _details):
        """
        Create the database
        """
        result = self.api.create_db()
        if result:
            print "Error:", result
        else:
            print "Database created"
        result = self.api.initialise_db()
        if result:
            print "Error:", result
        else:
            print "Database initialised"
        result = self.api.ensure_open_games()
        if result:
            print "Error:", result
        else:
            print "Open games refreshed."            
    
    def do_login(self, params):
        """
        Calls the login API function
        login(identity, email, screenname)
        """
        params = params.split(None, 2)
        if len(params) == 3:
            request = LoginRequest(identity=params[0],
                                   email=params[1],
                                   screenname=params[2])
        else:
            print "Need exactly 3 parameters."
            print "For more info, help login"
            return
        response = self.api.login(request)
        if isinstance(response, APIError):
            print "Error:", response
            return
        print "User is logged in with userid='%s', screenname='%s'" % \
            (response.userid, response.screenname)

    def do_getuserid(self, details):
        """
        getuserid <screenname>
        shows userid by screenname
        """
        user = self.api.get_user_by_screenname(details)
        if user is None:
            print "No such user"
        else:
            print "'%s' has userid %s" % (user.screenname, user.userid)
    
    def do_rmuser(self, details):
        """
        rmuser <userid>
        deletes user <userid>
        """
        userid = int(details)
        response = self.api.delete_user(userid)
        if isinstance(response, APIError):
            print "Error:", response
        elif response:
            print "Deleted."
        else:
            print "Nothing happened."
    
    def do_getuser(self, details):
        """
        getuser <userid>
        shows user's login details
        """
        userid = int(details)
        response = self.api.get_user(userid)
        if isinstance(response, APIError):
            print "Error:", response
        else:
            print "userid='%s'\nidentity='%s'\nemail='%s'\nscreenname='%s'" %  \
                (response.userid, response.identity, response.email,
                 response.screenname)

    def do_changesn(self, details):
        """
        changesn <userid> <newname>
        changes user's screenname to <newname>
        """
        args = details.split(None, 1)
        userid = int(args[0])
        newname = args[1]
        req = ChangeScreennameRequest(userid, newname)
        result = self.api.change_screenname(req)
        if isinstance(result, APIError):
            print "Error:", result.description
        else:
            print "Changed userid %d's screenname to '%s'" %  \
                (userid, newname)

    def do_opengames(self, _details):
        """
        Display open games, their descriptions, and their registered users.
        """
        response = self.api.get_open_games()
        if isinstance(response, APIError):
            print response
            return
        print "Open games:"
        for details in response:
            print details

    def do_runninggames(self, _details):
        """
        Display running games, their descriptions, and their users.
        """
        response = self.api.get_running_games()
        print "Running games:"
        for details in response:
            print details

    def do_joingame(self, params):
        """
        joingame <userid> <gameid>
        registers <userid> in open game <gameid>
        """
        args = params.split()
        userid = int(args[0])
        gameid = int(args[1])
        result = self.api.join_game(userid, gameid)
        if isinstance(result, APIError):
            print "Error:", result.description
        elif result is None:
            print "Registered userid %d in open game %d" % (userid, gameid)
        else:
            print "Registered userid %d in open game %d" % (userid, gameid)
            print "Started running game %d" % (result,)

    def do_leavegame(self, params):
        """
        leavegame <userid> <gameid>
        unregisters <userid> from open game <gameid>
        """
        args = params.split()
        userid = int(args[0])
        gameid = int(args[1])
        result = self.api.leave_game(userid, gameid)
        if isinstance(result, APIError):
            print "Error:", result.description
        else:
            print "Unregistered userid %d from open game %d" % (userid, gameid)

    def do_usersgames(self, params):
        """
        usersgames <userid>
        show details of all games associated with userid
        """
        userid = int(params)
        result = self.api.get_user_games(userid)
        if isinstance(result, APIError):
            print "Error:", result.description  # pylint:disable=E1101
            return
        print "Running games:"
        for game in result.running_details:
            print game

    def do_update(self, _details):
        """
        The kind of updates a background process would normally do. Currently
        includes:
         - ensure there's exactly one empty open game of each situation.
        """
        result = self.api.ensure_open_games()
        if result:
            print "Error:", result
        else:
            print "Open games refreshed."            

    def do_handhistory(self, params):
        """
        handhistory <gameid> [<userid>]
        display hand history for given game, from given user's perspective, if
        specified.
        """
        args = params.split(None, 1)
        gameid = int(args[0])
        if len(args) > 1:
            userid = int(args[1])
            result = self.api.get_private_game(gameid, userid)
        else:
            userid = None
            result = self.api.get_public_game(gameid)
        if isinstance(result, APIError):
            print "Error:", result.description  # pylint:disable=E1101
            return
        print "Game details: %r" % (result.game_details,)
        print "History for game %d, userid %s:" % (gameid, userid)
        for item in result.history:
            print item

    def do_exit(self, _details):
        """
        Close the admin interface
        """
        print "Goodbye."
        return True

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

CMD = AdminCmd()
CMD.prompt = "> "
CMD.cmdloop("Range vs. Range admin tool. Type ? for help.")