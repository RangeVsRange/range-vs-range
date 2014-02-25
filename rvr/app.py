"""
Defines the Flask container, 'APP'
"""
from flask import Flask
from werkzeug import SharedDataMiddleware  #IGNORE:E0611 @UnresolvedImport
import os
from flask_googleauth import GoogleAuth
from flask_openid import OpenID

APP = Flask(__name__)
APP.config.from_object('rvr.config')
APP.config.from_pyfile('local_settings.py', silent=True)
APP.wsgi_app = SharedDataMiddleware(APP.wsgi_app,
    {'/':os.path.join(os.path.dirname(__file__), 'static')})

# Flask-GoogleAuth, used by main.py
AUTH = GoogleAuth(APP)

# Flask-OpenID, used by main_openid.py (OpenID rewrite of main.py)
OID = OpenID(APP)