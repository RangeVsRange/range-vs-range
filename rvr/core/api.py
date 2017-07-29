#pylint:disable=R0903,R0904,C0302
"""
Core API for Range vs. Range backend.
"""
from rvr.db.creation import BASE, ENGINE, create_session, session_scope
from rvr.db import tables
from rvr.core import dtos
from functools import wraps
import logging
from sqlalchemy.exc import IntegrityError
import traceback
from rvr.poker.handrange import remove_board_from_range,  \
    ANYTHING, NOTHING, deal_from_ranges, IncompatibleRangesError
from rvr.poker.action import range_action_fits, calculate_current_options,  \
    PREFLOP, RIVER, FLOP,  \
    NEXT_ROUND, TOTAL_COMMUNITY_CARDS,\
    act_passive, act_fold, act_aggressive, WhatCouldBe,\
    generate_excluded_cards
from rvr.core.dtos import MAP_TABLE_DTO, GamePayment, ActionResult
from rvr.infrastructure.util import concatenate, on_a_different_thread
from rvr.poker.cards import deal_cards, Card, RANKS_HIGH_TO_LOW,  \
    SUITS_HIGH_TO_LOW, TURN, FINISHED
from sqlalchemy.orm.exc import NoResultFound
from rvr.mail.notifications import notify_current_player, notify_started
from rvr.analysis.analyse import AnalysisReplayer
from rvr.db.tables import AnalysisFoldEquity, RangeItem, MAX_CHAT,\
    PaymentToPlayer, GAME_HISTORY_TABLES
import datetime
from rvr.local_settings import SUPPRESSED_SITUATIONS
import re
from rvr.analysis import statistics
from rvr.analysis.statistics import recalculate_global_statistics
from sqlalchemy.orm.session import sessionmaker
from rvr.core.gametree import GameTreeNode, GameTree

def exception_mapper(fun):
    """
    Converts database exceptions to APIError
    """
    @wraps(fun)
    def inner(*args, **kwargs):
        """
        Catch exceptions and return API.ERR_UNKNOWN
        """
        # pylint:disable=W0703
        try:
            return fun(*args, **kwargs)
        except Exception as ex:
            logging.info("Unhandled exception in API function: %r", ex)
            for line in traceback.format_exc().splitlines():
                logging.info(line)
            return API.ERR_UNKNOWN
    return inner

def api(fun):
    """
    Equivalent to:
        @exception_mapper
        @create_session

    Used to ensure exception_mapper and create_session are applied in the
    correct order.
    """
    @wraps(fun)
    @exception_mapper
    @create_session
    def inner(*args, **kwargs):
        """
        Additional functionality: rollback on error. That needs to be here
        because it needs knowledge of both self.session and APIError.
        """
        try:
            result = fun(*args, **kwargs)
            if isinstance(result, APIError):
                self = args[0]
                self.session.rollback()
            return result
        except:
            self = args[0]
            self.session.rollback()
            raise
    return inner

class APIError(object):
    """
    These objects will be returned by @exception_mapper
    """
    def __init__(self, description):
        self.description = description

    def __str__(self):
        return self.description

