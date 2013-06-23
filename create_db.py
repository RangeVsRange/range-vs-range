"""
Module for creating database
"""
from rvr.db.connect import DB
import rvr.db.tables  # IGNORE:W0611 @UnusedImport

def create_all():
    """
    Creates the database
    """
    DB.create_all()
    
if __name__ == '__main__':
    create_all()