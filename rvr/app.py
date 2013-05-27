"""
Defines the Flask container, 'APP'
"""
from flask import Flask
APP = Flask(__name__)
APP.config.from_object('rvr.config')