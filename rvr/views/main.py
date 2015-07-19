"""
The main pages for the site
"""
from flask import render_template, redirect, url_for
from rvr.app import APP
from rvr.forms.change import ChangeForm
from rvr.core.api import API, APIError
from rvr.app import OIDC
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest,  \
    GameItemUserRange, GameItemBoard, GameItemActionResult,  \
    GameItemRangeAction, GameItemTimeout, GameItemChat, GameItemShowdown,\
    game_line_key
import logging
from flask.helpers import flash, make_response
from flask.globals import request, session, g
from rvr.forms.action import action_form
from rvr.core import dtos
from rvr.poker.handrange import NOTHING, SET_ANYTHING_OPTIONS,  \
    HandRange, unweighted_options_to_description
import urlparse
from rvr.forms.chat import ChatForm
from rvr import local_settings
from rvr.forms.backdoor import BackdoorForm
from rvr.db.tables import PaymentToPlayer, RunningGameParticipantResult
from functools import wraps

# pylint:disable=R0911,R0912,R0914

# TODO: 0: poll /r/poker for ranges for:
# TODO: 0.1: BTN vs. BB
# TODO: 0.2: MP vs. BTN
# TODO: 0.3: BB 3bet vs. BTN
# TODO: 0: or at least playtest them with StrayJ

# TODO: 1: finish a HU game and show it off!

# TODO: 5: a 'situation' page that describes the situation...
# TODO: 5: reused in situation tab of game page - with starting pot!...
# TODO: 5: and card removal effects of board (change to range editor)

def auth_check(view_func):
    """
    Like OIDC.check, but respects the backdoor, and lets sessions live forever.
    """
    if local_settings.ALLOW_BACKDOOR:
        return view_func
    else:
        @wraps(view_func)
        def decorated(*args, **kwargs):
            if 'userid' not in session and 'screenname' not in session:
                response = OIDC.authenticate_or_redirect()
                if response is not None:
                    return response
            return view_func(*args, **kwargs)
        return decorated

def is_authenticated_oidc():
    """
    Is the user authenticated with OpenID Connect?
    """
    if 'userid' in session and 'screenname' in session:
        return True  # I don't care if Google's OIDC token expires
    if request.cookies.get(OIDC.id_token_cookie_name, None) is None:
        # Otherwise OIDC gets a little confused
        return False
    else:
        return OIDC.authenticate_or_redirect() is None

def is_authenticated():
    """
    Is the user authenticated (OIDC or backdoor)?
    """
    if is_authenticated_oidc():
        return True
    if not local_settings.ALLOW_BACKDOOR:
        return False
    return 'backdoor_sub' in request.cookies  \
        and 'backdoor_email' in request.cookies

def is_logged_in():
    """
    Is the user logged in (i.e. they've been to the database)
    """
    return is_authenticated() and  \
        'userid' in session and 'screenname' in session

def get_backdoor_details():
    """
    They're not authenticated by OIDC. We allow self-identification.
    """
    # TODO: REVISIT: Obviously, this needs a security review
    return request.cookies.get('backdoor_sub'),  \
        request.cookies.get('backdoor_email')

def get_oidc_token_details():
    """
    Implements a backdoor login alternative, for use in development only ldo.

    Returns (subject identifier, subject email)
    """
    try:
        return g.oidc_id_token['sub'], g.oidc_id_token['email']
    except (TypeError, AttributeError):
        if local_settings.ALLOW_BACKDOOR:
            return get_backdoor_details()
        raise

def ensure_user():
    """
    Commit user to database and determine userid.

    May return a complete web response (e.g. in case of error).

    May flash messages.
    """
    # TODO: REVISIT: automagically hook this into OIDC.check
    api = API()
    if not is_authenticated():
        # user is not authenticated yet
        return
    if is_logged_in():
        # user is authenticated and authorised (logged in)
        api.resubscribe(session['userid'])
        return
    identity, email = get_oidc_token_details()
    req = LoginRequest(identity=identity,
                       email=email)
    result = api.login(req)
    if isinstance(result, APIError):
        flash("Error registering user details.")
        logging.debug("login error: %s", result)
        return redirect(url_for('error_page'))
    session['userid'] = result.userid
    session['screenname'] = result.screenname
    flash("You have logged in as '%s'" % (session['screenname'],))

