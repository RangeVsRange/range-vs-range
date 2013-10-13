from rvr.app import APP
from flask_openid import OpenID
from flask.globals import g, session, request
from rvr.db.tables import RvrUser
from werkzeug.utils import redirect
from flask.templating import render_template
from flask.helpers import flash, url_for

OID = OpenID(APP)  # gets store location from config

@APP.before_request
def lookup_current_user():
    g.user = None
    if 'openid' in session:
        g.user = RvrUser.query.filter_by(openid=session['openid']).first()  # @UndefinedVariable
        
@APP.route('/login', methods=['GET', 'POST'])
@OID.loginhandler
def login():
    if g.user is not None:
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
    session['openid'] = resp.identity_url  # Push openid into session cookie... But is this forgeable?
    user = RvrUser.query.filter_by(openid=resp.identity_url).first()  # @UndefinedVariable
    if user is not None:
        flash(u'Successfully signed in')
        g.user = user
        return redirect(OID.get_next_url())
    return redirect(url_for('create_profile', next=OID.get_next_url(),
                            name=resp.fullname or resp.nickname,
                            email=resp.email))
    
@APP.route('/create-profile')
def create_profile():
    """
    Get params: next, email, name
    """
    return redirect(OID.get_next_url())