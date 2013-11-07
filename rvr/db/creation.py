"""
Creation of database, connection to database, sessions for use of database
"""
from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from rvr.core import backendconfig
from contextlib import contextmanager
from functools import wraps

ENGINE = create_engine('sqlite:///%s' % backendconfig.DB_PATH, echo=False)
SESSION = sessionmaker(bind=ENGINE)
BASE = declarative_base()

#pylint:disable=R0903

# from http://docs.sqlalchemy.org/en/rel_0_8/orm/session.html
@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SESSION()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def create_session(fun):
    """
    Creates a session_scope() for session and assigns it to the parent object,
    setting it back to None after the call.
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        See parent.
        """
        self = args[0]
        if self.session is None:
            with session_scope() as session:
                self.session = session
                try:
                    return fun(*args, **kwargs)
                finally:
                    self.session = None
        else:
            return fun(*args, **kwargs)
    return inner

if __name__ == '__main__':
    class Class(object):
        """
        Class to test @create_session only
        """
        def __init__(self):
            self.session = None
            
        @create_session
        def method(self, arg):
            """ recurse iff arg """
            print arg, self.session
            if arg:
                self.method(False)
    
    CLS = Class()
    print "cls.method(True):"
    CLS.method(True)
    print
    print "cls.method(False):"
    CLS.method(False)