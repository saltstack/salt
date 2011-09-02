'''
Routines to set up a minion
'''
# Import python libs
import os
import distutils.sysconfig
import glob
import re
import time
import logging
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
import salt.client

log = logging.getLogger(__name__)

# To set up a minion:
# 1, Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the aes key
# 5. connect to the publisher
# 6. handle publications

class MinionError(Exception): pass


class SMinion(object):
    '''
    Create an object that has loaded all of the minion module functions,
    grains, modules, returners etc.
    The SMinion allows developers to generate all of the salt minion functions
    and present them with these functions for general use.
    '''
    def __init__(self, opts):
        # Generate all of the minion side components
        self.opts = opts
        self.functions = salt.loader.minion_mods(self.opts)
        self.returners = salt.loader.returners(self.opts)
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.matcher = Matcher(self.opts, self.functions)


class Minion(object):
    '''
    This class instantiates a minion, runs connections for a minion, and loads
    all of the functions into the minion
    '''
    def __init__(self, opts):
        '''
        Pass in the options dict
        '''
        self.opts = opts
        self.mod_opts = self.__prep_mod_opts()
        self.functions, self.returners = self.__load_modules()
        self.matcher = Matcher(self.opts, self.functions)
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
        Takes the aes encrypted load, decrypts is and runs the encapsulated
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
            if not getattr(self.matcher, data['tgt_type'] + '_match')(data['tgt']):
                return
        else:
            if not self.matcher.glob_match(data['tgt']):
                return
        # If the minion does not have the function, don't execute, this prevents
        # minions that could not load a minion module from returning a
        # predictable exception
        #if not self.functions.has_key(data['fun']):
        #    return
        log.debug('Executing command {0[fun]} with jid {0[jid]}'.format(data))
        self._handle_decoded_payload(data)

    def _handle_pub(self, load):
        '''
        Handle public key payloads
        '''
        pass

    def _handle_clear(self, load):
        '''
        Handle un-encrypted transmissions
        '''
        pass

    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle the decoded data differently.
        '''
        if self.opts['multiprocessing']:
            if type(data['fun']) == type(list()):
                multiprocessing.Process(
                    target=lambda: self._thread_multi_return(data)
                ).start()
            else:
                multiprocessing.Process(
                    target=lambda: self._thread_return(data)
                ).start()
        else:
            if type(data['fun']) == type(list()):
                threading.Thread(
                    target=lambda: self._thread_multi_return(data)
                ).start()
            else:
                threading.Thread(
                    target=lambda: self._thread_return(data)
                ).start()

    def _thread_return(self, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        ret = {}
        for ind in range(0, len(data['arg'])):
            try:
                data['arg'][ind] = eval(data['arg'][ind])
            except:
                pass

        function_name = data['fun']
        if function_name in self.functions:
            try:
                ret['return'] = self.functions[data['fun']](*data['arg'])
            except Exception as exc:
                trb = traceback.format_exc()
                log.warning('The minion function caused an exception: %s', exc)
                ret['return'] = trb
        else:
            ret['return'] = '"%s" is not available.' % function_name

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        if data['ret']:
            ret['id'] = self.opts['id']
            try:
                self.returners[data['ret']](ret)
            except Exception as exc:
                log.error('The return failed for job %s %s', data['jid'], exc)
        else:
            self._return_pub(ret)

    def _thread_multi_return(self, data):
        '''
        This method should be used as a threading target, start the actual
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
                log.warning('The minion function caused an exception: %s', exc)
                ret['return'][data['fun'][ind]] = trb
            ret['jid'] = data['jid']
        if data['ret']:
            ret['id'] = self.opts['id']
            try:
                self.returners[data['ret']](ret)
            except Exception as exc:
                log.error('The return failed for job %s %s', data['jid'], exc)
        else:
            self._return_pub(ret)

    def _return_pub(self, ret, ret_cmd='_return'):
        '''
        Return the data from the executed command to the master server
        '''
        log.info('Returning information for job: %(jid)s', ret)
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(self.opts['master_uri'])
        payload = {'enc': 'aes'}
        if ret_cmd == '_syndic_return':
            load = {'cmd': ret_cmd,
                    'jid': ret['jid']}
            load['return'] = {}
            for key, value in ret.items():
                if key == 'jid' or key == 'fun':
                    continue
                load['return'][key] = value
        else:
            load = {'return': ret['return'],
                    'cmd': ret_cmd,
                    'jid': ret['jid'],
                    'id': self.opts['id']}
        if hasattr(self.functions[ret['fun']], '__outputter__'):
            oput = self.functions[ret['fun']].__outputter__
            if isinstance(oput, str):
                load['out'] = oput
        payload['load'] = self.crypticle.dumps(load)
        socket.send_pyobj(payload)
        return socket.recv()

    def reload_functions(self):
        '''
        Reload the functions dict for this minion, reading in any new functions
        '''
        self.functions = self.__load_functions()
        log.debug('Refreshed functions, loaded functions: %s', self.functions)
        return True

    def authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign in,
        signing in can occur as often as needed to keep up with the revolving
        master aes key.
        '''
        log.debug('Attempting to authenticate with the Salt Master')
        auth = salt.crypt.Auth(self.opts)
        while True:
            creds = auth.sign_in()
            if creds != 'retry':
                log.info('Authentication with master successful!')
                break
            log.info('Waiting for minion key to be accepted by the master.')
            time.sleep(10)
        self.aes = creds['aes']
        self.publish_port = creds['publish_port']
        self.crypticle = salt.crypt.Crypticle(self.aes)

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        master_pub = 'tcp://' + self.opts['master_ip'] + ':'\
                   + str(self.publish_port)
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(master_pub)
        socket.setsockopt(zmq.SUBSCRIBE, '')
        while True:
            payload = socket.recv_pyobj()
            self._handle_payload(payload)


class Syndic(salt.client.LocalClient, Minion):
    '''
    Make a Syndic minion, this minion will use the minion keys on the master to
    authenticate with a higher level master.
    '''
    def __init__(self, opts):
        salt.client.LocalClient.__init__(self, opts['_master_conf_file'])
        Minion.__init__(self, opts)

    def _handle_aes(self, load):
        '''
        Takes the aes encrypted load, decrypts is and runs the encapsulated
        instructions
        '''
        data = None
        # If the AES authentication has changed, re-authenticate
        try:
            data = self.crypticle.loads(load)
        except AuthenticationError:
            self.authenticate()
            data = self.crypticle.loads(load)
        # Verify that the publication is valid
        if not data.has_key('tgt')\
                or not data.has_key('jid')\
                or not data.has_key('fun')\
                or not data.has_key('to')\
                or not data.has_key('arg'):
            return
        data['to'] = int(data['to']) - 1
        log.debug('Executing syndic command {0[fun]} with jid {0[jid]}'.format(data))
        self._handle_decoded_payload(data)

    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle the decoded data differently.
        '''
        if self.opts['multiprocessing']:
            multiprocessing.Process(
                target=lambda: self.syndic_cmd(data)
            ).start()
        else:
            threading.Thread(
                target=lambda: self.syndic_cmd(data)
            ).start()

    def syndic_cmd(self, data):
        '''
        Take the now clear load and forward it on to the client cmd
        '''
        #{'tgt_type': 'glob', 'jid': '20110817205225753516', 'tgt': '*', 'ret': '', 'to': 4, 'arg': [], 'fun': 'test.ping'}
        # Set up default expr_form
        if not data.has_key('expr_form'):
            data['expr_form'] = 'glob'
        # Send out the publication
        pub_data = self.pub(
                data['tgt'],
                data['fun'],
                data['arg'],
                data['expr_form'],
                data['ret'],
                data['jid'],
                data['to']
                )
        # Gather the return data
        ret = self.get_returns(
                pub_data['jid'],
                pub_data['minions'],
                data['to']
                )
        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        # Return the publication data up the pipe
        self._return_pub(ret, '_syndic_return')