def get_my_screenname():
    """
    Get logged in user's screenname
    """
    if not is_logged_in() or 'screenname' not in session:
        return ""
    return session['screenname']

def error(message):
    """
    Flash error message and redirect to error page.
    """
    flash(message)
    return redirect(url_for('error_page'))

def is_what_now():
    """
    Does the user have the first_action cookie set?
    """
    return request.cookies.has_key("first_action")

@APP.route('/backdoor', methods=['GET', 'POST'])
def backdoor_page():
    """
    Let user declare their subject identifier, email address. While we're at it,
    let them know whether or not backdoor is enabled.
    """
    logging.error("/backdoor requested")
    is_enabled = local_settings.ALLOW_BACKDOOR
    # Also show the values of these on the page.
    form = BackdoorForm()
    success = form.validate_on_submit()
    if success:
        backdoor_sub = form.backdoor_sub.data
        backdoor_email = form.backdoor_email.data
        response = redirect(url_for('logout'))
    else:
        backdoor_sub, backdoor_email = get_backdoor_details()
        response = make_response(render_template('web/backdoor.html', form=form,
            backdoor_sub=backdoor_sub, backdoor_email=backdoor_email,
            is_enabled=is_enabled))
    if backdoor_sub is not None:
        response.set_cookie('backdoor_sub', backdoor_sub)
    if backdoor_email is not None:
        response.set_cookie('backdoor_email', backdoor_email)
    return response

@APP.route('/change', methods=['GET','POST'])
@auth_check
def change_screenname():
    """
    Without the user being logged in, give the user the option to change their
    screenname from what Google OpenID Connect gave us.
    """
    alternate_response = ensure_user()
    if alternate_response:
        return alternate_response
    form = ChangeForm()
    if form.validate_on_submit():
        new_screenname = form.change.data
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
    current = session['screenname']
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/change.html', title='Change Your Screenname',
        current=current, form=form, navbar_items=navbar_items,
        is_logged_in=is_logged_in(), is_account=True,
        my_screenname=get_my_screenname())

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
    return render_template('web/flash.html', title='Unsubscribe')

@APP.route('/logout', methods=['GET'])
def logout():
    """
    Explicit logout
    """
    session.pop('userid', None)
    session.pop('screenname', None)
    response = redirect(url_for('home_page'))
    response.set_cookie(OIDC.id_token_cookie_name, expires=0)
    return response

@APP.route('/login', methods=['GET'])
@auth_check
def login():
    """
    Log user in and redirect to some target page
    """
    req = request.args.get('next', url_for('home_page'))
    nxt = urlparse.urlparse(req)
    cur = urlparse.urlparse(request.url)
    if ((nxt.scheme and nxt.scheme != cur.scheme) or
        (nxt.netloc and nxt.netloc != cur.netloc)):
        # Avoid open redirect - a minor security vulnerability
        flash("Invalid redirect.")
        return redirect(url_for('home_page'))
    return redirect(req)

@APP.route('/error', methods=['GET'])
def error_page():
    """
    Unauthenticated page for showing errors to user.
    """
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/flash.html', title='Sorry',
        navbar_items=navbar_items, is_logged_in=is_logged_in(),
        my_screenname=get_my_screenname())

@APP.route('/about', methods=['GET'])
def about_page():
    """
    Unauthenticated information page.
    """
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('active', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/about.html', title="About",
        navbar_items=navbar_items,
        is_logged_in=is_logged_in(),
        my_screenname=get_my_screenname())

@APP.route('/faq', methods=['GET'])
def faq_page():
    """
    Frequently asked questions (unauthenticated).
    """
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('active', url_for('faq_page'), 'FAQ')]
    return render_template('web/faq.html', title="FAQ",
        navbar_items=navbar_items,
        is_logged_in=is_logged_in(),
        my_screenname=get_my_screenname())

