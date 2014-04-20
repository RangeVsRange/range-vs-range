"""
The main pages for the site
"""
from flask import render_template, redirect, url_for
from rvr.app import APP
from rvr.forms.change import ChangeForm
from rvr.core.api import API, APIError
from rvr.app import AUTH
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest,  \
    GameItemUserRange, GameItemBoard, GameItemActionResult, GameItemRangeAction
import logging
from flask.helpers import flash
from flask.globals import request, session, g
from rvr.forms.action import action_form
from rvr.core import dtos
from rvr.poker.handrange import NOTHING, SET_ANYTHING_OPTIONS,  \
    HandRange
from flask_googleauth import logout
from rvr.poker.cards import RIVER, TURN, FLOP

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
            msg = "An unknown error occurred unsubscribing you, sorry."
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
        msg = "Game %d is full." % (gameid,)
    elif response is api.ERR_NO_SUCH_OPEN_GAME:
        msg = "Invalid game ID."
    elif response is api.ERR_NO_SUCH_USER:
        msg = "Oddly, your account does not seem to exist. " +  \
            "Try logging out and logging back in."
        logging.debug("userid %d can't register for game %d, " +
                      "because user doesn't exist.",
                      userid, gameid)
    elif isinstance(response, APIError):
        msg = "An unknown error occurred joining game %d, sorry." % (gameid,)
        logging.debug("unrecognised error from api.join_game: %s", response)
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
        msg = "An unknown error occurred leaving game %d, sorry." % (gameid,)
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
    # pylint:disable=R0912
    fold = form.fold.data
    passive = form.passive.data
    aggressive = form.aggressive.data
    if aggressive != NOTHING:
        try:
            total = int(form.total.data)
        except ValueError:
            flash("Incomprehensible raise total.")
            return redirect(url_for('game_page', gameid=gameid))
    else:
        total = 0
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
            msg = "An unknown error occurred performing action, sorry."
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
            msg = "The game is finished."
        else:
            msg = "I can't figure out what happened, eh."
        flash(msg)
        return redirect(url_for('game_page', gameid=gameid))

def _board_to_html(item):
    """
    Replace little images into it
    """
    cards = ['<img alt="" src="/static/smallcards/%s.png">' %
             item.cards[i:i+2] for i in range(0, len(item.cards), 2)]
    if item.street == FLOP:
        return "%s: %s%s%s" % (item.street, cards[0], cards[1], cards[2])
    elif item.street == TURN:
        return "%s: %s%s%s %s" % (item.street, cards[0], cards[1], cards[2],
                                  cards[3])
    elif item.street == RIVER:
        return "%s: %s%s%s %s %s" % (item.street, cards[0], cards[1],
                                     cards[2], cards[3], cards[4])
    else:
        # Unknown, but probably PREFLOP, but shouldn't happen.
        return "(unknown street) %s: %s" % (item.street, item.cards)        
    return str(item)

def _range_action_to_html(item):
    """
    Convert to percentages (relative)
    """
    fold_total = len(item.range_action.fold_range
        .generate_options_unweighted())
    passive_total = len(item.range_action.passive_range
        .generate_options_unweighted())
    aggressive_total = len(item.range_action.aggressive_range
        .generate_options_unweighted())
    total = fold_total + passive_total + aggressive_total
    return "%s folds %0.2f%%, passive %0.2f%%, aggressive %0.2f%%"  \
        " (to total %d chips)" % (item.user, 100.0 * fold_total / total,
                                  100.0 * passive_total / total,
                                  100.0 * aggressive_total / total,
                                  item.range_action.raise_total)

def _user_range_to_html(item):
    """
    Convert to a percentage (absolute)
    """
    total = len(HandRange(item.range_raw).generate_options_unweighted())
    return "%s's range now includes %0.2f%% of hands." %  \
        (item.user, 100.0 * total / len(SET_ANYTHING_OPTIONS))

def _hand_history_to_html(item):
    """
    Hand history items provide a basic to-text function. This function adds a little
    extra HTML where necessary, to make them prettier.
    """
    if isinstance(item, GameItemUserRange):
        return _user_range_to_html(item)
    elif isinstance(item, GameItemRangeAction):
        return _range_action_to_html(item)
    elif isinstance(item, GameItemActionResult):
        return str(item)
    elif isinstance(item, GameItemBoard):
        return _board_to_html(item)
    else:
        logging.debug("unrecognised type of hand history item: %s", item)
        return str(item)

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
    history = [_hand_history_to_html(item) for item in game.history]
    return render_template('running_game.html', title=title, form=form,
        game_details=game.game_details, history=history,
        current_options=game.current_options,
        is_me=(userid == game.game_details.current_player.user.userid),
        range_editor_url=range_editor_url)

def _finished_game(game, gameid):
    """
    Response from game page when the requested game is finished.
    """
    # TODO: 1: display only %ages, not full ranges, link to range viewer
    # also for running_game.
    # - cards become images
    # - range actions become three numbers (with link to range editor)
    # - players' ranges become singular numbers (with link to range editor)
    title = 'Game %d (finished)' % (gameid,)
    history = [_hand_history_to_html(item) for item in game.history]
    return render_template('finished_game.html', title=title,
        game_details=game.game_details, history=history)

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
            msg = "An unknown error occurred retrieving game %d, sorry." %  \
                (gameid,)
        flash(msg)
        return redirect(url_for('error_page'))
    
    if response.is_finished():
        return _finished_game(response, gameid)
    else:
        return _running_game(response, gameid, userid, api)
