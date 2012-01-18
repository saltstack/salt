'''
Routines to set up a minion
'''

# Import python libs
import BaseHTTPServer
import contextlib
import glob
import logging
import multiprocessing
import hashlib
import os
import re
import shutil
import tempfile
import threading
import time
import traceback
import urllib2
import urlparse

# Import zeromq libs
import zmq

# Import salt libs
from salt.exceptions import AuthenticationError, MinionError, \
    CommandExecutionError, SaltInvocationError
import salt.client
import salt.crypt
import salt.loader
import salt.modules
import salt.returners
import salt.utils
import salt.payload

log = logging.getLogger(__name__)

# To set up a minion:
# 1, Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the aes key
# 5. connect to the publisher
# 6. handle publications


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
        self.gen_modules()

    def gen_modules(self):
        '''
        Load all of the modules for the minion
        '''
        self.functions = salt.loader.minion_mods(self.opts)
        self.returners = salt.loader.returners(self.opts)
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.matcher = Matcher(self.opts, self.functions)
        self.functions['sys.reload_modules'] = self.gen_modules

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
        self.serial = salt.payload.Serial(self.opts)
        self.mod_opts = self.__prep_mod_opts()
        self.functions, self.returners = self.__load_modules()
        self.matcher = Matcher(self.opts, self.functions)
        if hasattr(self,'_syndic') and self._syndic:
            log.warn('Starting the Salt Syndic Minion')
        else:
            log.warn('Starting the Salt Minion')
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
        if 'tgt' not in data or 'jid' not in data or 'fun' not in data \
           or 'arg' not in data:
            return
        # Verify that the publication applies to this minion
        if 'tgt_type' in data:
            if not getattr(self.matcher,
                           '{0}_match'.format(data['tgt_type']))(data['tgt']):
                return
        else:
            if not self.matcher.glob_match(data['tgt']):
                return
        # If the minion does not have the function, don't execute,
        # this prevents minions that could not load a minion module
        # from returning a predictable exception
        #if data['fun'] not in self.functions:
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
        Override this method if you wish to handle the decoded
        data differently.
        '''
        if isinstance(data['fun'], str):
            if data['fun'] == 'sys.reload_modules':
                self.functions, self.returners = self.__load_modules()

        if self.opts['multiprocessing']:
            if isinstance(data['fun'], list):
                multiprocessing.Process(
                    target=lambda: self._thread_multi_return(data)
                ).start()
            else:
                multiprocessing.Process(
                    target=lambda: self._thread_return(data)
                ).start()
        else:
            if isinstance(data['fun'], list):
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
                arg = eval(data['arg'][ind])
                if isinstance(arg, bool):
                    data['arg'][ind] = str(data['arg'][ind])
                elif isinstance(arg, (dict, int, list, str)):
                    data['arg'][ind] = arg
                else:
                    data['arg'][ind] = str(data['arg'][ind])
            except:
                pass

        function_name = data['fun']
        if function_name in self.functions:
            try:
                ret['return'] = self.functions[data['fun']](*data['arg'])
            except CommandExecutionError as exc:
                msg = 'A command in {0} had a problem: {1}'
                log.error(msg.format(function_name, str(exc)))
                ret['return'] = 'ERROR: {0}'.format(str(exc))
            except SaltInvocationError as exc:
                msg = 'Problem executing "{0}": {1}'
                log.error(msg.format(function_name, str(exc)))
                ret['return'] = 'ERROR executing {0}: {1}'.format(function_name, str(exc))
            except Exception as exc:
                trb = traceback.format_exc()
                msg = 'The minion function caused an exception: {0}'
                log.warning(msg.format(trb))
                ret['return'] = trb
        else:
            ret['return'] = '"{0}" is not available.'.format(function_name)

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        self._return_pub(ret)
        if data['ret']:
            for returner in set(data['ret'].split(',')):
                ret['id'] = self.opts['id']
                try:
                    self.returners[returner](ret)
                except Exception as exc:
                    log.error(
                            'The return failed for job {0} {1}'.format(
                                data['jid'],
                                exc
                                )
                            )

    def _thread_multi_return(self, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        ret = {'return': {}}
        for ind in range(0, len(data['fun'])):
            for index in range(0, len(data['arg'][ind])):
                try:
                    arg = eval(data['arg'][ind][index])
                    if isinstance(arg, bool):
                        data['arg'][ind][index] = str(data['arg'][ind][index])
                    elif isinstance(arg, (dict, int, list, str)):
                        data['arg'][ind][index] = arg
                    else:
                        data['arg'][ind][index] = str(data['arg'][ind][index])
                except:
                    pass

            try:
                ret['return'][data['fun'][ind]]\
                    = self.functions[data['fun'][ind]](*data['arg'][ind])
            except Exception as exc:
                trb = traceback.format_exc()
                log.warning(
                        'The minion function caused an exception: {0}'.format(
                            exc
                            )
                        )
                ret['return'][data['fun'][ind]] = trb
            ret['jid'] = data['jid']
        self._return_pub(ret)
        if data['ret']:
            for returner in set(data['ret'].split(',')):
                ret['id'] = self.opts['id']
                try:
                    self.returners[returner](ret)
                except Exception as exc:
                    log.error(
                            'The return failed for job {0} {1}'.format(
                                data['jid'],
                                exc
                                )
                            )

    def _return_pub(self, ret, ret_cmd='_return'):
        '''
        Return the data from the executed command to the master server
        '''
        log.info('Returning information for job: {0}'.format(ret['jid']))
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
        try:
            if hasattr(self.functions[ret['fun']], '__outputter__'):
                oput = self.functions[ret['fun']].__outputter__
                if isinstance(oput, str):
                    load['out'] = oput
        except KeyError:
            pass
        payload['load'] = self.crypticle.dumps(load)
        data = self.serial.dumps(payload)
        socket.send(data)
        ret_val = socket.recv()
        if self.opts['cache_jobs']:
            # Local job cache has been enabled
            fn_ = os.path.join(
                    self.opts['cachedir'],
                    'minion_jobs',
                    load['jid'],
                    'return.p')
            jdir = os.path.dirname(fn_)
            if not os.path.isdir(jdir):
                os.makedirs(jdir)
            open(fn_, 'w+').write(self.serial.dumps(ret))
        return ret_val

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
            time.sleep(self.opts['acceptance_wait_time'])
        self.aes = creds['aes']
        self.publish_port = creds['publish_port']
        self.crypticle = salt.crypt.Crypticle(self.opts, self.aes)

    def passive_refresh(self):
        '''
        Check to see if the salt refresh file has been laid down, if it has,
        refresh the functions and returners.
        '''
        if os.path.isfile(
                os.path.join(
                    self.opts['cachedir'],
                    '.module_refresh'
                    )
                ):
            self.functions, self.returners = self.__load_modules()
            os.remove(
                    os.path.join(
                        self.opts['cachedir'],
                        '.module_refresh'
                        )
                    )

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        master_pub = 'tcp://{0}:{1}'.format(
            self.opts['master_ip'],
            str(self.publish_port)
            )
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, '')
        socket.connect(master_pub)
        if self.opts['sub_timeout']:
            last = time.time()
            while True:
                payload = None
                try:
                    payload = self.serial.loads(socket.recv(1))
                    self._handle_payload(payload)
                    last = time.time()
                except:
                    pass
                if time.time() - last > self.opts['sub_timeout']:
                    # It has been a while since the last command, make sure
                    # the connection is fresh by reconnecting
                    socket.close()
                    socket = context.socket(zmq.SUB)
                    socket.setsockopt(zmq.SUBSCRIBE, '')
                    socket.connect(master_pub)
                    last = time.time()
                time.sleep(0.05)
                multiprocessing.active_children()
                self.passive_refresh()
        else:
            while True:
                payload = None
                try:
                    payload = self.serial(socket.recv(1))
                    self._handle_payload(payload)
                except:
                    pass
                time.sleep(0.05)
                multiprocessing.active_children()
                self.passive_refresh()


class Syndic(salt.client.LocalClient, Minion):
    '''
    Make a Syndic minion, this minion will use the minion keys on the master to
    authenticate with a higher level master.
    '''
    def __init__(self, opts):
        self._syndic = True
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
        if 'tgt' not in data or 'jid' not in data or 'fun' not in data \
           or 'to' not in data or 'arg' not in data:
            return
        data['to'] = int(data['to']) - 1
        log.debug(('Executing syndic command {0[fun]} with jid {0[jid]}'
                  .format(data)))
        self._handle_decoded_payload(data)

    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle
        the decoded data differently.
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
        # Set up default expr_form
        if 'expr_form' not in data:
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
            if isinstance(item, dict):
                if 'match' in item:
                    matcher = item['match']
        if hasattr(self, matcher + '_match'):
            return getattr(self, '{0}_match'.format(matcher))(match)
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
        return bool(tgt in self.opts['id'])

    def grain_match(self, tgt):
        '''
        Reads in the grains regular expression match
        '''
        comps = tgt.split(':')
        if len(comps) < 2:
            log.error('Got insufficient arguments for grains from master')
            return False
        if comps[0] not in self.opts['grains']:
            log.error('Got unknown grain from master: {0}'.format(comps[0]))
            return False
        return bool(re.match(comps[1], self.opts['grains'][comps[0]]))

    def exsel_match(self, tgt):
        '''
        Runs a function and return the exit code
        '''
        if tgt not in self.functions:
            return False
        return(self.functions[tgt]())

    def compound_match(self, tgt):
        '''
        Runs the compound target check
        '''
        if not isinstance(tgt, str):
            log.debug('Compound target received that is not a string')
            return False
        ref = {'G': 'grain',
               'X': 'exsel',
               'L': 'list',
               'E': 'pcre'}
        results = []
        for match in tgt.split():
            # Attach the boolean operator
            if match == 'and':
                results.append('and')
                continue
            elif match == 'or':
                results.append('or')
                continue
            # If we are here then it is not a boolean operator, check if the
            # last member of the result list is a boolean, if no, append and
            if results:
                if results[-1] != 'and' or results[-1] != 'or':
                    results.append('and')
            if match[1] == '@':
                comps = match.split('@')
                matcher = ref.get(comps[0])
                if not matcher:
                    # If an unknown matcher is called at any time, fail out
                    return False
                results.append(
                        str(getattr(
                            self,
                            '{0}_match'.format(matcher)
                            )('@'.join(comps[1:]))
                        ))
            else:
                results.append(
                        str(getattr(
                            self,
                            '{0}_match'.format(matcher)
                            )('@'.join(comps[1:]))
                        ))

        return eval(' '.join(results))

class FileClient(object):
    '''
    Interact with the salt master file server.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)
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
            raise MinionError('Unsupported path: {0}'.format(path))
        return path[7:]

    def _file_local_list(self, dest):
        '''
        Helper util to return a list of files in a directory
        '''
        if os.path.isdir(dest):
            destdir = dest
        else:
            destdir = os.path.dirname(dest)

        filelist = []

        for root, dirs, files in os.walk(destdir):
            for name in files:
                path = os.path.join(root, name)
                filelist.append(path)

        return filelist

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
            self.socket.send(self.serial.dumps(payload))
            data = self.auth.crypticle.loads(self.serial.loads(self.socket.recv()))
            if not data['data']:
                if not fn_ and data['dest']:
                    # This is a 0 byte file on the master
                    dest = os.path.join(
                        self.opts['cachedir'],
                        'files',
                        env,
                        data['dest']
                        )
                    destdir = os.path.dirname(dest)
                    cumask = os.umask(191)
                    if not os.path.isdir(destdir):
                        os.makedirs(destdir)
                    if not os.path.exists(dest):
                        open(dest, 'w+').write(data['data'])
                    os.chmod(dest, 384)
                    os.umask(cumask)
                break
            if not fn_:
                dest = os.path.join(
                    self.opts['cachedir'],
                    'files',
                    env,
                    data['dest']
                    )
                destdir = os.path.dirname(dest)
                cumask = os.umask(191)
                if not os.path.isdir(destdir):
                    os.makedirs(destdir)
                fn_ = open(dest, 'w+')
                os.chmod(dest, 384)
                os.umask(cumask)
            fn_.write(data['data'])
        return dest

    def get_url(self, url, dest, makedirs=False, env='base'):
        '''
        Get a single file from a URL.
        '''
        url_data = urlparse.urlparse(url)
        if url_data.scheme == 'salt':
            return self.get_file(url, dest, makedirs, env)
        if dest:
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                if makedirs:
                    os.makedirs(destdir)
                else:
                    return False
        else:
            dest = os.path.join(
                self.opts['cachedir'],
                'extrn_files',
                env,
                os.path.join(
                    url_data.netloc,
                    os.path.relpath(url_data.path, '/'))
                )
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
        try:
            with contextlib.closing(urllib2.urlopen(url)) as srcfp:
                with open(dest, 'wb') as destfp:
                    shutil.copyfileobj(srcfp, destfp)
            return dest
        except urllib2.HTTPError, ex:
            raise MinionError('HTTP error {0} reading {1}: {3}'.format(
                    ex.code,
                    url,
                    *BaseHTTPServer.BaseHTTPRequestHandler.responses[ex.code]))
        except urllib2.URLError, ex:
            raise MinionError('Error reading {0}: {1}'.format(url, ex.reason))
        return False

    def cache_file(self, path, env='base'):
        '''
        Pull a file down from the file server and store it in the minion file
        cache
        '''
        return self.get_url(path, '', True, env)

    def cache_files(self, paths, env='base'):
        '''
        Download a list of files stored on the master and put them
        in the minion file cache
        '''
        ret = []
        for path in paths:
            ret.append(self.cache_file(path, env))
        return ret

    def cache_master(self, env='base'):
        '''
        Download and cache all files on a master in a specified environment
        '''
        ret = []
        for path in self.file_list(env):
            ret.append(self.cache_file('salt://{0}'.format(path), env))
        return ret

    def cache_dir(self, path, env='base'):
        '''
        Download all of the files in a subdir of the master
        '''
        ret = []
        path = self._check_proto(path)
        for fn_ in self.file_list(env):
            if fn_.startswith(path):
                ret.append(self.cache_file('salt://{0}'.format(fn_), env))
        return ret

    def cache_local_file(self, path, **kwargs):
        '''
        Cache a local file on the minion in the localfiles cache
        '''
        dest = os.path.join(self.opts['cachedir'], 'localfiles',
                path.lstrip('/'))
        destdir = os.path.dirname(dest)

        if not os.path.isdir(destdir):
            os.makedirs(destdir)

        shutil.copyfile(path, dest)
        return dest

    def file_list(self, env='base'):
        '''
        List the files on the master
        '''
        payload = {'enc': 'aes'}
        load = {'env': env,
                'cmd': '_file_list'}
        payload['load'] = self.auth.crypticle.dumps(load)
        self.socket.send(self.serial.dumps(payload))
        return self.auth.crypticle.loads(self.serial.loads(self.socket.recv()))

    def file_local_list(self, env='base'):
        '''
        List files in the local minion files and localfiles caches
        '''
        filesdest = os.path.join(self.opts['cachedir'], 'files', env)
        localfilesdest = os.path.join(self.opts['cachedir'], 'localfiles')

        return sorted(self._file_local_list(filesdest) +
                self._file_local_list(localfilesdest))

    def is_cached(self, path, env='base'):
        '''
        Returns the full path to a file if it is cached locally on the minion
        otherwise returns a blank string
        '''
        localsfilesdest = os.path.join(
                self.opts['cachedir'], 'localfiles', path.lstrip('/'))
        filesdest = os.path.join(
                self.opts['cachedir'], 'files', env, path.lstrip('salt://'))

        if os.path.exists(filesdest):
            return filesdest
        elif os.path.exists(localsfilesdest):
            return localsfilesdest

        return ''

    def hash_file(self, path, env='base'):
        '''
        Return the hash of a file, to get the hash of a file on the
        salt master file server prepend the path with salt://<file on server>
        otherwise, prepend the file with / for a local file.
        '''
        try:
            path = self._check_proto(path)
        except MinionError:
            if not os.path.isfile(path):
                err = ('Specified file {0} is not present to generate '
                        'hash').format(path)
                log.warning(err)
                return {}
            else:
                ret = {}
                ret['hsum'] = hashlib.md5(open(path, 'rb').read()).hexdigest()
                ret['hash_type'] = 'md5'
                return ret
        payload = {'enc': 'aes'}
        load = {'path': path,
                'env': env,
                'cmd': '_file_hash'}
        payload['load'] = self.auth.crypticle.dumps(load)
        self.socket.send(self.serial.dumps(payload))
        return self.auth.crypticle.loads(self.serial.loads(self.socket.recv()))

    def list_env(self, path, env='base'):
        '''
        Return a list of the files in the file server's specified environment
        '''
        payload = {'enc': 'aes'}
        load = {'env': env,
                'cmd': '_file_list'}
        payload['load'] = self.auth.crypticle.dumps(load)
        self.socket.send(self.serial.dumps(payload))
        return self.auth.crypticle.loads(self.serial.loads(self.socket.recv()))

    def get_state(self, sls, env):
        '''
        Get a state file from the master and store it in the local minion cache
        return the location of the file
        '''
        if sls.count('.'):
            sls = sls.replace('.', '/')
        for path in ['salt://' + sls + '.sls',
                     os.path.join('salt://', sls, 'init.sls')]:
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
        self.socket.send(self.serial.dumps(payload))
        return self.auth.crypticle.loads(self.serial.loads(self.socket.recv()))