@APP.route('/', methods=['GET'])
def home_page():
    """
    Generates the authenticated landing page. AKA the main or home page.
    """
    # TODO: 3: 'updated!' indicator on finished games (on the RGPs)

    # TODO: 3: account page with email preferences, screenname, and spawn

    if not is_authenticated():
        if local_settings.ALLOW_BACKDOOR:
            return redirect(url_for('backdoor_page'))
        else:
            return render_template('web/landing.html')
    alternate_response = ensure_user()
    if alternate_response:
        return alternate_response
    cfp = request.args.get('cfp', '1')
    ofp = request.args.get('ofp', '1')
    try:
        cfp = int(cfp)
    except ValueError:
        cfp = 1
    try:
        ofp = int(ofp)
    except ValueError:
        ofp = 1
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
    selected_heading = request.cookies.get("selected-heading", "heading-open")
    selected_mode = request.cookies.get("selected-mode", "mode-competition")
    my_running_games = sorted(my_games.running_details,
                              key=lambda g: not g.is_on_me)
    my_finished_games = sorted(my_games.finished_details,
                               key=lambda g: g.gameid, reverse=True)
    my_running_groups = sorted(my_games.running_groups,
                               key=lambda g: not g.is_on_me)
    my_finished_groups = sorted(my_games.finished_groups,
                                key=lambda g: g.groupid, reverse=True)
    my_open = [og for og in open_games
               if any([u.userid == userid for u in og.users])]
    others_open = [og for og in open_games
                   if not any([u.userid == userid for u in og.users])]

    cfp_less = cfp > 1
    cfp_more = len(my_finished_games) > cfp * 20
    my_finished_games = my_finished_games[(cfp - 1) * 20: cfp * 20]

    ofp_less = ofp > 1
    ofp_more = len(my_finished_groups) > ofp * 20
    my_finished_groups = my_finished_groups[(ofp - 1) * 20: ofp * 20]

    form = ChangeForm()
    navbar_items = [('active', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/home.html', title='Home',
        screenname=screenname, userid=userid, change_form=form,
        my_running_games=my_running_games,
        my_finished_games=my_finished_games,
        my_running_groups=my_running_groups,
        my_finished_groups=my_finished_groups,
        my_open=my_open,
        others_open=others_open,
        cfp=cfp, cfp_less=cfp_less, cfp_more=cfp_more,
        ofp=ofp, ofp_less=ofp_less, ofp_more=ofp_more,
        navbar_items=navbar_items,
        selected_heading=selected_heading,
        selected_mode=selected_mode,
        is_logged_in=is_logged_in(),
        is_first_action=is_what_now(),
        my_screenname=get_my_screenname())

@APP.route('/join', methods=['GET'])
@auth_check
def join_game():
    """
    Join game, flash status, redirect back to /home
    """
    # TODO: REVISIT: vulnerable to cross-site request forgery
    alternate_response = ensure_user()
    if alternate_response:
        return alternate_response
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
        msg = "Game joined!"
        flash(msg)
        if response is None:
            return redirect(url_for('home_page'))
        else:
            return redirect(url_for('game_page', gameid=response))
    flash(msg)
    return redirect(url_for('error_page'))

@APP.route('/leave', methods=['GET'])
@auth_check
def leave_game():
    """
    Leave game, flash status, redirect back to /home
    """
    # TODO: REVISIT: vulnerable to cross-site request forgery
    alternate_response = ensure_user()
    if alternate_response:
        return alternate_response
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

def _handle_action(gameid, userid, api, form, can_check, can_raise):
    """
    Handle response from an action form
    """
    # pylint:disable=R0912,R0913
    fold = form.fold.data
    passive = form.passive.data
    aggressive = form.aggressive.data
    if aggressive != NOTHING:
        try:
            total = int(form.total.data)
        except ValueError:
            flash("Incomprehensible raise total.")
            return False, False
    else:
        total = 0
    range_action = dtos.ActionDetails(fold_raw=fold, passive_raw=passive,
                                      aggressive_raw=aggressive,
                                      raise_total=total)
    try:
        range_name = "Fold"
        range_action.fold_range.validate()
        range_name = "Check" if can_check else "Call"
        range_action.passive_range.validate()
        range_name = "Raise" if can_raise else "Bet"
        range_action.aggressive_range.validate()
    except ValueError as err:
        flash("%s range is invalid. Reason: %s." % (range_name, err.message))
        return False, False
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
        return False, False
    action, spawned, is_first_action = result
    if action.is_fold:
        msg = "You folded."
    elif action.is_passive:
        if action.call_cost == 0:
            msg = "You checked."
        else:
            msg = "You called for %d." % (action.call_cost,)
    elif action.is_aggressive:
        if action.is_raise:
            msg = "You raised to %d." % (action.raise_total,)
        else:
            msg = "You bet %d." % (action.raise_total,)
    elif action.is_terminate:
        msg = "The game is finished."
    else:
        msg = "I can't figure out what happened, eh."
    flash(msg)
    for gameid in spawned:
        flash("A different line of this game will continue in game %d" %
              (gameid,))
    return True, is_first_action

def __board_to_vars(street, cards, order):
    """
    Break down cards
    """
    cards_ = [cards[i:i+2] for i in range(0, len(cards), 2)]
    return {'street': street,
            'cards': cards_,
            'order': order}

def _board_to_vars(item):
    """
    Replace little images into it
    """
    return __board_to_vars(item.street, item.cards, item.order)

def _range_action_to_vars(item):
    """
    Convert to percentages (relative), and such.

    Returns (total_range, fold_range, passive_range, aggressive_range, username,
             fold_pct, passive_pct, aggressive_pct, raise_total)
    """
    fold_options = item.range_action.fold_range  \
        .generate_options()
    passive_options = item.range_action.passive_range  \
        .generate_options()
    aggressive_options = item.range_action.aggressive_range  \
        .generate_options()
    all_options = fold_options + passive_options + aggressive_options
    combined_range = unweighted_options_to_description(all_options)
    fold_total = len(fold_options)
    passive_total = len(passive_options)
    aggressive_total = len(aggressive_options)
    total = len(all_options)
    # NOTE: some of this is necessarily common with ACTION_SUMMARY
    return {"screenname": item.user.screenname,
            "fold_pct": 100.0 * fold_total / total,
            "passive_pct": 100.0 * passive_total / total,
            "aggressive_pct": 100.0 * aggressive_total / total,
            "raise_total": item.range_action.raise_total,
            "is_check": item.is_check,
            "is_raise": item.is_raise,
            "original": combined_range,
            "fold": item.range_action.fold_range.description,
            "passive": item.range_action.passive_range.description,
            "aggressive": item.range_action.aggressive_range.description,
            "order": item.order}

def _action_summary_to_vars(range_action, action_result, action_result_order,
                            user_range):
    """
    Summarise an action result and user range in the context of the most recent
    range action.
    """
    new_total = len(HandRange(user_range.range_raw).  \
        generate_options())
    fol = pas = agg = NOTHING
    if action_result.action_result.is_fold:
        original = fol = range_action.range_action.fold_range.description
    elif action_result.action_result.is_passive:
        original = pas = range_action.range_action.passive_range.description
    else:
        original = agg = range_action.range_action.aggressive_range.description
    # NOTE: some of this is necessarily common with RANGE_ACTION
    return {"screenname": user_range.user.screenname,
            "action_result": action_result.action_result,
            "action_result_order": action_result_order,
            "percent": 100.0 * new_total / len(SET_ANYTHING_OPTIONS),
            "combos": new_total,
            "is_check": range_action.is_check,
            "is_raise": range_action.is_raise,
            "original": original,
            "fold": fol,
            "passive": pas,
            "aggressive": agg,
            "order": user_range.order}

def _action_result_to_vars(action_result):
    """
    Summarises action result for the case where the hand is in progress, and
    the user is not allowed to view the other players' ranges.
    """
    return {"screenname": action_result.user.screenname,
            "action_result": action_result.action_result,
            "order": action_result.order}

def _timeout_to_vars(timeout):
    """
    Summarises a timeout.
    """
    return {"screenname": timeout.user.screenname,
            "order": timeout.order}

def _chat_to_vars(chat):
    """
    Summarises a chat.
    """
    return {"screenname": chat.user.screenname,
            "message": chat.message,
            "order": chat.order}

def _showdown_to_vars(showdown):
    """
    Summarises a showdown.
    """
    return {"order": showdown.order,
            "is_passive": showdown.is_passive,
            "pot": showdown.pot,
            "players": showdown.players_desc(),
            "equities": showdown.equities}

def _make_history_list(game_history, situation):
    """
    Return a details list of each hand history item, as needed to display in
    HTML.
    """
    results = []
    # There is always a range action and an action before a user range
    most_recent_range_action = None
    most_recent_action_result = None
    pending_action_result = None
    # First, inject a board if there is one in the situation
    if situation.board_raw:
        results.append(("BOARD", __board_to_vars(situation.current_round,
                                                 situation.board_raw, -1)))
    for item in game_history:
        if isinstance(item, GameItemUserRange):
            if pending_action_result is not None:
                results.remove(pending_action_result)
                action_result_order = pending_action_result[1]['order']
                pending_action_result = None
            results.append(("ACTION_SUMMARY",
                            _action_summary_to_vars(most_recent_range_action,
                                                    most_recent_action_result,
                                                    action_result_order,
                                                    item)))
        elif isinstance(item, GameItemRangeAction):
            most_recent_range_action = item
            results.append(("RANGE_ACTION",
                            _range_action_to_vars(item)))
        elif isinstance(item, GameItemActionResult):
            most_recent_action_result = item
            pending_action_result = ("ACTION_RESULT",
                                     _action_result_to_vars(item))
            results.append(pending_action_result)
            # This will be removed if there is a following user range
        elif isinstance(item, GameItemBoard):
            results.append(("BOARD", _board_to_vars(item)))
        elif isinstance(item, GameItemTimeout):
            results.append(("TIMEOUT", _timeout_to_vars(item)))
        elif isinstance(item, GameItemChat):
            results.append(("CHAT", _chat_to_vars(item)))
        elif isinstance(item, GameItemShowdown):
            results.append(("SHOWDOWN", _showdown_to_vars(item)))
        else:
            logging.error("unrecognised type of hand history item: %s", item)
            results.append(("UNKNOWN", (str(item),)))
    return results

def _make_payments(game_history, game_payments, scheme_includes):
    """
    game_payments maps order to map of reason to list of GamePayment

    Return dict mapping range action order to list of payments.

    One payment includes a reason, and a dict mapping player order to payment.
    """
    all_payments = {}
    writing_order = None
    for item in game_history:
        if isinstance(item, (GameItemRangeAction, GameItemBoard)):
            writing_order = item.order
            all_payments[writing_order] = []
        if writing_order is None:
            continue
        by_reason = game_payments[item.order]  # map reason to list
        for reason in [PaymentToPlayer.REASON_FOLD_EQUITY,
                       PaymentToPlayer.REASON_BRANCH,
                       PaymentToPlayer.REASON_SHOWDOWN_CALL,
                       PaymentToPlayer.REASON_SHOWDOWN,
                       PaymentToPlayer.REASON_POT,
                       PaymentToPlayer.REASON_BOARD]:
            if reason not in scheme_includes:
                continue
            relevant_payments = by_reason.get(reason, [])
            for raw in relevant_payments:
                digested = {
                    'reason': reason,
                    'screenname': raw.user.screenname,
                    'amount': raw.amount
                }
                # TODO: REVISIT: it'd be nice if we could include the amounts...
                # ... but we actually don't record the call cost for range
                # actions! (ActionDetails is probably the right DTO,
                # corresponding to GameHistoryRangeAction in the database.)
                # Note that it's the showdown call that's a problem, not the
                # regular call.
                if reason == PaymentToPlayer.REASON_POT:
                    if item.action_result.is_passive:
                        if item.action_result.raise_total == 0:
                            digested['action'] = 'check'
                        else:
                            digested['action'] = 'call'
                    elif item.action_result.is_aggressive:
                        if item.action_result.is_raise:
                            digested['action'] = 'raise to %d' %  \
                                (item.action_result.raise_total,)
                        else:
                            digested['action'] = 'bet %d' %  \
                                (item.action_result.raise_total,)
                elif reason == PaymentToPlayer.REASON_SHOWDOWN_CALL:
                    digested['action'] = 'call'
                all_payments[writing_order].append(digested)
    return all_payments

def _calc_is_new_chat(game_history, userid):
    """
    Determine if there is new chat, from userid's perspective.

    Specifically, if there is a chat more recent than userid's last action.
    """
    is_new_chat = False
    for item in game_history:
        if isinstance(item, GameItemChat):
            is_new_chat = True
        if isinstance(item, (GameItemActionResult, GameItemChat)) and  \
                item.user.userid == userid:
            is_new_chat = False
    return is_new_chat

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
        success, set_first_action = _handle_action(gameid, userid, api, form,
                game.current_options.can_check(),
                game.current_options.can_raise())
        if success:
            response = redirect(url_for('game_page', gameid=gameid))
            if set_first_action:
                response.set_cookie('first_action', 'True', max_age=86400)
            return response

    # First load, OR something's wrong with their data.
    range_editor_url = url_for('range_editor',
        rng_original=game.game_details.current_player.range_raw,
        board=game.game_details.board_raw,
        raised="true" if game.current_options.is_raise else "false",
        can_check="true" if game.current_options.can_check() else "false",
        can_raise="true" if game.current_options.can_raise() else "false",
        min_raise=game.current_options.min_raise,
        max_raise=game.current_options.max_raise)
    title = 'Game %d' % (gameid,)
    history = _make_history_list(game.history, game.game_details.situation)
    is_new_chat = _calc_is_new_chat(game.history, userid)
    board_raw = game.game_details.board_raw
    board = [board_raw[i:i+2] for i in range(0, len(board_raw), 2)]
    is_me = (userid == game.game_details.current_player.user.userid)
    is_mine = (userid in [rgp.user.userid
                          for rgp in game.game_details.rgp_details])
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/game.html', title=title, form=form,
        board=board, game_details=game.game_details,
        num_players=len(game.game_details.rgp_details), history=history,
        current_options=game.current_options,
        is_me=is_me, is_mine=is_mine, is_new_chat=is_new_chat, is_running=True,
        range_editor_url=range_editor_url,
        navbar_items=navbar_items, is_logged_in=is_logged_in(),
        is_first_action=is_what_now(), url=request.url,
        my_screenname=get_my_screenname())

