from cmd import Cmd
import logging
from rvr.core.api import API
from rvr.core.dtos import LoginDetails

class AdminCmd(Cmd):        
    def __init__(self):
        Cmd.__init__(self)
        self.api = API()
    
    def do_createdb(self, _details):
        """
        Create the database
        """
        self.api.create_db()
        print "Database created"
        self.api.initialise_db()
        print "Database initialised"
    
    def do_login(self, params):
        """
        Calls the login API function
        login(provider, email, screenname)
        """
        params = params.split(None, 2)
        if len(params) == 3:
            details = LoginDetails(userid=None,
                                   provider=params[0],
                                   email=params[1],
                                   screenname=params[2])
        else:
            print "Need exactly 3 parameters."
            print "For more info, help login"
            return
        response = self.api.login(details)
        print "Created user with userid='%s', provider='%s', email='%s', screenname='%s'" %  \
            (response.userid, response.provider, response.email, response.screenname)

    def do_getuser(self, details):
        """
        getuser <screenname>
        gets userid by screenname
        """
        user = self.api.get_user_by_screenname(details)
        if user is None:
            print "No such user"
        else:
            print "'%s' has userid %s" % (user.screenname, user.userid)

    def do_opengames(self, _details):
        """
        Display open games, their descriptions, and their registered users.
        """
        response = self.api.get_open_games()
        print "Open games:"
        for details in response:
            if details.screennames:
                names = ', '.join(["'%s'" % (name, ) 
                                   for name in details.screennames])
            else:
                names = '(empty)'
            gameid = details.gameid
            print "%d -> '%s': %s" % (gameid, details.description, names)

    def do_update(self, _details):
        """
        The kind of updates a background process would normally do. Currently
        includes:
         - ensure there's exactly one empty open game of each situation.
        """
        delta = self.api.ensure_open_games()
        print "Open games refreshed. Game count delta: %d" % (delta, )

    def do_exit(self, _details):
        """
        Close the admin interface
        """
        print "Goodbye."
        return True

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

cmd = AdminCmd()
cmd.prompt = "Enter command (? for help): "
cmd.cmdloop("Range vs. Range admin tool")