class API(object):
    """
    Core Range vs. Range API, which may be called by:
     - a website
     - an admin console or command line
     - a thick client
    """

    ERR_UNKNOWN = APIError("Internal error")
    ERR_NO_SUCH_USER = APIError("No such user")
    ERR_NO_SUCH_OPEN_GAME = APIError("No such open game")
    ERR_NO_SUCH_GAME = APIError("No such running game")
    ERR_DUPLICATE_SCREENNAME = APIError("Duplicate screenname")
    ERR_JOIN_GAME_ALREADY_IN = APIError("User is already registered")
    ERR_JOIN_GAME_GAME_FULL = APIError("Game is full")
    ERR_DELETE_USER_PLAYING = APIError("User is playing")
    ERR_USER_NOT_IN_GAME = APIError("User is not in the specified game")
    ERR_DUPLICATE_SITUATION = APIError("Duplicate situation")
    ERR_CHAT_TOO_LONG = APIError("Chat too long, max %d chars" % (MAX_CHAT,))

    def __init__(self):
        self.session = None  # required for @create_session

    @exception_mapper
    def create_db(self):
        """
        Create and seed the database
        """
        #pylint:disable=R0201
        BASE.metadata.create_all(ENGINE)  # @UndefinedVariable
        self._add_card_combos()

    @exception_mapper
    def delete_db(self):
        """
        Delete database, and everything in it
        """
        #pylint:disable=R0201
        BASE.metadata.drop_all(ENGINE)  # @UndefinedVariable

    def _add_all_situations(self):
        """
        Add all situations
        """
        self._add_situation(_create_hu())

    def _add_card_combo(self, higher_card, lower_card):
        """
        Add a RangeItem
        """
        item = RangeItem()
        item.higher_card = higher_card.to_mnemonic()
        item.lower_card = lower_card.to_mnemonic()
        self.session.add(item)
        logging.debug("Added range item: %s, %s", item.higher_card,
                      item.lower_card)

    @create_session
    def _add_card_combos(self):
        """
        Populate table of RangeItem
        """
        deck1 = [Card(rank, suit)
                 for rank in RANKS_HIGH_TO_LOW
                 for suit in SUITS_HIGH_TO_LOW]
        deck2 = deck1[:]
        err = None
        for card1 in deck1:
            for card2 in deck2:
                if card1 > card2:
                    err = err or self._add_card_combo(higher_card=card1,
                                                      lower_card=card2)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()  # already there, no worries
        return err

    @api
    def initialise_db(self):
        """
        Create initial data for database
        """
        self.session.commit()  # any errors are our own

        # Each of these also commits.
        err = None
        err = self._add_all_situations() or err
        return err

    @api
    def add_situation(self, situation):
        """
        Add a new situation to the database. Return situation id, or APIError.
        """
        self.session.commit()  # any errors are our own
        return self._add_situation(situation)

    @api
    def login(self, request):
        """
        1. Create or validate OpenID Connect-based account
        inputs: identity, email
        outputs: existed, user_details
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.email == request.email).all()
        if matches:
            # return user from database
            user = matches[0]
            user.unsubscribed = False
            user.identity = request.identity
            self.session.commit()
            logging.debug("Updated user %d with identity '%s'", user.userid,
                          user.identity)
            return dtos.LoginResponse.from_user(user, True)
        else:
            # create user in database
            user = tables.User()
            self.session.add(user)
            user.identity = request.identity
            user.email = request.email
            user.screenname = None
            user.unsubscribed = False
            user.last_seen = datetime.datetime.utcnow()
            self.session.commit()
            logging.debug("Created user %d with screenname '%s'",
                          user.userid, user.screenname)
            return dtos.LoginResponse.from_user(user, False)

    @api
    def unsubscribe(self, identity):
        """
        Unsubscribe the user from further emails (until they log in again).
        """
        try:
            user = self.session.query(tables.User)  \
                .filter(tables.User.identity == identity).one()
        except NoResultFound:
            return API.ERR_NO_SUCH_USER
        user.unsubscribed = True

    @api
    def resubscribe(self, userid):
        """
        Re-subscribe user
        """
        try:
            user = self.session.query(tables.User)  \
                .filter(tables.User.userid == userid).one()
        except NoResultFound:
            return API.ERR_NO_SUCH_USER
        user.unsubscribed = False

    @api
    def change_screenname(self, request):
        """
        Change user's screenname
        """
        # "Player X" is reserved for userid X
        if request.screenname.startswith("Player ") and  \
                request.screenname != "Player %d" % (request.userid,):
            return self.ERR_DUPLICATE_SCREENNAME
        # Check for existing user with this screenname
        matches = self.session.query(tables.User)  \
            .filter(tables.User.screenname_raw == request.screenname).all()
        if matches:
            return self.ERR_DUPLICATE_SCREENNAME
        try:
            self.session.query(tables.User)  \
                .filter(tables.User.userid == request.userid)  \
                .one().screenname = request.screenname
        except NoResultFound:
            return self.ERR_NO_SUCH_USER

    @api
    def get_user(self, userid):
        """
        Get user's LoginDetails
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not matches:
            return self.ERR_NO_SUCH_USER
        user = matches[0]
        return dtos.DetailedUser(userid=user.userid,
                                 identity=user.identity,
                                 email=user.email,
                                 screenname=user.screenname)

    @api
    def delete_user(self, userid):
        """
        Delete user if not playing any games.
        """
        matches = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not matches:
            return self.ERR_NO_SUCH_USER
        user = matches[0]
        if user.rgps or user.fgps:
            return self.ERR_DELETE_USER_PLAYING
        for ogp in user.ogps:
            self.session.delete(ogp)
        self.session.delete(user)
        return True

    @api
    def get_user_by_screenname(self, screenname):
        """
        Return userid, screenname
        """
        # Look for screenname
        matches = self.session.query(tables.User)  \
            .filter(tables.User.screenname_raw == screenname).all()
        if matches:
            user = matches[0]
        else:
            # Look for userid
            matches = re.match(r"Player (\d+)$", screenname)
            if not matches:
                return API.ERR_NO_SUCH_USER
            userid = int(matches.group(1))
            matches = self.session.query(tables.User)  \
                .filter(tables.User.userid == userid).all()
            if matches:
                user = matches[0]
            else:
                return API.ERR_NO_SUCH_USER
        return dtos.UserDetails.from_user(user)

    def _add_situation(self, dto):
        """
        Add a dtos.SituationDetails to the database, as a tables.Situation and
        associated tables.SituationPlayer objects.

        Returns situation id, or APIError
        """
        situation = tables.Situation()
        situation.description = dto.description
        situation.participants = len(dto.players)
        situation.is_limit = dto.is_limit
        situation.big_blind = dto.big_blind
        situation.board_raw = dto.board_raw
        situation.current_round = dto.current_round
        situation.pot_pre = dto.pot_pre
        situation.increment = dto.increment
        situation.bet_count = dto.bet_count
        situation.current_player_num = dto.current_player
        self.session.add(situation)
        for order, player in enumerate(dto.players):
            child = tables.SituationPlayer()
            child.situation = situation
            child.order = order
            child.name = player.name
            child.stack = player.stack
            child.contributed = player.contributed
            child.range_raw = player.range_raw
            child.left_to_act = player.left_to_act
            self.session.add(child)
        try:
            self.session.commit()
            logging.debug("Added situation: %s", dto.description)
            return situation.situationid
        except IntegrityError:
            self.session.rollback()
            return self.ERR_DUPLICATE_SITUATION

    @api
    def get_open_games(self):
        """
        2. Retrieve open games including registered users
        inputs: (none)
        outputs: List of open games. For each game, users in game, details of
                 game
        """
        all_open_games = self.session.query(tables.OpenGame).all()
        results = [dtos.OpenGameDetails.from_open_game(game)
                   for game in all_open_games]
        return results

    @api
    def get_user_running_games(self, userid, cstart=0, ostart=0, page=20):
        """
        3. Retrieve user's games and their statuses
        inputs:
         - userid
         - starting index for finished competition mode games
         - starting index for finished optimisation mode games
         - number of finished games of each mode to return
        outputs: list of user's games. each may be open game, running (not our
        turn), running (our turn), finished. no more details of each game.

        Note: we don't validate that userid is a real userid!
        """
        rgps = self.session.query(tables.RunningGameParticipant)  \
            .filter(tables.RunningGameParticipant.userid == userid).all()
        running_games =  \
            [dtos.RunningGameSummary.from_running_game(rgp.game, userid)
             for rgp in rgps if not rgp.game.game_finished
             and not rgp.game.public_ranges]
        c = 0; c_less = False; c_more = False
        finished_games = []
        for rgp in sorted(rgps, key=lambda rgp: rgp.gameid, reverse=True):
            if not rgp.game.game_finished:
                continue
            if not (rgp.game.game_finished and not rgp.game.public_ranges):
                continue
            if c < cstart:
                c_less = True
            elif c >= cstart + page:
                c_more = True
            else:
                finished_games.append(
                    dtos.RunningGameSummary.from_running_game(rgp.game, userid))
            c += 1
        group_ids = set(rgp.game.spawn_group for rgp in rgps
                        if rgp.game.public_ranges)
        running_groups = []
        o = 0; o_less = False; o_more = False
        finished_groups = []
        for group in sorted(group_ids, reverse=True):
            spawns = [rgp for rgp in rgps if rgp.game.spawn_group == group
                      and rgp.game.public_ranges]
            is_finished = all(spawn.game.game_finished for spawn in spawns)
            is_on_me = any(spawn.game.current_userid == userid
                           for spawn in spawns)
            if is_finished:
                if o < ostart:
                    o_less = True
                elif o >= ostart + page:
                    o_more = True
                else:
                    finished_groups.append(
                        dtos.RunningGroup.from_rgps(group, is_finished,
                            is_on_me, [rgp.game for rgp in spawns]))
                o += 1
            else:
                running_groups.append(
                    dtos.RunningGroup.from_rgps(group, is_finished, is_on_me,
                        [rgp.game for rgp in spawns]))
        return dtos.UsersGameDetails(userid, running_games, finished_games,
                                     running_groups, finished_groups,
                                     c_less, c_more, o_less, o_more)

    def _start_game(self, open_game, final_ogp):
        """
        Takes the id of a full OpenGame, creates a new RunningGame from it,
        deletes the original and returns the id of the new RunningGame.

        This gets called when a game fills up, so that we can immediately tell
        the user that the game was started, and the new running game's id.

        Because adding a user to an open game happens in the same context as
        starting the game here, it's not possible for an open game to be left
        full.

        Returns RunningGame object, because there is no game id, because the
        object hasn't been committed yet, so the database hasn't created the id
        yet.
        """
        situation = open_game.situation
        all_ogps = open_game.ogps + [final_ogp]
        # move everyone left so that final_ogp will act first
        offset = len(all_ogps) - 1 - situation.current_player_num
        all_ogps = all_ogps[offset:] + all_ogps[:offset]
        total_board = self._generate_total_board(situation)
        running_game = tables.RunningGame()
        running_game.next_hh = 0
        running_game.public_ranges = open_game.public_ranges
        running_game.situation = situation
        # We have to calculate current userid in advance so we can flush.
        running_game.current_userid =  \
            all_ogps[situation.current_player_num].userid
        running_game.board_raw = situation.board_raw
        running_game.current_round = situation.current_round
        running_game.pot_pre = situation.pot_pre
        running_game.increment = situation.increment
        running_game.bet_count = situation.bet_count
        running_game.current_factor = 1.0
        running_game.last_action_time = datetime.datetime.utcnow()
        running_game.analysis_performed = False
        running_game.spawn_factor = 1.0
        running_game.total_board = total_board
        self.session.add(running_game)
        self.session.flush()  # get gameid from database
        logging.debug('Secret total board for game %d: %r',
                      running_game.gameid, running_game.total_board_raw)
        running_game.spawn_group = running_game.gameid
        situation_players = situation.ordered_players()
        for order, (ogp, s_p) in enumerate(zip(all_ogps, situation_players)):
            # create rgps in the order they will act in future rounds
            rgp = tables.RunningGameParticipant()
            rgp.gameid = running_game.gameid
            rgp.userid = ogp.userid  # haven't loaded users, so just copy userid
            rgp.order = order
            rgp.stack = s_p.stack
            rgp.contributed = s_p.contributed
            rgp.range_raw = s_p.range_raw
            rgp.left_to_act = s_p.left_to_act
            rgp.folded = False
            if situation.current_player_num == order:
                assert running_game.current_userid == ogp.userid
            self.session.add(rgp)
            self.session.flush()  # populate game
            # Note that we do NOT create a range history item for them,
            # it is implied.
        self.session.delete(open_game)  # cascades to OGPs
        self._deal_to_board(running_game)  # also changes ranges
        notify_started(running_game, starter_id=final_ogp.userid)
        logging.debug("Started game %d", open_game.gameid)
        return running_game

    def _record_hand_history_item(self, game, item, factor=None):
        """
        Create a GameHistoryBase, and add it and item to the session.
        """
        base = tables.GameHistoryBase()
        base.gameid = game.gameid
        base.order = game.next_hh
        base.factor = game.current_factor if factor is None else factor
        base.time = datetime.datetime.utcnow()
        game.next_hh += 1
        item.gameid = base.gameid
        item.order = base.order
        self.session.add(base)
        self.session.add(item)

    def _record_showdown_participant(self, gameid, order, is_passive,
                                     showdown_order, userid):
        """
        Create a GameHistoryShowdownEquity, and add it to the session.
        """
        equity = tables.GameHistoryShowdownEquity()
        equity.gameid = gameid
        equity.order = order
        equity.is_passive = is_passive
        equity.showdown_order = showdown_order
        equity.userid = userid
        equity.equity = None  # will be populated by analysis
        self.session.add(equity)

    def _record_action_result(self, rgp, action_result):
        """
        Record that this user's range action resulted in this actual action.
        """
        if action_result.is_terminate:
            raise ValueError("Only real actions are supported.")
        element = tables.GameHistoryActionResult()
        element.userid = rgp.userid
        element.is_fold = action_result.is_fold
        element.is_passive = action_result.is_passive
        element.is_aggressive = action_result.is_aggressive
        element.call_cost = action_result.call_cost
        element.raise_total = action_result.raise_total
        element.is_raise = action_result.is_raise
        self._record_hand_history_item(rgp.game, element)
        rgp.game.last_action_time = datetime.datetime.utcnow()

    def _record_rgp_range(self, rgp, range_raw):
        """
        Record that this user now has this range in this game, in the hand
        history.
        """
        element = tables.GameHistoryUserRange()
        element.userid = rgp.userid
        element.range_raw = range_raw
        self._record_hand_history_item(rgp.game, element)

    def _record_range_action(self, rgp, range_action, is_check, is_raise,
                             range_ratios):
        """
        Record that this user has made this range-based action
        """
        element = tables.GameHistoryRangeAction()
        element.userid = rgp.userid
        element.fold_range = range_action.fold_range.description
        element.passive_range = range_action.passive_range.description
        element.aggressive_range = range_action.aggressive_range.description
        element.raise_total = range_action.raise_total
        element.is_check = is_check
        element.is_raise = is_raise
        element.fold_ratio = range_ratios['fold']
        element.passive_ratio = range_ratios['passive']
        element.aggressive_ratio = range_ratios['aggressive']
        self._record_hand_history_item(rgp.game, element)

    def _record_board(self, game):
        """
        Record board at street
        """
        element = tables.GameHistoryBoard()
        element.street = game.current_round
        element.cards = game.board_raw
        self._record_hand_history_item(game, element)

    def _record_timeout(self, rgp):
        """
        Record timeout
        """
        element = tables.GameHistoryTimeout()
        element.user = rgp.user
        self._record_hand_history_item(rgp.game, element)

    def _record_chat(self, rgp, message):
        """
        Record chat message
        """
        element = tables.GameHistoryChat()
        element.user = rgp.user
        element.message = message
        self._record_hand_history_item(rgp.game, element)

    def _record_showdown(self, game, is_passive, pot, factor, participants):
        """
        Record showdown (but not participants / equity)

        Note that the factor is not the game's current factor!
        """
        element = tables.GameHistoryShowdown()
        element.is_passive = is_passive
        element.pot = pot
        self._record_hand_history_item(game, element, factor=factor)
        for showdown_order, rgp in enumerate(participants):
            self._record_showdown_participant(
                gameid=game.gameid,
                order=element.order,
                is_passive=is_passive,
                showdown_order=showdown_order,
                userid=rgp.userid)

    @api
    def join_game(self, userid, gameid):
        """
        5. Join/start game we're not in
        inputs: userid, gameid
        outputs: - running game id if the game started
                 - otherwise nothing
        errors: - gameid doesn't exist
                - userid doesn't exist
                - game is full
                - user is already registered
        """
        # check error conditions
        games = self.session.query(tables.OpenGame)  \
            .filter(tables.OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not users:
            return self.ERR_NO_SUCH_USER
        user = users[0]
        if any(ogp.userid == userid for ogp in game.ogps):
            return self.ERR_JOIN_GAME_ALREADY_IN
        game.participants += 1
        if game.participants > game.situation.participants:
            return self.ERR_JOIN_GAME_GAME_FULL  # This can't happen.

        ogp = tables.OpenGameParticipant()
        ogp.gameid = game.gameid
        ogp.userid = user.userid
        ogp.order = game.participants  # evidently 1-based

        # start game?
        start_game = game.participants == game.situation.participants
        if start_game:
            running_game = self._start_game(game, ogp)
        else:
            # add user to game
            self.session.add(ogp)
            running_game = None

        try:
            # This commits either the add or the start game. We do this so that
            # if it's going to fail, it fails before the ensure_open_games()
            # below. This is important so that there are never duplicate game
            # ids.
            self.session.commit()  # explicitly check that it commits okay
        except IntegrityError as _:
            # An error will occur if game no longer exists, or user no longer
            # exists, or user has already been added to game, or game has
            # already been filled, or problems with starting the game!
            self.session.rollback()
            # Complete fail, okay, here we just try again!
            running_game = self.join_game(userid, gameid)

        logging.debug("User %d joined game %d", userid, gameid)

        self._see_user(user)

        self.ensure_open_games()

        # it's committed, so we will have the id
        if running_game is not None:
            return running_game.gameid

    @api
    def leave_game(self, userid, gameid):
        """
        Leave/cancel game we're in
        inputs: userid, gameid
        outputs: (none)
        """
        return self._leave_game(userid, gameid)

    def _leave_game(self, userid, gameid):
        """
        Leave/cancel game we're in
        inputs: userid, gameid
        outputs: (none)
        """
        # check error conditions
        games = self.session.query(tables.OpenGame)  \
            .filter(tables.OpenGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_OPEN_GAME
        game = games[0]
        users = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not users:
            return self.ERR_NO_SUCH_USER
        for ogp in game.ogps:
            if ogp.userid == userid:
                self.session.delete(ogp)
                break
        else:
            return self.ERR_USER_NOT_IN_GAME
        game.participants -= 1
        # I don't know why, but flush here causes ensure_open_games to fail.
        # Failure to merge appropriately?
        self.session.commit()
        logging.debug("User %d left game %d", userid, gameid)
        self.ensure_open_games()

    ERR_NOT_USERS_TURN = APIError("It's not that user's turn.")
    ERR_INVALID_RAISE_TOTAL = APIError("Invalid raise total.")
    ERR_INVALID_RANGES = APIError("Invalid ranges or raise size.")

    def _spawn_game(self, game):
        """
        Make a current, running copy of the current, running game.

        This includes:
         - RunningGame
         - RunningGameParticipant
         - GAME_HISTORY_TABLES

        Basically copies every table that holds info on a running game, and
        changes the gameid.
        """
        ng = game.copy()
        ng.spawn_group = game.spawn_group  \
            if game.spawn_group is not None else game.gameid
        self.session.add(ng)
        self.session.flush()  # get gameid
        for rgp in game.rgps:
            np = rgp.copy()
            np.gameid = ng.gameid
            self.session.add(np)
        for table in GAME_HISTORY_TABLES:
            for row in self.session.query(table)  \
                    .filter(table.gameid == game.gameid).all():
                nr = row.copy()
                nr.gameid = ng.gameid
                self.session.add(nr)
        return ng

    def _deal_to_board(self, game):
        """
        Deal as many cards as are needed to bring the board up to the current
        round. Also remove these cards from players' ranges.
        """
        total = TOTAL_COMMUNITY_CARDS[game.current_round]
        current = len(game.board)
        if game.total_board:
            new_board = game.total_board[0:total]
        else:
            excluded_cards = generate_excluded_cards(game)
            new_board = game.board + deal_cards(excluded_cards, total - current)
        game.board = new_board
        if total > current:
            self._record_board(game)
        for rgp in game.rgps:
            rgp.range = remove_board_from_range(rgp.range, game.board)

    def _generate_total_board(self, situation):
        """
        Generate (but don't deal) all future board cards.
        """
        ranges = {p: p.range for p in situation.players}
        situation_board = situation.board
        for _ in range(10):
            # We can at least assume an incompatible deal is very unlikely,
            # because it being likely implies the players already know what the
            # future board cards will be... If we want to support that, we may
            # as well allow the situation to define the future board cards.
            to_deal = TOTAL_COMMUNITY_CARDS[RIVER] - len(situation_board)
            board = situation_board
            deal_cards(board, to_deal)
            try:
                deal_from_ranges(ranges, board)
                return board
            except IncompatibleRangesError:
                pass
        raise IncompatibleRangesError()

    def _open_the_gate(self, spawn_group, current_round):
        """
        Time to finish the betting round for the group?
        """
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.spawn_group ==
                    spawn_group).all()
        for g in games:
            # TODO: REVISIT: Legacy support: this game has already advanced.
            if g.current_round != current_round:
                continue
            # This one is already waiting, not holding others up.
            if g.round_finished:
                continue
            # Is any player all in in this game? If they are, all other games
            # are free to continue to the next street, because the remaining
            # players knowing what the future board cards will be cannot help
            # them, because when players get all in, they have a
            # subject-all-in-equity showdown, not an actual board runout.
            for rgp in g.rgps:
                if rgp.stack == 0:
                    continue
            return False
        return True

    def _attempt_start_next_round(self, gameid, spawn_group, current_round):
        """
        Finish the betting round for all games in the group, if and only if:
         - they are all ready for the next card, or
         - it's already the river, or
         - just for this game if this game is all in, but still for the others
           if one of the other two conditions hold

        Finish all games in group if:
         - all games have finished this betting round, except river

        Finish just this game if:
         - all in and not river

        Finish no games if:
         - not river, not all in, other games haven't finished this round

        More concisely:
         - if all games finished this round, finish games still at this round
         - else if all in and not river, finish just this game
         - else... do nothing
        """
        assert current_round in [PREFLOP, FLOP, TURN]
        if self._open_the_gate(spawn_group, current_round):
            # finish all
            games = self.session.query(tables.RunningGame)  \
                .filter(tables.RunningGame.spawn_group ==
                        spawn_group).all()
            for g in games:
                if g.game_finished:
                    # all in already
                    continue
                if g.current_round != current_round:
                    # legacy support!
                    continue
                assert not any(p.left_to_act for p in g.rgps)
                assert g.current_userid == None
                assert g.current_round == current_round
                self._start_next_round(g)
        else:
            # ... do nothing
            logging.debug("gameid %d, waiting for others in group", gameid)

    def _start_next_round(self, game):
        """
        Deal and such
        """
        remain = [p for p in game.rgps if not p.folded]
        game.current_userid = min(remain, key=lambda r: r.order).userid
        game.current_round = NEXT_ROUND[game.current_round]
        self._deal_to_board(game)
        game.increment = game.situation.big_blind
        game.bet_count = 0
        for rgp in game.rgps:
            # We move the contributed money into the pot
            # Note: from everyone, not just from those who remain
            game.pot_pre += rgp.contributed
            rgp.contributed = 0
            if rgp.folded:
                continue
            rgp.left_to_act = True
        notify_current_player(game)

    def _create_showdown(self, game, participants, is_passive, pot, factor):
        # pylint:disable=R0913
        """
        Create a showdown in the game history

        game is a RunningGame
        participants is a list of RGPs showing down
        is_passive signals that this showdown was created by a call
        pot is the hypothetical pot
        factor is the hypothetical current factor

        equity is handled by analysis (because it takes time to calculate)
        """
        logging.debug('gameid %d, is_passive %r, factor %0.8f, pot %d, '
                      'creating showdown with userids: %r',
                      game.gameid, is_passive, factor, pot,
                      [rgp.userid for rgp in participants])
        self._record_showdown(game, is_passive, pot, factor, participants)

    def _range_action_showdown(self, game, actor,
                               current_options, range_ratios):
        # pylint:disable=R0914
        """
        Consider showdowns based on this range action resulting in a fold, and
        another based on this resulting in a check or call.
        """
        remain = []
        # check if betting round has finished
        prev_contrib = None
        any_stack = None
        for rgp in game.rgps:
            if not rgp.folded:
                remain.append(rgp)
            if rgp.userid == actor.userid:
                continue
            if rgp.left_to_act:
                return  # no showdown yet
            if prev_contrib is not None and rgp.contributed != prev_contrib:
                return  # no showdown yet
            prev_contrib = rgp.contributed
            any_stack = rgp.stack
        if any_stack > 0 and game.current_round != RIVER:
            # not all in, nor river showdown
            return
        fold_ratio = range_ratios['fold']
        passive_ratio = range_ratios['passive']
        pot = game.pot_pre + sum(rgp.contributed for rgp in game.rgps)
        # TODO: REVISIT: use true probability of fold or call
        # (This assumes that each option in a user's range is as likely to be
        # held, but that is not the case.)
        # (Example, {AA,KK} vs. {A2o+} on a board of "AsAc7h", the first range
        # never has AA. If that player is folding KK, they are folding 100% of
        # the time.)
        # arbitrarily, we call the showdown created by a fold "first"
        if len(remain) > 2 and fold_ratio > 0:
            # this player folds, but leave 2 or more players to a showdown
            factor = game.current_factor * fold_ratio
            participants = [rgp for rgp in game.rgps
                if rgp in remain and rgp.userid != actor.userid]
            self._create_showdown(game=game,
                participants=participants,
                is_passive=False,
                pot=pot,
                factor=factor)
        if passive_ratio > 0:
            # this player calls and creates a showdown
            pot += current_options.call_cost
            factor = game.current_factor * passive_ratio
            participants = [rgp for rgp in game.rgps
                if rgp in remain]
            self._create_showdown(game=game,
                participants=participants,
                is_passive=True,
                pot=pot,
                factor=factor)

    def _apply_action_result(self, game, weight, action_result, range_raw):
        """
        Apply a spawn weight and an action result to a (potentially spawned)
        game
        """
        logging.debug("gameid %r, determined to continue", game.gameid)
        game.spawn_factor *= weight
        rgp = game.current_rgp
        self._record_action_result(rgp, action_result)
        rgp.range_raw = range_raw
        logging.debug("gameid %d, new range for userid %d, new range %r",
                      rgp.gameid, rgp.userid, rgp.range_raw)
        self._record_rgp_range(rgp, range_raw)
        if action_result.is_fold:
            act_fold(rgp)
        elif action_result.is_passive:
            act_passive(rgp, action_result.call_cost)
        elif action_result.is_aggressive:
            act_aggressive(game, rgp, action_result.raise_total)
        else:
            # terminate must not be passed here
            raise ValueError("Invalid action result")
        left_to_act = [p for p in game.rgps if p.left_to_act]
        if left_to_act:
            # Who's up next? And not someone named Who, but the pronoun.
            later = [p for p in left_to_act if p.order > rgp.order]
            earlier = [p for p in left_to_act if p.order < rgp.order]
            chosen = later if later else earlier
            next_rgp = min(chosen, key=lambda p: p.order)
            game.current_userid = next_rgp.userid
            logging.debug("Next to act in game %d: userid %d, order %d",
                          game.gameid, next_rgp.userid, next_rgp.order)
            notify_current_player(game)
        else:
            # Betting round is done. Game is not. This triggers attempting
            # to start the next betting round, but it is not the only thing
            # that does - also the players getting all in, which never gets
            # here because it finished the game!
            game.current_userid = None

    def _inner_perform_action(self, game, rgp, range_action, current_options):
        """
        Inputs:
         - game, tables.RunningGame object, from database
         - rgp, tables.RunningGameParticipant object, == game.current_rgp
         - range_action, action to perform
         - current_options, options user had here (re-computed)

        Outputs:
         - ActionResult, and spawned game IDs

        Side effects:
         - Records range action in DB (purely copying input to DB)
         - Records action result in DB
         - Records resulting range for rgp in DB
         - Applied the resulting action to the game, i.e. things like:
           - removing folded player from game
           - putting chips in the pot
           - starting the next betting round, if betting round finishes
           - determining who is next to act, if still same betting round
         - If the game is finished:
           - flag that the game is finished

        It's as simple as that. Now we just need to do / calculate as described,
        but instead of redealing based on can_call and can_fold, we'll play out
        each option, and terminate only when all options are terminal.
        """
        what_could_be = WhatCouldBe(game, rgp, range_action, current_options)
        range_ratios = what_could_be.consider_all()
        self._record_range_action(rgp, range_action,
            current_options.can_check(), current_options.is_raise,
            range_ratios)
        self._range_action_showdown(game, rgp, current_options, range_ratios)
        # this also changes game's current factor
        results = what_could_be.calculate_what_will_be(game.is_auto_spawn)

        if not results:
            logging.debug("gameid %d, determined to terminate", game.gameid)
            rgp.left_to_act = False
            game.game_finished = True
            return ActionResult.terminate(), []

        games = [game] + [self._spawn_game(game) for _ in results[1:]]
        for g, details in zip(games, results):
            self._apply_action_result(g, *details)
        return results[0][1], [g.gameid for g in games[1:]]

    def _perform_action(self, game, rgp, range_action, current_options):
        """
        _inner_perform_action, but with _attempt_start_next_round
        """
        round_initially = game.current_round
        result = self._inner_perform_action(game, rgp, range_action,
                                            current_options)
        # Deal, change round, set new game state. If it is time to!
        # condition: the betting round is finished for this game, and
        # it wasn't the river (the game may or may not be finished)
        if round_initially != RIVER:
            self.session.commit()
            self._attempt_start_next_round(game.gameid, game.spawn_group,
                                           round_initially)
        return result

    def _has_never_acted(self, userid):
        """
        True if user has never acted in any game. It's a trigger to let them
        know they have to wait for the other player to move.
        """
        return None is self.session.query(tables.GameHistoryRangeAction)  \
            .filter(tables.GameHistoryRangeAction.userid == userid).first()

    def _see_user(self, user):
        """
        Record that user has logged in and done something constructive. They
        won't be timed out, for now.
        """
        user.last_seen = datetime.datetime.utcnow()

    @api
    def perform_action(self, gameid, userid, range_action):
        """
        Performs range_action for specified user in specified game.

        Fails if:
         - game is not a running game with user in it
         - it's not user's turn
         - range_action does not sum to user's current range
         - range_action raise_total isn't appropriate
        """
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_GAME
        game = games[0]

        # check that they're in the game and it's their turn
        if game.current_userid == userid:
            rgp = game.current_rgp
        else:
            return self.ERR_NOT_USERS_TURN
        current_options = calculate_current_options(game, rgp)
        # check that their range action is valid for their options + range
        is_valid, _err = range_action_fits(range_action, current_options,
                                           rgp.range)
        if not is_valid:
            logging.debug("perform_action failing for reason %r in gameid %r, "
                          + "userid %r, range_action %r",
                          _err, gameid, userid, range_action)
            return API.ERR_INVALID_RANGES
        self._see_user(rgp.user)
        is_first_action = self._has_never_acted(userid)
        results, spawned_gameids = self._perform_action(
            game, rgp, range_action, current_options)
        return results, spawned_gameids, is_first_action

    @api
    def chat(self, gameid, userid, message):
        """
        User chats message in specified game.
        """
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_GAME
        game = games[0]

        # check that they're in the game
        for rgp_ in game.rgps:
            if rgp_.userid == userid:
                rgp = rgp_
                break
        else:
            return self.ERR_USER_NOT_IN_GAME

        # check that their message is short enough (clobber if not, sorry)
        if len(message) > MAX_CHAT:
            logging.debug("chat failing, gameid=%r, userid=%r, message=%r",
                          gameid, userid, message)
            return API.ERR_CHAT_TOO_LONG

        # check that it's not a duplicate (ignore if so)
        last = self.session.query(tables.GameHistoryChat)  \
            .filter(tables.GameHistoryChat.gameid == gameid)  \
            .filter(tables.GameHistoryChat.order == game.next_hh - 1).all()
        if last and last[0].message == message and last[0].userid == userid:
            # very last item in hand history is a chat
            # with the same message
            # by the same user
            return

        self._record_chat(rgp, message)

    def _get_payments(self, child):
        """
        Return list of payment DTOs
        """
        results = []
        payments = self.session.query(PaymentToPlayer)  \
            .filter(PaymentToPlayer.gameid == child.gameid)  \
            .filter(PaymentToPlayer.order == child.order).all()
        for payment in payments:
            results.append(GamePayment(payment))
        return results

    def _get_history_items(self, game, userid, public_ranges, hide):
        """
        Returns a list of game history items (tables.GameHistoryBase with
        additional details from child tables), with private data only for
        <userid>, if specified.
        """
        child_items = [self.session.query(table)
                       .filter(table.gameid == game.gameid).all()
                       for table in MAP_TABLE_DTO.keys()]
        all_child_items = sorted(concatenate(child_items),
                                 key=lambda c: c.order)
        child_dtos = [dtos.GameItem.from_game_history_child(child)
                      for child in all_child_items]
        all_userids = [rgp.userid for rgp in game.rgps]
        history = [dto for dto in child_dtos if
            dto.should_include_for(userid, all_userids,
                game.game_finished and not hide, public_ranges)]
        payments = {} # map order to map reason to list payments
        for child in all_child_items:
            payments[child.order] = {}
            for payment in self._get_payments(child):
                if not payments[child.order].has_key(payment.reason):
                    payments[child.order][payment.reason] = []
                payments[child.order][payment.reason].append(payment)
        return history, payments

    def _get_analysis_items(self, game):
        """
        Returns an ordered list of analysis items form the game.
        """
        afes = self.session.query(AnalysisFoldEquity)  \
            .filter(AnalysisFoldEquity.gameid == game.gameid).all()
        return {afe.order: dtos.AnalysisItemFoldEquity.from_afe(afe)
                for afe in afes}

    def _get_game(self, gameid, userid=None):
        """
        Return game <gameid>. If <userid> is not None, return private data for
        the specified user. If the game is finished, return all private data.
        Analysis items are considered private data, because they include both
        players' ranges.
        """
        if userid is not None:
            users = self.session.query(tables.User)  \
                .filter(tables.User.userid == userid).all()
            if not users:
                return self.ERR_NO_SUCH_USER
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_GAME
        game = games[0]
        game_details = dtos.RunningGameDetails.from_running_game(game)
        # TODO: 0: DODGY HACK!
        screennames = [details.user.screenname
                       for details in game_details.rgp_details]
        is_hack = set(screennames) == set(['Cwlrs2', 'screenname'])
        public_ranges = game_details.public_ranges and not is_hack
        hide = False
        if is_hack and game.game_finished:
            group_games = self.session.query(tables.RunningGame)  \
                .filter(tables.RunningGame.spawn_group ==
                        game.spawn_group).all()
            hide = not all(g.game_finished for g in group_games)
        history_items, payment_items = self._get_history_items(game,
            userid=userid, public_ranges=public_ranges,
            hide=hide)
        analysis_items = self._get_analysis_items(game)
        if game.current_userid is None:
            current_options = None
        else:
            current_options = calculate_current_options(game, game.current_rgp)
        return dtos.RunningGameHistory(game_details=game_details,
                                       history_items=history_items,
                                       payment_items=payment_items,
                                       analysis_items=analysis_items,
                                       current_options=current_options)

    @api
    def get_public_game(self, gameid):
        """
        7. Retrieve game history without current player's ranges
        inputs: gameid
        outputs: hand history populated with ranges iff finished
        """
        return self._get_game(gameid)

    @api
    def get_private_game(self, gameid, userid):
        """
        8. Retrieve game history with current player's ranges
        inputs: userid, gameid
        outputs: hand history partially populated with ranges for userid only
        """
        return self._get_game(gameid, userid=userid)

    @api
    def get_player_volumes(self):
        """
        How many games has each player completed?
        """
        games = self.session.query(tables.RunningGame).all()
        games_by_player = {}
        for game in games:
            if not game.game_finished:
                continue
            timeouts = self.session.query(tables.GameHistoryTimeout)  \
                .filter(tables.GameHistoryTimeout.gameid == game.gameid).all()
            if timeouts:
                continue
            for rgp in game.rgps:
                games_by_player.setdefault(rgp.userid, 0)
                games_by_player[rgp.userid] += 1
        return sorted(games_by_player.items(), key=lambda x: x[1], reverse=True)

    @api
    def ensure_open_games(self):
        """
        Ensure there is exactly one empty open game for each situation in the
        database.
        """
        for situation in self.session.query(tables.Situation).all():
            for public_ranges in [False, True]:
                empty_open = self.session.query(tables.OpenGame)  \
                    .filter(tables.OpenGame.situationid ==
                            situation.situationid)  \
                    .filter(tables.OpenGame.public_ranges == public_ranges)  \
                    .filter(tables.OpenGame.participants == 0).all()
                if len(empty_open) > 1:
                    # delete all except one
                    for game in empty_open[:-1]:
                        logging.debug("Deleted open game %d for situation %d",
                                      game.gameid, situation.situationid)
                        self.session.delete(game)
                elif len(empty_open) == 0 and  \
                        situation.situationid not in SUPPRESSED_SITUATIONS:
                    # add one!
                    new_game = tables.OpenGame()
                    new_game.situationid = situation.situationid
                    new_game.public_ranges = public_ranges
                    new_game.participants = 0
                    self.session.add(new_game)
                    self.session.flush()  # get gameid
                    logging.debug("Created open game %d for situation %d",
                                  new_game.gameid, situation.situationid)

    @api
    def get_user_statistics(self, userid, min_hands=1, is_competition=True):
        """
        Return user's site-wide results for all situations / positions.
        """
        # TODO: 3: optimisation mode stats collate group data, not game data
        # (and completely separate from competition mode stats)
        # (though competition mode stats could include optimisation mode game
        # data weighted by line weight)

        # TODO: 3: confidence for a situation
        # sd = sqrt(n1.sd1^2 + n2.sd2^2 + n3.sd3^2 + ...)

        # TODO: 3: global confidence, in the same fashion
        matches = self.session.query(tables.User)  \
            .filter(tables.User.userid == userid).all()
        if not matches:
            return self.ERR_NO_SUCH_USER
        return statistics.get_user_statistics(self.session, userid, min_hands,
                                              is_competition)

    def _run_pending_analysis(self):
        """
        Look through all games for analysis that has not yet been done, and do
        it, and record the analysis in the database.

        If you need to RE-analyse the database, delete existing analysis first.
        """
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.current_round == FINISHED).all()
        for game in games:
            if not game.analysis_performed:
                replayer = AnalysisReplayer(self.session, game)
                replayer.analyse()
                replayer.finalise()
        recalculate_global_statistics(self.session)

    def _analyse_immediately(self, gameid):
        """
        Analyse game on a different thread.
        """
        # TODO: 5: on-going semi-immediate analysis (long-running process)
        # with analysis etc. triggered by socket
        # (_analyse_immediately didn't work in production)
        def do_analyse():
            """
            With new session, because I doubt they're thread safe.
            """
            with session_scope(sessionmaker(bind=ENGINE)) as session:
                try:
                    game = session.query(tables.RunningGame)  \
                        .filter(tables.RunningGame.gameid == gameid).one()
                except NoResultFound:
                    logging.warning("No game for immediate analysis: %d", gameid)
                    return
                if game.analysis_performed:
                    return
                replayer = AnalysisReplayer(session, game)
                replayer.analyse()
                replayer.finalise()
                session.commit()
                session.close()
        on_a_different_thread(do_analyse)

    @api
    def run_pending_analysis(self):
        """
        Analyse games that haven't been analysed.
        """
        return self._run_pending_analysis()

    @api
    def reanalyse(self, gameid):
        """
        Delete analysis for this game, reanalyse this game.
        """
        self.session.query(tables.AnalysisFoldEquityItem)  \
            .filter(tables.AnalysisFoldEquityItem.gameid == gameid).delete()
        self.session.query(tables.AnalysisFoldEquity)  \
            .filter(tables.AnalysisFoldEquity.gameid == gameid).delete()
        for equity in self.session.query(tables.GameHistoryShowdownEquity)  \
                .filter(tables.GameHistoryShowdownEquity.gameid == gameid).all():
            equity.equity = None
        self.session.query(tables.RunningGameParticipantResult)  \
            .filter(tables.RunningGameParticipantResult.gameid == gameid)  \
            .delete()
        self.session.query(tables.PaymentToPlayer)  \
            .filter(tables.PaymentToPlayer.gameid == gameid).delete()
        self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid)  \
            .one().analysis_performed = False
        self.session.commit()
        return self._run_pending_analysis()

    @api
    def reanalyse_all(self):
        """
        Delete all analysis, and reanalyse all games.
        """
        self.session.query(tables.AnalysisFoldEquityItem).delete()
        self.session.query(tables.AnalysisFoldEquity).delete()
        for equity in self.session.query(tables.GameHistoryShowdownEquity)  \
                .all():
            equity.equity = None
        self.session.query(tables.RunningGameParticipantResult).delete()
        self.session.query(tables.PaymentToPlayer).delete()
        for game in self.session.query(tables.RunningGame).all():
            game.analysis_performed = False
        self.session.commit()
        return self._run_pending_analysis()

    def _timeout_running(self, rgp):
        """
        Timeout user from running game - make them fold their entire range
        """
        current_options = calculate_current_options(rgp.game, rgp)
        range_action = dtos.ActionDetails(fold_raw=rgp.range_raw,
            passive_raw=NOTHING, aggressive_raw=NOTHING, raise_total=0)
        logging.debug("gameid %d, userid %d being timed out", rgp.gameid,
                      rgp.userid)
        self._record_timeout(rgp)
        self._perform_action(rgp.game, rgp, range_action, current_options)

    def _timeout_open(self, ogp):
        """
        Timeout user from open game - make the leave
        """
        logging.debug("open game %d, userid %d being timed out",
                      ogp.gameid, ogp.userid)
        self._leave_game(ogp.userid, ogp.gameid)

    @api
    def process_timeouts(self):
        """
        Fold players' hands where those players have not acted for the
        standard timeout time period.
        """
        # This has to be kind of idempotent - we're not recording that users
        # have been timed out, so we will keep seeing them as needing to be
        # timed out. This is okay, because they won't actually have any running
        # or open games to be timed out of, so nothing will happen.

        # TODO: BUG: user can be timed out without even the option to move!
        # TODO: BUG: ...should timeout game+user, not user
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        users = self.session.query(tables.User)  \
            .filter(tables.User.last_seen < cutoff).all()
        count = 0
        for user in users:
            games = self.session.query(tables.RunningGame)  \
                .filter(tables.RunningGame.current_userid == user.userid)  \
                .all()
            for game in games:
                if game.game_finished:
                    continue
                rgp = game.current_rgp
                if rgp is None or rgp.userid != user.userid:
                    continue  # avoid race condition of user returning right now
                count += 1
                self._timeout_running(rgp)
            ogps = self.session.query(tables.OpenGameParticipant)  \
                .filter(tables.OpenGameParticipant.userid == user.userid).all()
            for ogp in ogps:
                self._timeout_open(ogp)
        return count

    @api
    def get_group_games(self, gameid, userid=None):
        """
        Get all running games in group.

        Gameid may not be the parent game.

        Returns groupid, gameids (for now).
        """
        try:
            root = self.session.query(tables.RunningGame)  \
                .filter(tables.RunningGame.gameid == gameid).one()
        except NoResultFound:
            return API.ERR_NO_SUCH_GAME
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.spawn_group == root.gameid).all()
        return root.gameid, [dtos.RunningGameSummary.from_running_game(game,
                                                                       userid)
                             for game in games]

    @api
    def get_game_tree(self, gameid):
        """
        Retrieve game tree for given single game.
        """
        # TODO: 1: remove this / change to retrieve from DB instead of calc
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.gameid == gameid).all()
        if not games:
            return self.ERR_NO_SUCH_GAME
        return GameTree.from_games(games)

    @api
    def get_group_tree(self, groupid):
        """
        Retrieve game tree for given group.
        """
        # TODO: 1: remove this / change to retrieve from DB instead of calc
        games = self.session.query(tables.RunningGame)  \
            .filter(tables.RunningGame.spawn_group == groupid).all()
        if not games:
            return self.ERR_NO_SUCH_GAME
        return GameTree.from_games(games)