def _paused_game(game, gameid, userid):
    """
    Response from game page when the requested game is paused.
    """
    title = 'Game %d' % (gameid,)
    history = _make_history_list(game.history, game.game_details.situation)
    is_new_chat = _calc_is_new_chat(game.history, userid)
    board_raw = game.game_details.board_raw
    board = [board_raw[i:i+2] for i in range(0, len(board_raw), 2)]
    is_mine = (userid in [rgp.user.userid
                          for rgp in game.game_details.rgp_details])
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/game.html', title=title,
        board=board, game_details=game.game_details,
        num_players=len(game.game_details.rgp_details), history=history,
        is_me=False, is_mine=is_mine, is_new_chat=is_new_chat, is_running=True,
        navbar_items=navbar_items, is_logged_in=is_logged_in(),
        is_first_action=is_what_now(), url=request.url,
        my_screenname=get_my_screenname())

def _finished_game(game, gameid, userid):
    """
    Response from game page when the requested game is finished.
    """
    title = 'Game %d' % (gameid,)
    history = _make_history_list(game.history, game.game_details.situation)
    scheme = request.args.get('scheme', 'ev')
    scheme_includes = RunningGameParticipantResult.SCHEME_DETAILS[scheme]
    payments = _make_payments(game.history, game.payments, scheme_includes)
    is_new_chat = _calc_is_new_chat(game.history, userid)
    analyses = []  # TODO: 5: fold equity analysis: game.analysis.keys()
    is_mine = (userid in [rgp.user.userid
                          for rgp in game.game_details.rgp_details])
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/game.html', title=title,
        game_details=game.game_details, history=history, payments=payments,
        num_players=len(game.game_details.rgp_details), analyses=analyses,
        is_running=False, is_mine=is_mine, is_new_chat=is_new_chat,
        scheme=scheme, navbar_items=navbar_items, is_logged_in=is_logged_in(),
        is_first_action=is_what_now(), url=request.url,
        my_screenname=get_my_screenname())

