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
    setting it back to None after the call. This is a neater approach than the
    old with_session, which was not object-aware. 
    """
    @wraps(fun)
    def inner(*args, **kwargs):
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
        def __init__(self):
            self.session = None
            
        @create_session
        def method(self, arg):
            """ recurse iff arg """
            print arg, self.session
            if arg:
                self.method(False)
    
    cls = Class()
    print "cls.method(True):"
    cls.method(True)
    print
    print "cls.method(False):"
    cls.method(False)