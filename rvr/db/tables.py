"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Boolean, Sequence, ForeignKey
from sqlalchemy.orm import relationship, backref
from rvr.db.creation import BASE
from sqlalchemy.types import Float, DateTime
from rvr.poker.cards import Card, FINISHED, RIVER
from rvr.poker.handrange import HandRange, unweighted_options_to_description
from sqlalchemy.orm.session import object_session
from sqlalchemy.sql.schema import ForeignKeyConstraint
from sqlalchemy.orm.exc import NoResultFound

#pylint:disable=W0232,R0903

# TODO: 3: add indexes (index=True parameter) to all columns that are searched
# http://docs.sqlalchemy.org/en/latest/core/constraints.html#indexes

MAX_CHAT = 10000
MAX_RANGE_LENGTH = 6629

class User(BASE, object):
    """
    A user of the application.

    Has many-to-many relationships with OpenGame, RunningGame.
    """
    __tablename__ = 'user'
    userid = Column(Integer, Sequence('user_seq'), primary_key=True)
    identity = Column(String(120), nullable=False, index=True)
    screenname_raw = Column(String(20), nullable=True, unique=True)
    email = Column(String(256), nullable=False)
    unsubscribed = Column(Boolean, nullable=False)
    last_seen = Column(DateTime, nullable=False)

    # attributes
    def get_screenname(self):
        """
        Screenname of None means screenname is "Player <userid>"
        """
        if self.screenname_raw is not None:
            return self.screenname_raw
        else:
            return 'Player %d' % (self.userid,)
    def set_screenname(self, screenname):
        """
        Screenname of None means screenname is "Player <userid>"
        """
        if screenname is None:
            self.screenname_raw = None
        elif self.userid is None:
            self.screenname_raw = None
        elif screenname.startswith('Player ') and  \
                screenname != 'Player %d' % (self.userid,):
            # TODO: REVISIT: silent error, unexpected behaviour
            self.screenname_raw = None
        else:
            self.screenname_raw = screenname
    screenname = property(get_screenname, set_screenname)

class Situation(BASE, object):
    """
    Training situations, e.g. HU NL HE for 100 BB preflop.

    Has one-to-many relationships with OpenGame, RunningGame.
    """
    __tablename__ = 'situation'
    situationid = Column(Integer, primary_key=True)
    description = Column(String(100), unique=True, nullable=False)
    participants = Column(Integer, nullable=False)
    is_limit = Column(Boolean, nullable=False)
    big_blind = Column(Integer, nullable=False)
    board_raw = Column(String(10), nullable=False)
    current_round = Column(String(7), nullable=False)
    pot_pre = Column(Integer, nullable=False)
    increment = Column(Integer, nullable=False)
    bet_count = Column(Integer, nullable=False)
    # TODO: REVISIT: foreign key, possibly with use_alter=True
    # ... or move this to a Boolean on SituationPlayer
    current_player_num = Column(Integer, nullable=False)

    def ordered_players(self):
        """
        Returns a list of SituationPlayer in the order they are seated.
        """
        # pylint:disable=E1101
        return sorted(self.players, key=lambda p: p.order)

    def get_board(self):
        """
        Get board, as list of Card
        """
        return Card.many_from_text(self.board_raw)
    def set_board(self, cards):
        """
        Set board, from list of Card
        """
        self.board_raw = ''.join([card.to_mnemonic() for card in cards])
    board = property(get_board, set_board)

class SituationPlayer(BASE, object):
    """
    Details of a player in a situation
    """
    __tablename__ = 'situation_player'
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         primary_key=True)
    order = Column(Integer, primary_key=True, autoincrement=False)
    name_raw = Column(String(20), nullable=True)
    stack = Column(Integer, nullable=False)
    contributed = Column(Integer, nullable=False)
    range_raw = Column(String(MAX_RANGE_LENGTH), nullable=False)
    left_to_act = Column(Boolean, nullable=False)
    average_result = Column(Float, nullable=True)
    stddev = Column(Float, nullable=True)

    situation = relationship("Situation", primaryjoin=  \
        "Situation.situationid==SituationPlayer.situationid",
        backref="players")

    # attributes
    def get_range(self):
        """
        Get range, as HandRange instance
        """
        return HandRange(self.range_raw)
    def set_range(self, range_):
        """
        Set range, from HandRange instance
        """
        self.range_raw =  \
            unweighted_options_to_description(range_.generate_options())
    range = property(get_range, set_range)

    def get_name(self):
        """ Get name """
        if self.name_raw is not None:
            return self.name_raw
        else:
            return "Position %d" % (self.order,)
    def set_name(self, name):
        """ Set name """
        self.name_raw = name
    name = property(get_name, set_name)

