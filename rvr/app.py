"""
Defines the Flask container, 'APP'
"""
from flask import Flask
from werkzeug import SharedDataMiddleware  #IGNORE:E0611 @UnresolvedImport
import os
import logging
from flask_googleauth import GoogleAuth
# from flask_openid import OpenID

APP = Flask(__name__)
APP.config.from_object('rvr.config')
APP.config.from_pyfile('local-settings.py', silent=True)
APP.wsgi_app = SharedDataMiddleware(APP.wsgi_app,
    {'/':os.path.join(os.path.dirname(__file__), 'static')})

# TODO: 0: replace Flask-GoogleAuth with Flask-OpenID 
# flask_googleauth is not working on PythonAnywhere, and there doesn't seem to
# be any way to get sufficient debug information to diagnose the problem. So I'm
# going to replace it with the less friendly, more portable, less google-
# specific flask.ext.openid (Flask-OpenID). I'm going to do this by creating a
# copy of all the functionality that currently uses Flask-GoogleAuth, and update
# the copy to now use Flask-OpenID. At this point the application will support
# both (if not at the same moment). Then I will swap to using Flask-OpenID, and
# see if that makes PythonAnywhere happier.

# Flask-GoogleAuth
AUTH = GoogleAuth(APP)

# Flask-OpenID
# OID = OpenID(APP)

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)