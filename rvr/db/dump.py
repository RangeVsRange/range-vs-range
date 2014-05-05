"""
How to use this file:

This file is kept up to date. It can read and write the current version of the
database. If you need to dump out an old version of the database, find the
dump.py for that version of the code (it's probably right there).

To load it into a new version, release the new version of the code, create a
new database, and use the new dump.py to load in the old data.

This won't quite work, but it's a good start. The major difference is that the
reads below need to be aware of the changes since the previous version.

At deployment time:
- make sure the existing production dump code is up to date for the database you
  want to dump (visually)
- make sure this code can write (to the database) what the previous version will
  be reading (from the file) (visually)
- in production:
  - dump the previous version of the database ('dump out' from the console)
- in a local development environment:
  - create a new database
  - run the site to create and populate the database
  - try loading the dump (from production) into the new database
    (using the updated code)
  - if it works, this is your new database file
- in production:
  - backup the old database
  - copy in the new database
"""
import pickle
from rvr.db.tables import User
from rvr.db.creation import SESSION

def read_users(session):
    """ Read User table from DB into memory """
    users = session.query(User).all()
    return [(u.userid,
             u.identity,
             u.screenname,
             u.email,
             u.unsubscribed)
            for u in users]

def write_users(session, users):
    """ Write User table from memory into DB """
    for userid, identity, screenname, email, unsubscribed in users:
        user = User()
        session.add(user)
        user.userid = userid
        user.identity = identity
        user.screenname = screenname
        user.email = email
        user.unsubscribed = unsubscribed

def read_db():
    """ Read all tables from DB into memory """
    session = SESSION()
    users = read_users(session)
    return {"User": users}

def write_db(data):
    """ Write all tables from memory into DB """
    session = SESSION()
    write_users(session, data["User"])
    session.commit()

def dump(filename):
    """ Read all tables from DB into memory, and write to file """
    file_ = open(filename, 'w')
    data = read_db()
    pickle.dump(data, file_)
    file_.close()

def load(filename):
    """ Read all tables from file into memory, and write to DB """
    file_ = open(filename, 'r')
    data = pickle.load(file_)
    write_db(data)
    file_.close()