"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Boolean, Sequence, ForeignKey
from sqlalchemy.orm import relationship, backref
from rvr.db.creation import BASE
from sqlalchemy.types import Float, Numeric, DateTime
from rvr.poker.cards import Card
from rvr.poker.handrange import HandRange, weighted_options_to_description
from sqlalchemy.orm.session import object_session

#pylint:disable=W0232,R0903

# TODO: REVISIT: do strings need fixed lengths?

MAX_CHAT = 10000

class User(BASE):
    """
    A user of the application.
    
    Has many-to-many relationships with OpenGame, RunningGame.
    """
    __tablename__ = 'user'
    userid = Column(Integer, Sequence('user_seq'), primary_key=True)
    identity = Column(String(120), nullable=False)
    screenname = Column(String(20), nullable=False, unique=True)
    email = Column(String(256), nullable=False, unique=True)
    unsubscribed = Column(Boolean, nullable=False)
    
    def __repr__(self):
        return ("User(userid='%r', screenname='%r', email='%r', " +  \
            "identity='%r', unsubscribed='%r')") %  \
            (self.userid, self.screenname, self.email, self.identity,
             self.unsubscribed)

class SituationPlayer(BASE, object):
    """
    Details of a player in a situation
    """
    __tablename__ = 'situation_player'
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         primary_key=True)
    order = Column(Integer, primary_key=True)
    stack = Column(Integer, nullable=False)
    contributed = Column(Integer, nullable=False)
    range_raw = Column(String, nullable=False)
    left_to_act = Column(Boolean, nullable=False)

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
            weighted_options_to_description(range_.generate_options())
    range = property(get_range, set_range)    

class Situation(BASE):
    """
    Training situations, e.g. HU NL HE for 100 BB preflop.
    
    Has one-to-many relationships with OpenGame, RunningGame. 
    """
    __tablename__ = 'situation'
    situationid = Column(Integer, primary_key=True)
    description = Column(String, unique=True, nullable=False)
    participants = Column(Integer, nullable=False)
    is_limit = Column(Boolean, nullable=False)
    big_blind = Column(Integer, nullable=False)
    board_raw = Column(String, nullable=False)
    current_round = Column(String, nullable=False)
    pot_pre = Column(Integer, nullable=False)
    increment = Column(Integer, nullable=False)
    bet_count = Column(Integer, nullable=False)
    # TODO: REVISIT: It's possible to do this FK better: http://goo.gl/CHgYzP
    current_player_num = Column(Integer, ForeignKey("situation_player.order",
        use_alter=True, name="fk_current_player"), nullable=False)
    
    def ordered_players(self):
        """
        Returns a list of SituationPlayer in the order they are seated.
        """
        # pylint:disable=E1101
        return sorted(self.players, key=lambda p: p.order)

