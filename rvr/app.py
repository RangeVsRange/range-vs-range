"""
Defines the Flask container, 'APP'
"""
from rvr.infrastructure.ioc import FEATURES
from flask import Flask
from rvr.mocks.opengames import MockGameFilter
from rvr.mocks.situations import MockSituationProvider

# IoC registration
FEATURES.provide('GameFilter', MockGameFilter())  # singleton
FEATURES.provide('SituationProvider', MockSituationProvider())  # singleton

APP = Flask(__name__)
APP.config.from_object('rvr.config')