def _create_hu():
    """
    Create the heads-up situation
    """
    hu_bb = dtos.SituationPlayerDetails(  # pylint:disable=C0103
        name="BB",
        stack=198,
        contributed=2,
        left_to_act=True,
        range_raw=ANYTHING)
    hu_btn = dtos.SituationPlayerDetails(
        name="BTN",
        stack=199,
        contributed=1,
        left_to_act=True,
        range_raw=ANYTHING)
    hu_situation = dtos.SituationDetails(
        situationid=None,
        description="Heads-up preflop, 100 BB",
        players=[hu_bb, hu_btn],  # BB acts first in future rounds
        current_player=1,  # BTN acts next (this round)
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=PREFLOP,
        pot_pre=0,
        increment=2,
        bet_count=1)
    return hu_situation

def _create_three():
    """
    Create the three-handed situation
    """
    # pylint:disable=C0301
    three_co = dtos.SituationPlayerDetails(
        name="CO",
        stack=195,
        contributed=0,
        left_to_act=True,
        range_raw="22+,A2s+,K7s+,Q9s+,J8s+,T8s+,97s+,87s,76s,65s,A8o+,KTo+,QTo+,JTo,T9o")
    three_btn = dtos.SituationPlayerDetails(
        name="BTN",
        stack=195,
        contributed=0,
        left_to_act=True,
        range_raw="88-22,AJs-A2s,KTs-K7s,Q9s,J9s,T8s+,97s+,86s+,75s+,64s+,54s,A8o+,KTo+,QJo")
    three_bb = dtos.SituationPlayerDetails(
        name="BB",
        stack=195,
        contributed=0,
        left_to_act=True,
        range_raw="88-22,AJs-A2s,K7s+,Q9s+,J8s+,T7s+,96s+,86s+,75s+,64s+,54s,A8o+,KTo+,QTo+,J9o+,T9o,98o,87o")
    three_situation = dtos.SituationDetails(
        situationid=None,
        description="Three-way flop. CO minraised, BTN cold called, BB called. BB to act first on the flop.",
        players=[three_bb, three_co, three_btn],  # BB is first to act
        current_player=0,  # BB is next to act
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=FLOP,
        pot_pre=16,
        increment=2,
        bet_count=0)
    return three_situation