class OpenGame(BASE):
    """
    Details of an open game, not yet full of registered participants.
    
    Has a many-to-many relationship with User, via OpenGameParticipant.
    """
    __tablename__ = 'open_game'
    gameid = Column(Integer, Sequence('gameid_seq'), primary_key=True)
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         nullable=False)
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
    user = relationship("User", backref="ogps")
    game = relationship("OpenGame", backref=backref("ogps", cascade="all"))

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
    # TODO: REVISIT: ForeignKey("running_game_participant.userid")
    # This should be a foreign key, but then SQLAlchemy thinks there's a
    # circular dependency, and won't create the database. Even with
    # post_update=True :(
    # Surely the fact that this is nullable should allow post_update to work!
    # if current_userid is None, game is finished
    current_userid = Column(Integer, nullable=True)
    next_hh = Column(Integer, default=0, nullable=False)
    # game state
    board_raw = Column(String, nullable=False)
    current_round = Column(String, nullable=False)
    pot_pre = Column(Integer, nullable=False)
    increment = Column(Integer, nullable=False)
    bet_count = Column(Integer, nullable=False)
    # keeping track of how unlikely this line is
    current_factor = Column(Float, nullable=False)
    # keeping track of timeouts
    last_action_time = Column(DateTime, nullable=False)  # or game start time
    # TODO: 3: a flag to mark completed game as "completed with no timeouts"
    # in lieu of a relationship...
    # TODO: REVISIT: can we do this with a one-to-one relationship?
    # ... and not cause circular reference issues?!
    def get_current_rgp(self):
        """
        Get current RunningGameParticipant, from current_userid
        """
        if self.current_userid is None:
            return None
        session = object_session(self)
        return session.query(RunningGameParticipant)  \
            .filter(RunningGameParticipant.userid == self.current_userid)  \
            .filter(RunningGameParticipant.gameid == self.gameid).one()
    def set_current_rgp(self, rgp):
        """
        Set current_userid, from RunningGameParticipant 
        """
        self.current_userid = rgp.userid
    current_rgp = property(get_current_rgp, set_current_rgp)
    # attributes
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
    def get_is_finished(self):
        """
        Is the game finished
        """
        return self.current_userid == None
    def set_is_finished(self, value):
        """
        Finish the game. Value must be True.
        """
        if not value:  # attempting to start a game
            if self.get_is_finished():  # attempting to restart a finished game.
                raise ValueError("Cannot restart a game")
        self.current_userid = None
    is_finished = property(get_is_finished, set_is_finished)

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
    range_raw = Column(String, nullable=False)
    left_to_act = Column(Boolean, nullable=False)
    folded = Column(Boolean, nullable=False)
    # note importantly, this is a secret from the user!
    cards_dealt_raw = Column(String, nullable=False)
    # relationships
    user = relationship("User", backref="rgps")
    game = relationship("RunningGame", backref=backref("rgps", cascade="all"),
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
        self.range_raw = weighted_options_to_description(
            range_.generate_options())
    range = property(get_range, set_range)
    def get_cards_dealt(self):
        """
        Get cards dealt, as list of two Card
        """
        return Card.many_from_text(self.cards_dealt_raw)
    def set_cards_dealt(self, cards):
        """
        Set cards dealt, from list of two Card
        """
        self.cards_dealt_raw = ''.join([card.to_mnemonic() for card in cards])
    cards_dealt = property(get_cards_dealt, set_cards_dealt)

class GameHistoryBase(BASE):
    """
    Base table for all different kinds of hand history items.
    
    Each item of whatever type has a link to a base item.
    """
    __tablename__ = 'game_history_base'
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, primary_key=True)
    time = Column(DateTime, nullable=False)
    game = relationship("RunningGame",
                        backref=backref("history", cascade="all"))

class GameHistoryUserRange(BASE):
    """
    User has range. We have one of these for each user at the start of a hand,
    and after each range action.
    """
    __tablename__ = "game_history_user_range"
    
    gameid = Column(Integer, ForeignKey("game_history_base.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_base.order"),
                   primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    # longest possible range = 6,629 chars
    range_raw = Column(String, nullable=False)

    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryUserRange.gameid," +  \
        " GameHistoryBase.order==GameHistoryUserRange.order)")
    user = relationship("User")
    
class GameHistoryActionResult(BASE):
    """
    User's range action results in this action result (fold, call, etc.)
    """
    __tablename__ = "game_history_action_result"
    
    gameid = Column(Integer, ForeignKey("game_history_base.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_base.order"),
                   primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    is_fold = Column(Boolean, nullable=False)
    is_passive = Column(Boolean, nullable=False)
    is_aggressive = Column(Boolean, nullable=False)
    call_cost = Column(Integer, nullable=True)
    raise_total = Column(Integer, nullable=True)
    is_raise = Column(Boolean, nullable=True)

    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryActionResult.gameid," +  \
        " GameHistoryBase.order==GameHistoryActionResult.order)")
    user = relationship("User")
    
class GameHistoryRangeAction(BASE):
    """
    User folds part of range, checks or calls part of range, and bets or raises
    part of range.
    """
    __tablename__ = "game_history_range_action"
    
    gameid = Column(Integer, ForeignKey("game_history_base.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_base.order"),
                   primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    fold_range = Column(String, nullable=False)
    passive_range = Column(String, nullable=False)
    aggressive_range = Column(String, nullable=False)
    raise_total = Column(Integer, nullable=False)
    # For syntactical context, call or check, bet or raise:
    is_check = Column(Boolean, nullable=False)
    is_raise = Column(Boolean, nullable=False)
    
    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryRangeAction.gameid," +  \
        " GameHistoryBase.order==GameHistoryRangeAction.order)")
    user = relationship("User")