class UserSituationPlayer(BASE, object):
    """
    Details of the same user in the same seat across all games.

    (Many-to-many relationship between User and SituationPlayer, for the
    purpose of tracking results and having leaderboards.)
    """
    __tablename__ = 'user_situation_player'
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    situationid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint([situationid, order],
            [SituationPlayer.situationid, SituationPlayer.order]),
        {})
    public_ranges = Column(Boolean, primary_key=True)

    amount_won = Column(Float, nullable=True)  # games or groups
    redline = Column(Float, nullable=True)
    blueline = Column(Float, nullable=True)
    hands_played = Column(Integer, nullable=True)  # games or groups
    confidence = Column(Float, nullable=True, index=True)  # for leaderboards

    user = relationship("User")

    def get_ev(self):
        if self.amount_won is None or self.hands_played is None:
            return None
        else:
            return 1.0 * self.amount_won / self.hands_played
    ev = property(get_ev)

class OpenGame(BASE):
    """
    Details of an open game, not yet full of registered participants.

    Has a many-to-many relationship with User, via OpenGameParticipant.
    """
    __tablename__ = 'open_game'
    gameid = Column(Integer, Sequence('gameid_seq'), primary_key=True)
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         nullable=False)
    public_ranges = Column(Boolean, nullable=False)
    participants = Column(Integer, nullable=False)
    situation = relationship("Situation", backref="open_games")

class OpenGameParticipant(BASE):
    """
    Association object for the many-to-many relationship between users and open
    games.
    """
    __tablename__ = 'open_game_participant'
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("open_game.gameid"), primary_key=True)
    order = Column(Integer)
    user = relationship("User",
        backref=backref("ogps", order_by="OpenGameParticipant.order"))
    game = relationship("OpenGame",
        backref=backref("ogps", cascade="all",
                        order_by="OpenGameParticipant.order"))

