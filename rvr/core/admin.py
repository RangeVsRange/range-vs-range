"""
Admin Cmd class for interacting with API
"""
from cmd import Cmd
from rvr.core.api import APIError, API
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest
from rvr.core import dtos
from rvr.poker import cards  # (for dynamic situations) @UnusedImport pylint:disable=unused-import
from rvr.db.dump import load, dump
from sqlalchemy.exc import IntegrityError, OperationalError
from rvr import local_settings

#pylint:disable=R0201,R0904,E1103,unused-argument

def display_game_tree(tree):
    """
    Display every node of tree.
    """
    print tree
    for node in tree.children:
        display_game_tree(node)

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

    def do_initialise(self, _details):
        """
        Initialise a (created but empty) database
        """
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

    def do_dump(self, params):
        """
        dump { out | in }

        dump out pickles the database to db.pkl
        dump in unpickles it

        To restore a database from a db.pkl file:
        1. delete the database file (rvr.db)
        2. "createdb"
        3. "dump in"
        4. "initialise"

        The "initiialise" does things like refreshing open games, because open
        games are not dumped out by "dump out".
        """
        filename = 'db.pkl'
        if params == 'out':
            dump(filename)
            print "Successfully exported database to %s." % (filename,)
        elif params == 'in':
            try:
                load(filename)
            except IntegrityError as err:
                print "IntegrityError. Is the database empty?"
                print "Perhaps delete the database and try the 'createdb' command."  # pylint:disable=C0301
                print "Details:", err
                return
            except OperationalError as err:
                print "OperationalError. Does the database exist?"
                print "Perhaps try the 'createdb' command."
                print "Details:", err
                return
            print "Successfully read %s into database." % (filename,)
        else:
            print "Bad syntax. See 'help dump'."

    def do_situation(self, details):
        """
        Load situation from given python module and add it to the DB. E.g.:

        situation hu.py

        will load a situation from a method called reate_situation defined in
        hu.py, and add it to the database.

        You can also load directly from the command line:

        python console.py situation hu.py
        """
        # TODO: REVISIT: this can't be used to accept user-defined situations.
        with open(details, 'r') as handle:
            source = handle.read()
        exec(source)  # pylint:disable=exec-used
        # pylint:disable=undefined-variable
        situation = create_situation()  # @UndefinedVariable
        result = self.api.add_situation(situation)
        print "added situation, result", result

    def do_login(self, params):
        """
        Calls the login API function
        login(identity, email)
        """
        params = params.split(None, 1)
        if len(params) == 2:
            request = LoginRequest(identity=params[0],
                                   email=params[1])
        else:
            print "Need exactly 2 parameters."
            print "For more info, help login"
            return
        response = self.api.login(request)
        if isinstance(response, APIError):
            print "Error:", response
            return
        print "User is logged in, response %r" % \
            (response)

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
        result = self.api.get_user_running_games(userid)
        if isinstance(result, APIError):
            print "Error:", result.description  # pylint:disable=E1101
            return
        print "Running games:"
        for game in result.running_details:
            print game
        print "Finished games:"
        for game in result.finished_details:
            print game

    def do_act(self, params):
        """
        act <gameid> <userid> <fold> <passive> <aggressive> <total>
        perform an action in a game as a user
        """
        params = params.split()
        gameid = int(params[0])
        userid = int(params[1])
        fold = params[2]
        passive = params[3]
        aggressive = params[4]
        total = int(params[5])
        range_action = dtos.ActionDetails(
            fold_raw=fold,
            passive_raw=passive,
            aggressive_raw=aggressive,
            raise_total=total)
        response = self.api.perform_action(gameid, userid, range_action)
        if isinstance(response, APIError):
            print "Error:", response.description  # pylint:disable=E1101
            return
        action, spawned, is_first_action = response  # pylint:disable=unpacking-non-sequence,line-too-long
        # pylint:disable=E1103
        if action.is_fold:
            print "You folded."
        elif action.is_passive:
            print "You called."
        elif action.is_aggressive:
            print "You raised to %d." % (action.raise_total,)
        else:
            print "Action:", action
        print "Spawned:", spawned
        print "Is first action:", is_first_action

    def do_chat(self, details):
        """
        chat <gameid> <userid> <message>
        """
        params = details.split(None, 2)
        if len(params) != 3:
            print "Need exactly 3 parameters."
            print "For more info: help chat"
            return
        gameid = int(params[0])
        userid = int(params[1])
        message = params[2]
        response = self.api.chat(gameid, userid, message)
        if isinstance(response, APIError):
            print "Error:", response.description  # pylint:disable=E1101
            return
        print "Chatted in game %d, for userid %d, message %r" %  \
            (gameid, userid, message)

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
        Display hand history for given game, from given user's perspective, if
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
        print "(suppressing analysis)"
        # There's just so damn much of it, the best way to see it is on the web.
        result.analysis = None
        print result

    def do_statistics(self, params):
        """
        statistics <username> <is_competition>
        Display user's statistics
        """
        args = params.split(None, 1)
        screenname = args[0]
        is_competition = len(args) == 1 or args[1] == 'True'
        result = self.api.get_user_by_screenname(screenname)
        if isinstance(result, APIError):
            print "Error:", result.description
            return
        result = self.api.get_user_statistics(result.userid, min_hands=1,
                                              is_competition=is_competition)
        if isinstance(result, APIError):
            print "Error:", result.description
            return
        for situation in result:
            print situation

    def do_analyse(self, details):
        """
        analyse
        Run pending analysis

        analyse <gameid>
        Re/analyse gameid

        analyse [refresh]
        Reanalyse everything.
        """
        if details == "":
            result = self.api.run_pending_analysis()
        elif details == "refresh":
            print "This may re-email everyone for games they have already" \
                " had analysis for. If you don't want to do that, turn off" \
                " email in local_settings.py first. If you are okay with" \
                " re-emailing everyone, or you have checked local_settings.py" \
                " the command is 'analyse refresh confirm'."
            return
        elif details == "refresh confirm":
            result = self.api.reanalyse_all()
        else:
            try:
                gameid = int(details)
            except ValueError:
                print "Bad syntax. See 'help analyse'."
                return
            result = self.api.reanalyse(gameid)
        if isinstance(result, APIError):
            print "Error:", result.description
        else:
            print "Analysis run."
        if local_settings.SUPPRESS_EMAIL:
            print "Email is turned off in local_settings.py. You may now"  \
                " want to turn it back on."

    def do_timeout(self, _details):
        """
        timeout
        Fold any players who have timed out.
        """
        result = self.api.process_timeouts()
        if isinstance(result, APIError):
            print "Error:", result.description
        else:
            print result, "timeouts processed."

    def do_tree(self, params):
        """
        tree game <gameid>
        tree group <groupid>
        Print game tree for game or group.
        """
        params = params.split(None, 1)
        if len(params) != 2:
            print "Need exactly 2 parameters."
            print "For more info, help tree"
            return
        if params[0] not in ['game', 'group']:
            print "Bad syntax. See 'help tree'. (1)"
        try:
            gameid = int(params[1])
        except ValueError:
            print "Bad syntax. See 'help tree'. (2)"
        if params[0] == 'game':
            result = self.api.get_game_tree(gameid)
        else:
            result = self.api.get_group_tree(gameid)
        if isinstance(result, APIError):
            print "Error:", result.description
        else:
            display_game_tree(result)

    def do_exit(self, _details):
        """
        Close the admin interface
        """
        print "Goodbye."
        return True