def _create_cap():
    """
    Create a 6-max full hand CAP situation
    """
    cap_sb = dtos.SituationPlayerDetails(
        name="SB",
        stack=39,
        contributed=1,
        left_to_act=True,
        range_raw=ANYTHING)
    cap_bb = dtos.SituationPlayerDetails(
        name="BB",
        stack=38,
        contributed=2,
        left_to_act=True,
        range_raw=ANYTHING)
    cap_utg = dtos.SituationPlayerDetails(
        name="UTG",
        stack=40,
        contributed=0,
        left_to_act=True,
        range_raw=ANYTHING)
    cap_mp = dtos.SituationPlayerDetails(
        name="MP",
        stack=40,
        contributed=0,
        left_to_act=True,
        range_raw=ANYTHING)
    cap_co = dtos.SituationPlayerDetails(
        name="CO",
        stack=40,
        contributed=0,
        left_to_act=True,
        range_raw=ANYTHING)
    cap_btn = dtos.SituationPlayerDetails(
        name="BTN",
        stack=40,
        contributed=0,
        left_to_act=True,
        range_raw=ANYTHING)
    cap_situation = dtos.SituationDetails(
        situationid=None,
        description="6-max CAP, 20 BB",
        players=[cap_sb, cap_bb, cap_utg,
                 cap_mp, cap_co, cap_btn],  # SB is first to act
        current_player=2,  # UTG is next to act
        is_limit=False,
        big_blind=2,
        board_raw='',
        current_round=PREFLOP,
        pot_pre=0,
        increment=2,
        bet_count=1)
    return cap_situation
