"""
Contains flask db object
"""
# pylint:disable=import-error
from flask_sqlalchemy import SQLAlchemy  # @UnresolvedImport
from rvr.app import APP

DB = SQLAlchemy(APP)
