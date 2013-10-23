"""
Creation of database, connection to database, sessions for use of database
"""
from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from rvr.core import backendconfig

ENGINE = create_engine('sqlite:///%s' % backendconfig.DB_PATH, echo=False)
SESSION = sessionmaker(bind=ENGINE)
BASE = declarative_base()