def authenticated_game_page(gameid):
    """
    Game page when user is authenticated (i.e. the private view)
    """
    alternate_response = ensure_user()
    if alternate_response:
        return alternate_response
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
        return _finished_game(response, gameid, userid)
    elif response.game_details.current_player == None:
        return _paused_game(response, gameid, userid)
    else:
        return _running_game(response, gameid, userid, api)

def unauthenticated_game_page(gameid):
    """
    Game page when user is not authenticated (i.e. the public view)
    """
    api = API()
    response = api.get_public_game(gameid)
    if isinstance(response, APIError):
        if response is api.ERR_NO_SUCH_RUNNING_GAME:
            msg = "Invalid game ID."
        else:
            msg = "An unknown error occurred retrieving game %d, sorry." %  \
                (gameid,)
        flash(msg)
        return redirect(url_for('error_page'))

    if response.is_finished():
        return _finished_game(response, gameid, None)
    else:
        return _running_game(response, gameid, None, api)

@APP.route('/game', methods=['GET', 'POST'])
def game_page():
    """
    View of the specified game, authentication-aware
    """
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))

    if is_authenticated():
        return authenticated_game_page(gameid)
    else:
        flash("You are not logged in. You are viewing this page anonymously.")
        return unauthenticated_game_page(gameid)