class RunningGame(BASE, object):
    """
    Details of an active running game.

    Has a many-to-many relationship with User, via RunningGameParticipant.
    """
    __tablename__ = 'running_game'
    # TODO: REVISIT: ForeignKey("running_game_participant.gameid")
    gameid = Column(Integer, primary_key=True)
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         nullable=False)
    situation = relationship("Situation", backref="running_games")
    public_ranges = Column(Boolean, nullable=False)
    # TODO: REVISIT: ForeignKey("running_game_participant.userid")
    # This should be a foreign key, but then SQLAlchemy thinks there's a
    # circular dependency, and won't create the database. Even with
    # post_update=True :(
    # Surely the fact that this is nullable should allow post_update to work!
    # if current_userid is None, current round is finished
    current_userid = Column(Integer, nullable=True)
    next_hh = Column(Integer, default=0, nullable=False)
    # game state
    # current board
    board_raw = Column(String(10), nullable=False)
    # future board
    total_board_raw = Column(String(10), nullable=False)
    current_round = Column(String(7), nullable=False)
    pot_pre = Column(Integer, nullable=False)
    increment = Column(Integer, nullable=False)
    bet_count = Column(Integer, nullable=False)
    # keeping track of how unlikely this line is, considering folds don't happen
    current_factor = Column(Float, nullable=False)
    # keeping track of timeouts
    last_action_time = Column(DateTime, nullable=False, index=True)
    # shortcut to know if analysis has been done
    analysis_performed = Column(Boolean, nullable=False, index=True)
    # game this was (originally) spawned from, if any
    spawn_group = Column(Integer, ForeignKey("running_game.gameid"),
                         nullable=True, index=True)
    spawn_finished = Column(Boolean, nullable=False, index=True)
    # starts at 1.0, reduces when spawned
    # across all games with this spawn_group, this will sum to 1.0
    spawn_factor = Column(Float, nullable=False)

    spawn_root = relationship("RunningGame")

    def copy(self):
        """
        Creates new RunningGame, spawned from this one
        """
        game = RunningGame()
        game.situationid = self.situationid
        game.public_ranges = self.public_ranges
        game.current_userid = self.current_userid
        game.next_hh = self.next_hh
        game.board_raw = self.board_raw
        game.total_board_raw = self.total_board_raw
        game.current_round = self.current_round
        game.pot_pre = self.pot_pre
        game.increment = self.increment
        game.bet_count = self.bet_count
        game.current_factor = self.current_factor
        game.last_action_time = self.last_action_time
        game.analysis_performed = self.analysis_performed
        game.spawn_group = self.spawn_group
        game.spawn_finished = self.spawn_finished
        game.spawn_factor = self.spawn_factor
        return game

    # Attributes

    def get_is_auto_spawn(self):
        """
        For now, we do this in lieu of having a setting on the game.
        """
        return self.public_ranges
    is_auto_spawn = property(get_is_auto_spawn)

    # in lieu of a relationship...
    # TODO: REVISIT: can we do this with a one-to-one relationship?
    # ... and not cause circular reference issues?!
    def get_current_rgp(self):
        """
        Get current RunningGameParticipant, from current_userid
        """
        session = object_session(self)
        try:
            return session.query(RunningGameParticipant)  \
                .filter(RunningGameParticipant.userid == self.current_userid)  \
                .filter(RunningGameParticipant.gameid == self.gameid).one()
        except NoResultFound:
            return None
    def set_current_rgp(self, rgp):
        """
        Set current_userid, from RunningGameParticipant
        """
        self.current_userid = rgp.userid
    current_rgp = property(get_current_rgp, set_current_rgp)

    def get_board(self):
        """
        Get board, as list of Card
        """
        return Card.many_from_text(self.board_raw)
    def set_board(self, cards):
        """
        Set board, from list of Card
        """
        self.board_raw = ''.join([card.to_mnemonic() for card in cards])
    board = property(get_board, set_board)

    def get_total_board(self):
        """
        Get total board, as list of Card
        """
        return Card.many_from_text(self.total_board_raw)
    def set_total_board(self, cards):
        """
        Set total board, from list of Card
        """
        self.total_board_raw = ''.join([card.to_mnemonic() for card in cards])
    total_board = property(get_total_board, set_total_board)

    def get_game_finished(self):
        """
        Is the game finished?
        """
        # legacy support:
        if self.current_round == RIVER and self.current_userid == None:
            # old-style finishments on river
            return True
        # pylint:disable=no-member
        if self.current_userid == None and  \
                any(rgp.stack == 0 for rgp in self.rgps):
            # old-style finishments pre-river
            return True
        # TODO: 3: remove the above legacy support; prod is updated now
        # real logic:
        return self.current_round == FINISHED
    def set_game_finished(self, value):
        """
        Set game finished. Value must be true.
        """
        if not value:
            raise ValueError("can't restart a game")
        self.current_round = FINISHED
        self.current_userid = None
        # check if group is finished
        session = object_session(self)
        unfinished = session.query(RunningGame)  \
            .filter(RunningGame.spawn_group == self.spawn_group)  \
            .filter(RunningGame.current_round != FINISHED).count()
        if not unfinished:  # they're all finished
            # not using ORM for this, just update rows
            session.query(RunningGame)  \
                .filter(RunningGame.spawn_group == self.spawn_group)  \
                .update({RunningGame.spawn_finished: True})
    game_finished = property(get_game_finished, set_game_finished)

    def get_round_finished(self):
        """
        Is the current round finished?
        """
        return self.current_userid == None
    round_finished = property(get_round_finished)

    def get_game_waiting(self):
        """
        Is the game waiting for another game, before proceeding to the next
        betting round?
        """
        return self.round_finished and not self.game_finished
    game_waiting = property(get_game_waiting)

