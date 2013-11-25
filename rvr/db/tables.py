"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Sequence, ForeignKey
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

class Situation(BASE):
    """
    Training situations, e.g. HU NL HE for 100 BB preflop.
    
    Has one-to-many relationships with OpenGame, RunningGame. 
    """
    __tablename__ = 'situation'
    situationid = Column(Integer, primary_key=True)
    description = Column(String(500), nullable=False, unique=True)
    participants = Column(Integer, nullable=False)
    
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
    gameid = Column(Integer, primary_key=True)
    situationid = Column(Integer, ForeignKey("situation.situationid"),
                         nullable=False)
    next_hh = Column(Integer, default=0, nullable=False)
    situation = relationship("Situation", backref="running_games")
    # if current_userid is None, game is finished
    current_userid = Column(Integer, ForeignKey("user.userid"), nullable=True)
    current_user = relationship("User")

class RunningGameParticipant(BASE):
    """
    Association object for the many-to-many relationship between users and
    running games.
    """
    __tablename__ = 'running_game_participant'
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("running_game.gameid"),
                    primary_key=True)
    order = Column(Integer, primary_key=True)
    user = relationship("User", backref="rgps")
    game = relationship("RunningGame", backref=backref("rgps", cascade="all"))

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
    range_ = Column(String(), nullable=False)
    hh_base = relationship("GameHistoryBase", primaryjoin=  \
        "and_(GameHistoryBase.gameid==GameHistoryUserRange.gameid," +  \
        " GameHistoryBase.order==GameHistoryUserRange.order)")
    user = relationship("User")

# TODO: the following hand history items:
#  - (done) user has range
#  - card dealt to the board
#  - hand dealt to player
#  - player makes a range-based action
#  - player bets / raises
#  - player calls / checks
#  - player folds
# (that's enough to play; then...)
#  - analysis of a fold, bet, call
#  - fold equity payment
#  - board card equity payment
#  - showdown equities
#  - showdown payment
#  - chat
