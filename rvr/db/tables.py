"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Sequence
from rvr.db.connect import DB
from rvr.db.creation import BASE

#pylint:disable=E1101,R0903
class RvrUser(DB.Model):
    """
    A user of the application
    """
    id = DB.Column(DB.Integer, primary_key=True)  # @UndefinedVariable
    openid = DB.Column(DB.String(120), unique=True)  # @UndefinedVariable

    def __init__(self, openid):
        self.openid = openid

    def __repr__(self):
        return '<User %r>' % self.openid
    
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