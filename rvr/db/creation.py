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

def with_session(fun):
    """
    Creates a session_scope() and replace last parameter with it (if None)
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        If session argument exists, call fun as such.
        If session argument doesn't exist, wrap fun in session_scope()
        """
        if len(args) > 0 and isinstance(args[-1], SESSION):
            return fun(*args, **kwargs)
        else:
            with session_scope() as session:
                args2 = args + (session,)
                return fun(*args2, **kwargs)
    return inner

if __name__ == '__main__':
    @with_session
    def func(arg, session):
        """Recurse iff arg"""
        print arg, session
        if arg:
            func(False, session)
    
    print "func(True):"
    func(True)
    print
    print "func(False):"
    func(False)