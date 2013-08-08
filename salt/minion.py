# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
import logging
import getpass
import multiprocessing
import fnmatch
import copy
import os
import hashlib
import re
import threading
import time
import traceback
import sys
import signal
from random import randint

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
# 4. Store the AES key
# 5. Connect to the publisher
# 6. Handle publications


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
            ret['master_ip'] = \
                    salt.utils.dns_check(opts['master'], True, opts['ipv6'])
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
                            opts['master'], True, opts['ipv6']
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
    Given the cache directory, return the directory that process data is
    stored in, creating it if it doesn't exist.
    '''
    fn_ = os.path.join(cachedir, 'proc')
    if not os.path.isdir(fn_):
        # proc_dir is not present, create it
        os.makedirs(fn_)
    return fn_


def parse_args_and_kwargs(func, args, data=None):
    '''
    Detect the args and kwargs that need to be passed to a function call,
    and yamlify all arguments and key-word argument values if:
    - they are strings
    - they do not contain '\n'
    If yamlify results in a dict, and the original argument or kwarg value
    did not start with a "{", then keep the original string value.
    This is to prevent things like 'echo "Hello: world"' to be parsed as
    dictionaries.
    '''
    spec_args, _, has_kwargs, _ = salt.state._getargs(func)
    _args = []
    kwargs = {}
    for arg in args:
        if isinstance(arg, string_types):
            arg_name, arg_value = salt.utils.parse_kwarg(arg)
            if arg_name:
                if has_kwargs or arg_name in spec_args:
                    kwargs[arg_name] = yamlify_arg(arg_value)
                    continue
            else:
                # Not a kwarg
                pass
        _args.append(yamlify_arg(arg))
    if has_kwargs and isinstance(data, dict):
        # this function accepts kwargs, pack in the publish data
        for key, val in data.items():
            kwargs['__pub_{0}'.format(key)] = val
    return _args, kwargs


def yamlify_arg(arg):
    '''
    yaml.safe_load the arg unless it has a newline in it.
    '''
    try:
        original_arg = arg
        if isinstance(arg, string_types):
            if '\n' not in arg:
                arg = yaml.safe_load(arg)
        if isinstance(arg, dict):
            # dicts must be wrapped in curly braces
            if (isinstance(original_arg, string_types) and
                not original_arg.startswith("{")):
                return original_arg
            else:
                return arg
        elif isinstance(arg, (int, list, string_types)):
            return arg
        else:
            # we don't support this type
            return str(original_arg)
    except Exception:
        # In case anything goes wrong...
        return str(original_arg)


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
            if isinstance(self.opts['master'], list):
                masters = self.opts['master']
                self.opts['_auth_timeout'] = 3
                self.opts['_safe_auth'] = False
                for master in masters:
                    self.opts['master'] = master
                    self.opts.update(resolve_dns(opts))
                    try:
                        self.gen_modules()
                        break
                    except SaltClientError:
                        log.warning(('Attempted to authenticate with master '
                                     '{0} and failed'.format(master)))
                        continue
            else:
                self.opts.update(resolve_dns(opts))
                self.gen_modules()
        else:
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


class MultiMinion(object):
    '''
    Create a multi minion interface, this creates as many minions as are
    defined in the master option and binds each minion object to a respective
    master.
    '''
    def __init__(self, opts):
        self.opts = opts

    def _gen_minions(self):
        '''
        Set up and tune in the minion options
        '''
        if not isinstance(self.opts['master'], list):
            log.error(
                'Attempting to start a multimaster system with one master')
            return False
        minions = []
        for master in set(self.opts['master']):
            s_opts = copy.copy(self.opts)
            s_opts['master'] = master
            try:
                minions.append(Minion(s_opts, 5, False))
            except SaltClientError:
                minions.append(s_opts)
        return minions

    def minions(self):
        '''
        Return a list of minion generators bound to the tune_in method
        '''
        ret = {}
        minions = self._gen_minions()
        for minion in minions:
            if isinstance(minion, dict):
                ret[minion['master']] = minion
            else:
                ret[minion.opts['master']] = {
                    'minion': minion,
                    'generator': minion.tune_in_no_block()}
        return ret

    # Multi Master Tune In
    def tune_in(self):
        '''
        Bind to the masters
        '''
        # Prepare the minion event system
        #
        # Start with the publish socket
        self.context = zmq.Context()
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
        if self.opts.get('ipc_mode', '') != 'tcp':
            os.chmod(
                epub_sock_path,
                448
            )
            os.chmod(
                epull_sock_path,
                448
            )

        self.epoller = zmq.Poller()
        module_refresh = False
        pillar_refresh = False

        # Prepare the minion generators
        minions = self.minions()
        loop_interval = int(self.opts['loop_interval'])
        last = time.time()
        auth_wait = self.opts['acceptance_wait_time']
        max_wait = auth_wait * 6

        while True:
            for minion in minions.values():
                if isinstance(minion, dict):
                    continue
                if not hasattr(minion, 'schedule'):
                    continue
                try:
                    minion.schedule.eval()
                    # Check if scheduler requires lower loop interval than
                    # the loop_interval setting
                    if minion.schedule.loop_interval < loop_interval:
                        loop_interval = minion.schedule.loop_interval
                        log.debug(
                            'Overriding loop_interval because of scheduled jobs.'
                        )
                except Exception as exc:
                    log.error(
                        'Exception {0} occurred in scheduled job'.format(exc)
                    )
                break
            if self.epoller.poll(1):
                try:
                    while True:
                        package = self.epull_sock.recv(zmq.NOBLOCK)
                        if package.startswith('module_refresh'):
                            module_refresh = True
                        elif package.startswith('pillar_refresh'):
                            pillar_refresh = True
                        self.epub_sock.send(package)
                except Exception:
                    pass
            # get commands from each master
            for master, minion in minions.items():
                if 'generator' not in minion:
                    if time.time() - auth_wait > last:
                        last = time.time()
                        if auth_wait < max_wait:
                            auth_wait += auth_wait
                        try:
                            if not isinstance(minion, dict):
                                minions[master] = {'minion': minion}
                            t_minion = Minion(minion, 1, False)
                            minions[master]['minion'] = t_minion
                            minions[master]['generator'] = t_minion.tune_in_no_block()
                            auth_wait = self.opts['acceptance_wait_time']
                        except SaltClientError:
                            continue
                    else:
                        continue
                if module_refresh:
                    minion['minion'].module_refresh()
                if pillar_refresh:
                    minion['minion'].pillar_refresh()
                minion['generator'].next()


class Minion(object):
    '''
    This class instantiates a minion, runs connections for a minion,
    and loads all of the functions into the minion
    '''
    def __init__(self, opts, timeout=60, safe=True):
        '''
        Pass in the options dict
        '''
        # Late setup the of the opts grains, so we can log from the grains
        # module
        opts['grains'] = salt.loader.grains(opts)
        opts.update(resolve_dns(opts))
        self.opts = opts
        self.authenticate(timeout, safe)
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

    def _fire_master(self, data=None, tag=None, events=None):
        '''
        Fire an event on the master
        '''
        load = {'id': self.opts['id'],
                'cmd': '_minion_event'}
        if events:
            load['events'] = events
        elif data and tag:
            load['data'] = data
            load['tag'] = tag
        else:
            return
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        try:
            sreq.send('aes', self.crypticle.dumps(load))
        except Exception:
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
        Takes the AES encrypted load, decrypts it, and runs the encapsulated
        instructions
        '''
        try:
            data = self.crypticle.loads(load)
        except AuthenticationError:
            # decryption of the payload failed, try to re-auth but wait
            # random seconds if set in config with random_reauth_delay
            if 'random_reauth_delay' in self.opts:
                reauth_delay = randint(0, int(self.opts['random_reauth_delay']))
                log.debug("Waiting {0} seconds to re-authenticate".format(reauth_delay))
                time.sleep(reauth_delay)

            self.authenticate()
            data = self.crypticle.loads(load)
        # Verify that the publication is valid
        if 'tgt' not in data or 'jid' not in data or 'fun' not in data \
           or 'arg' not in data:
            return
        # Verify that the publication applies to this minion
        if 'tgt_type' in data:
            match_func = getattr(self.matcher,
                                 '{0}_match'.format(data['tgt_type']), None)
            if match_func is None or not match_func(data['tgt']):
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
            log.info(
                'User {0[user]} Executing command {0[fun]} with jid '
                '{0[jid]}'.format(data)
            )
        else:
            log.info(
                'Executing command {0[fun]} with jid {0[jid]}'.format(data)
            )
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
    def _thread_return(cls, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        # this seems awkward at first, but it's a workaround for Windows
        # multiprocessing communication.
        if not minion_instance:
            minion_instance = cls(opts)
        if opts['multiprocessing']:
            fn_ = os.path.join(minion_instance.proc_dir, data['jid'])
            salt.utils.daemonize_if(opts)
            sdata = {'pid': os.getpid()}
            sdata.update(data)
            with salt.utils.fopen(fn_, 'w+') as fp_:
                fp_.write(minion_instance.serial.dumps(sdata))
        ret = {}
        function_name = data['fun']
        if function_name in minion_instance.functions:
            ret['success'] = False
            try:
                func = minion_instance.functions[data['fun']]
                args, kwargs = parse_args_and_kwargs(func, data['arg'], data)
                sys.modules[func.__module__].__context__['retcode'] = 0
                ret['return'] = func(*args, **kwargs)
                ret['retcode'] = sys.modules[func.__module__].__context__.get(
                    'retcode',
                    0
                )
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
                trb = traceback.format_exc()
                aspec = _getargs(minion_instance.functions[data['fun']])
                msg =('TypeError encountered executing {0}: {1}. See '
                      'debug log for more info.  Possibly a missing '
                      'arguments issue:  {2}').format(function_name, exc,
                                                      aspec)
                log.warning(msg)
                log.debug(
                    'TypeError intercepted: {0}\n{1}'.format(exc, trb),
                    exc_info=True
                )
                ret['return'] = msg
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
    def _thread_multi_return(cls, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        # this seems awkward at first, but it's a workaround for Windows
        # multiprocessing communication.
        if not minion_instance:
            minion_instance = cls(opts)
        ret = {
            'return': {},
            'success': {},
        }
        for ind in range(0, len(data['fun'])):
            ret['success'][data['fun'][ind]] = False
            try:
                func = minion_instance.functions[data['fun'][ind]]
                args, kwargs = parse_args_and_kwargs(func, data['arg'][ind], data)
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
        jid = ret.get('jid', ret.get('__jid__'))
        fun = ret.get('fun', ret.get('__fun__'))
        if self.opts['multiprocessing']:
            fn_ = os.path.join(self.proc_dir, jid)
            if os.path.isfile(fn_):
                try:
                    os.remove(fn_)
                except (OSError, IOError):
                    # The file is gone already
                    pass
        log.info('Returning information for job: {0}'.format(jid))
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        if ret_cmd == '_syndic_return':
            load = {'cmd': ret_cmd,
                    'id': self.opts['id'],
                    'jid': jid,
                    'fun': fun,
                    'load': ret.get('__load__')}
            load['return'] = {}
            for key, value in ret.items():
                if key.startswith('__'):
                    continue
                load['return'][key] = value
        else:
            load = {'cmd': ret_cmd,
                    'id': self.opts['id']}
            for key, value in ret.items():
                load[key] = value
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
        '''
        Return the master publish port
        '''
        return 'tcp://{ip}:{port}'.format(ip=self.opts['master_ip'],
                                          port=self.publish_port)

    def authenticate(self, timeout=60, safe=True):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master AES key.
        '''
        log.debug(
            'Attempting to authenticate with the Salt Master at {0}'.format(
                self.opts['master_ip']
            )
        )
        auth = salt.crypt.Auth(self.opts)
        acceptance_wait_time = self.opts['acceptance_wait_time']
        acceptance_wait_time_max = self.opts['acceptance_wait_time_max']
        if not acceptance_wait_time_max:
            acceptance_wait_time_max = acceptance_wait_time
        while True:
            creds = auth.sign_in(timeout, safe)
            if creds != 'retry':
                log.info('Authentication with master successful!')
                break
            log.info('Waiting for minion key to be accepted by the master.')
            time.sleep(acceptance_wait_time)
            if acceptance_wait_time < acceptance_wait_time_max:
                acceptance_wait_time += acceptance_wait_time
                log.debug('Authentication wait time is {0}'.format(acceptance_wait_time))
        self.aes = creds['aes']
        self.publish_port = creds['publish_port']
        self.crypticle = salt.crypt.Crypticle(self.opts, self.aes)

    def module_refresh(self):
        '''
        Refresh the functions and returners.
        '''
        self.functions, self.returners = self.__load_modules()
        self.schedule.functions = self.functions
        self.schedule.returners = self.returners

    def pillar_refresh(self):
        '''
        Refresh the pillar
        '''
        self.opts['pillar'] = salt.pillar.get_pillar(
            self.opts,
            self.opts['grains'],
            self.opts['id'],
            self.opts['environment'],
        ).compile_pillar()
        self.module_refresh()

    def clean_die(self, signum, frame):
        '''
        Python does not handle the SIGTERM cleanly, if it is signaled exit
        the minion process cleanly
        '''
        exit(0)

    # Main Minion Tune In
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
        except Exception as err:
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
        if self.opts.get('ipc_mode', '') != 'tcp':
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

        recon_delay = self.opts['recon_default']

        if self.opts['recon_randomize']:
            recon_delay = randint(self.opts['recon_default'],
                                  self.opts['recon_default'] + self.opts['recon_max']
                          )

            log.debug("Generated random reconnect delay between '{0}ms' and '{1}ms' ({2})".format(
                self.opts['recon_default'],
                self.opts['recon_default'] + self.opts['recon_max'],
                recon_delay)
            )

        log.debug("Setting zmq_reconnect_ivl to '{0}ms'".format(recon_delay))
        self.socket.setsockopt(zmq.RECONNECT_IVL, recon_delay)

        if hasattr(zmq, 'RECONNECT_IVL_MAX'):
            log.debug("Setting zmq_reconnect_ivl_max to '{0}ms'".format(
                self.opts['recon_default'] + self.opts['recon_max'])
            )

            self.socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, self.opts['recon_max']
            )

        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.socket.setsockopt(zmq.IPV4ONLY, 0)

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

        # Make sure to gracefully handle CTRL_LOGOFF_EVENT
        salt.utils.enable_ctrl_logoff_handler()

        # On first startup execute a state run if configured to do so
        self._state_run()
        time.sleep(.5)

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
                # Check the event system
                if self.epoller.poll(1):
                    try:
                        while True:
                            package = self.epull_sock.recv(zmq.NOBLOCK)
                            if package.startswith('module_refresh'):
                                self.module_refresh()
                            elif package.startswith('pillar_refresh'):
                                self.pillar_refresh()
                            self.epub_sock.send(package)
                    except Exception:
                        pass
            except zmq.ZMQError:
                # This is thrown by the interrupt caused by python handling the
                # SIGCHLD. This is a safe error and we just start the poll
                # again
                continue
            except Exception:
                log.critical(
                    'An exception occurred while polling the minion',
                    exc_info=True
                )

    def tune_in_no_block(self):
        '''
        Executes the tune_in sequence but omits extra logging and the
        management of the event bus assuming that these are handled outside
        the tune_in sequence
        '''
        self.context = zmq.Context()
        self.poller = zmq.Poller()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, '')
        self.socket.setsockopt(zmq.IDENTITY, self.opts['id'])
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.socket.setsockopt(zmq.IPV4ONLY, 0)
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
        # Send an event to the master that the minion is live
        self._fire_master(
            'Minion {0} started at {1}'.format(
            self.opts['id'],
            time.asctime()
            ),
            'minion_start'
        )
        loop_interval = int(self.opts['loop_interval'])
        while True:
            try:
                socks = dict(self.poller.poll(
                    loop_interval * 1000)
                )
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    payload = self.serial.loads(self.socket.recv())
                    self._handle_payload(payload)
                # Check the event system
            except zmq.ZMQError:
                # If a zeromq error happens recover
                yield True
            except Exception:
                log.critical(
                    'An exception occurred while polling the minion',
                    exc_info=True
                )
            yield True

    def destroy(self):
        '''
        Tear down the minion
        '''
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
        self._syndic_interface = opts.get('interface')
        self._syndic = True
        opts['loop_interval'] = 1
        Minion.__init__(self, opts)
        opts.update(self.opts)
        self.opts = opts

    def _handle_aes(self, load):
        '''
        Takes the AES encrypted load, decrypts it, and runs the encapsulated
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
        self.syndic_cmd(data)

    def syndic_cmd(self, data):
        '''
        Take the now clear load and forward it on to the client cmd
        '''
        # Set up default tgt_type
        if 'tgt_type' not in data:
            data['tgt_type'] = 'glob'
        # Send out the publication
        self.local.pub(data['tgt'],
                       data['fun'],
                       data['arg'],
                       data['tgt_type'],
                       data['ret'],
                       data['jid'],
                       data['to'])

    # Syndic Tune In
    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the syndic
        '''
        # Instantiate the local client
        self.local = salt.client.LocalClient(self.opts['_master_conf_file'])
        self.local.event.subscribe('')
        self.local.opts['interface'] = self._syndic_interface

        signal.signal(signal.SIGTERM, self.clean_die)
        log.debug('Syndic "{0}" trying to tune in'.format(self.opts['id']))

        self.context = zmq.Context()

        # Start with the publish socket
        self.poller = zmq.Poller()
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
        # Send an event to the master that the minion is live
        self._fire_master(
            'Syndic {0} started at {1}'.format(
            self.opts['id'],
            time.asctime()
            ),
            'syndic_start'
        )

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        loop_interval = int(self.opts['loop_interval'])
        while True:
            try:
                socks = dict(self.poller.poll(
                    loop_interval * 1000)
                )
                if self.socket in socks and socks[self.socket] == zmq.POLLIN:
                    payload = self.serial.loads(self.socket.recv())
                    self._handle_payload(payload)
                time.sleep(0.05)
                jids = {}
                raw_events = []
                while True:
                    event = self.local.event.get_event(0.5, full=True)
                    if event is None:
                        # Timeout reached
                        break
                    if salt.utils.is_jid(event['tag']) and 'return' in event['data']:
                        if not event['tag'] in jids:
                            if not 'jid' in event['data']:
                                # Not a job return
                                continue
                            jids[event['tag']] = {}
                            jids[event['tag']]['__fun__'] = event['data'].get('fun')
                            jids[event['tag']]['__jid__'] = event['data']['jid']
                            jids[event['tag']]['__load__'] = salt.utils.jid_load(
                                event['data']['jid'],
                                self.local.opts['cachedir'],
                                self.opts['hash_type'])
                        jids[event['tag']][event['data']['id']] = event['data']['return']
                    else:
                        # Add generic event aggregation here
                        if not 'retcode' in event['data']:
                            raw_events.append(event)
                if raw_events:
                    self._fire_master(events=raw_events)
                for jid in jids:
                    self._return_pub(jids[jid], '_syndic_return')
            except zmq.ZMQError:
                # This is thrown by the interrupt caused by python handling the
                # SIGCHLD. This is a safe error and we just start the poll
                # again
                continue
            except Exception:
                log.critical(
                    'An exception occurred while polling the syndic',
                    exc_info=True
                )

    def destroy(self):
        '''
        Tear down the syndic minion
        '''
        super(Syndic, self).destroy()
        if hasattr(self, 'local'):
            del self.local


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
            log.error('Received bad data when setting the match from the top '
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
            if comps[1] == '*':
                # We are just checking that the key exists
                return True
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
        if isinstance(self.opts['grains'][comps[0]], dict) and comps[1] == '*':
            # We are just checking that the key exists
            return True
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
            if comps[1] == '*':
                # We are just checking that the key exists
                return True
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
            # Target is not valid CIDR
            return False
        elif num_parts == 2:
            # Target is CIDR
            return salt.utils.network.in_subnet(
                tgt,
                addrs=self.opts['grains'].get('ipv4', [])
            )
        else:
            # Target is an IPv4 address
            import socket
            try:
                socket.inet_aton(tgt)
            except socket.error:
                # Not a valid IPv4 address
                return False
            else:
                return tgt in self.opts['grains'].get('ipv4', [])

    def range_match(self, tgt):
        '''
        Matches based on range cluster
        '''
        if HAS_RANGE:
            range_ = seco.range.Range(self.opts['range_server'])
            try:
                return self.opts['grains']['fqdn'] in range_.expand(tgt)
            except seco.range.RangeException as e:
                log.debug('Range exception in compound match: {0}'.format(e))
                return False
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
                    # seq start with oper, fail
                    if match not in ['(', ')']:
                        return False
            else:
                # The match is not explicitly defined, evaluate it as a glob
                results.append(str(self.glob_match(match)))
        results = ' '.join(results)
        try:
            return eval(results)
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
