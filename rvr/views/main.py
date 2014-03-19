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
        others_turn_games=others_turn_games
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
            logging.info('Unknown error from api.perform_action: %s', result)
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

RANKS_HIDDEN = 'r_hdn'
RANKS_SELECTED = 'r_sel'
RANKS_UNASSIGNED = 'r_una'
RANKS_FOLD = 'r_fol'
RANKS_PASSIVE = 'r_pas'
RANKS_AGGRESSIVE = 'r_agg'
RANKS_MIXED = 'r_mix'

POS_TO_RANK = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

SUITED = 0
PAIR = 1
OFFSUIT = 2

SUITS_HIDDEN = 's_hdn'
SUITS_SELECTED = 's_sel'
SUITS_DESELECTED = 's_des'

POS_TO_SUIT = ['s', 'h', 'd', 'c']  # i.e. s.svg, h.svg, etc.

def rank_text(row, col):
    """
    Give the text for this rank combo (e.g. 0, 0 -> 'AA')
    """
    if row < col:
        # suited
        return "%s%ss" % (POS_TO_RANK[row], POS_TO_RANK[col])
    elif row > col:
        # offsuit
        return "%s%so" % (POS_TO_RANK[col], POS_TO_RANK[row])
    else:
        # pair
        return "%s%s" % (POS_TO_RANK[row], POS_TO_RANK[col])

def rank_id(row, col):
    """
    Give the appropriate id for this rank combo
    """
    return rank_text(row, col)

def rank_class(row, col):
    """
    Give the appropriate class for this rank combo
    """
    # Just a bit of mock data for now
    if row == 3:
        return RANKS_HIDDEN
    if row == 6:
        return RANKS_FOLD
    if col == 5:
        return RANKS_PASSIVE
    if row == 7:
        return RANKS_AGGRESSIVE
    if col == 8:
        return RANKS_MIXED
    return RANKS_UNASSIGNED

def suit_text(row, col, is_left):
    """
    Give the appropriate text for this suit combo (e.g. 0, 0 -> 's')
    """
    return POS_TO_SUIT[row] if is_left else POS_TO_SUIT[col]

def suit_id(row, col, table):
    """
    Give the appropriate id for this suit combo 
    """
    if table == SUITED:
        return "s_%s" % (POS_TO_SUIT[row])
    elif table == PAIR:
        return "p_%s%s" % (POS_TO_SUIT[row], POS_TO_SUIT[col])
    elif table == OFFSUIT:
        return "o_%s%s" % (POS_TO_SUIT[row], POS_TO_SUIT[col])

def suit_class(row, col, table):
    """
    Give the appropriate class for this suit combo
    """
    if table == SUITED:
        return SUITS_SELECTED if row == col else SUITS_HIDDEN
    elif table == PAIR:
        return SUITS_SELECTED if row < col else SUITS_HIDDEN
    elif table == OFFSUIT:
        return SUITS_SELECTED if row != col else SUITS_HIDDEN

@APP.route('/range-editor', methods=['GET', 'POST'])
def range_editor():
    """
    An HTML range editor!
    
    (Mostly a playground for experimentation right now.)
    """
    # TODO: 0: range editor, firstly as a stand-alone webpage
    # The display should include:
    #  - a 13 x 13 grid of basic combos (T6o, etc.)
    #  - 22 suit combo buttons (4 x pair, 6 x suited, 12 x offsuited)
    #  - select all and select none buttons for these suit combos
    #  - 4 "lock range" buttons (reset / fold / call / raise)
    #  - 4 "move hands" buttons (reset / fold / call / raise)
    # The 13 x 13 grid has the following states (colours):
    #  - unallocated
    #  - fold
    #  - call / check
    #  - raise / bet
    #  - a combo of the previous three
    #  - selected (displayed as a depressed and/or greyed button)
    # To start with, the "move hands" buttons can reload the page.
    # Exact colours can be retrieved from (e.g.)
    #   http://rangevsrange.wordpress.com/introduction/
    # TODO: 0: move all (most) <tag style="details"> to (external?) CSS
    # TODO: 0: make the bottom table work again, with 15x padding
    rank_table = [[{'text': rank_text(row, col),
                    'id': rank_id(row, col),
                    'class': rank_class(row, col)}
                   for col in range(13)] for row in range(13)]
    suited_table = [[{'left': suit_text(row, col, True),
                      'right': suit_text(row, col, False),
                      'id': suit_id(row, col, SUITED),
                      'class': suit_class(row, col, SUITED)}
                     for col in range(4)] for row in range(4)] 
    pair_table = [[{'left': suit_text(row, col, True),
                    'right': suit_text(row, col, False),
                    'id': suit_id(row, col, PAIR),
                    'class': suit_class(row, col, PAIR)}
                   for col in range(4)] for row in range(3)]
    offsuit_table = [[{'left': suit_text(row, col, True),
                       'right': suit_text(row, col, False),
                       'id': suit_id(row, col, OFFSUIT),
                       'class': suit_class(row, col, OFFSUIT)}
                      for col in range(4)] for row in range(4)]
    return render_template('range_editor.html', title="Range Editor",
        rank_table=rank_table, suited_table=suited_table,
        pair_table=pair_table, offsuit_table=offsuit_table,
        pct_unassigned=100.0, pct_fold=0.0, pct_passive=0.0, pct_aggressive=0.0)