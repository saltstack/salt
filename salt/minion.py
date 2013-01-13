# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
import logging
import getpass
import multiprocessing
import fnmatch
import os
import hashlib
import re
import threading
import time
import traceback
import sys

# Import third party libs
import zmq

# Import salt libs
from salt.exceptions import (
    AuthenticationError, CommandExecutionError, CommandNotFoundError,
    SaltInvocationError, SaltReqTimeoutError, SaltSystemExit
)
import salt.client
import salt.crypt
import salt.loader
import salt.utils
import salt.payload
from salt._compat import string_types
from salt.utils.debug import enable_sigusr1_handler

log = logging.getLogger(__name__)

# To set up a minion:
# 1. Read in the configuration
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
        # Late setup the of the opts grains, so we can log from the grains
        # module
        opts['grains'] = salt.loader.grains(opts)
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
        self.returners = salt.loader.returners(self.opts, self.functions)
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.matcher = Matcher(self.opts, self.functions)
        self.functions['sys.reload_modules'] = self.gen_modules


class MasterMinion(object):
    '''
    Create a fully loaded minion function object for generic use on the
    master. What makes this class different is that the pillar is
    omitted, otherwise everything else is loaded cleanly.
    '''
    def __init__(
            self,
            opts,
            returners=True,
            states=True,
            rend=True,
            matcher=True,
            whitelist=None):
        self.opts = opts
        self.whitelist = whitelist
        self.opts['grains'] = salt.loader.grains(opts)
        self.opts['pillar'] = {}
        self.mk_returners = returners
        self.mk_states = states
        self.mk_rend = rend
        self.mk_matcher = matcher
        self.gen_modules()

    def gen_modules(self):
        '''
        Load all of the modules for the minion
        '''
        self.functions = salt.loader.minion_mods(
                self.opts,
                whitelist=self.whitelist)
        if self.mk_returners:
            self.returners = salt.loader.returners(self.opts, self.functions)
        if self.mk_states:
            self.states = salt.loader.states(self.opts, self.functions)
        if self.mk_rend:
            self.rend = salt.loader.render(self.opts, self.functions)
        if self.mk_matcher:
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
        # Late setup the of the opts grains, so we can log from the grains
        # module
        opts['grains'] = salt.loader.grains(opts)
        self.opts = opts
        self.authenticate()
        self.opts['pillar'] = salt.pillar.get_pillar(
            opts,
            opts['grains'],
            opts['id'],
            opts['environment'],
            ).compile_pillar()
        self.serial = salt.payload.Serial(self.opts)
        self.mod_opts = self.__prep_mod_opts()
        self.functions, self.returners = self.__load_modules()
        self.matcher = Matcher(self.opts, self.functions)
        self.proc_dir = get_proc_dir(opts['cachedir'])
        self.__processing = []

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
        returners = salt.loader.returners(self.opts, functions)
        return functions, returners

    def _fire_master(self, data, tag):
        '''
        Fire an event on the master
        '''
        load = {'id': self.opts['id'],
                'tag': tag,
                'data': data,
                'cmd': '_minion_event'}
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        try:
            sreq.send('aes', self.crypticle.dumps(load))
        except:
            pass

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
        if isinstance(data['fun'], tuple) or isinstance(data['fun'], list):
            target = Minion._thread_multi_return
        else:
            target = Minion._thread_return
        # We stash an instance references to allow for the socket
        # communication in Windows. You can't pickle functions, and thus
        # python needs to be able to reconstruct the reference on the other
        # side.
        instance = self
        if self.opts['multiprocessing']:
            if sys.platform.startswith('win'):
                # let python reconstruct the minion on the other side if we're
                # running on windows
                instance = None
            process = multiprocessing.Process(
                target=target, args=(instance, self.opts, data)
            )
        else:
            process = threading.Thread(
                target=target, args=(instance, self.opts, data)
            )
        self.__processing.append(process)
        process.start()

    @classmethod
    def _thread_return(class_, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        # this seems awkward at first, but it's a workaround for Windows
        # multiprocessing communication.
        if not minion_instance:
            minion_instance = class_(opts)
        if opts['multiprocessing']:
            fn_ = os.path.join(minion_instance.proc_dir, data['jid'])
            sdata = {'pid': os.getpid()}
            sdata.update(data)
            with salt.utils.fopen(fn_, 'w+') as fp_:
                fp_.write(minion_instance.serial.dumps(sdata))
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
        if function_name in minion_instance.functions:
            ret['success'] = False
            try:
                func = minion_instance.functions[data['fun']]
                args, kwargs = detect_kwargs(func, data['arg'], data)
                ret['return'] = func(*args, **kwargs)
                ret['success'] = True
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
                ret['return'] = 'ERROR executing {0}: {1}'.format(
                    function_name, exc
                )
            except Exception:
                trb = traceback.format_exc()
                msg = 'The minion function caused an exception: {0}'
                log.warning(msg.format(trb))
                ret['return'] = trb
        else:
            ret['return'] = '"{0}" is not available.'.format(function_name)

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        minion_instance._return_pub(ret)
        if data['ret']:
            for returner in set(data['ret'].split(',')):
                ret['id'] = opts['id']
                try:
                    minion_instance.returners['{0}.returner'.format(
                        returner
                        )](ret)
                except Exception as exc:
                    log.error(
                            'The return failed for job {0} {1}'.format(
                                data['jid'],
                                exc
                                )
                            )

    @classmethod
    def _thread_multi_return(class_, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        # this seems awkward at first, but it's a workaround for Windows
        # multiprocessing communication.
        if not minion_instance:
            minion_instance = class_(opts)
        ret = {
                'return': {},
                'success': {},
                }
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

            ret['success'][data['fun'][ind]] = False
            try:
                func = minion_instance.functions[data['fun'][ind]]
                args, kwargs = detect_kwargs(func, data['arg'][ind], data)
                ret['return'][data['fun'][ind]] = func(*args, **kwargs)
                ret['success'][data['fun'][ind]] = True
            except Exception as exc:
                trb = traceback.format_exc()
                log.warning(
                        'The minion function caused an exception: {0}'.format(
                            exc
                            )
                        )
                ret['return'][data['fun'][ind]] = trb
            ret['jid'] = data['jid']
        minion_instance._return_pub(ret)
        if data['ret']:
            for returner in set(data['ret'].split(',')):
                ret['id'] = opts['id']
                try:
                    minion_instance.returners['{0}.returner'.format(
                        returner
                        )](ret)
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
            ret_val = sreq.send('aes', self.crypticle.dumps(load))
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
            salt.utils.fopen(fn_, 'w+').write(self.serial.dumps(ret))
        return ret_val

    def _state_run(self):
        '''
        Execute a state run based on information set in the minion config file
        '''
        if self.opts['startup_states']:
            data = {'jid': 'req', 'ret': ''}
            if self.opts['startup_states'] == 'sls':
                data['fun'] = 'state.sls'
                data['arg'] = [self.opts['sls_list']]
            elif self.opts['startup_states'] == 'top':
                data['fun'] = 'state.top'
                data['arg'] = [self.opts['top_file']]
            else:
                data['fun'] = 'state.highstate'
                data['arg'] = []
            self._handle_decoded_payload(data)

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
        log.debug(
            'Attempting to authenticate with the Salt Master at {0}'.format(
                self.opts['master_ip']
            )
        )
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
            with salt.utils.fopen(fn_, 'r+') as ifile:
                data = ifile.read()
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

    def cleanup_processes(self):
        for process in self.__processing[:]:
            if process.is_alive():
                continue
            process.join(0.025)
            if isinstance(process, multiprocessing.Process):
                process.terminate()
            self.__processing.pop(self.__processing.index(process))
            del(process)

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        log.info(
            '{0} is starting as user \'{1}\''.format(
                self.__class__.__name__,
                getpass.getuser()
            )
        )
        log.debug('Minion "{0}" trying to tune in'.format(self.opts['id']))
        self.context = zmq.Context()

        # Prepare the minion event system
        #
        # Start with the publish socket
        id_hash = hashlib.md5(self.opts['id']).hexdigest()
        epub_sock_path = os.path.join(
                self.opts['sock_dir'],
                'minion_event_{0}_pub.ipc'.format(id_hash)
                )
        epull_sock_path = os.path.join(
                self.opts['sock_dir'],
                'minion_event_{0}_pull.ipc'.format(id_hash)
                )
        self.epub_sock = self.context.socket(zmq.PUB)
        if self.opts.get('ipc_mode', '') == 'tcp':
            epub_uri = 'tcp://127.0.0.1:{0}'.format(
                    self.opts['tcp_pub_port']
                    )
            epull_uri = 'tcp://127.0.0.1:{0}'.format(
                    self.opts['tcp_pull_port']
                    )
        else:
            epub_uri = 'ipc://{0}'.format(epub_sock_path)
            epull_uri = 'ipc://{0}'.format(epull_sock_path)
            for uri in (epub_uri, epull_uri):
                if uri.startswith('tcp://'):
                    # This check only applies to IPC sockets
                    continue
                # The socket path is limited to 107 characters on Solaris and
                # Linux, and 103 characters on BSD-based systems.
                # Let's fail at the lower level so no system checks are
                # required.
                if len(uri) > 103:
                    raise SaltSystemExit(
                        'The socket path length is more that what ZMQ allows. '
                        'The length of {0!r} is more than 103 characters. '
                        'Either try to reduce the length of this setting\'s '
                        'path or switch to TCP; In the configuration file set '
                        '"ipc_mode: tcp"'.format(
                            uri
                        )
                    )
        log.debug(
            '{0} PUB socket URI: {1}'.format(
                self.__class__.__name__, epub_uri
            )
        )
        log.debug(
            '{0} PULL socket URI: {1}'.format(
                self.__class__.__name__, epull_uri
            )
        )

        # Create the pull socket
        self.epull_sock = self.context.socket(zmq.PULL)
        # Bind the event sockets
        self.epub_sock.bind(epub_uri)
        self.epull_sock.bind(epull_uri)
        # Restrict access to the sockets
        if not self.opts.get('ipc_mode', '') == 'tcp':
            os.chmod(
                    epub_sock_path,
                    448
                    )
            os.chmod(
                    epull_sock_path,
                    448
                    )

        self.poller = zmq.Poller()
        self.epoller = zmq.Poller()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, '')
        self.socket.setsockopt(zmq.IDENTITY, self.opts['id'])
        if hasattr(zmq, 'RECONNECT_IVL_MAX'):
            self.socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, self.opts['recon_max']
            )
        if hasattr(zmq, 'TCP_KEEPALIVE'):
            self.socket.setsockopt(
                zmq.TCP_KEEPALIVE, self.opts['tcp_keepalive']
            )
            self.socket.setsockopt(
                zmq.TCP_KEEPALIVE_IDLE, self.opts['tcp_keepalive_idle']
            )
            self.socket.setsockopt(
                zmq.TCP_KEEPALIVE_CNT, self.opts['tcp_keepalive_cnt']
            )
            self.socket.setsockopt(
                zmq.TCP_KEEPALIVE_INTVL, self.opts['tcp_keepalive_intvl']
            )
        self.socket.connect(self.master_pub)
        self.poller.register(self.socket, zmq.POLLIN)
        self.epoller.register(self.epull_sock, zmq.POLLIN)
        # Send an event to the master that the minion is live
        self._fire_master(
                'Minion {0} started at {1}'.format(
                    self.opts['id'],
                    time.asctime()
                    ),
                'minion_start'
                )

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        # On first startup execute a state run if configured to do so
        self._state_run()

        while True:
            try:
                socks = dict(self.poller.poll(60000))
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    payload = self.serial.loads(self.socket.recv())
                    self._handle_payload(payload)
                time.sleep(0.05)
                # This next call(multiprocessing.active_children()) is
                # intentional, from docs, "Calling this has the side affect of
                # “joining” any processes which have already finished."
                multiprocessing.active_children()
                self.passive_refresh()
                self.cleanup_processes()
                # Check the event system
                if self.epoller.poll(1):
                    try:
                        package = self.epull_sock.recv(zmq.NOBLOCK)
                        self.epub_sock.send(package)
                    except Exception:
                        pass
            except Exception:
                log.critical(traceback.format_exc())

    def destroy(self):
        if hasattr(self, 'poller'):
            for socket in self.poller.sockets.keys():
                if socket.closed is False:
                    socket.close()
                self.poller.unregister(socket)
        if hasattr(self, 'epoller'):
            for socket in self.epoller.sockets.keys():
                if socket.closed is False:
                    socket.close()
                self.epoller.unregister(socket)
        if hasattr(self, 'epub_sock') and self.epub_sock.closed is False:
            self.epub_sock.close()
        if hasattr(self, 'epull_sock') and self.epull_sock.closed is False:
            self.epull_sock.close()
        if hasattr(self, 'socket') and self.socket.closed is False:
            self.socket.close()
        if hasattr(self, 'context') and self.context.closed is False:
            self.context.term()

    def __del__(self):
        self.destroy()


