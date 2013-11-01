"""
Declares database tables
"""
from sqlalchemy import Column, Integer, String, Sequence, ForeignKey
from sqlalchemy.orm import relationship, backref
from rvr.db.creation import BASE

#pylint:disable=W0232

class User(BASE):
    """
    A user of the application.
    
    Has many-to-many relationships with OpenGame, RunningGame and FinishedGame.
    """
    __tablename__ = 'user'
    userid = Column(Integer, Sequence('user_seq'), primary_key=True)
    provider = Column(String(120), nullable=False)
    screenname = Column(String(20), nullable=False, unique=True)
    email = Column(String(256), nullable=False, unique=True)
    
    def __repr__(self):
        return "User<userid='%s', screenname='%s'>" %  \
            (self.userid, self.screenname)

class Situation(BASE):
    """
    Training situations, e.g. HU NL HE for 100 BB preflop.
    
    Has one-to-many relationships with OpenGame, RunningGame and FinishedGame. 
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
    situationid = Column(Integer, ForeignKey("situation.situationid"), nullable=False)
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
    situationid = Column(Integer, ForeignKey("situation.situationid"), nullable=False)
    current_userid = Column(Integer, ForeignKey("user.userid"), nullable=False)
    situation = relationship("Situation", backref="running_games")
    current_user = relationship("User")

class RunningGameParticipant(BASE):
    """
    Association object for the many-to-many relationship between users and
    running games.
    """
    # TODO: record the order of players in the game!
    __tablename__ = 'running_game_participant'
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("running_game.gameid"), primary_key=True)
    user = relationship("User", backref="rgps")
    game = relationship("RunningGame", backref=backref("rgps", cascade="all"))

class FinishedGame(BASE):
    """
    A record of a game that has been played and finished.

    Has a many-to-many relationship with User, via FinishedGameParticipant.
    """
    __tablename__ = 'finished_game'
    gameid = Column(Integer, primary_key=True)
    situationid = Column(Integer, ForeignKey("situation.situationid"), nullable=False)
    situation = relationship("Situation", backref="finished_games")

class FinishedGameParticipant(BASE):
    """
    Association object for the many-to-many relationship between users and
    finished games.
    """
    __tablename__ = 'finished_game_participant'
    userid = Column(Integer, ForeignKey("user.userid"), primary_key=True)
    gameid = Column(Integer, ForeignKey("finished_game.gameid"), primary_key=True)
    user = relationship("User", backref="fgps")
    game = relationship("FinishedGame", backref="fgps")
