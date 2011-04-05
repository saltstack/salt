'''
Routines to set up a minion
'''
# Import python libs
import os
import distutils.sysconfig
import glob
import re
import time
import tempfile
import threading

# Import zeromq libs
import zmq
# Import salt libs
import salt.crypt
from salt.crypt import AuthenticationError
import salt.utils
import salt.modules

cython_enable = False
try:
    import pyximport; pyximport.install()
    cython_enable = True
except:
    pass


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
        mods = set()
        # Load up the facter information
        functions = {}
        mod_dir = os.path.join(distutils.sysconfig.get_python_lib(),
                'salt/modules')
        for fn_ in os.listdir(mod_dir):
            if fn_.startswith('__init__.py'):
                continue
            if fn_.endswith('.pyo')\
                    or fn_.endswith('.py')\
                    or fn_.endswith('.pyc'):
                mods.add(fn_[:fn_.rindex('.')])
            if fn_.endswith('.pyx') and cython_enable:
                mods.add(fn_[:fn_.rindex('.')])

        for mod in mods:
            if self.opts['disable_modules'].count(mod):
                continue
            try:
                tmodule = __import__('salt.modules', globals(), locals(), [mod])
                module = getattr(tmodule, mod)
                module.__facter__ = self.opts['facter']
            except:
                continue
            for attr in dir(module):
                if attr.startswith('_'):
                    continue
                if callable(getattr(module, attr)):
                    functions[mod + '.' + attr] = getattr(module, attr)
        functions['sys.list_functions'] = functions.keys
        functions['sys.doc'] = self.__get_docs
        functions['sys.reload_functions'] = self.reload_functions
        self.opts['logger'].info('Loaded the following functions: '\
                + str(functions))
        return functions

    def __get_docs(self, module=''):
        '''
        Return a dict containing all of the doc strings in the functions dict
        '''
        docs = {}
        for fun in self.functions:
            if fun.startswith(module):
                docs[fun] = self.functions[fun].__doc__
        return docs

    def _handle_payload(self, payload):
        '''
        Takes a payload from the master publisher and does whatever the
        master wants done.
        '''
        {'aes': self._handle_aes,
         'pub': self._handle_pub,
         'clear': self._handle_clear}[payload['enc']](payload['load'])

    def _handle_aes(self, load):
        '''
        Takes the aes encrypted load, decypts is and runs the encapsulated
        instructions
        '''
        data = None
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
            return
        # Verify that the publication applies to this minion
        if data.has_key('tgt_type'):
            if not getattr(self, '_' + data['tgt_type'] + '_match')(data['tgt']):
                return
        else:
            if not self._glob_match(data['tgt']):
                return

        threading.Thread(target=lambda: self._thread_return(data)).start()

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
        shutil.rmtree(tmp_dir)
        return ret

    def _pcre_match(self, tgt):
        '''
        Returns true if the passed pcre regex matches
        '''
        return bool(re.match(tgt, self.opts['hostname']))

    def _list_match(self, tgt):
        '''
        Determines if this host is on the list
        '''
        return bool(tgt.count(self.opts['hostname']))

    def _facter_match(self, tgt):
        '''
        Reads in the facter regular expresion match
        '''
        facter = salt.config.facter_data()
        comps = tgt.split(':')
        return bool(re.match(comps[1], facter[comps[0]]))

    def _thread_return(self, data):
        '''
        This methos should be used as a threading target, start the actual
        minion side execution.
        '''
        ret = {}
        for ind in range(0, len(data['arg'])):
            try:
                data['arg'][ind] = eval(data['arg'][ind])
            except:
                pass

        try:
            ret['return'] = self.functions[data['fun']](*data['arg'])
        except Exception as exc:
            self.opts['logger'].warning('The minion function caused an'\
                    + ' exception: ' + str(exc))
            ret['return'] = exc
        ret['jid'] = data['jid']
        self._return_pub(ret)

    def _return_pub(self, ret):
        '''
        Return the data from the executed command to the master server
        '''
        self.opts['logger'].info('Returning information for job: '\
                + ret['jid'])
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

    def reload_functions(self):
        '''
        Reload the functions dict for this minion, reading in any new functions
        '''
        self.opts['facter'] = salt.config.facter_data()
        self.functions = self.__load_functions()
        self.opts['logger'].debug('Refreshed functions, loaded functions: '\
                + str(self.functions))
        return True

    def authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        pardigmn, it will update the master information from a fresh sign in,
        signing in can occur as often as needed to keep up with the revolving
        master aes key.
        '''
        self.opts['logger'].debug('Attempting to authenticate with the Salt'\
                + ' Master')
        auth = salt.crypt.Auth(self.opts)
        while True:
            creds = auth.sign_in()
            if creds != 'retry':
                self.opts['logger'].info('Authentication with master'\
                        + ' sucessful!')
                break
            self.opts['logger'].info('Waiting for minion key to be accepted'\
                    + ' by the master.')
            time.sleep(10)
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

