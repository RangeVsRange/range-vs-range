"""
The main pages for the site
"""
from flask import render_template, redirect, url_for
from rvr.app import APP
from rvr.forms.change import ChangeForm
from rvr.core.api import API, APIError
from rvr.app import AUTH
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest
import logging
from flask.helpers import flash
from flask.globals import request, session, g
from rvr.forms.action import action_form
from rvr.core import dtos
from rvr.poker.handrange import NOTHING
from flask_googleauth import logout

# TODO: 1: make raise total not mandatory at client side, and only mandatory at
# server side if necessary

def is_authenticated():
    """
    Is the user authenticated with OpenID?
    """
    return g.user and 'identity' in g.user

def ensure_user():
    """
    Commit user to database and determine userid
    """
    # TODO: REVISIT: automagically hook this into AUTH.required 
    if not is_authenticated():
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
        screenname = g.user['name']
    api = API()
    req = LoginRequest(identity=g.user['identity'],  # @UndefinedVariable
                       email=g.user['email'],  # @UndefinedVariable
                       screenname=screenname)
    result = api.login(req)
    if result == API.ERR_DUPLICATE_SCREENNAME:
        session['screenname'] = g.user['name']
        # User is authenticated with OpenID, but not yet authorised (logged
        # in). We redirect them to a page that allows them to choose a
        # different screenname.
        if request.endpoint != 'change_screenname':
            flash("The screenname '%s' is already taken." % screenname)
            return redirect(url_for('change_screenname'))
    elif isinstance(result, APIError):
        flash("Error registering user details.")
        logging.debug("login error: %s", result)
        return redirect(url_for('error_page'))
    else:
        session['screenname'] = result.screenname
        session['userid'] = result.userid
        flash("You have logged in as '%s'." %
              (result.screenname, ))

@APP.route('/change', methods=['GET','POST'])
@AUTH.required
def change_screenname():
    """
    Without the user being logged in, give the user the option to change their
    screenname from what Google OpenID gave us.
    """
    alt = ensure_user()
    if alt:
        return alt
    form = ChangeForm()
    if form.validate_on_submit():
        new_screenname = form.change.data
        if 'userid' in session:
            # Having a userid means they're in the database.
            req = ChangeScreennameRequest(session['userid'],
                                          new_screenname)
            resp = API().change_screenname(req)
            if resp == API.ERR_DUPLICATE_SCREENNAME:
                flash("That screenname is already taken.")
            elif isinstance(resp, APIError):
                logging.debug("change_screenname error: %s", resp)
                flash("An error occurred.")
            else:
                session['screenname'] = new_screenname
                flash("Your screenname has been changed to '%s'." %
                      (new_screenname, ))
                return redirect(url_for('home_page'))
        else:
            # User is not logged in. Changing screenname in session is enough.
            # Now when they go to the home page, ensure_user() will create their
            # account.
            session['screenname'] = new_screenname
            return redirect(url_for('home_page'))
    current = session['screenname'] if 'screenname' in session  \
        else g.user['name']
    return render_template('change.html', title='Change Your Screenname',
                           current=current, form=form)

@APP.route('/unsubscribe', methods=['GET'])
def unsubscribe():
    """
    Record that the user does not want to receive any more emails, at least
    until they log in again and in so doing clear that flag.
    
    Note that authentication is not required.
    """
    api = API()
    identity = request.args.get('identity', None)
    if identity is None:
        msg = "Invalid request, sorry."
    else:
        response = api.unsubscribe(identity)
        if response is api.ERR_NO_SUCH_USER:
            msg = "No record of you on Range vs. Range, sorry."
        elif isinstance(response, APIError):
            msg = "An unknown error occurred."
        else:
            msg = "You have been unsubscribed. If you log in again, you will start receiving emails again."  # pylint:disable=C0301
    flash(msg)
    return render_template('base.html', title='Unsubscribe')

@logout.connect_via(APP)
def on_logout(_source, **_kwargs):
    """
    I prefer to be explicit about what we remove on logout. 
    """
    session.pop('userid', None)
    session.pop('screenname', None)

@APP.route('/log-in', methods=['GET'])
@AUTH.required
def log_in():
    """
    Does what /login does, but in a way that I can get a URL for with url_for!
    """
    # TODO: REVISIT: get a relative URL for /login, instead of this.
    return redirect(url_for('home_page'))

@APP.route('/error', methods=['GET'])
def error_page():
    """
    Unauthenticated page for showing errors to user.
    """
    return render_template('base.html', title='Sorry')

