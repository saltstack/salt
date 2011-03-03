'''
Routines to set up a minion
'''
# Import python libs
import os
import distutils.sysconfig
# Import zeromq libs
import zmq
# Import salt libs
import salt.crypt
import salt.utils

# To set up a minion:
# 1, Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the aes key
# 5. connect to the publisher
# 6. handle publications

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
        self.authenticate()

    def __load_functions(self):
        '''
        Parses through the modules in the modules directory and loads up all of
        the functions.
        '''
        # This is going to need some work to clean it up and expand
        # functionality.
        functions = {}
        mods = set()
        mod_dir = os.path.join(distutils.sysconfig.get_python_lib(),
                'salt/modules')
        for fn_ in os.listdir(mod_dir):
            if fn_.startswith('__init__.py'):
                continue
            if fn_.endswith('.pyo')\
                    or fn_.endswith('.py')\
                    or fn_.endswith('.pyc'):
                mods.add(fn_[:fn_.rindex('.')])
        for mod in mods:
            imp = __import__('salt.modules.' + mod)
            for attr in dir(imp):
                if attr.startswith('_'):
                    continue
                if callable(getattr(imp, attr)):
                    functions[mod + '.' + attr] = getattr(imp, attr)
        return functions

    def _handle_payload(self, payload):
        '''
        Takes a payload from the master publisher and edoes whatever the
        master wants done.
        '''
        pass

    def authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        pardigmn, it will update the master information from a fesh sign in,
        signing in can occur as often as needed to keep up with the revolving
        master aes key.
        '''
        auth = salt.crypt.Auth(self.opts)
        creds = auth.sign_in()
        self.aes = creds['aes']
        self.master_publish_port = creds['master_publish_port']

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        master_pub = 'tcp://' + self.opts['master'] + ':'\
                   + str(self.master_publish_port)
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(master_pub)
        while True:
            payload = socket.recv()
            self._handle_payload(payload)