class GameHistoryBoard(BASE):
    """
    The board at <street> is <cards>.
    """
    __tablename__ = "game_history_board"
    
    gameid = Column(Integer, ForeignKey("game_history_base.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_base.order"),
                   primary_key=True)
    street = Column(String, nullable=False)
    cards = Column(String, nullable=False)
    
    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryBoard.gameid," +  \
        " GameHistoryBase.order==GameHistoryBoard.order)")

class GameHistoryTimeout(BASE):
    """
    Player <userid> has timed out.
    """
    __tablename__ = "game_history_timeout"
    
    gameid = Column(Integer, ForeignKey("game_history_base.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_base.order"),
                   primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    
    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryTimeout.gameid," +  \
        " GameHistoryBase.order==GameHistoryTimeout.order)")
    user = relationship("User")
    
class GameHistoryChat(BASE):
    """
    Player <userid> says <message>.
    """
    # TODO: 0: Chat entry (with action, or independent of action?)
    __tablename__ = "game_history_chat"
    
    gameid = Column(Integer, ForeignKey("game_history_base.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_base.order"),
                   primary_key=True)
    userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    message = Column(String(MAX_CHAT), nullable=False)
    
    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryChat.gameid," +  \
        " GameHistoryBase.order==GameHistoryChat.order)")
    user = relationship("User")

# TODO: HAND HISTORY: the following hand history items:
#  - analysis of a fold, bet, call
#  - equity payment (fold equity, board card equity, etc.)
#  - showdown equities
#  - showdown result
# Record analysis against specific hand history (range action) items.
# Record equity payments against hand history items - deals, range actions, etc.

# TODO: 3: strategic analysis
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
    higher_card = Column(String, primary_key=True)
    lower_card = Column(String, primary_key=True)

class AnalysisFoldEquity(BASE):
    """
    Profitability, or required semibluff EV, of a bet, on any street.
    """
    __tablename__ = "analysis_fold_equity"
    # Keys
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("game_history_action_result.order"),
                   primary_key=True)
    # Relationships
    action_result = relationship("GameHistoryActionResult",
        primaryjoin="and_(GameHistoryActionResult.gameid"
        "==AnalysisFoldEquity.gameid,GameHistoryActionResult.order"
        "==AnalysisFoldEquity.order)")
    # Relevant columns
    street = Column(String, nullable=False)
    pot_before_bet = Column(Integer, nullable=False)
    is_raise = Column(Boolean, nullable=False)
    is_check = Column(Boolean, nullable=False)
    bet_cost = Column(Integer, nullable=False)
    raise_total = Column(Integer, nullable=False)
    pot_if_called = Column(Integer, nullable=False)

class AnalysisFoldEquityItem(BASE):
    """
    Individual combo in the analysis of fold equity in a spot.
    """
    __tablename__ = "analysis_fold_equity_item"
    # Keys
    gameid = Column(Integer, ForeignKey("analysis_fold_equity.gameid"),
                    primary_key=True)
    order = Column(Integer, ForeignKey("analysis_fold_equity.order"),
                   primary_key=True)
    higher_card = Column(String, ForeignKey("range_item.higher_card"),
                         primary_key=True)
    lower_card = Column(String, ForeignKey("range_item.lower_card"),
                        primary_key=True)
    is_aggressive = Column(Boolean, nullable=False)
    is_passive = Column(Boolean, nullable=False)
    is_fold = Column(Boolean, nullable=False)
    # Relationships
    analysis_fold_item = relationship("AnalysisFoldEquity",
        backref=backref("items", cascade="all"),
        primaryjoin="and_(AnalysisFoldEquityItem.gameid"
        "==AnalysisFoldEquity.gameid,AnalysisFoldEquityItem.order"
        "==AnalysisFoldEquity.order)")
    range_item = relationship("RangeItem",
        primaryjoin="and_(AnalysisFoldEquityItem.higher_card"
        "==RangeItem.higher_card,AnalysisFoldEquityItem.lower_card"
        "==RangeItem.lower_card)")
    # Relevant columns
    fold_ratio = Column(Numeric, nullable=False)
    immediate_result = Column(Numeric, nullable=False)
    # These next two can be negative, but if so we won't show them to the user.
    # Example: a bluff here wins 1.0 chips, and requires -0.3 chips EV to
    # semibluff, or -8.0% equity when called.
    semibluff_ev = Column(Numeric, nullable=True)
    semibluff_equity = Column(Numeric, nullable=True)

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
