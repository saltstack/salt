'''
Routines to set up a minion
'''

# Import python libs

import logging
import multiprocessing

import fnmatch
import os
import re
import threading
import time
import traceback

# Import third party libs
import zmq

# Import salt libs
from salt.exceptions import AuthenticationError, \
    CommandExecutionError, CommandNotFoundError, SaltInvocationError, \
    SaltClientError, SaltReqTimeoutError
import salt.client
import salt.crypt
import salt.loader
import salt.utils
import salt.payload
from salt._compat import string_types
from salt.utils.debug import enable_sigusr1_handler

log = logging.getLogger(__name__)

# To set up a minion:
# 1, Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the aes key
# 5. connect to the publisher
# 6. handle publications


def get_proc_dir(cachedir):
    '''
    Return the directory that process data is stored in
    '''
    fn_ = os.path.join(cachedir, 'proc')
    if not os.path.isdir(fn_):
        # proc_dir is not present, create it
        os.makedirs(fn_)
    else:
        # proc_dir is present, clean out old proc files
        for proc_fn in os.listdir(fn_):
            os.remove(os.path.join(fn_, proc_fn))
    return fn_


def detect_kwargs(func, args, data=None):
    '''
    Detect the args and kwargs that need to be passed to a function call
    '''
    spec_args, _, has_kwargs, defaults = salt.state._getargs(func)
    defaults = [] if defaults is None else defaults
    starti = len(spec_args) - len(defaults)
    kwarg_spec = set()
    for ind in range(len(defaults)):
        kwarg_spec.add(spec_args[starti])
        starti += 1
    _args = []
    kwargs = {}
    for arg in args:
        if isinstance(arg, string_types):
            if '=' in arg:
                comps = arg.split('=')
                if has_kwargs:
                    kwargs[comps[0]] = '='.join(comps[1:])
                    continue
                if comps[0] in kwarg_spec:
                    kwargs[comps[0]] = '='.join(comps[1:])
                    continue
        _args.append(arg)
    if has_kwargs and isinstance(data, dict):
        # this function accepts kwargs, pack in the publish data
        for key, val in data.items():
            kwargs['__pub_{0}'.format(key)] = val
    return _args, kwargs


class SMinion(object):
    '''
    Create an object that has loaded all of the minion module functions,
    grains, modules, returners etc.  The SMinion allows developers to
    generate all of the salt minion functions and present them with these
    functions for general use.
    '''
    def __init__(self, opts):
        # Generate all of the minion side components
        self.opts = opts
        self.gen_modules()

    def gen_modules(self):
        '''
        Load all of the modules for the minion
        '''
        self.opts['pillar'] = salt.pillar.get_pillar(
                self.opts,
                self.opts['grains'],
                self.opts['id'],
                self.opts['environment'],
                ).compile_pillar()
        self.functions = salt.loader.minion_mods(self.opts)
        self.returners = salt.loader.returners(self.opts)
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.matcher = Matcher(self.opts, self.functions)
        self.functions['sys.reload_modules'] = self.gen_modules


