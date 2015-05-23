"""
Defines the Flask container, 'APP'
"""
# pylint:disable=no-name-in-module
from flask import Flask
from werkzeug import SharedDataMiddleware  #IGNORE:E0611 @UnresolvedImport
import os
from flask_mail import Mail
from flask.helpers import url_for
from flask_bootstrap import Bootstrap
from flask_oidc import OpenIDConnect

APP = Flask(__name__)
APP.config.from_object('rvr.config')
APP.config.from_object('rvr.local_settings')
APP.wsgi_app = SharedDataMiddleware(APP.wsgi_app,
    {'/':os.path.join(os.path.dirname(__file__), 'static')})

Bootstrap(APP)
MAIL = Mail(APP)
OIDC = OpenIDConnect(APP)

def make_unsubscribe_url(identity):
    """
    Make a proper Flask-smart URL for unsubscribing.
    """
    return url_for('unsubscribe', _external=True, identity=identity)

def make_game_url(gameid, login=False):
    """
    Make a game URL for sending via email.
    """
    if not login:
        return url_for('game_page', _external=True, gameid=gameid)
    else:
        relative = url_for('game_page', gameid=gameid)
        return url_for('login', _external=True, next=relative)