class RunningGameParticipant(BASE, object):
    """
    Association object for the many-to-many relationship between users and
    running games.
    """
    __tablename__ = 'running_game_participant'
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, nullable=False)
    # game state
    stack = Column(Integer, nullable=False)
    contributed = Column(Integer, nullable=False)
    range_raw = Column(String(MAX_RANGE_LENGTH), nullable=False)
    left_to_act = Column(Boolean, nullable=False)
    folded = Column(Boolean, nullable=False)

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = RunningGameParticipant()
        new.userid = self.userid
        new.gameid = None
        new.order = self.order
        new.stack = self.stack
        new.contributed = self.contributed
        new.range_raw = self.range_raw
        new.left_to_act = self.left_to_act
        new.folded = self.folded
        return new

    # relationships
    user = relationship("User", backref="rgps")
    game = relationship("RunningGame",
        backref=backref("rgps", cascade="all",
                        order_by="RunningGameParticipant.order"),
        primaryjoin="RunningGame.gameid==RunningGameParticipant.gameid")
    # attributes
    def get_range(self):
        """
        Get range, as HandRange instance
        """
        return HandRange(self.range_raw)
    def set_range(self, range_):
        """
        Set range, from HandRange instance
        """
        self.range_raw = unweighted_options_to_description(
            range_.generate_options())
    range = property(get_range, set_range)

class GameHistoryBase(BASE):
    """
    Base table for all different kinds of hand history items.

    Each item of whatever type has a link to a base item.
    """
    __tablename__ = 'game_history_base'
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, primary_key=True, autoincrement=False)
    time = Column(DateTime, nullable=False)
    factor = Column(Float, nullable=False)
    game = relationship("RunningGame",
                        backref=backref("history", cascade="all"))

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryBase()
        new.gameid = None
        new.order = self.order
        new.time = self.time
        new.factor = self.factor
        return new

class FactorMixin(object):
    """
    Mixin to proxy to GameHistoryBase.factor
    """
    def get_factor(self):
        """
        Get factor from associated GameHistoryBase
        """
        return self.hh_base.factor
    def set_factor(self, factor):
        """
        Set factor on associated GameHistoryBase
        """
        self.hh_base.factor = factor
    factor = property(get_factor, set_factor)

