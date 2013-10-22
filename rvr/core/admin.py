from cmd import Cmd
import logging
from rvr.core.api import API
from rvr.core.dtos import LoginDetails
from rvr.db.creation import do_create
from rvr.db.initialise import do_initialise

class AdminCmd(Cmd):        
    def __init__(self):
        Cmd.__init__(self)
        self.api = API()
    
    def do_createdb(self, _details):
        """
        Create the database
        """
        do_create()
        print "Database created"
        do_initialise()
        print "Database initialised"
    
    def do_adduser(self, params):
        """
        Calls the adduser API function
        adduser(provider, email, screenname)
        """
        params = params.split(None, 2)
        if len(params) == 3:
            details = LoginDetails(userid=None,
                                   provider=params[0],
                                   email=params[1],
                                   screenname=params[2])
        else:
            print "Need exactly 3 parameters."
            print "For more info, help adduser"
            return
        response = self.api.login(details)
        print "Created user with userid='%s', provider='%s', email='%s', screenname='%s'" %  \
            (response.userid, response.provider, response.email, response.screenname)

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