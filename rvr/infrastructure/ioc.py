"""
FeatureBroker, a dependency injection container
"""
#pylint:disable=R0903
class FeatureBroker:  #IGNORE:R0924
    """
    Implementation of main broker
    """
    def __init__(self, allow_replace=False):
        self.providers = {}
        self.allow_replace = allow_replace
    def provide(self, feature, provider, *args, **kwargs):
        """
        Register provider against feature.
        If provider is callable, will provide the return result on request.
        If provider is not callable, will provide as-is on request.
        """
        if not self.allow_replace:
            assert not self.providers.has_key(feature),  \
                "Duplicate feature: %r" % feature
        if callable(provider):
            def call():  #IGNORE:C0111
                return provider(*args, **kwargs)  #IGNORE:W0142
        else:
            def call():  #IGNORE:C0111
                return provider
        self.providers[feature] = call
    def resolve(self, feature):
        """
        Resolve the feature.
        """
        return self[feature]
    def __getitem__(self, feature):
        try:
            provider = self.providers[feature]
        except KeyError:
            raise KeyError, "Unknown feature named %r" % feature
        return provider()

FEATURES = FeatureBroker()

class LateResolvedSingleton(object):
    """
    An attribute descriptor to "declare" required features, lazy-loads from
    FEATURES. On load, a singleton is created, so even if the feature is not a
    singleton, this is (hence the name).
    """
    def __init__(self, feature):
        self.feature = feature
    def resolve(self):
        """
        Resolve the requested feature
        """
        return self.result
    def __get__(self, name, cls):
        return self.result  # will request the feature upon first call
    def __getattr__(self, name):
        assert name == 'result',  \
            "Unexpected attribute request other then 'result'."
        self.result = FEATURES[self.feature]  #IGNORE:W0201
        return self.result

class IocComponent(object):
    "Symbolic base class for components"

def demo():
    """
    Demonstrate a working IoC container / broker / providers
    """
    class Bar(IocComponent):
        """
        # ---------------------------------------------------------------------------------
        # Some python module defines a Bar component and states the dependencies
        # We will assume that
        # - Console denotes an object with a method WriteLine(string)
        # - AppTitle denotes a string that represents the current application name
        # - CurrentUser denotes a string that represents the current user name
        #
        """
        con   = LateResolvedSingleton('Console')
        title = LateResolvedSingleton('AppTitle')
        user  = LateResolvedSingleton('CurrentUser')
        def __init__(self):
            self.val = 0
        def print_yourself(self):
            """
            Do some work, using retrieved providers
            """
            self.con.write_line('-- Bar instance --')
            self.con.write_line('Title: %s' % self.title)
            self.con.write_line('User: %s' % self.user)
            self.con.write_line('X: %d' % self.val)
    
    class BetterConsole(IocComponent):
        """
        # ---------------------------------------------------------------------------------
        # Yet another python module defines a better Console component
        #
        """
        def __init__(self, prefix=''):
            self.prefix = prefix
        def write_line(self, str_):
            """
            Implement write_line
            """
            lines = str_.split('\n')
            for line in lines:
                if line:
                    print self.prefix, line
                else:
                    print
    
    def get_current_user():
        """
        Some third python module knows how to discover the current user's name
        """
        import os
        # USERNAME is platform-specific
        return os.getenv('USERNAME') or 'Some User'

    # --------------------------------------------------------------------------
    # Finally, the main python script specifies the application name,
    # decides which components/values to use for what feature,
    # and creates an instance of Bar to work with
    #
    print '\n*** IoC Demo ***'
    FEATURES.provide('AppTitle',
        'Inversion of Control... The Python Way')
    FEATURES.provide('CurrentUser', get_current_user)
    FEATURES.provide('Console',
        BetterConsole, prefix='-->') # <-- transient lifestyle
    FEATURES['Console'].write_line('ad-hoc resolution')
    
    #FEATURES.provide('Console',
    #    BetterConsole(prefix='-->')) # <-- singleton lifestyle

    instance = Bar()
    instance.print_yourself()
    #
    # Evidently, none of the used components needed to know about each other
    # => Loose coupling goal achieved
    # --------------------------------------------------------------------------
    ## end of http://code.activestate.com/recipes/413268/ }}}

if __name__ == '__main__':
    demo()