class Syndic(Minion):
    '''
    Make a Syndic minion, this minion will use the minion keys on the
    master to authenticate with a higher level master.
    '''
    def __init__(self, opts):
        self._syndic = True
        Minion.__init__(self, opts)
        self.local = salt.client.LocalClient(opts['_master_conf_file'])
        opts.update(self.opts)
        self.opts = opts

    def _handle_aes(self, load):
        '''
        Takes the aes encrypted load, decrypts is and runs the encapsulated
        instructions
        '''
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
            log.debug(
                'User {0[user]} Executing syndic command {0[fun]} with '
                'jid {0[jid]}'.format(
                    data
                )
            )
        else:
            log.debug(
                'Executing syndic command {0[fun]} with jid {0[jid]}'.format(
                    data
                )
            )
        log.debug('Command details: {0}'.format(data))
        self._handle_decoded_payload(data)

    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle the decoded data
        differently.
        '''
        if self.opts['multiprocessing']:
            multiprocessing.Process(
                target=self.syndic_cmd, args=(data,)
            ).start()
        else:
            threading.Thread(
                target=self.syndic_cmd, args=(data,)
            ).start()

    def syndic_cmd(self, data):
        '''
        Take the now clear load and forward it on to the client cmd
        '''
        # Set up default tgt_type
        if 'tgt_type' not in data:
            data['tgt_type'] = 'glob'
        # Send out the publication
        pub_data = self.local.pub(
                data['tgt'],
                data['fun'],
                data['arg'],
                data['tgt_type'],
                data['ret'],
                data['jid'],
                data['to']
                )
        # Gather the return data
        ret = self.local.get_full_returns(
                pub_data['jid'],
                pub_data['minions'],
                data['to']
                )
        for minion in ret:
            ret[minion] = ret[minion]['ret']
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
        if functions is None:
            functions = salt.loader.minion_mods(self.opts)
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
            funcname = '{0}_match'.format(matcher)
            if matcher == 'nodegroup':
                return getattr(self, funcname)(match, nodegroups)
            return getattr(self, funcname)(match)
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

    def data_match(self, tgt):
        '''
        Match based on the local data store on the minion
        '''
        comps = tgt.split(':')
        if len(comps) < 2:
            return False
        val = self.functions['data.getval'](comps[0])
        if val is None:
            # The value is not defined
            return False
        if isinstance(val, list):
            # We are matching a single component to a single list member
            for member in val:
                if fnmatch.fnmatch(str(member).lower(), comps[1].lower()):
                    return True
            return False
        return bool(fnmatch.fnmatch(
            val,
            comps[1],
            ))

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
            log.error(
                'Got insufficient arguments for pillar match statement '
                'from master'
            )
            return False
        if comps[0] not in self.opts['pillar']:
            log.error(
                'Got unknown pillar match statement from master: {0}'.format(
                    comps[0]
                )
            )
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

    def ipcidr_match(self, tgt):
        '''
        Matches based on ip address or CIDR notation
        '''
        num_parts = len(tgt.split('/'))
        if num_parts > 2:
            return False
        elif num_parts == 2:
            return self.functions['network.in_subnet'](tgt)
        else:
            import socket
            try:
                socket.inet_aton(tgt)
            except socket.error:
                # Not a valid IPv4 address
                return False
            else:
                return tgt in self.functions['network.ip_addrs']()

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
               'S': 'ipcidr',
               'E': 'pcre'}
        results = []
        opers = ['and', 'or', 'not', '(', ')']
        tokens = re.findall(r'[^\s()]+|[()]', tgt)
        for match in tokens:
            # Try to match tokens from the compound target, first by using
            # the 'G, X, I, L, S, E' matcher types, then by hostname glob.
            if '@' in match and match[1] == '@':
                comps = match.split('@')
                matcher = ref.get(comps[0])
                if not matcher:
                    # If an unknown matcher is called at any time, fail out
                    return False
                results.append(
                    str(
                        getattr(self, '{0}_match'.format(matcher))(
                            '@'.join(comps[1:])
                        )
                    )
                )
            elif match in opers:
                # We didn't match a target, so append a boolean operator or subexpression
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
            return self.compound_match(
                    salt.utils.minions.nodegroup_comp(tgt, nodegroups)
                    )
        return False
