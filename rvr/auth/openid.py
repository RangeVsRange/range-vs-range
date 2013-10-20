from rvr.app import APP
from flask_openid import OpenID
from flask.globals import g, session, request
from rvr.db.tables import RvrUser
from werkzeug.utils import redirect
from flask.templating import render_template
from flask.helpers import flash, url_for
from rvr.core.dtos import LoginDetails
from rvr.core.api import API

OID = OpenID(APP)  # gets store location from config

@APP.before_request
def lookup_current_user():
    g.userid = None
    if 'userid' in session:
        g.userid = session['userid']
        
@APP.route('/login', methods=['GET', 'POST'])
@OID.loginhandler
def login():
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
    # Here we give the user this identity. I believe this is not forgeable
    # because this method is only called internally when we complete the
    # OpenID check_authentication, which is done directly with the OpenID
    # provider. The session is secured by HMAC using our SECRET_KEY
    request = LoginDetails(userid=None,
                           provider='Google',
                           email=resp.email,
                           screenname=resp.nickname or resp.fullname)
    result = API().login(request)
    if result.userid is not None:
        session['userid'] = result.userid
        flash(u'Successfully signed in')
        g.userid = result.userid
        return redirect(OID.get_next_url())
#    return redirect(url_for('create_profile', next=OID.get_next_url(),
#                            name=resp.fullname or resp.nickname,
#                            email=resp.email))
#
#@APP.route('/create-profile')
#def create_profile():
#    """
#    Get params: next, email, name
#    """
#    return redirect(OID.get_next_url())