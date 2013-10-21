"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Sequence
from rvr.db.creation import BASE

#pylint:disable=W0232
class User(BASE):
    """
    A user of the application
    """
    __tablename__ = 'user'
    userid = Column(Integer, Sequence('userid_seq'), primary_key=True)
    provider = Column(String(120), nullable=False, unique=False)
    screenname = Column(String(20), nullable=False, unique=True)
    email = Column(String(256), nullable=False, unique=True)
    
    def __repr__(self):
        return "User<userid='%s', screenname='%s'>" %  \
            (self.userid, self.screenname)