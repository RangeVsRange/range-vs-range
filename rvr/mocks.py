"""
Mock objects, to be used with the IoC container: FEATURES
"""
from rvr.infrastructure.ioc import IocComponent

#pylint:disable=R0201,R0903
class MockGameFilter(IocComponent):
    """
    Mocks out the calculation of how many matching games are available, based
    on the partial signup information entered by the user during signup.
    """    
    def count_all(self):
        """
        All open games
        """
        return 17
    
    def count_all_preflop(self):
        """
        All preflop situations
        """
        return 13
    
    def count_all_situations(self):
        """
        All postflop situations
        """
        return 14
    
    def count_situation(self, _situation):
        """
        Situations that match situation
        """
        return 12