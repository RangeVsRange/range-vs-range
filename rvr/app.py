"""
Defines the Flask container, 'APP'
"""
from flask import Flask
from flask_googleauth import GoogleAuth
from werkzeug import SharedDataMiddleware  #IGNORE:E0611 @UnresolvedImport
import os
import logging

APP = Flask(__name__)
APP.config.from_object('rvr.config')
APP.config.from_pyfile('local-settings.py', silent=True)
APP.wsgi_app = SharedDataMiddleware(APP.wsgi_app,
    {'/':os.path.join(os.path.dirname(__file__), 'static')})

AUTH = GoogleAuth(APP)

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)
