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
import traceback
import shutil
import threading
import multiprocessing

# Import zeromq libs
import zmq
# Import salt libs
import salt.crypt
from salt.crypt import AuthenticationError
import salt.utils
import salt.modules
import salt.returners
import salt.loader

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
        self.mod_opts = self.__prep_mod_opts()
        self.functions, self.returners = self.__load_modules()
        self.authenticate()

    def __prep_mod_opts(self):
        '''
        Returns a deep copy of the opts with key bits stripped out
        '''
        mod_opts = {}
        for key, val in self.opts.items():
            if key == 'logger':
                continue
            mod_opts[key] = val
        return mod_opts

    def __load_modules(self):
        '''
        Return the functions and the returners loaded up from the loader module
        '''
        functions = salt.loader.minion_mods(self.opts)
        returners = salt.loader.returners(self.opts)
        return functions, returners

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
        if self.opts['multiprocessing']:
            if type(data['fun']) == type(list()):
                multiprocessing.Process(target=lambda: self._thread_multi_return(data)).start()
            else:
                multiprocessing.Process(target=lambda: self._thread_return(data)).start()
        else:
            if type(data['fun']) == type(list()):
                threading.Thread(target=lambda: self._thread_multi_return(data)).start()
            else:
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
        Returns true if the passed glob matches the id
        '''
        tmp_dir = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(tmp_dir)
        open(self.opts['id'], 'w+').write('salt')
        ret = bool(glob.glob(tgt))
        os.chdir(cwd)
        shutil.rmtree(tmp_dir)
        return ret

    def _pcre_match(self, tgt):
        '''
        Returns true if the passed pcre regex matches
        '''
        return bool(re.match(tgt, self.opts['id']))

    def _list_match(self, tgt):
        '''
        Determines if this host is on the list
        '''
        return bool(tgt.count(self.opts['id']))

    def _grain_match(self, tgt):
        '''
        Reads in the grains regular expresion match
        '''
        comps = tgt.split(':')
        return bool(re.match(comps[1], self.opts['grains'][comps[0]]))

    def _exsel_match(self, tgt):
        '''
        Runs a function and return the exit code
        '''
        if not self.functions.has_key(tgt):
            return False
        return(self.functions[tgt]())

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
            trb = traceback.format_exc()
            self.opts['logger'].warning('The minion function caused an'\
                    + ' exception: ' + str(exc))
            ret['return'] = trb
        ret['jid'] = data['jid']
        if data['ret']:
            ret['id'] = self.opts['id']
            try:
                self.returners[data['ret']](ret)
            except Exception as exc:
                self.opts['logger'].error('The return failed for job '\
                    + data['jid'] + ' ' + str(exc))
        else:
            self._return_pub(ret)

    def _thread_multi_return(self, data):
        '''
        This methos should be used as a threading target, start the actual
        minion side execution.
        '''
        ret = {'return': {}}
        for ind in range(0, len(data['fun'])):
            for index in range(0, len(data['arg'][ind])):
                try:
                    data['arg'][ind][index] = eval(data['arg'][ind][index])
                except:
                    pass

            try:
                ret['return'][data['fun'][ind]]\
                    = self.functions[data['fun'][ind]](*data['arg'][ind])
            except Exception as exc:
                trb = traceback.format_exc()
                self.opts['logger'].warning('The minion function caused an'\
                        + ' exception: ' + str(exc))
                ret['return'][data['fun'][ind]] = trb
            ret['jid'] = data['jid']
        if data['ret']:
            ret['id'] = self.opts['id']
            try:
                self.returners[data['ret']](ret)
            except Exception as exc:
                self.opts['logger'].error('The return failed for job '\
                    + data['jid'] + ' ' + str(exc))
        else:
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
                'id': self.opts['id']}
        payload['load'] = self.crypticle.dumps(load)
        socket.send_pyobj(payload)
        return socket.recv()

    def reload_functions(self):
        '''
        Reload the functions dict for this minion, reading in any new functions
        '''
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

