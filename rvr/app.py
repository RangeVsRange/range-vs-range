"""
Defines the Flask container, 'APP'
"""
from rvr.infrastructure.ioc import FEATURES
from rvr.mocks.opengames import MockGameFilter
from rvr.mocks.situations import MockSituationProvider
from flask import Flask
from flask_googleauth import GoogleAuth
from werkzeug import SharedDataMiddleware  #IGNORE:E0611 @UnresolvedImport
import os
import logging

# IoC registration
FEATURES.provide('GameFilter', MockGameFilter())  # singleton
FEATURES.provide('SituationProvider', MockSituationProvider())  # singleton

APP = Flask(__name__)
APP.config.from_object('rvr.config')
APP.config.from_pyfile('local-settings.py', silent=True)
APP.wsgi_app = SharedDataMiddleware(APP.wsgi_app,
    {'/':os.path.join(os.path.dirname(__file__), 'static')})

AUTH = GoogleAuth(APP)

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)
