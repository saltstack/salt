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
import signal

# Import third party libs
import zmq
import yaml

HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

# Import salt libs
from salt.exceptions import (
    AuthenticationError, CommandExecutionError, CommandNotFoundError,
    SaltInvocationError, SaltReqTimeoutError, SaltClientError
)
import salt.client
import salt.crypt
import salt.loader
import salt.utils
import salt.payload
import salt.utils.schedule
# TODO: should probably use _getargs() from salt.utils?
from salt.state import _getargs
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

def resolve_dns(opts):
    '''
    Resolves the master_ip and master_uri options
    '''
    ret = {}
    check_dns = True
    if opts.get('file_client', 'remote') == 'local' and check_dns:
        check_dns = False

    if check_dns is True:
        # Because I import salt.log below I need to re-import salt.utils here
        import salt.utils
        try:
            ret['master_ip'] = salt.utils.dns_check(opts['master'], True)
        except SaltClientError:
            if opts['retry_dns']:
                while True:
                    import salt.log
                    msg = ('Master hostname: {0} not found. Retrying in {1} '
                           'seconds').format(opts['master'], opts['retry_dns'])
                    if salt.log.is_console_configured():
                        log.warn(msg)
                    else:
                        print('WARNING: {0}'.format(msg))
                    time.sleep(opts['retry_dns'])
                    try:
                        ret['master_ip'] = salt.utils.dns_check(
                            opts['master'], True
                        )
                        break
                    except SaltClientError:
                        pass
            else:
                ret['master_ip'] = '127.0.0.1'
    else:
        ret['master_ip'] = '127.0.0.1'

    ret['master_uri'] = 'tcp://{ip}:{port}'.format(ip=ret['master_ip'],
                                                    port=opts['master_port'])
    return ret


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
        if self.opts.get('file_client', 'remote') == 'remote':
            self.opts.update(resolve_dns(opts))
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
        opts.update(resolve_dns(opts))
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
        self.schedule = salt.utils.schedule.Schedule(
            self.opts,
            self.functions,
            self.returners)

    def __prep_mod_opts(self):
        '''
        Returns a copy of the opts with key bits stripped out
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
                self.schedule.functions = self.functions
                self.schedule.returners = self.returners
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
        process.start()
        process.join()

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
            salt.utils.daemonize_if(opts, **data)
            sdata = {'pid': os.getpid()}
            sdata.update(data)
            with salt.utils.fopen(fn_, 'w+') as fp_:
                fp_.write(minion_instance.serial.dumps(sdata))
        ret = {}
        for ind in range(0, len(data['arg'])):
            try:
                arg = data['arg'][ind]
                if '\n' not in arg:
                    arg = yaml.safe_load(arg)
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
            except TypeError as exc:
                aspec = _getargs(minion_instance.functions[data['fun']])
                msg = 'Missing arguments executing "{0}": {1}'
                log.warning(msg.format(function_name, aspec))
                ret['return'] = msg.format(function_name, aspec)
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
                    arg = data['arg'][ind][index]
                    if '\n' not in arg:
                        arg = yaml.safe_load(arg)
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
            self.schedule.functions = self.functions
            self.schedule.returners = self.returners

    def clean_die(self, signum, frame):
        '''
        Python does not handle the SIGTERM cleanly, if it is signaled exit
        the minion process cleanly
        '''
        exit(0)

    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        '''
        try:
            log.info(
                '{0} is starting as user \'{1}\''.format(
                    self.__class__.__name__,
                    getpass.getuser()
                )
            )
        except Exception, err:
            # Only windows is allowed to fail here. See #3189. Log as debug in
            # that case. Else, error.
            log.log(
                salt.utils.is_windows() and logging.DEBUG or logging.ERROR,
                'Failed to get the user who is starting {0}'.format(
                    self.__class__.__name__
                ),
                exc_info=err
            )
        signal.signal(signal.SIGTERM, self.clean_die)
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
            salt.utils.check_ipc_path_max_len(epub_uri)
            epull_uri = 'ipc://{0}'.format(epull_sock_path)
            salt.utils.check_ipc_path_max_len(epull_uri)
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

        loop_interval = int(self.opts['loop_interval'])
        while True:
            try:
                self.schedule.eval()
                # Check if scheduler requires lower loop interval than
                # the loop_interval setting
                if self.schedule.loop_interval < loop_interval:
                    loop_interval = self.schedule.loop_interval
                    log.debug(
                        'Overriding loop_interval because of scheduled jobs.'
                    )
            except Exception as exc:
                log.error(
                    'Exception {0} occurred in scheduled job'.format(exc)
                )
            try:
                socks = dict(self.poller.poll(
                    loop_interval * 1000)
                )
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    payload = self.serial.loads(self.socket.recv())
                    self._handle_payload(payload)
                time.sleep(0.05)
                # Clean up the minion processes which have been executed and
                # have finished
                # Check if modules and grains need to be refreshed
                self.passive_refresh()
                # Check the event system
                if self.epoller.poll(1):
                    try:
                        package = self.epull_sock.recv(zmq.NOBLOCK)
                        self.epub_sock.send(package)
                    except Exception:
                        pass
            except zmq.ZMQError:
                # This is thrown by the inturupt caused by python handling the
                # SIGCHLD. This is a safe error and we just start the poll
                # again
                continue
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
        interface = opts.get('interface')
        self._syndic = True
        Minion.__init__(self, opts)
        self.local = salt.client.LocalClient(opts['_master_conf_file'])
        opts.update(self.opts)
        self.opts = opts
        self.local.opts['interface'] = interface

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
        log.debug('grains target: {0}'.format(tgt))
        comps = tgt.rsplit(':', 1)
        if len(comps) != 2:
            log.error('Got insufficient arguments for grains match '
                      'statement from master')
            return False
        match = salt.utils.traverse_dict(self.opts['grains'], comps[0], {})
        if match == {}:
            log.error('Targeted grain "{0}" not found'.format(comps[0]))
            return False
        if isinstance(match, dict):
            log.error('Targeted grain "{0}" must correspond to a list, '
                      'string, or numeric value'.format(comps[0]))
            return False
        if isinstance(match, list):
            # We are matching a single component to a single list member
            for member in match:
                if fnmatch.fnmatch(str(member).lower(), comps[1].lower()):
                    return True
            return False
        return bool(fnmatch.fnmatch(str(match).lower(), comps[1].lower()))

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
        if isinstance(val, dict):
            if comps[1] in val:
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
        log.debug('pillar target: {0}'.format(tgt))
        comps = tgt.rsplit(':', 1)
        if len(comps) != 2:
            log.error('Got insufficient arguments for pillar match '
                      'statement from master')
            return False
        match = salt.utils.traverse_dict(self.opts['pillar'], comps[0], {})
        if match == {}:
            log.error('Targeted pillar "{0}" not found'.format(comps[0]))
            return False
        if isinstance(match, dict):
            log.error('Targeted pillar "{0}" must correspond to a list, '
                      'string, or numeric value'.format(comps[0]))
            return False
        if isinstance(match, list):
            # We are matching a single component to a single list member
            for member in match:
                if fnmatch.fnmatch(str(member).lower(), comps[1].lower()):
                    return True
            return False
        return bool(fnmatch.fnmatch(str(match).lower(), comps[1].lower()))

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

    def range_match(self, tgt):
        '''
        Matches based on range cluster
        '''
        if HAS_RANGE:
            range = seco.range.Range(self.opts['range_server'])
            return self.opts['grains']['fqdn'] in range.expand(tgt)
        return

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
               'E': 'pcre',
               'D': 'data'}
        if HAS_RANGE:
            ref['R'] = 'range'
        results = []
        opers = ['and', 'or', 'not', '(', ')']
        tokens = tgt.split()
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
                # We didn't match a target, so append a boolean operator or
                # subexpression
                if results:
                    if match == 'not':
                        if results[-1] == 'and':
                            pass
                        elif results[-1] == 'or':
                            pass
                        else:
                            results.append('and')
                    results.append(match)
            else:
                # The match is not explicitly defined, evaluate it as a glob
                results.append(str(self.glob_match(match)))
        try:
            return eval(' '.join(results))
        except Exception:
            log.error('Invalid compound target: {0}'.format(tgt))
            return False
        return False

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
