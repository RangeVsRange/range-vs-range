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
from rvr.db.tables import User, SituationPlayer, Situation
from rvr.db.creation import SESSION

#pylint:disable=C0103

# TODO: 0: support other tables, starting with least dependencies

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

def read_situations(session):
    """ Read Situation table from DB into memory """
    situations = session.query(Situation).all()
    return [(situation.situationid,
             situation.description,
             situation.participants,
             situation.is_limit,
             situation.big_blind,
             situation.board_raw,
             situation.current_round,
             situation.pot_pre,
             situation.increment,
             situation.bet_count,
             situation.current_player_num)
            for situation in situations]

def write_situations(session, situations):
    """ Write Situation from memory into DB """
    for situationid, description, participants, is_limit, big_blind,  \
            board_raw, current_round, pot_pre, increment, bet_count,  \
            current_player_num in situations:
        situation = Situation()
        session.add(situation)
        situation.situationid = situationid
        situation.description = description
        situation.participants = participants
        situation.is_limit = is_limit
        situation.big_blind = big_blind
        situation.board_raw = board_raw
        situation.current_round = current_round
        situation.pot_pre = pot_pre
        situation.increment = increment
        situation.bet_count = bet_count
        situation.current_player_num = current_player_num

def read_situation_players(session):
    """ Read SituationPlayer table from DB into memory """
    sps = session.query(SituationPlayer).all()
    return [(sp.situationid,
             sp.order,
             sp.stack,
             sp.contributed,
             sp.range_raw,
             sp.left_to_act)
            for sp in sps]

def write_situation_players(session, sps):
    """ Write SituationPlayer from memory into DB """
    for situationid, order, stack, contributed, range_raw, left_to_act in sps:
        sp = SituationPlayer()
        session.add(sp)
        sp.situationid = situationid
        sp.order = order
        sp.stack = stack
        sp.contributed = contributed
        sp.range_raw = range_raw
        sp.left_to_act = left_to_act

def read_open_games(session):
    # TODO:
    """ Read OpenGame table from DB into memory """

def write_open_games(session, ogs):
    # TODO:
    """ Write OpenGame from memory into DB """

def read_open_game_participants(session):
    # TODO:
    """ Read GameParticipant table from DB into memory """

def write_open_game_participants(session, ogps):
    # TODO:
    """ Write GameParticipant from memory into DB """

def read_running_games(session):
    # TODO:
    """ Read RunningGame table from DB into memory """

def write_running_games(session, rgs):
    # TODO:
    """ Write RunningGame from memory into DB """

def read_running_game_participants(session):
    # TODO:
    """ Read RunningGameParticipant table from DB into memory """

def write_running_game_participants(session, rgps):
    # TODO:
    """ Write RunningGameParticipant from memory into DB """

def read_game_history_bases(session):
    # TODO:
    """ Read GameHistoryBase table from DB into memory """

def write_game_history_bases(session, ghbs):
    # TODO:
    """ Write GameHistoryBase from memory into DB """

def read_game_history_user_ranges(session):
    # TODO:
    """ Read GameHistoryUserRange table from DB into memory """

def write_game_history_user_ranges(session, ghurs):
    # TODO:
    """ Write GameHistoryUserRange from memory into DB """

def read_game_history_action_results(session):
    # TODO:
    """ Read GameHistoryActionResult table from DB into memory """

def write_game_history_action_results(session, ghars):
    # TODO:
    """ Write GameHistoryActionResult from memory into DB """

def read_game_history_range_actions(session):
    # TODO:
    """ Read HandHistoryRangeAction table from DB into memory """

def write_game_history_range_actions(session, ghras):
    # TODO:
    """ Write HandHistoryRangeAction from memory into DB """

def read_game_history_boards(session):
    # TODO:
    """ Read GameHistoryBoard table from DB into memory """

def write_game_history_boards(session, ghbs):
    # TODO:
    """ Write GameHistoryBoard from memory into DB """

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