class GameHistoryUserRange(BASE, FactorMixin):
    """
    User has range. We have one of these for each user at the start of a hand,
    and after each range action.
    """
    __tablename__ = "game_history_user_range"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    # longest possible range = 6,629 chars
    range_raw = Column(String(MAX_RANGE_LENGTH), nullable=False)

    hh_base = relationship("GameHistoryBase")
    user = relationship("User")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryUserRange()
        new.gameid = None
        new.order = self.order
        new.userid = self.userid
        new.range_raw = self.range_raw
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class GameHistoryActionResult(BASE, FactorMixin):
    """
    User's range action results in this action result (fold, call, etc.)
    """
    __tablename__ = "game_history_action_result"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    is_fold = Column(Boolean, nullable=False)
    is_passive = Column(Boolean, nullable=False)
    is_aggressive = Column(Boolean, nullable=False)
    call_cost = Column(Integer, nullable=True)
    raise_total = Column(Integer, nullable=True)
    is_raise = Column(Boolean, nullable=True)

    hh_base = relationship("GameHistoryBase")
    user = relationship("User")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryActionResult()
        new.gameid = None
        new.order = self.order
        new.userid = self.userid
        new.is_fold = self.is_fold
        new.is_passive = self.is_passive
        new.is_aggressive = self.is_aggressive
        new.call_cost = self.call_cost
        new.raise_total = self.raise_total
        new.is_raise = self.is_raise
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class GameHistoryRangeAction(BASE, FactorMixin):
    """
    User folds part of range, checks or calls part of range, and bets or raises
    part of range.
    """
    __tablename__ = "game_history_range_action"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    fold_range = Column(String(MAX_RANGE_LENGTH), nullable=False)
    passive_range = Column(String(MAX_RANGE_LENGTH), nullable=False)
    aggressive_range = Column(String(MAX_RANGE_LENGTH), nullable=False)
    raise_total = Column(Integer, nullable=False)
    # For syntactical context, call or check, bet or raise:
    is_check = Column(Boolean, nullable=False)
    is_raise = Column(Boolean, nullable=False)
    # Objective (considering cards_dealt) range sizes
    fold_ratio = Column(Float, nullable=True)
    passive_ratio = Column(Float, nullable=True)
    aggressive_ratio = Column(Float, nullable=True)

    hh_base = relationship("GameHistoryBase")
    user = relationship("User")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryRangeAction()
        new.gameid = None
        new.order = self.order
        new.userid = self.userid
        new.fold_range = self.fold_range
        new.passive_range = self.passive_range
        new.aggressive_range = self.aggressive_range
        new.raise_total = self.raise_total
        new.is_check = self.is_check
        new.is_raise = self.is_raise
        new.fold_ratio = self.fold_ratio
        new.passive_ratio = self.passive_ratio
        new.aggressive_ratio = self.aggressive_ratio
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class GameHistoryBoard(BASE, FactorMixin):
    """
    The board at <street> is <cards>.
    """
    __tablename__ = "game_history_board"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    street = Column(String(7), nullable=False)
    cards = Column(String(10), nullable=False)

    hh_base = relationship("GameHistoryBase")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryBoard()
        new.gameid = None
        new.order = self.order
        new.street = self.street
        new.cards = self.cards
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class GameHistoryTimeout(BASE, FactorMixin):
    """
    Player <userid> has timed out.
    """
    __tablename__ = "game_history_timeout"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)

    hh_base = relationship("GameHistoryBase")
    user = relationship("User")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryTimeout()
        new.gameid = None
        new.order = self.order
        new.userid = self.userid
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class GameHistoryChat(BASE, FactorMixin):
    """
    Player <userid> says <message>.
    """
    __tablename__ = "game_history_chat"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    message = Column(String(MAX_CHAT), nullable=False)

    hh_base = relationship("GameHistoryBase")
    user = relationship("User")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryChat()
        new.gameid = None
        new.order = self.order
        new.userid = self.userid
        new.message = self.message
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class GameHistoryShowdown(BASE, FactorMixin):
    """
    Users <list of user> have showdown with equities <equity map>

    Note that showdowns always follow the range action that creates them.
    """
    __tablename__ = "game_history_showdown"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    # Was this showdown created by a call/check, or by a fold?
    is_passive = Column(Boolean, primary_key=True)
    pot = Column(Integer, nullable=False)

    hh_base = relationship("GameHistoryBase")

    def copy(self):
        """ For spawn: copies, but not gameid """
        new = GameHistoryShowdown()
        new.gameid = None
        new.order = self.order
        new.is_passive = self.is_passive
        new.pot = self.pot
        return new

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
            [GameHistoryBase.gameid, GameHistoryBase.order]),
        # TODO: REVISIT: Why doesn't this work on MySQL?! Bad data?!
        # ForeignKeyConstraint([gameid, order],
        #     [GameHistoryRangeAction.gameid, GameHistoryRangeAction.order]),
        {})

class GameHistoryShowdownEquity(BASE):
    """
    User <userid> has equity <equity> in showdown <gameid, order, is_passive>
    """
    __tablename__ = "game_history_showdown_equity"

    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    is_passive = Column(Boolean, primary_key=True)
    # ordering within equity rows for this showdown
    showdown_order = Column(Integer, primary_key=True, autoincrement=False)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    equity = Column(Float, nullable=True)  # populated by analysis

    showdown = relationship("GameHistoryShowdown",
        backref=backref("participants", cascade="all",
            order_by="GameHistoryShowdownEquity.showdown_order"))
    user = relationship("User")

    __table_args__ = (
        ForeignKeyConstraint([gameid, order, is_passive],
            [GameHistoryShowdown.gameid,
             GameHistoryShowdown.order,
             GameHistoryShowdown.is_passive]),
        {})

# This is what we copy, when we copy a running game
GAME_HISTORY_TABLES = [
    GameHistoryBase,
    GameHistoryUserRange,
    GameHistoryActionResult,
    GameHistoryRangeAction,
    GameHistoryBoard,
    GameHistoryTimeout,
    GameHistoryChat,
    GameHistoryShowdown  # while GHSEquity is more of an analysis table
    ]

