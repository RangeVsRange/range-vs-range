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
    Creates a session_scope() and passes it as first parameter.
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        If session argument exists, call fun as such.
        If session argument doesn't exist, wrap fun in session_scope()
        """
        # TODO: make session last arg, not kwarg. Check for presense of session
        # before injecting.
        if 'session' in kwargs:
            return fun(*args, **kwargs)
        else:
            with session_scope() as session:
                kwargs['session'] = session
                return fun(*args, **kwargs)
    return inner

if __name__ == '__main__':
    @with_session
    def func(arg, **kwargs):
        """Pull out session, recurse iff arg"""
        session = kwargs['session']
        print arg, session
        if arg:
            func(False, session=session)
    
    print "func(True):"
    func(True)
    print
    print "func(False):"
    func(False)