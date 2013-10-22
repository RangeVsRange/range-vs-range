from rvr.db.tables import Situation
from rvr.db.creation import SESSION

def do_initialise():
    situation = Situation()
    situation.description = "Heads-up preflop, 100 BB"
    session = SESSION()
    session.add(situation)
    session.commit()
    