class Matcher(object):
    '''
    Use to return the value for matching calls from the master
    '''
    def __init__(self, opts, functions=None):
        self.opts = opts
        if not functions:
            functions = salt.loader.minion_mods(self.opts)
        else:
            self.functions = functions

    def confirm_top(self, match, data):            
        '''
        Takes the data passed to a top file environment and determines if the
        data matches this minion
        '''
        matcher = 'glob'
        for item in data:
            if type(item) == type(dict()):
                if item.has_key('match'):
                    matcher = item['match']
        if hasattr(self, matcher + '_match'):
            return getattr(self, matcher + '_match')(match)
        else:
            log.error('Attempting to match with unknown matcher: %s', matcher)
            return False

    def glob_match(self, tgt):
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

    def pcre_match(self, tgt):
        '''
        Returns true if the passed pcre regex matches
        '''
        return bool(re.match(tgt, self.opts['id']))

    def list_match(self, tgt):
        '''
        Determines if this host is on the list
        '''
        return bool(tgt.count(self.opts['id']))

    def grain_match(self, tgt):
        '''
        Reads in the grains regular expression match
        '''
        comps = tgt.split(':')
        if len(comps) < 2:
            log.error('Got insufficient arguments for grains from master')
            return False
        if not self.opts['grains'].has_key(comps[0]):
            log.error('Got unknown grain from master: %s', comps[0])
            return False
        return bool(re.match(comps[1], self.opts['grains'][comps[0]]))

    def exsel_match(self, tgt):
        '''
        Runs a function and return the exit code
        '''
        if not self.functions.has_key(tgt):
            return False
        return(self.functions[tgt]())


