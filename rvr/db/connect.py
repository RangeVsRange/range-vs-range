"""
Contains flask db object
"""
from flask_sqlalchemy import SQLAlchemy
from rvr.app import APP

DB = SQLAlchemy(APP)
