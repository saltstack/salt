'''
Routines to set up a minion
'''
# Import python libs
import os
import distutils.sysconfig
import importlib
import glob
import re
import tempfile

# Import zeromq libs
import zmq
# Import salt libs
import salt.crypt
from salt.crypt import AuthenticationError
import salt.utils
import salt.modules

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
            try:
                module = importlib.import_module('salt.modules.' + mod)
            except:
                continue
            for attr in dir(module):
                if attr.startswith('_'):
                    continue
                if callable(getattr(module, attr)):
                    functions[mod + '.' + attr] = getattr(module, attr)
        functions['sys.list_functions'] = lambda: functions.keys()
        functions['sys.doc'] = lambda: self.__get_docs()
        print functions
        return functions

    def __get_docs(self):
        '''
        Return a dict containing all of the doc strings in the functions dict
        '''
        docs = {}
        for fun in self.functions:
            docs[fun] = self.functions[fun].__doc__
        return docs

    def _handle_payload(self, payload):
        '''
        Takes a payload from the master publisher and does whatever the
        master wants done.
        '''
        ret = {'aes': self._handle_aes,
               'pub': self._handle_pub,
               'clear': self._handle_clear}[payload['enc']](payload['load'])
        self._return_pub(ret)

    def _handle_aes(self, load):
        '''
        Takes the aes encrypted load, decypts is and runs the encapsulated
        instructions
        '''
        data = None
        ret = {}
        try:
            data = self.crypticle.loads(load)
        except AuthenticationError:
            self.authenticate()
            data = self.crypticle.loads(load)
        # Verify that the publication is valid
        if not data.has_key('tgt')\
                or not data.has_key('jid')\
                or not data.has_key('fun')\
                or not data.has_key('arg'):
            return ret
        # Verify that the publication applies to this minion
        if data.has_key('tgt_type'):
            if not getattr(self, '_' + data['tgt_type'] + '_match')(*(data['tgt'])):
                return ret
        else:
            if not self._glob_match(data['tgt']):
                return ret

        if self.functions.has_key(data['fun']):
            ret['return'] = self.functions[data['fun']](*data['arg'])
        ret['jid'] = data['jid']
        return ret

    def _handle_pub(self, load):
        '''
        Handle public key payloads
        '''
        pass
    
    def _handle_clear(self, load):
        '''
        Handle unencrypted transmisions
        '''
        pass

    def _glob_match(self, tgt):
        '''
        Returns true if the passed glob matches the hostname
        '''
        tmp_dir = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(tmp_dir)
        open(self.opts['hostname'], 'w+').write('salt')
        ret = bool(glob.glob(tgt))
        os.chdir(cwd)
        return ret

    def _pcre_match(self, tgt):
        '''
        Returns true if the passed pcre regex matches
        '''
        return bool(re.match(tgt, self.opts['hostname']))

    def _return_pub(self, ret):
        '''
        Returnt the data from the executed command to the master server
        '''
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(self.opts['master_uri'])
        payload = {'enc': 'aes'}
        load = {'return': ret['return'],
                'cmd': '_return',
                'jid': ret['jid'],
                'hostname': self.opts['hostname']}
        payload['load'] = self.crypticle.dumps(load)
        socket.send_pyobj(payload)
        return socket.recv()

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
        self.publish_port = creds['publish_port']
        self.crypticle = salt.crypt.Crypticle(self.aes)

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        master_pub = 'tcp://' + self.opts['master'] + ':'\
                   + str(self.publish_port)
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(master_pub)
        socket.setsockopt(zmq.SUBSCRIBE, '')
        while True:
            payload = socket.recv_pyobj()
            self._handle_payload(payload)