class FileClient(object):
    '''
    Interact with the salt master file server.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.auth = salt.crypt.SAuth(opts)
        self.socket = self.__get_socket()

    def __get_socket(self):
        '''
        Return the ZeroMQ socket to use
        '''
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(self.opts['master_uri'])
        return socket

    def _check_proto(self, path):
        '''
        Make sure that this path is intended for the salt master and trim it
        '''
        if not path.startswith('salt://'):
            raise MinionError('Unsupported path')
        return path[7:]
        
    def get_file(self, path, dest='', makedirs=False, env='base'):
        '''
        Get a single file from the salt-master
        '''
        path = self._check_proto(path)
        payload = {'enc': 'aes'}
        fn_ = None
        if dest:
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                if makedirs:
                    os.makedirs(destdir)
                else:
                    return False
            fn_ = open(dest, 'w+')
        load = {'path': path,
                'env': env,
                'cmd': '_serve_file'}
        while True:
            if not fn_:
                load['loc'] = 0
            else:
                load['loc'] = fn_.tell()
            payload['load'] = self.auth.crypticle.dumps(load)
            self.socket.send_pyobj(payload)
            data = self.auth.crypticle.loads(self.socket.recv_pyobj())
            if not data['data']:
                break
            if not fn_:
                dest = os.path.join(
                    self.opts['cachedir'],
                    'files',
                    data['dest']
                    )
                destdir = os.path.dirname(dest)
                if not os.path.isdir(destdir):
                    os.makedirs(destdir)
                fn_ = open(dest, 'w+')
            fn_.write(data['data'])
        return dest

    def cache_file(self, path, env='base'):
        '''
        Pull a file down from the file server and store it in the minion file
        cache
        '''
        return self.get_file(path, '', True, env)

    def cache_files(self, paths, env='base'):
        '''
        Download a list of files stored on the master and put them in the minion
        file cache
        '''
        ret = []
        for path in paths:
            ret.append(self.cache_file(path, env))
        return ret

    def hash_file(self, path, env='base'):
        '''
        Return the hash of a file, to get the hash of a file on the
        salt master file server prepend the path with salt://<file on server>
        otherwise, prepend the file with / for a local file.
        '''
        path = self._check_proto(path)
        payload = {'enc': 'aes'}
        load = {'path': path,
                'env': env,
                'cmd': '_file_hash'}
        payload['load'] = self.auth.crypticle.dumps(load)
        self.socket.send_pyobj(payload)
        return self.auth.crypticle.loads(self.socket.recv_pyobj())

    def get_state(self, sls, env):
        '''
        Get a state file from the master and store it in the local minion cache
        return the location of the file
        '''
        if sls.count('.'):
            sls = sls.replace('.', '/')
        for path in [
                'salt://' + sls + '.sls', 
                os.path.join('salt://', sls, 'init.sls')
                ]:
            dest = self.cache_file(path, env)
            if dest:
                return dest
        return False

    def master_opts(self):
        '''
        Return the master opts data 
        '''
        payload = {'enc': 'aes'}
        load = {'cmd': '_master_opts'}
        payload['load'] = self.auth.crypticle.dumps(load)
        self.socket.send_pyobj(payload)
        return self.auth.crypticle.loads(self.socket.recv_pyobj())

