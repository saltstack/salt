'''
Salt's pluggable authentication system

This sysetm allows for authentication to be managed in a module pluggable way
so that any external authentication system can be used inside of Salt
'''

# 1. Create auth loader instance
# 2. Accept arguments as a dict
# 3. Verify with function introspection
# 4. Execute function
# 5. Cache auth token with relative data
# 6. Interface to verify tokens

# Import Python libs
import inspect
#
# Import Salt libs
import salt.loader


def getargs(func):
    '''
    Returns a parsable data set from inspect.getargspec
    '''
    pass

class LoadAuth(object):
    '''
    Wrap the authentication system to handle periphrial components
    '''
    def __init__(self, opts):
        self.opts = opts
        self.auth = salt.loader.auth(opts)

    def auth(self, load):
        '''
        Return the token and set the cache data for use 
        '''
        pass