@APP.route('/', methods=['GET'])
def home_page():
    """
    Generates the unauthenticated landing page. AKA the main or home page.
    """
    if not is_authenticated():
        return render_template('landing.html', title='Welcome')
    alt = ensure_user()
    if alt:
        return alt
    api = API()
    userid = session['userid']
    screenname = session['screenname']
    open_games = api.get_open_games()
    if isinstance(open_games, APIError):
        flash("An unknown error occurred retrieving your open games.")
        return redirect(url_for("error_page"))
    my_games = api.get_user_running_games(userid)
    if isinstance(my_games, APIError):
        flash("An unknown error occurred retrieving your running games.")
        return redirect(url_for("error_page"))
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
        others_turn_games=others_turn_games,
        my_finished_games=my_games.finished_details
        )

@APP.route('/join', methods=['GET'])
@AUTH.required
def join_game():
    """
    Join game, flash status, redirect back to /home
    """
    alt = ensure_user()
    if alt:
        return alt
    api = API()
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
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
    flash(msg)
    return redirect(url_for('error_page'))

@APP.route('/leave', methods=['GET'])
@AUTH.required
def leave_game():
    """
    Leave game, flash status, redirect back to /home
    """
    alt = ensure_user()
    if alt:
        return alt
    api = API()
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
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
    flash(msg)
    return redirect(url_for('error_page'))

def _handle_action(gameid, userid, api, form):
    """
    Handle response from an action form
    """
    # TODO: 0: a shitload of logging in all the code under _handle_action
    # TODO: 0: then release.
    # pylint:disable=R0912
    fold = form.fold.data
    passive = form.passive.data
    aggressive = form.aggressive.data
    total = form.total.data if aggressive != NOTHING else 0
    range_action = dtos.ActionDetails(fold_raw=fold, passive_raw=passive,
                                      aggressive_raw=aggressive,
                                      raise_total=total)
    logging.debug("gameid %r, performing action, userid %r, range_action %r",
                  gameid, userid, range_action)
    result = api.perform_action(gameid, userid, range_action)
    # why do validation twice...
    if isinstance(result, APIError):
        if result is api.ERR_INVALID_RAISE_TOTAL:
            msg = "Invalid raise total."
        elif result is api.ERR_INVALID_RANGES:
            msg = "Invalid ranges for that action."
        else:
            msg = "An unknown error occurred."
            logging.info('Unknown error from api.perform_action: %s', result)
        flash(msg)
        return redirect(url_for('game_page', gameid=gameid))
    else:
        if result.is_fold:
            msg = "You folded."
        elif result.is_passive:
            if result.call_cost == 0:
                msg = "You checked."
            else:
                msg = "You called for %d." % (result.call_cost,)
        elif result.is_aggressive:
            if result.is_raise:
                msg = "You raised to %d." % (result.raise_total,)
            else:
                msg = "You bet %d." % (result.raise_total,)
        elif result.is_terminate:
            msg = "The hand is over."
        else:
            msg = "I can't figure out what happened, eh."
        flash(msg)
        if result.game_over:
            flash("The game is finished.")
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
    
    range_editor_url = url_for('range_editor',
        rng_original=game.game_details.current_player.range_raw,
        board=game.game_details.board_raw,
        raised="true" if game.current_options.is_raise else "false",
        can_check="true" if game.current_options.can_check() else "false")
    title = 'Game %d (running)' % (gameid,)
    return render_template('running_game.html', title=title, form=form,
        game_details=game.game_details, history=game.history,
        current_options=game.current_options,
        is_me=(userid == game.game_details.current_player.user.userid),
        range_editor_url=range_editor_url)

def _finished_game(game, gameid):
    """
    Response from game page when the requested game is finished.
    """
    # TODO: 1: display only %ages, not full ranges, link to range viewer
    # also for running game.
    title = 'Game %d (finished)' % (gameid,)
    return render_template('finished_game.html', title=title,
        game_details=game.game_details, history=game.history)

@APP.route('/game', methods=['GET', 'POST'])
@AUTH.required
def game_page():
    """
    User's view of the specified game
    """
    alt = ensure_user()
    if alt:
        return alt
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
    userid = session['userid']

    api = API()
    response = api.get_private_game(gameid, userid)
    if isinstance(response, APIError):
        if response is api.ERR_NO_SUCH_RUNNING_GAME:
            msg = "Invalid game ID."
        else:
            msg = "An unknown error occurred."
        flash(msg)
        return redirect(url_for('error_page'))
    
    if response.is_finished():
        return _finished_game(response, gameid)
    else:
        return _running_game(response, gameid, userid, api)
