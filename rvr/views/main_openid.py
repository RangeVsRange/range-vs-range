"""
The main pages for the site
"""
from flask import render_template, redirect, url_for
from rvr.app import APP
from rvr.forms.change import ChangeForm
from rvr.core.api import API, APIError
from rvr.app import OID
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest
from werkzeug.exceptions import abort  # @UnresolvedImport
import logging
from flask.helpers import flash
from flask.globals import request, session
from rvr.forms.action import action_form
from rvr.core import dtos
from rvr.poker.handrange import NOTHING
from functools import wraps

def auth_required(fun):
    @wraps(fun)
    def inner():
        if 'identity' not in session:
            return redirect(url_for('login',
                                    next=url_for(request.endpoint,
                                                 **request.args)))
        else:
            ensure_user()
            return fun()
    return inner

# I'm getting 403 errors on PAW. I'd at least like to see what is in the
# session.
@APP.errorhandler(403)
def not_authorised(e):
    return """
        You are not authorised.
        identity=%r;
        email=%r;
        name=%r;
        screenname=%r;
        userid=%s.
        """ % (session.get('identity'),
               session.get('email'),
               session.get('name'),
               session.get('screenname'),
               "exists" if session.get('userid') else None)

@APP.route('/login.html', methods=['GET', 'POST'])
@OID.loginhandler
def login():
    if 'identity' in session:
        # already authenticated
        return redirect(OID.get_next_url())
    if request.method == 'POST':
        openid = request.form.get('openid')
        if openid:
            return OID.try_login(openid,
                                 ask_for=['email', 'nickname', 'fullname'])
    return render_template('login.html', next=OID.get_next_url(),
                           error=OID.fetch_error())    

@OID.after_login
def create_or_login(resp):
    session['identity'] = resp.identity_url
    session['email'] = resp.email
    session['name'] = resp.nickname or resp.fullname
    return redirect(OID.get_next_url())

def ensure_user():
    """
    Commit user to database and determine userid
    """
    if 'identity' not in session:
        # user is not authenticated yet
        return
    if 'userid' in session and 'screenname' in session:
        # user is authenticated and authorised (logged in)
        return
    if 'screenname' in session:
        # user had changed screenname but not yet logged in
        screenname = session['screenname']
    else:
        # regular login
        screenname = session['name']
    api = API()
    req = LoginRequest(identity=session['identity'],  # @UndefinedVariable
                       email=session['email'],  # @UndefinedVariable
                       screenname=screenname)  # @UndefinedVariable
    result = api.login(req)
    if result == API.ERR_LOGIN_DUPLICATE_SCREENNAME:
        session['screenname'] = session['name']
        # User is authenticated with OpenID, but not yet authorised (logged
        # in). We redirect them to a page that allows them to choose a
        # different screenname.
        flash("The screenname '%s' is already taken." % screenname)
        if request.endpoint != 'change_screenname':
            return redirect(url_for('change_screenname'))
    elif isinstance(result, APIError):
        flash("Error registering user details.")
        logging.debug("login error: %s", result)
        return redirect(url_for('landing_page'))
    else:
        session['screenname'] = result.screenname
        session['userid'] = result.userid

@APP.route('/change', methods=['GET', 'POST'])
@auth_required
def change_screenname():
    """
    Without the user being logged in, give the user the option to change their
    screenname from what Google OpenID gave us.
    """
    form = ChangeForm()
    if form.validate_on_submit():
        new_screenname = form.change.data
        if 'userid' in session:
            req = ChangeScreennameRequest(session['userid'],
                                          session['screenname'])
            resp = API().change_screenname(req)
            if isinstance(resp, APIError):
                logging.debug("change_screenname error: %s", resp)
                flash("An error occurred.")
                return redirect(url_for('change_screenname'))
            flash("Your screenname has been changed to '%s'." %
                  (new_screenname,))
        session['screenname'] = new_screenname
        return redirect(url_for('home_page'))
    screenname = session['screenname'] if 'screenname' in session  \
        else session['name']
    return render_template('change.html', title='Change Your Screenname',
                           current=screenname, form=form)

@APP.route('/', methods=['GET'])
def landing_page():
    """
    Generates the unauthenticated landing page. AKA the main or home page.
    """
    return render_template('landing.html', title='Welcome')

@APP.route('/home', methods=['GET'])
@auth_required
def home_page():
    """
    Authenticated landing page. User is taken here when logged in.
    """
    api = API()
    userid = session['userid']
    screenname = session['screenname']
    open_games = api.get_open_games()
    if isinstance(open_games, APIError):
        flash("An unknown error occurred retrieving your open games.")
        return redirect(url_for("landing_page"))
    my_games = api.get_user_running_games(userid)
    if isinstance(my_games, APIError):
        flash("An unknown error occurred retrieving your running games.")
        return redirect(url_for("landing_page"))
    my_open = [og for og in open_games
               if any([u.userid == userid for u in og.users])]
    others_open = [og for og in open_games
                   if not any([u.userid == userid for u in og.users])]
    my_turn_games = [mg for mg in my_games.running_details
                     if mg.current_user_details.userid == userid]
    others_turn_games = [mg for mg in my_games.running_details
                         if mg.current_user_details.userid != userid]
    return render_template('home.html', title='Home',
        screenname=screenname,
        my_open=my_open,
        others_open=others_open,
        my_turn_games=my_turn_games,
        others_turn_games=others_turn_games
        )