class Minion(object):
    '''
    This class instantiates a minion, runs connections for a minion,
    and loads all of the functions into the minion
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
        self.proc_dir = get_proc_dir(opts['cachedir'])
        if hasattr(self, '_syndic') and self._syndic:
            log.warn('Starting the Salt Syndic Minion')
        else:
            log.warn('Starting the Salt Minion')
        self.authenticate()
        opts['pillar'] = salt.pillar.get_pillar(
            opts,
            opts['grains'],
            opts['id'],
            opts['environment'],
            ).compile_pillar()

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
        Return the functions and the returners loaded up from the loader
        module
        '''
        self.opts['grains'] = salt.loader.grains(self.opts)
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
        if 'user' in data:
            log.info(('User {0[user]} Executing command {0[fun]} with jid '
                '{0[jid]}'.format(data)))
        else:
            log.info(('Executing command {0[fun]} with jid {0[jid]}'
                .format(data)))
        log.debug('Command details {0}'.format(data))
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
        Override this method if you wish to handle the decoded data
        differently.
        '''
        if isinstance(data['fun'], string_types):
            if data['fun'] == 'sys.reload_modules':
                self.functions, self.returners = self.__load_modules()

        if self.opts['multiprocessing']:
            if isinstance(data['fun'], tuple) or isinstance(data['fun'], list):
                multiprocessing.Process(
                    target=lambda: self._thread_multi_return(data)
                ).start()
            else:
                multiprocessing.Process(
                    target=lambda: self._thread_return(data)
                ).start()
        else:
            if isinstance(data['fun'], tuple) or isinstance(data['fun'], list):
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
        if self.opts['multiprocessing']:
            fn_ = os.path.join(self.proc_dir, data['jid'])
            sdata = {'pid': os.getpid()}
            sdata.update(data)
            open(fn_, 'w+').write(self.serial.dumps(sdata))
        ret = {}
        for ind in range(0, len(data['arg'])):
            try:
                arg = eval(data['arg'][ind])
                if isinstance(arg, bool):
                    data['arg'][ind] = str(data['arg'][ind])
                elif isinstance(arg, (dict, int, list, string_types)):
                    data['arg'][ind] = arg
                else:
                    data['arg'][ind] = str(data['arg'][ind])
            except Exception:
                pass

        function_name = data['fun']
        if function_name in self.functions:
            try:
                func = self.functions[data['fun']]
                args, kw = detect_kwargs(func, data['arg'], data)
                ret['return'] = func(*args, **kw)
            except CommandNotFoundError as exc:
                msg = 'Command required for \'{0}\' not found: {1}'
                log.debug(msg.format(function_name, str(exc)))
                ret['return'] = msg.format(function_name, str(exc))
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
                    elif isinstance(arg, (dict, int, list, string_types)):
                        data['arg'][ind][index] = arg
                    else:
                        data['arg'][ind][index] = str(data['arg'][ind][index])
                except Exception:
                    pass

            try:
                func = self.functions[data['fun'][ind]]
                args, kw = detect_kwargs(func, data['arg'][ind], data)
                ret['return'][data['fun'][ind]] = func(*args, **kw)
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
        if self.opts['multiprocessing']:
            fn_ = os.path.join(self.proc_dir, ret['jid'])
            if os.path.isfile(fn_):
                try:
                    os.remove(fn_)
                except (OSError, IOError):
                    # The file is gone already
                    pass
        log.info('Returning information for job: {0}'.format(ret['jid']))
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        if ret_cmd == '_syndic_return':
            load = {'cmd': ret_cmd,
                    'jid': ret['jid'],
                    'id': self.opts['id']}
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
                if isinstance(oput, string_types):
                    load['out'] = oput
        except KeyError:
            pass
        try:
            ret_val = sreq.send('aes', self.crypticle.dumps(load))
        except SaltReqTimeoutError:
            ret_val = ''
        if isinstance(ret_val, string_types) and not ret_val:
            # The master AES key has changed, reauth
            self.authenticate()
            payload['load'] = self.crypticle.dumps(load)
            data = self.serial.dumps(payload)
            socket.send(data)
            ret_val = self.serial.loads(socket.recv())
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

    @property
    def master_pub(self):
        return 'tcp://{ip}:{port}'.format(ip=self.opts['master_ip'],
                                          port=self.publish_port)

    def authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master aes key.
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
        fn_ = os.path.join(self.opts['cachedir'], 'module_refresh')
        if os.path.isfile(fn_):
            with open(fn_, 'r+') as f:
                data = f.read()
                if 'pillar' in data:
                    self.opts['pillar'] = salt.pillar.get_pillar(
                        self.opts,
                        self.opts['grains'],
                        self.opts['id'],
                        self.opts['environment'],
                        ).compile_pillar()
            try:
                os.remove(fn_)
            except OSError:
                pass
            self.functions, self.returners = self.__load_modules()

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        context = zmq.Context()

        # Prepare the minion event system
        #
        # Start with the publish socket
        epub_sock = context.socket(zmq.PUB)
        epub_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'minion_event_pub.ipc')
                )
        # Create the pull socket
        epull_sock = context.socket(zmq.PULL)
        epull_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'minion_event_pull.ipc')
                )
        # Bind the event sockets
        epub_sock.bind(epub_uri)
        epull_sock.bind(epull_uri)
        # Restrict access to the sockets
        os.chmod(
                os.path.join(self.opts['sock_dir'],
                    'minion_event_pub.ipc'),
                448
                )
        os.chmod(
                os.path.join(self.opts['sock_dir'],
                    'minion_event_pull.ipc'),
                448
                )

        poller = zmq.Poller()
        epoller = zmq.Poller()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, '')
        if self.opts['sub_timeout']:
            socket.setsockopt(zmq.IDENTITY, self.opts['id'])
        socket.connect(self.master_pub)
        poller.register(socket, zmq.POLLIN)
        epoller.register(epull_sock, zmq.POLLIN)

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        if self.opts['sub_timeout']:
            last = time.time()
            while True:
                try:
                    socks = dict(poller.poll(self.opts['sub_timeout']))
                    if socket in socks and socks[socket] == zmq.POLLIN:
                        payload = self.serial.loads(socket.recv())
                        self._handle_payload(payload)
                        last = time.time()
                    if time.time() - last > self.opts['sub_timeout']:
                        # It has been a while since the last command, make sure
                        # the connection is fresh by reconnecting
                        if self.opts['dns_check']:
                            try:
                                # Verify that the dns entry has not changed
                                self.opts['master_ip'] = salt.utils.dns_check(
                                    self.opts['master'], safe=True)
                            except SaltClientError:
                                # Failed to update the dns, keep the old addr
                                pass
                        poller.unregister(socket)
                        socket.close()
                        socket = context.socket(zmq.SUB)
                        socket.setsockopt(zmq.SUBSCRIBE, '')
                        socket.setsockopt(zmq.IDENTITY, self.opts['id'])
                        socket.connect(self.master_pub)
                        poller.register(socket, zmq.POLLIN)
                        last = time.time()
                    time.sleep(0.05)
                    multiprocessing.active_children()
                    self.passive_refresh()
                    # Check the event system
                    if epoller.poll(1):
                        try:
                            package = epull_sock.recv(zmq.NOBLOCK)
                            epub_sock.send(package)
                        except Exception:
                            pass
                except Exception as exc:
                    log.critical('A fault occured in the main minion loop {0}'.format(exc))
        else:
            while True:
                try:
                    socks = dict(poller.poll(60))
                    if socket in socks and socks[socket] == zmq.POLLIN:
                        payload = self.serial.loads(socket.recv())
                        self._handle_payload(payload)
                        last = time.time()
                    time.sleep(0.05)
                    multiprocessing.active_children()
                    self.passive_refresh()
                    # Check the event system
                    if epoller.poll(1):
                        try:
                            package = epull_sock.recv(zmq.NOBLOCK)
                            epub_sock.send(package)
                        except Exception:
                            pass
                except Exception as exc:
                    log.critical('A fault occured in the main minion loop {0}'.format(exc))


class Syndic(salt.client.LocalClient, Minion):
    '''
    Make a Syndic minion, this minion will use the minion keys on the
    master to authenticate with a higher level master.
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
        if 'user' in data:
            log.debug(('User {0[user]} Executing syndic command {0[fun]} with '
                'jid {0[jid]}'.format(data)))
        else:
            log.debug(('Executing syndic command {0[fun]} with jid {0[jid]}'
                .format(data)))
        log.debug('Command details: {0}'.format(data))
        self._handle_decoded_payload(data)

    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle the decoded data
        differently.
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
        # Set up default tgt_type
        if 'tgt_type' not in data:
            data['tgt_type'] = 'glob'
        # Send out the publication
        pub_data = self.pub(
                data['tgt'],
                data['fun'],
                data['arg'],
                data['tgt_type'],
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

    def confirm_top(self, match, data, nodegroups=None):
        '''
        Takes the data passed to a top file environment and determines if the
        data matches this minion
        '''
        matcher = 'glob'
        if not data:
            log.error('Recived bad data when setting the match from the top '
                      'file')
            return False
        for item in data:
            if isinstance(item, dict):
                if 'match' in item:
                    matcher = item['match']
        if hasattr(self, matcher + '_match'):
            if matcher == 'nodegroup':
                return getattr(self, '{0}_match'.format(matcher))(match, nodegroups)
            return getattr(self, '{0}_match'.format(matcher))(match)
        else:
            log.error('Attempting to match with unknown matcher: {0}'.format(
                matcher
                ))
            return False

    def glob_match(self, tgt):
        '''
        Returns true if the passed glob matches the id
        '''
        return fnmatch.fnmatch(self.opts['id'], tgt)

    def pcre_match(self, tgt):
        '''
        Returns true if the passed pcre regex matches
        '''
        return bool(re.match(tgt, self.opts['id']))

    def list_match(self, tgt):
        '''
        Determines if this host is on the list
        '''
        if isinstance(tgt, string_types):
            tgt = tgt.split(',')
        return bool(self.opts['id'] in tgt)

    def grain_match(self, tgt):
        '''
        Reads in the grains glob match
        '''
        comps = tgt.split(':')
        if len(comps) < 2:
            log.error('Got insufficient arguments for grains from master')
            return False
        if comps[0] not in self.opts['grains']:
            log.error('Got unknown grain from master: {0}'.format(comps[0]))
            return False
        if isinstance(self.opts['grains'][comps[0]], list):
            # We are matching a single component to a single list member
            for member in self.opts['grains'][comps[0]]:
                if fnmatch.fnmatch(str(member).lower(), comps[1].lower()):
                    return True
            return False
        return bool(fnmatch.fnmatch(
            str(self.opts['grains'][comps[0]]).lower(),
            comps[1].lower(),
            ))

    def grain_pcre_match(self, tgt):
        '''
        Matches a grain based on regex
        '''
        comps = tgt.split(':')
        if len(comps) < 2:
            log.error('Got insufficient arguments for grains from master')
            return False
        if comps[0] not in self.opts['grains']:
            log.error('Got unknown grain from master: {0}'.format(comps[0]))
            return False
        if isinstance(self.opts['grains'][comps[0]], list):
            # We are matching a single component to a single list member
            for member in self.opts['grains'][comps[0]]:
                if re.match(comps[1].lower(), str(member).lower()):
                    return True
            return False
        return bool(
                re.match(
                    comps[1].lower(),
                    str(self.opts['grains'][comps[0]]).lower()
                    )
                )

    def exsel_match(self, tgt):
        '''
        Runs a function and return the exit code
        '''
        if tgt not in self.functions:
            return False
        return(self.functions[tgt]())

    def pillar_match(self, tgt):
        '''
        Reads in the pillar glob match
        '''
        log.debug('tgt {0}'.format(tgt))
        comps = tgt.split(':')
        if len(comps) < 2:
            log.error('Got insufficient arguments for pillar match statement from master')
            return False
        if comps[0] not in self.opts['pillar']:
            log.error('Got unknown pillar match statement from master: {0}'.format(comps[0]))
            return False
        if isinstance(self.opts['pillar'][comps[0]], list):
            # We are matching a single component to a single list member
            for member in self.opts['pillar'][comps[0]]:
                if fnmatch.fnmatch(str(member).lower(), comps[1].lower()):
                    return True
            return False
        return bool(fnmatch.fnmatch(
            str(self.opts['pillar'][comps[0]]).lower(),
            comps[1].lower(),
            ))

    def compound_match(self, tgt):
        '''
        Runs the compound target check
        '''
        if not isinstance(tgt, string_types):
            log.debug('Compound target received that is not a string')
            return False
        ref = {'G': 'grain',
               'P': 'grain_pcre',
               'X': 'exsel',
               'I': 'pillar',
               'L': 'list',
               'E': 'pcre'}
        results = []
        opers = ['and', 'or', 'not']
        for match in tgt.split():
            # Try to match tokens from the compound target, first by using
            # the 'G, X, I, L, E' matcher types, then by hostname glob.
            if '@' in match and match[1] == '@':
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
            elif match in opers:
                # We didn't match a target, so append a boolean operator
                results.append(match)
            else:
                # The match is not explicitly defined, evaluate it as a glob
                results.append(str(self.glob_match(match)))
        return eval(' '.join(results))

    def nodegroup_match(self, tgt, nodegroups):
        '''
        This is a compatibility matcher and is NOT called when using
        nodegroups for remote execution, but is called when the nodegroups
        matcher is used in states
        '''
        if tgt in nodegroups:
            return self.compound_match(nodegroups[tgt])
        return False