def _chat_page(game, gameid, userid, api):
    """
    Post-validation chat page functionality.
    """
    form = ChatForm()
    if form.validate_on_submit():
        response = api.chat(gameid, userid, form.message.data)
        if isinstance(response, APIError):
            # No further info, because none of the errors should ever happen
            flash(str(response))
        else:
            # Success, refresh
            return redirect(url_for('chat_page', gameid=gameid))
    # First load, OR something's wrong with their data.
    all_chats = [h[1] for h in _make_history_list(game.history,
                                                  game.game_details.situation)
                 if h[0] == 'CHAT']
    return render_template('web/chat.html', gameid=gameid, form=form,
        all_chats=all_chats)

@APP.route('/chat', methods=['GET', 'POST'])
@auth_check
def chat_page():
    """
    Chat history for game, and a text field to chat into game.

    Requires that user is registered in game.
    """
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

    return _chat_page(response, gameid, userid, api)

@APP.route('/analysis', methods=['GET'])
def analysis_page():
    """
    Analysis of a particular hand history item.
    """
    # TODO: 5: the range viewer on the analysis page

    # This can simply display each rank combo and allow selection of suit
    # combos. Then it can display, for each rank combo, the average EV of the
    # selected suit combos, as hover text. I'm not sure about colours.

    # Or more simply, display EV of each combo in hover text, and colour squares
    # like a normal range viewer (green / yellow / red / blue).
    gameid = request.args.get('gameid', None)
    if gameid is None:
        return error("Invalid game ID.")
    try:
        gameid = int(gameid)
    except ValueError:
        return error("Invalid game ID (not a number).")

    api = API()
    response = api.get_public_game(gameid)
    if isinstance(response, APIError):
        if response is api.ERR_NO_SUCH_RUNNING_GAME:
            msg = "Invalid game ID."
        else:
            msg = "An unknown error occurred retrieving game %d, sorry." %  \
                (gameid,)
        return error(msg)
    game = response

    order = request.args.get('order', None)
    if order is None:
        return error("Invalid order.")
    try:
        order = int(order)
    except ValueError:
        return error("Invalid order (not a number).")

    item = None
    for item in game.history:
        if item.order == order:
            break
    else:
        return error("Invalid order (not in game).")

    if not isinstance(item, dtos.GameItemActionResult):
        return error("Invalid order (not a bet or raise).")

    if not item.action_result.is_aggressive:
        return error("Analysis only for bets right now, sorry.")

    try:
        aife = game.analysis[order]
    except KeyError:
        return error("Analysis for this action is not ready yet.")

    street_text = aife.STREET_DESCRIPTIONS[aife.street]
    if item.action_result.is_raise:
        action_text = "raises to %d" % (item.action_result.raise_total,)
    else:
        action_text = "bets %d" % (item.action_result.raise_total,)

    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    items_aggressive = [i for i in aife.items if i.is_aggressive]
    items_passive = [i for i in aife.items if i.is_passive]
    items_fold = [i for i in aife.items if i.is_fold]
    items_aggressive.sort(key=lambda i: i.immediate_result)  # most negative 1st
    items_passive.sort(key=lambda i: i.immediate_result, reverse=True)
    items_fold.sort(key=lambda i: i.immediate_result, reverse=True)
    # Could also have a status column or popover or similar:
    # "good bluff" = +EV
    # "bad bluff" = -EV on river
    # "possible semibluff" = -EV not on river
    return render_template('web/analysis.html', gameid=gameid,
        screenname=item.user.screenname, street_text=street_text,
        action_text=action_text,
        items_aggressive=items_aggressive,
        items_passive=items_passive,
        items_fold=items_fold,
        is_raise=aife.is_raise, is_check=aife.is_check,
        navbar_items=navbar_items, is_logged_in=is_logged_in(), url=request.url,
        my_screenname=get_my_screenname())

