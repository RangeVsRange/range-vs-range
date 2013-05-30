"""
Defines the Flask container, 'APP'
"""
from rvr.infrastructure.ioc import FEATURES
from flask import Flask
from rvr.mocks import MockGameFilter

# IoC registration
FEATURES.provide('GameFilter', MockGameFilter())  # singleton

APP = Flask(__name__)
APP.config.from_object('rvr.config')