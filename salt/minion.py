'''
Routines to set up a minion
'''
# Import python libs
import os
import distutils.sysconfig
# Import salt libs
import salt.crypt
import salt.utils

# To set up a minion:
# 1, Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the aes key
# 5. connect to the publisher
#

class Minion(object):
    '''
    This class instanciates a minion, runs connections for a minion, and loads
    all of the functions into the minion
    '''
    def __init__(self, opts):
        '''
        Pass in the options dict
        '''
        self.opts = opts
        self.functions = self.__load_functions()

    def __load_functions(self):
        '''
        Parses through the modules in the modules directory and loads up all of
        the functions.
        '''
        functions = {}
        mods = set()
        mod_dir = os.path.join(distutils.sysconfig.get_python_lib(),
                'salt/modules')
        for fn_ in os.listdir(mod_dir):
            if fn_.startswith('__init__.py'):
                continue
            if fn_.endswith('.pyo') or fn_.endswith('.py') or fn_.endswith('.pyc'):
                mods.add(fn_[:fn_.rindex('.')])
        for mod in mods:
            imp = __import__(mod)
            for attr in dir(imp):
                if attr.startswith('_'):
                    continue
                if callable(getattr(imp, attr)):
                    functions[mod + '.' + attr] = getattr(imp, attr)
        return functions

    def authenticate(self):
        '''
        Authenticate with the master
        '''
        pass
