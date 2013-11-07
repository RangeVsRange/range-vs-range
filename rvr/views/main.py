"""
The main pages for the site
"""
from flask import render_template, redirect, url_for
from rvr import APP
from rvr.forms.change import ChangeForm
from rvr.core.api import API, APIError
from rvr.app import AUTH
from rvr.core.dtos import LoginRequest, ChangeScreennameRequest
from werkzeug.exceptions import abort  # @UnresolvedImport
import logging
from flask.helpers import flash
from flask.globals import request, session, g

@APP.before_request
def ensure_user():
    """
    Commit user to database and determine userid
    """
    if request.endpoint == 'change_screenname':
        # avoid redirect loop
        return
    if not g.user or 'identity' not in g.user:
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
        screenname = g.user.name
    api = API()
    req = LoginRequest(identity=g.user.identity,  # @UndefinedVariable
                       email=g.user.email,  # @UndefinedVariable
                       screenname=screenname)  # @UndefinedVariable
    result = api.login(req)
    if result == API.ERR_LOGIN_DUPLICATE_SCREENNAME:
        # User is authenticated with OpenID, but not yet authorised (logged
        # in). We redirect them to a page that allows them to choose a
        # different screenname.
        flash("The screenname '%s' is already taken." % g.user.name)
        return redirect(url_for('change_screenname'))
    if isinstance(result, APIError):
        logging.debug("login error: %s", result)
        abort(403)
    session['userid'] = result.userid
    session['screenname'] = result.screenname

@APP.route('/change', methods=['GET', 'POST'])
@AUTH.required
def change_screenname():
    """
    Without the user being logged in, give the user the option to change their
    screenname from what Google OpenID gave us.
    """
    form = ChangeForm()
    if form.validate_on_submit():
        new_screenname = form.change.data
        session['screenname'] = new_screenname
        if 'userid' in session:
            req = ChangeScreennameRequest(session['userid'],
                                          session['screenname'])
            resp = API().change_screenname(req)
            if isinstance(resp, APIError):
                logging.debug("change_screenname error: %s", resp)
                flash("An error occurred.")
            else:
                flash("Your screenname has been changed to '%s'." %
                      (new_screenname, ))
        return redirect(url_for('home_page'))
    return render_template('change.html', title='Change Your Screenname',
                           current=g.user.name, form=form)

@APP.route('/', methods=['GET'])
def landing_page():
    """
    Generates the unauthenticated landing page. AKA the main or home page.
    """
    return render_template('landing.html', title='Welcome')

@APP.route('/home', methods=['GET', 'POST'])
@AUTH.required
def home_page():
    """
    Authenticated landing page. User is taken here when logged in.
    """
    api = API()
    userid = session['userid']
    screenname = session['screenname']
    open_games = api.get_open_games()
    my_games = api.get_user_games(userid)
    my_open = [og for og in open_games
               if any([u.userid == userid for u in og.users])]
    others_open = [og for og in open_games
                   if not any([u.userid == userid for u in og.users])]
    my_turn_games = [mg for mg in my_games.running_details
                     if mg.current_user_details.userid == userid]
    others_turn_games = [mg for mg in my_games.running_details
                         if mg.current_user_details.userid != userid]
    finished_games = my_games.finished_details
    return render_template('home.html', title='Home',
        screenname=screenname,
        my_open=my_open,
        others_open=others_open,
        my_turn_games=my_turn_games,
        others_turn_games=others_turn_games,
        finished_games=finished_games
        )