@APP.route('/join', methods=['GET'])
@auth_required
def join_game():
    """
    Join game, flash status, redirect back to /home
    """
    api = API()
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('home_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('home_page'))
    userid = session['userid']
    response = api.join_game(userid, gameid)
    if response is api.ERR_JOIN_GAME_ALREADY_IN:
        msg = "You are already registered in game %s." % (gameid,)
    elif response is api.ERR_JOIN_GAME_GAME_FULL:
        msg = "Game %s is full." % (gameid,)
    elif response is api.ERR_NO_SUCH_OPEN_GAME:
        msg = "Invalid game ID."
    elif isinstance(response, APIError):
        msg = "An unknown error occurred."
    else:
        msg = "You have joined game %s." % (gameid,)
    flash(msg)
    return redirect(url_for('home_page'))

@APP.route('/leave', methods=['GET'])
@auth_required
def leave_game():
    """
    Leave game, flash status, redirect back to /home
    """
    api = API()
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('home_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('home_page'))
    userid = session['userid']
    response = api.leave_game(userid, gameid)
    if response is api.ERR_USER_NOT_IN_GAME:
        msg = "You are not registered in game %s." % (gameid,)
    elif response is api.ERR_NO_SUCH_OPEN_GAME:
        msg = "Invalid game ID."
    elif isinstance(response, APIError):
        msg = "An unknown error occurred."
    else:
        msg = "You have left game %s." % (gameid,)
    flash(msg)
    return redirect(url_for('home_page'))

def _handle_action(gameid, userid, api, form):
    """
    Handle response from an action form
    """
    fold = form.fold.data
    passive = form.passive.data
    aggressive = form.aggressive.data
    total = form.total.data if aggressive != NOTHING else 0
    range_action = dtos.ActionDetails(fold_raw=fold, passive_raw=passive,
                                      aggressive_raw=aggressive,
                                      raise_total=total)
    result = api.perform_action(gameid, userid, range_action)
    # why do validation twice...
    if isinstance(result, APIError):
        if result is api.ERR_INVALID_RAISE_TOTAL:
            msg = "Invalid raise total."
        elif result is api.ERR_INVALID_RANGES:
            msg = "Invalid ranges for that action."
        else:
            msg = "An unknown error occurred."
        flash(msg)
        return redirect(url_for('game_page', gameid=gameid))
    else:
        if result.is_fold:
            msg = "You folded."
        elif result.is_passive:
            msg = "You called for %d." % (result.call_cost,)
        elif result.is_aggressive:
            msg = "You raised to %d." % (result.raise_total,)
        elif result.is_terminate:
            msg = "The hand is over."
        else:
            msg = "I can't figure out what happened, eh."
        flash(msg)
        if result.game_over:
            flash("The game is finished.")
            return redirect(url_for('home_page'))
        else:   
            return redirect(url_for('game_page', gameid=gameid))

def _running_game(game, gameid, userid, api):
    """
    Response from game page when the requested game is still running.
    """
    form = action_form(is_check=game.current_options.can_check(),
        is_raise=game.current_options.is_raise,
        can_raise=game.current_options.can_raise(),
        min_raise=game.current_options.min_raise,
        max_raise=game.current_options.max_raise)
    if form.validate_on_submit():
        return _handle_action(gameid, userid, api, form)
    
    title = 'Game %d (running)' % (gameid,)
    return render_template('running_game.html', title=title, form=form,
        game_details=game.game_details, history=game.history,
        current_options=game.current_options,
        is_me=(userid == game.game_details.current_player.user.userid))

def _finished_game(game, gameid):
    """
    Response from game page when the requested game is finished.
    """
    title = 'Game %d (finished)' % (gameid,)
    return render_template('finished_game.html', title=title,
        game_details=game.game_details, history=game.history)

@APP.route('/game', methods=['GET', 'POST'])
@auth_required
def game_page():
    """
    User's view of the specified game
    """
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('home_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('home_page'))
    userid = session['userid']
        
    api = API()
    response = api.get_private_game(gameid, userid)
    if isinstance(response, APIError):
        if response is api.ERR_NO_SUCH_RUNNING_GAME:
            msg = "Invalid game ID."
        else:
            msg = "An unknown error occurred."
        flash(msg)
        return redirect(url_for('home_page'))
    
    if response.is_finished():
        return _finished_game(response, gameid)
    else:
        return _running_game(response, gameid, userid, api)