class PaymentToPlayer(BASE):
    """
    A single player's part of a payment for something.
    """
    __tablename__ = 'payment_to_player'
    gameid = Column(Integer,
                    primary_key=True)
    order = Column(Integer, primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"),
                    primary_key=True)
    reason = Column(String(20), primary_key=True)
    amount = Column(Float, nullable=False)
    history_base = relationship("GameHistoryBase",
        backref=backref("payments_to_players", cascade="all"))
    user = relationship("User")
    # Putting chips in the pot
    REASON_POT = 'pot'
    # Player doesn't fold, even though they have a fold range
    REASON_FOLD_EQUITY = 'fold-equity'
    # Showdowns never actually happen, because the calls that precede them never
    # actually happen, because play goes on. Like a fold, a showdown and the
    # call that precedes it are a leaf in the game tree, and play continues in
    # the main branch. Hence, like a fold equity payment, and a showdown
    # payment, we also need a showdown call payment.
    REASON_SHOWDOWN_CALL = 'showdown-call'
    # Getting money from the pot at showdown
    REASON_SHOWDOWN = 'showdown'
    # Showdown winnings and non-showdown winnings
    # Refer Discord, 00:06am Australian Eastern time, @gettohhole
    REASON_BLUELINE = 'blueline'  # negative, contribution to showdown
    REASON_REDLINE = 'redline'  # positive, contribution to showdown

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class RunningGameParticipantResult(BASE):
    """
    Result for a user in a game, under a result scheme
    """
    __tablename__ = 'running_game_participant_result'
    gameid = Column(Integer, primary_key=True)
    userid = Column(Integer, primary_key=True)
    scheme = Column(String(6), primary_key=True)
    result = Column(Float, nullable=False)
    rgp = relationship("RunningGameParticipant",
        backref=backref("results", cascade="all"))
    SCHEME_EV = 'ev'
    SCHEME_SD = 'sd'
    SCHEME_NSD = 'nsd'
    SCHEME_DETAILS = {
        # This is the only pure EV scheme, totally unbiased, but high-variance
        SCHEME_EV: {PaymentToPlayer.REASON_POT,
                    PaymentToPlayer.REASON_FOLD_EQUITY,
                    PaymentToPlayer.REASON_SHOWDOWN_CALL,
                    PaymentToPlayer.REASON_SHOWDOWN},
        SCHEME_SD: {PaymentToPlayer.REASON_SHOWDOWN,
                    PaymentToPlayer.REASON_BLUELINE},
        SCHEME_NSD: {PaymentToPlayer.REASON_POT,
                     PaymentToPlayer.REASON_FOLD_EQUITY,
                     PaymentToPlayer.REASON_SHOWDOWN_CALL,
                     PaymentToPlayer.REASON_REDLINE}
    }

    __table_args__ = (
        ForeignKeyConstraint([gameid, userid],
            [RunningGameParticipant.gameid, RunningGameParticipant.userid]),
        {})


# TODO: 5: further strategic analysis:
# - fold equity analysis row (might be semibluff EV, or immediate profit)
# - profitable float / bet (linked to call, and bet)
# - profitable float / raise (linked to call, and raise)
# - bets equity when called on river, and hand-by-hand
# - weak calls on river, and hand by hand
# - strong folds on river, and hand by hand
# - medium strength bluff-raises on river, and hand-by-hand

class RangeItem(BASE):
    """
    One hand in a range. Used to tie results to specific combos.

    Note: these are singletons, defined once and used everywhere.

    This table doesn't achieve much, except to ensure uniqueness within a range.
    """
    __tablename__ = "range_item"
    higher_card = Column(String(2), primary_key=True)
    lower_card = Column(String(2), primary_key=True)

"""
There is no such thing as "the EV of a AhKh", it's not a meaningful concept. But
there are:
 - EV of AhKh in Position X of Situation Y (situation EV)
 - EV of AhKh in Position X of Game W (game EV, comparable to situation EV)
 - EV of AhKh after Betting Z of Position X of Game W (node EV)
"""

class SituationComboEV(BASE):
    __tablename__ = "situation_combo_ev"
    higher_card = Column(String(2), primary_key=True)
    lower_card = Column(String(2), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint([higher_card, lower_card],
            [RangeItem.higher_card, RangeItem.lower_card]),
        {})

