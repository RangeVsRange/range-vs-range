"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Boolean, Sequence, ForeignKey
from sqlalchemy.orm import relationship, backref
from rvr.db.creation import BASE

#pylint:disable=W0232,R0903

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
    
    def __repr__(self):
        return "User(userid='%s', screenname='%s', email='%s')" %  \
            (self.userid, self.screenname, self.email)

class SituationPlayer(BASE):
    """
    Details of a player in a situation
    """
    __tablename__ = 'situation_player'
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         primary_key=True)
    order = Column(Integer, primary_key=True)
    stack = Column(Integer, nullable=False)
    contributed = Column(Integer, nullable=False)
    range = Column(String, nullable=False)
    left_to_act = Column(Boolean, nullable=False)

    situation = relationship("Situation", primaryjoin=  \
        "Situation.situationid==SituationPlayer.situationid",
        backref="players")

class Situation(BASE):
    """
    Training situations, e.g. HU NL HE for 100 BB preflop.
    
    Has one-to-many relationships with OpenGame, RunningGame. 
    """
    __tablename__ = 'situation'
    situationid = Column(Integer, primary_key=True)
    description = Column(String, nullable=False)
    participants = Column(Integer, nullable=False)
    is_limit = Column(Boolean, nullable=False)
    big_blind = Column(Integer, nullable=False)
    board = Column(String, nullable=False)
    current_round = Column(String, nullable=False)
    pot_pre = Column(Integer, nullable=False)
    increment = Column(Integer, nullable=False)
    bet_count = Column(Integer, nullable=False)
    # It's possible to do this FK better: http://goo.gl/CHgYzP
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

class RunningGame(BASE):
    """
    Details of an active running game.
    
    Has a many-to-many relationship with User, via RunningGameParticipant.
    """
    __tablename__ = 'running_game'
    # TODO: ForeignKey("running_game_participant.gameid")
    gameid = Column(Integer, primary_key=True)
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         nullable=False)
    next_hh = Column(Integer, default=0, nullable=False)
    situation = relationship("Situation", backref="running_games")
    # TODO: ForeignKey("running_game_participant.userid")
    # This should be a foreign key, but then SQLAlchemy thinks there's a
    # circular dependency, and won't create the database. Even with
    # post_update=True :(
    # Surely the fact that this is nullable should allow post_update to work!
    # if current_userid is None, game is finished
    current_userid = Column(Integer, nullable=True)
    # game state
    board = Column(String, nullable=False)
    current_round = Column(String, nullable=False)
    pot_pre = Column(Integer, nullable=False)
    increment = Column(Integer, nullable=False)
    bet_count = Column(Integer, nullable=False)
    # relationships
    current_rgp = relationship("RunningGameParticipant", primaryjoin=
        "and_(RunningGame.gameid==RunningGameParticipant.gameid," +  \
        " RunningGame.current_userid==RunningGameParticipant.userid)",
        foreign_keys=[gameid, current_userid])
    

class RunningGameParticipant(BASE):
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
    range = Column(String, nullable=False)
    left_to_act = Column(Boolean, nullable=False)
    folded = Column(Boolean, nullable=False)
    # relationships
    user = relationship("User", backref="rgps")
    game = relationship("RunningGame", backref=backref("rgps", cascade="all"),
        primaryjoin="RunningGame.gameid==RunningGameParticipant.gameid")

class GameHistoryBase(BASE):
    """
    Base table for all different kinds of hand history items.
    
    Each item of whatever type has a link to a base item.
    """
    __tablename__ = 'game_history_base'
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, primary_key=True)
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
    range = Column(String, nullable=False)

    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryUserRange.gameid," +  \
        " GameHistoryBase.order==GameHistoryUserRange.order)")
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
    
    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryRangeAction.gameid," +  \
        " GameHistoryBase.order==GameHistoryRangeAction.order)")
    user = relationship("User")

# TODO: the following hand history items:
#  - (done) user has range
#  - player makes a range-based action
#  - player bets / raises
#  - player calls / checks
#  - player folds
#  - card dealt to the board
# (that's enough to play; then...)
#  - analysis of a fold, bet, call
#  - fold equity payment
#  - board card equity payment
#  - showdown equities
#  - showdown payment
#  - chat
