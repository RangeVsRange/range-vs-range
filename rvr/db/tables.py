"""
Declares database tables
"""
from rvr.db.connect import DB

#pylint:disable=E1101,R0903
class User(DB.Model):
    """
    A user of the application
    """
    id = DB.Column(DB.Integer, primary_key=True)  # @UndefinedVariable
    openid = DB.Column(DB.String(120), unique=True)  # @UndefinedVariable

    def __init__(self, openid):
        self.openid = openid

    def __repr__(self):
        return '<User %r>' % self.openid