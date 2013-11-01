"""
Views to implement flask_openid support
"""
from rvr.app import APP
from flask_openid import OpenID
from flask.globals import g, session, request
from werkzeug.utils import redirect
from flask.templating import render_template
from flask.helpers import flash, url_for
from rvr.core.dtos import LoginDetails
from rvr.core.api import API

OID = OpenID(APP)  # gets store location from config

# pylint:disable=E1120

UNAUTHENTICATED = ['login', 'landing_page']

@APP.before_request
def ensure_login():
    """
    Auto-login with return to target URL. Redirect will lose post data, but if
    they're posting a form they've either already viewed a page, so they should
    be logged in, or they're posting cross-site, which is bad anyway.
    """
    g.userid = None
    if 'userid' in session:
        g.userid = session['userid']
    elif request.endpoint not in UNAUTHENTICATED:
        return redirect(url_for('login', next=request.url))

@APP.route('/login', methods=['GET', 'POST'])
@OID.loginhandler
def login():
    """
    Shows login page and handles OpenID login
    """
    if g.userid is not None:
        return redirect(OID.get_next_url())
    if request.method == 'POST':
        openid = request.form.get('openid')
        if openid:
            return OID.try_login(openid, ask_for=['email', 'fullname',
                                                  'nickname'])
    return render_template('login.html', next=OID.get_next_url(),
        error=OID.fetch_error())

@OID.after_login
def create_or_login(resp):
    """
    Here we give the user this identity. I believe this is not forgeable
    # because this method is only called internally when we complete the
    # OpenID check_authentication, which is done directly with the OpenID
    # provider.
    # The session is secured by HMAC using our SECRET_KEY.
    """
    api = API()
    req = LoginDetails(userid=None,
                       provider='Google',
                       email=resp.email,
                       screenname=resp.nickname or resp.fullname)
    result = api.login(req)
    if result.userid is not None:
        session['userid'] = result.userid
        session['screenname'] = result.screenname
        flash(u'Successfully signed in')
        g.userid = result.userid
        return redirect(OID.get_next_url())