class UserComboOrderEV(BASE):
    __tablename__ = "user_combo_order_ev"
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, primary_key=True)
    combo = Column(String(4), primary_key=True)
    ev = Column(Float, nullable=False)
    user = relationship("User")

    __table_args__ = (
        # has to be a valid gameid + order
        ForeignKeyConstraint([gameid, order],
                             [GameHistoryBase.gameid, GameHistoryBase.order]),
        {})

class UserComboGameEV(BASE):
    __tablename__ = "user_combo_game_ev"
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    combo = Column(String(4), primary_key=True)
    ev = Column(Float, nullable=False)
    user = relationship("User")

class AnalysisFoldEquity(BASE):
    """
    Profitability, or required semibluff EV, of a bet, on any street.
    """
    __tablename__ = "analysis_fold_equity"
    # Keys
    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    # Relationships
    action_result = relationship("GameHistoryActionResult")
    # Relevant columns
    street = Column(String(7), nullable=False)
    pot_before_bet = Column(Integer, nullable=False)
    is_raise = Column(Boolean, nullable=False)
    is_check = Column(Boolean, nullable=False)
    bet_cost = Column(Integer, nullable=False)
    raise_total = Column(Integer, nullable=False)
    pot_if_called = Column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
            [GameHistoryActionResult.gameid, GameHistoryActionResult.order]),
        {})

class AnalysisFoldEquityItem(BASE):
    """
    Individual combo in the analysis of fold equity in a spot.
    """
    __tablename__ = "analysis_fold_equity_item"
    # Keys
    gameid = Column(Integer, primary_key=True)
    order = Column(Integer, primary_key=True)
    higher_card = Column(String(2), primary_key=True)
    lower_card = Column(String(2), primary_key=True)
    is_aggressive = Column(Boolean, nullable=False)
    is_passive = Column(Boolean, nullable=False)
    is_fold = Column(Boolean, nullable=False)
    # Relationships
    analysis_fold_item = relationship("AnalysisFoldEquity",
        backref=backref("items", cascade="all"))
    range_item = relationship("RangeItem")
    # Relevant columns
    fold_ratio = Column(Float, nullable=False)
    immediate_result = Column(Float, nullable=False)
    # These next two can be negative, but if so we won't show them to the user.
    # Example: a bluff here wins 1.0 chips, and requires -0.3 chips EV to
    # semibluff, or -8.0% equity when called.
    semibluff_ev = Column(Float, nullable=True)
    semibluff_equity = Column(Float, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint([gameid, order],
            [AnalysisFoldEquity.gameid, AnalysisFoldEquity.order]),
        ForeignKeyConstraint([higher_card, lower_card],
            [RangeItem.higher_card, RangeItem.lower_card]),
        {})

# class AnalysisFloat(BASE):
#     """
#     Profitability of a call with the intention of betting later, on any street
#     """
#     pass
#
# class AnalysisRiverBet(BASE):
#     """
#     Equity of a bet when called, on the river, summary of the many hands.
#     """
#     pass
#
# class AnalysisRiverBetHand(BASE):
#     """
#     Analysis of the equity of an individual hand in a river bet range.
#     """
#     pass
#
# class AnalysisRiverCall(BASE):
#     """
#     EV and equity of all hands in a call range on the river, summary.
#     This should include checks, too. It's interesting to know what your
#     showdown value is.
#     """
#     pass
#
# class AnalysisRiverCallHand(BASE):
#     """
#     Analysis of the EV and equity of an individual hand in a river call (or
#     check) range.
#     """
#
# class AnalysisRiverFold(BASE):
#     """
#     EV and equity of all hands in a fold range on the river, summary. But only
#     when there's actually a bet.
#     """
#     pass
#
# class AnalysisRiverFoldHand(BASE):
#     """
#     Analysis of the EV and equity of an individual hand in a river fold range.
#     """
#     pass
#
# class AnalysisRiverBluffRaise(BASE):
#     """
#     EV and equity of a bluff raise on the river, summary. Includes betting as
#     a bluff when we could check.
#     """
#     pass
#
# class AnalysisRiverBluffRaiseHand(BASE):
#     """
#     EV and equity of an individual hand in a raise range on the river.
#     """