@APP.route('/user', methods=['GET'])
def user_page():
    screenname = request.args.get('screenname', None)
    if screenname is None:
        return error("Invalid screenname.")
    min_hands = request.args.get('min', '1')
    try:
        min_hands = int(min_hands)
    except ValueError:
        return error("Invalid min.")
    is_competition = request.args.get('mode', 'competition') == 'competition'

    api = API()
    result = api.get_user_by_screenname(screenname)
    if result == API.ERR_NO_SUCH_USER:
        return error("Unrecognised screenname.")
    userid = result.userid
    screenname = result.screenname
    result = api.get_user_statistics(userid, min_hands=min_hands,
                                     is_competition=is_competition)
    if result == API.ERR_NO_SUCH_USER:
        return error("No such user.")
    if isinstance(result, APIError):
        return error("An unknown error occurred retrieving results.")

    min_visible = 5  # stats only shown if 5 hands played

    # suppress user's situation results where insufficient position hands
    for situation in result:
        for position in situation.positions:
            if position.played < min_visible:
                situation.average = None

    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/user.html',
        screenname=screenname,
        situations=result,
        min_visible=min_visible,
        mode='competition' if is_competition else 'optimization',
        navbar_items=navbar_items,
        is_logged_in=is_logged_in(),
        is_first_action=is_what_now(),
        url=request.url,
        my_screenname=get_my_screenname())

