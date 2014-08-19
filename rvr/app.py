"""
Defines the Flask container, 'APP'
"""
from flask import Flask
from werkzeug import SharedDataMiddleware  #IGNORE:E0611 @UnresolvedImport
import os
from flask_googleauth import GoogleAuth
from flask_mail import Mail
from flask.helpers import url_for
from flask_bootstrap import Bootstrap

APP = Flask(__name__)
APP.config.from_object('rvr.config')
APP.config.from_object('rvr.local_settings')
APP.wsgi_app = SharedDataMiddleware(APP.wsgi_app,
    {'/':os.path.join(os.path.dirname(__file__), 'static')})

Bootstrap(APP)

MAIL = Mail(APP)

# Flask-GoogleAuth, used by main.py
AUTH = GoogleAuth(APP)

def make_unsubscribe_url(identity):
    """
    Make a proper Flask-smart URL for unsubscribing.
    """
    return url_for('unsubscribe', _external=True, identity=identity)

def make_game_url(gameid):
    """
    Make a game URL for sending via email.
    """
    return url_for('game_page', _external=True, gameid=gameid)