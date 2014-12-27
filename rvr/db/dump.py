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
  - create a new database (but don't initialise it)
  - try loading the dump (from production) into the new database
    (using the updated code)
  - if it works, this is your new database file
  - run some serious local testing
- in production:
  - backup the old database
  - copy in the new database
- if this file was doing special things to read dump files from older versions,
  update it to be correct
"""
import pickle
from rvr.db.tables import User, SituationPlayer, Situation, OpenGame, \
    OpenGameParticipant, RunningGame, RunningGameParticipant, \
    GameHistoryBoard, GameHistoryRangeAction, GameHistoryActionResult, \
    GameHistoryUserRange, GameHistoryBase, GameHistoryTimeout, RangeItem,\
    AnalysisFoldEquity, AnalysisFoldEquityItem, GameHistoryChat
from rvr.db.creation import SESSION

#pylint:disable=C0103

dumpable_tables = [
    User,
    Situation,
    SituationPlayer,
    OpenGame,
    OpenGameParticipant,
    RunningGame,
    RunningGameParticipant,
    GameHistoryBase,
    GameHistoryUserRange,
    GameHistoryActionResult,
    GameHistoryRangeAction,
    GameHistoryBoard,
    GameHistoryTimeout,
    GameHistoryChat,
    RangeItem,
    AnalysisFoldEquity,
    AnalysisFoldEquityItem]

def read_range_items(session):
    """ Read RangeItem table from DB into memory """
    range_items = session.query(RangeItem).all()
    return [(r.higher_card,
             r.lower_card)
            for r in range_items]
    
def write_range_items(session, range_items):
    """ Write RangeItem table from memory into DB """
    for higher_card, lower_card in range_items:
        range_item = RangeItem()
        session.add(range_item)
        range_item.higher_card = higher_card
        range_item.lower_card = lower_card

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
    """ Read OpenGame table from DB into memory """
    ogs = session.query(OpenGame).all()
    return [(og.gameid,
             og.situationid,
             og.participants)
            for og in ogs]

def write_open_games(session, ogs):
    """ Write OpenGame from memory into DB """
    for gameid, situationid, participants in ogs:
        og = OpenGame()
        session.add(og)
        og.gameid = gameid
        og.situationid = situationid
        og.participants = participants

def read_open_game_participants(session):
    """ Read GameParticipant table from DB into memory """
    ogps = session.query(OpenGameParticipant).all()
    return [(ogp.userid,
             ogp.gameid,
             ogp.order)
            for ogp in ogps]
    
def write_open_game_participants(session, ogps):
    """ Write GameParticipant from memory into DB """
    for userid, gameid, order in ogps:
        ogp = OpenGameParticipant()
        session.add(ogp)
        ogp.userid = userid
        ogp.gameid = gameid
        ogp.order = order

def read_running_games(session):
    """ Read RunningGame table from DB into memory """
    rgs = session.query(RunningGame).all()
    return [(rg.gameid,
             rg.situationid,
             rg.current_userid,
             rg.next_hh,
             rg.board_raw,
             rg.current_round,
             rg.pot_pre,
             rg.increment,
             rg.bet_count,
             rg.current_factor,
             rg.last_action_time)
            for rg in rgs]

def write_running_games(session, rgs):
    """ Write RunningGame from memory into DB """
    for gameid, situationid, current_userid, next_hh, board_raw,  \
            current_round, pot_pre, increment, bet_count,  \
            current_factor, last_action_time in rgs:
        rg = RunningGame()
        session.add(rg)
        rg.gameid = gameid
        rg.situationid = situationid
        rg.current_userid = current_userid
        rg.next_hh = next_hh
        rg.board_raw = board_raw
        rg.current_round = current_round
        rg.pot_pre = pot_pre
        rg.increment = increment
        rg.bet_count = bet_count
        rg.current_factor = current_factor
        rg.last_action_time = last_action_time

def read_running_game_participants(session):
    """ Read RunningGameParticipant table from DB into memory """
    rgps = session.query(RunningGameParticipant).all()
    return [(rgp.userid,
             rgp.gameid,
             rgp.order,
             rgp.stack,
             rgp.contributed,
             rgp.range_raw,
             rgp.left_to_act,
             rgp.folded)
            for rgp in rgps]

def write_running_game_participants(session, rgps):
    """ Write RunningGameParticipant from memory into DB """
    for userid, gameid, order, stack, contributed, range_raw, left_to_act, \
            folded in rgps:
        rgp = RunningGameParticipant()
        session.add(rgp)
        rgp.userid = userid
        rgp.gameid = gameid
        rgp.order = order
        rgp.stack = stack
        rgp.contributed = contributed
        rgp.range_raw = range_raw
        rgp.left_to_act = left_to_act
        rgp.folded = folded

def read_game_history_bases(session):
    """ Read GameHistoryBase table from DB into memory """
    ghbs = session.query(GameHistoryBase).all()
    return [(ghb.gameid,
             ghb.order,
             ghb.time,
             ghb.factor)
            for ghb in ghbs]

def write_game_history_bases(session, ghbs):
    """ Write GameHistoryBase from memory into DB """
    for gameid, order, time, factor in ghbs:
        ghb = GameHistoryBase()
        session.add(ghb)
        ghb.gameid = gameid
        ghb.order = order
        ghb.time = time
        ghb.factor = factor

def read_game_history_user_ranges(session):
    """ Read GameHistoryUserRange table from DB into memory """
    ghurs = session.query(GameHistoryUserRange).all()
    return [(ghur.gameid,
             ghur.order,
             ghur.userid,
             ghur.range_raw)
            for ghur in ghurs]

def write_game_history_user_ranges(session, ghurs):
    """ Write GameHistoryUserRange from memory into DB """
    for gameid, order, userid, range_raw in ghurs:
        ghur = GameHistoryUserRange()
        session.add(ghur)
        ghur.gameid = gameid
        ghur.order = order
        ghur.userid = userid
        ghur.range_raw = range_raw

def read_game_history_action_results(session):
    """ Read GameHistoryActionResult table from DB into memory """
    ghars = session.query(GameHistoryActionResult).all()
    return [(ghar.gameid,
             ghar.order,
             ghar.userid,
             ghar.is_fold,
             ghar.is_passive,
             ghar.is_aggressive,
             ghar.call_cost,
             ghar.raise_total,
             ghar.is_raise)
            for ghar in ghars]

def write_game_history_action_results(session, ghars):
    """ Write GameHistoryActionResult from memory into DB """
    for gameid, order, userid, is_fold, is_passive, is_aggressive, call_cost,  \
            raise_total, is_raise in ghars:
        ghar = GameHistoryActionResult()
        session.add(ghar)
        ghar.gameid = gameid
        ghar.order = order
        ghar.userid = userid
        ghar.is_fold = is_fold
        ghar.is_passive = is_passive
        ghar.is_aggressive = is_aggressive
        ghar.call_cost = call_cost
        ghar.raise_total = raise_total
        ghar.is_raise = is_raise

def read_game_history_range_actions(session):
    """ Read HandHistoryRangeAction table from DB into memory """
    ghras = session.query(GameHistoryRangeAction).all()
    return [(ghra.gameid,
             ghra.order,
             ghra.userid,
             ghra.fold_range,
             ghra.passive_range,
             ghra.aggressive_range,
             ghra.raise_total,
             ghra.is_check,
             ghra.is_raise)
            for ghra in ghras]

def write_game_history_range_actions(session, ghras):
    """ Write HandHistoryRangeAction from memory into DB """
    for gameid, order, userid, fold_range, passive_range, aggressive_range,  \
            raise_total, is_check, is_raise in ghras:
        ghra = GameHistoryRangeAction()
        session.add(ghra)
        ghra.gameid = gameid
        ghra.order = order
        ghra.userid = userid
        ghra.fold_range = fold_range
        ghra.passive_range = passive_range
        ghra.aggressive_range = aggressive_range
        ghra.raise_total = raise_total
        ghra.is_check = is_check
        ghra.is_raise = is_raise

def read_game_history_boards(session):
    """ Read GameHistoryBoard table from DB into memory """
    ghbs = session.query(GameHistoryBoard).all()
    return [(ghb.gameid,
             ghb.order,
             ghb.street,
             ghb.cards)
            for ghb in ghbs]

def write_game_history_boards(session, ghbs):
    """ Write GameHistoryBoard from memory into DB """
    for gameid, order, street, cards in ghbs:
        ghb = GameHistoryBoard()
        session.add(ghb)
        ghb.gameid = gameid
        ghb.order = order
        ghb.street = street
        ghb.cards = cards
        
def read_game_history_timeouts(session):
    """ Read GameHistoryTimeout table from DB into memory """
    ghts = session.query(GameHistoryTimeout).all()
    return [(ght.gameid,
             ght.order,
             ght.userid)
            for ght in ghts]
    
def write_game_history_timeouts(session, ghts):
    """ Write GameHistoryTimeout from memory into DB """
    for gameid, order, userid in ghts:
        ght = GameHistoryTimeout()
        session.add(ght)
        ght.gameid = gameid
        ght.order = order
        ght.userid = userid
        
def read_game_history_chats(session):
    """ Read GameHistoryChat table from DB into memory """
    ghcs = session.query(GameHistoryChat).all()
    return [(ghc.gameid,
             ghc.order,
             ghc.userid,
             ghc.message)
            for ghc in ghcs]
    
def write_game_history_chats(session, ghcs):
    """ Write GamehistoryChat table from memory into DB """
    for gameid, order, userid, message in ghcs:
        ghc = GameHistoryChat()
        session.add(ghc)
        ghc.gameid = gameid
        ghc.order = order
        ghc.userid = userid
        ghc.message = message

def read_analysis_fold_equities(session):
    """ Read AnalysisFoldEquity table from DB into memory """
    afes = session.query(AnalysisFoldEquity).all()
    return [(afe.gameid,
             afe.order,
             afe.street,
             afe.pot_before_bet,
             afe.is_raise,
             afe.is_check,
             afe.bet_cost,
             afe.raise_total,
             afe.pot_if_called)
            for afe in afes]

def write_analysis_fold_equities(session, afes):
    """ Write AnalysisFoldEquity table from memory into DB """
    for gameid, order, street, pot_before_bet, is_raise, is_check, bet_cost,  \
            raise_total, pot_if_called in afes:
        afe = AnalysisFoldEquity()
        session.add(afe)
        afe.gameid = gameid
        afe.order = order
        afe.street = street
        afe.pot_before_bet = pot_before_bet
        afe.is_raise = is_raise
        afe.is_check = is_check
        afe.bet_cost = bet_cost
        afe.raise_total = raise_total
        afe.pot_if_called = pot_if_called

def read_analysis_fold_equity_items(session):
    """ Read AnalysisFoldEquityItem table from DB into memory """
    afeis = session.query(AnalysisFoldEquityItem).all()
    return [(afei.gameid,
             afei.order,
             afei.higher_card,
             afei.lower_card,
             afei.is_aggressive,
             afei.is_passive,
             afei.is_fold,
             afei.fold_ratio,
             afei.immediate_result,
             afei.semibluff_ev,
             afei.semibluff_equity)
            for afei in afeis]

def write_analysis_fold_equity_items(session, afeis):
    """ Write AnalysisFoldEquityItem table from memory into DB """
    for gameid, order, higher_card, lower_card, is_aggressive, is_passive,  \
            is_fold, fold_ratio, immediate_result, semibluff_ev,  \
            semibluff_equity in afeis:
        afei = AnalysisFoldEquityItem()
        session.add(afei)
        afei.gameid = gameid
        afei.order = order
        afei.higher_card = higher_card
        afei.lower_card = lower_card
        afei.is_aggressive = is_aggressive
        afei.is_passive = is_passive
        afei.is_fold = is_fold
        afei.fold_ratio = fold_ratio
        afei.immediate_result = immediate_result
        afei.semibluff_ev = semibluff_ev
        afei.semibluff_equity = semibluff_equity

TABLE_READERS = {User: read_users,
                 Situation: read_situations,
                 SituationPlayer: read_situation_players,
                 OpenGame: read_open_games,
                 OpenGameParticipant: read_open_game_participants,
                 RunningGame: read_running_games,
                 RunningGameParticipant: read_running_game_participants,
                 GameHistoryBase: read_game_history_bases,
                 GameHistoryUserRange: read_game_history_user_ranges,
                 GameHistoryActionResult: read_game_history_action_results,
                 GameHistoryRangeAction: read_game_history_range_actions,
                 GameHistoryBoard: read_game_history_boards,
                 GameHistoryTimeout: read_game_history_timeouts,
                 GameHistoryChat: read_game_history_chats,
                 RangeItem: read_range_items,
                 AnalysisFoldEquity: read_analysis_fold_equities,
                 AnalysisFoldEquityItem: read_analysis_fold_equity_items}

TABLE_WRITERS = {User: write_users,
                 Situation: write_situations,
                 SituationPlayer: write_situation_players,
                 OpenGame: write_open_games,
                 OpenGameParticipant: write_open_game_participants,
                 RunningGame: write_running_games,
                 RunningGameParticipant: write_running_game_participants,
                 GameHistoryBase: write_game_history_bases,
                 GameHistoryUserRange: write_game_history_user_ranges,
                 GameHistoryActionResult: write_game_history_action_results,
                 GameHistoryRangeAction: write_game_history_range_actions,
                 GameHistoryBoard: write_game_history_boards,
                 GameHistoryTimeout: write_game_history_timeouts,
                 GameHistoryChat: write_game_history_chats,
                 RangeItem: write_range_items,
                 AnalysisFoldEquity: write_analysis_fold_equities,
                 AnalysisFoldEquityItem: write_analysis_fold_equity_items}

def read_db():
    """ Read all tables from DB into memory """
    session = SESSION()
    return {table.__tablename__: TABLE_READERS[table](session)
            for table in dumpable_tables}

def write_db(data):
    """ Write all tables from memory into DB """
    session = SESSION()
    for table in dumpable_tables:
        if data.has_key(table.__tablename__):
            TABLE_WRITERS[table](session, data[table.__tablename__])
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