@APP.route('/alpha', methods=['GET'])
def alpha():
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/alpha.html',
        navbar_items=navbar_items,
        is_logged_in=is_logged_in(),
        url=request.url,
        my_screenname=get_my_screenname())

@APP.route('/whatnow', methods=['GET'])
def whatnow():
    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]

    response = make_response(render_template('web/whatnow.html',
        navbar_items=navbar_items,
        is_logged_in=is_logged_in(),
        url=request.url,
        my_screenname=get_my_screenname()))
    response.set_cookie('first_action', expires=0)
    return response

@APP.route('/group', methods=['GET'])
def group_page():
    gameid = request.args.get('gameid', None)
    if gameid is None:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))
    try:
        gameid = int(gameid)
    except ValueError:
        flash("Invalid game ID.")
        return redirect(url_for('error_page'))

    if is_logged_in():
        userid = session['userid']
    else:
        userid = None

    api = API()
    result = api.get_group_games(gameid=gameid, userid=userid)
    if result == API.ERR_NO_SUCH_RUNNING_GAME:
        flash("No such game.")
        return redirect(url_for('error_page'))
    del gameid
    groupid, games = result  # pylint:disable=unpacking-non-sequence

    # We rely on all games having the same players here - and there being at
    # least one of them!
    screennames = [rgp.user.screenname for rgp in games[0].rgp_details]
    results_by_player = {screenname: 0.0 for screenname in screennames}
    for i, screenname in enumerate(screennames):
        for game in games:
            if not game.rgp_details[i].results:
                continue
            results_by_player[screenname] += game.spawn_factor *  \
                game.rgp_details[i].results['ev']
    total_results = [{'screenname': screenname,
                      'result': results_by_player[screenname]}
                     for screenname in screennames]
    total_weight = sum(game.spawn_factor
                       for game in games if game.is_analysed)

    # TODO: 2: (big work! awesome!) betting line "roll-up" and/or EV tree view

    games = sorted(games, key=game_line_key)

    navbar_items = [('', url_for('home_page'), 'Home'),
                    ('', url_for('about_page'), 'About'),
                    ('', url_for('faq_page'), 'FAQ')]
    return render_template('web/group.html',
        description=games[0].situation.description,
        games=games,
        screennames=[user.screenname for user in games[0].users],
        total_weight=total_weight,
        total_results=total_results,
        userid=userid,
        groupid=groupid,
        navbar_items=navbar_items,
        is_logged_in=is_logged_in(),
        is_first_action=is_what_now(),
        url=request.url,
        my_screenname=get_my_screenname())
