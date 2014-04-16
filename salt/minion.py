# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
from __future__ import print_function
import logging
import multiprocessing
import fnmatch
import copy
import os
import hashlib
import re
import types
import threading
import time
import traceback
import sys
import signal
import errno
from random import randint
import salt

# Import third party libs
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    # Running in local, zmq not needed
    HAS_ZMQ = False
import yaml

HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

HAS_RESOURCE = False
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    pass

# Import salt libs
from salt.exceptions import (
    AuthenticationError, CommandExecutionError, CommandNotFoundError,
    SaltInvocationError, SaltReqTimeoutError, SaltClientError, SaltSystemExit
)
import salt.client
import salt.crypt
import salt.loader
import salt.utils
import salt.payload
import salt.utils.schedule
import salt.utils.event

from salt._compat import string_types
from salt.utils.debug import enable_sigusr1_handler
from salt.utils.event import tagify
import salt.syspaths

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
        except SaltSystemExit:
            err = 'Master address: {0} could not be resolved. Invalid or unresolveable address.'.format(
                opts.get('master', 'Unknown'))
            log.error(err)
            raise SaltSystemExit(code=42, msg=err)
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
    argspec = salt.utils.get_function_argspec(func)
    _args = []
    kwargs = {}
    invalid_kwargs = []

    for arg in args:
        if isinstance(arg, string_types):
            arg_name, arg_value = salt.utils.parse_kwarg(arg)
            if arg_name:
                if argspec.keywords or arg_name in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    kwargs[arg_name] = yamlify_arg(arg_value)
                    continue

                # **kwargs not in argspec and parsed argument name not in
                # list of positional arguments. This keyword argument is
                # invalid.
                invalid_kwargs.append(arg)

        # if the arg is a dict with __kwarg__ == True, then its a kwarg
        elif isinstance(arg, dict) and arg.get('__kwarg__') is True:
            for key, val in arg.iteritems():
                if key == '__kwarg__':
                    continue
                if isinstance(val, string_types):
                    kwargs[key] = yamlify_arg(val)
                else:
                    kwargs[key] = val
            continue
        _args.append(yamlify_arg(arg))
    if argspec.keywords and isinstance(data, dict):
        # this function accepts **kwargs, pack in the publish data
        for key, val in data.items():
            kwargs['__pub_{0}'.format(key)] = val

    if invalid_kwargs:
        raise SaltInvocationError(
            'The following keyword arguments are not valid: {0}'
            .format(', '.join(invalid_kwargs))
        )
    return _args, kwargs


def yamlify_arg(arg):
    '''
    yaml.safe_load the arg unless it has a newline in it.
    '''
    if not isinstance(arg, string_types):
        return arg
    try:
        # Explicit late import to avoid circular import. DO NOT MOVE THIS.
        import salt.utils.yamlloader as yamlloader
        original_arg = arg
        if '#' in arg:
            # Don't yamlify this argument or the '#' and everything after
            # it will be interpreted as a comment.
            return arg
        if arg == 'None':
            arg = None
        elif '\n' not in arg:
            arg = yamlloader.load(arg, Loader=yamlloader.CustomLoader)

        if isinstance(arg, dict):
            # dicts must be wrapped in curly braces
            if not original_arg.startswith('{'):
                return original_arg
            else:
                return arg

        elif arg is None or isinstance(arg, (int, list, float, string_types)):
            # yaml.safe_load will load '|' as '', don't let it do that.
            if arg == '' and original_arg in ('|',):
                return original_arg
            # yaml.safe_load will treat '#' as a comment, so a value of '#'
            # will become None. Keep this value from being stomped as well.
            elif arg is None and original_arg.strip().startswith('#'):
                return original_arg
            elif arg is None and original_arg.strip() == '':
                # Because YAML loads empty strings as None, we return the original string
                # >>> import yaml
                # >>> yaml.load('') is None
                # True
                # >>> yaml.load('      ') is None
                # True
                return original_arg
            else:
                return arg
        else:
            # we don't support this type
            return original_arg
    except Exception:
        # In case anything goes wrong...
        return original_arg


class SMinion(object):
    '''
    Create an object that has loaded all of the minion module functions,
    grains, modules, returners etc.  The SMinion allows developers to
    generate all of the salt minion functions and present them with these
    functions for general use.
    '''
    def __init__(self, opts):
        # Late setup of the opts grains, so we can log from the grains module
        opts['grains'] = salt.loader.grains(opts)
        self.opts = opts

        # Clean out the proc directory (default /var/cache/salt/minion/proc)
        if self.opts.get('file_client', 'remote') == 'remote':
            if isinstance(self.opts['master'], list):
                masters = self.opts['master']
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
        self.opts = salt.config.minion_config(opts['conf_file'])
        self.opts.update(opts)
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
        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        id_hash = hash_type(self.opts['id']).hexdigest()
        if self.opts.get('hash_type', 'md5') == 'sha256':
            id_hash = id_hash[:10]
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
                        elif package.startswith('fire_master'):
                            tag, data = salt.utils.event.MinionEvent.unpack(package)
                            log.debug("Forwarding master event tag={tag}".format(tag=data['tag']))
                            self._fire_master(data['data'], data['tag'], data['events'], data['pretag'])

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
                            t_minion = Minion(minion, 5, False)
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
        self._running = None

        # Warn if ZMQ < 3.2
        if HAS_ZMQ and (not(hasattr(zmq, 'zmq_version_info')) or
                        zmq.zmq_version_info() < (3, 2)):
            # PyZMQ 2.1.9 does not have zmq_version_info
            log.warning('You have a version of ZMQ less than ZMQ 3.2! There '
                        'are known connection keep-alive issues with ZMQ < '
                        '3.2 which may result in loss of contact with '
                        'minions. Please upgrade your ZMQ!')
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
        self.mod_opts = self._prep_mod_opts()
        self.functions, self.returners = self._load_modules()
        self.matcher = Matcher(self.opts, self.functions)
        self.proc_dir = get_proc_dir(opts['cachedir'])
        self.schedule = salt.utils.schedule.Schedule(
            self.opts,
            self.functions,
            self.returners)

        self.grains_cache = self.opts['grains']

        if 'proxy' in self.opts['pillar']:
            log.debug('I am {0} and I need to start some proxies for {0}'.format(self.opts['id'],
                                                                                 self.opts['pillar']['proxy']))
            for p in self.opts['pillar']['proxy']:
                log.debug('Starting {0} proxy.'.format(p))
                pid = os.fork()
                if pid > 0:
                    continue
                else:
                    proxyminion = salt.ProxyMinion()
                    proxyminion.start(self.opts['pillar']['proxy'][p])
                    self.clean_die(signal.SIGTERM, None)
        else:
            log.debug("I am {0} and I am not supposed to start any proxies.".format(self.opts['id']))

    def _prep_mod_opts(self):
        '''
        Returns a copy of the opts with key bits stripped out
        '''
        mod_opts = {}
        for key, val in self.opts.items():
            if key == 'logger':
                continue
            mod_opts[key] = val
        return mod_opts

    def _load_modules(self):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        # if this is a *nix system AND modules_max_memory is set, lets enforce
        # a memory limit on module imports
        # this feature ONLY works on *nix like OSs (resource module doesn't work on windows)
        modules_max_memory = False
        if self.opts.get('modules_max_memory', -1) > 0 and HAS_PSUTIL and HAS_RESOURCE:
            log.debug('modules_max_memory set, enforcing a maximum of {0}'.format(self.opts['modules_max_memory']))
            modules_max_memory = True
            old_mem_limit = resource.getrlimit(resource.RLIMIT_AS)
            rss, vms = psutil.Process(os.getpid()).get_memory_info()
            mem_limit = rss + vms + self.opts['modules_max_memory']
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        elif self.opts.get('modules_max_memory', -1) > 0:
            if not HAS_PSUTIL:
                log.error('Unable to enforce modules_max_memory because psutil is missing')
            if not HAS_RESOURCE:
                log.error('Unable to enforce modules_max_memory because resource is missing')

        self.opts['grains'] = salt.loader.grains(self.opts)
        functions = salt.loader.minion_mods(self.opts)
        returners = salt.loader.returners(self.opts, functions)

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)

        return functions, returners

    def _fire_master(self, data=None, tag=None, events=None, pretag=None):
        '''
        Fire an event on the master, or drop message if unable to send.
        '''
        load = {'id': self.opts['id'],
                'cmd': '_minion_event',
                'pretag': pretag,
                'tok': self.tok}
        if events:
            load['events'] = events
        elif data and tag:
            load['data'] = data
            load['tag'] = tag
        else:
            return
        sreq = salt.payload.SREQ(self.opts['master_uri'])
        try:
            result = sreq.send('aes', self.crypticle.dumps(load))
            try:
                data = self.crypticle.loads(result)
            except AuthenticationError:
                log.info("AES key changed, re-authenticating")
                # We can't decode the master's response to our event,
                # so we will need to re-authenticate.
                self.authenticate()
        except Exception:
            log.info("fire_master failed: {0}".format(traceback.format_exc()))

    def _handle_payload(self, payload):
        '''
        Takes a payload from the master publisher and does whatever the
        master wants done.
        '''
        {'aes': self._handle_aes,
         'pub': self._handle_pub,
         'clear': self._handle_clear}[payload['enc']](payload['load'],
                                                      payload['sig'] if 'sig' in payload else None)

    def _handle_aes(self, load, sig=None):
        '''
        Takes the AES encrypted load, checks the signature if pub signatures
        are turned on, decrypts it, and runs the encapsulated instructions
        '''
        # Verify that the signature is valid
        master_pubkey_path = os.path.join(self.opts['pki_dir'], 'minion_master.pub')

        if sig and self.functions['config.get']('sign_pub_messages'):
            if not salt.crypt.verify_signature(master_pubkey_path, load, sig):
                raise AuthenticationError('Message signature failed to validate.')

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

        # It's important to note that the master does some pre-processing
        # to determine which minions to send a request to. So for example,
        # a "salt -G 'grain_key:grain_val' test.ping" will invoke some
        # pre-processing on the master and this minion should not see the
        # publication if the master does not determine that it should.

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
                self.functions, self.returners = self._load_modules()
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
                target=target, args=(instance, self.opts, data),
                name=data['jid']
            )
        process.start()
        if not sys.platform.startswith('win'):
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
        fn_ = os.path.join(minion_instance.proc_dir, data['jid'])
        if opts['multiprocessing']:
            salt.utils.daemonize_if(opts)
        sdata = {'pid': os.getpid()}
        sdata.update(data)
        with salt.utils.fopen(fn_, 'w+b') as fp_:
            fp_.write(minion_instance.serial.dumps(sdata))
        ret = {'success': False}
        function_name = data['fun']
        if function_name in minion_instance.functions:
            try:
                func = minion_instance.functions[data['fun']]
                args, kwargs = parse_args_and_kwargs(func, data['arg'], data)
                sys.modules[func.__module__].__context__['retcode'] = 0
                return_data = func(*args, **kwargs)
                if isinstance(return_data, types.GeneratorType):
                    ind = 0
                    iret = {}
                    for single in return_data:
                        if isinstance(single, dict) and isinstance(iret, list):
                            iret.update(single)
                        else:
                            if not iret:
                                iret = []
                            iret.append(single)
                        tag = tagify([data['jid'], 'prog', opts['id'], str(ind)], 'job')
                        event_data = {'return': single}
                        minion_instance._fire_master(event_data, tag)
                        ind += 1
                    ret['return'] = iret
                else:
                    ret['return'] = return_data
                ret['retcode'] = sys.modules[func.__module__].__context__.get(
                    'retcode',
                    0
                )
                ret['success'] = True
            except CommandNotFoundError as exc:
                msg = 'Command required for {0!r} not found'.format(
                    function_name
                )
                log.debug(msg, exc_info=True)
                ret['return'] = '{0}: {1}'.format(msg, exc)
                ret['out'] = 'nested'
            except CommandExecutionError as exc:
                log.error(
                    'A command in {0!r} had a problem: {1}'.format(
                        function_name,
                        exc
                    ),
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
                ret['return'] = 'ERROR: {0}'.format(exc)
                ret['out'] = 'nested'
            except SaltInvocationError as exc:
                log.error(
                    'Problem executing {0!r}: {1}'.format(
                        function_name,
                        exc
                    ),
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
                ret['return'] = 'ERROR executing {0!r}: {1}'.format(
                    function_name, exc
                )
                ret['out'] = 'nested'
            except TypeError as exc:
                trb = traceback.format_exc()
                aspec = salt.utils.get_function_argspec(
                    minion_instance.functions[data['fun']]
                )
                msg = ('TypeError encountered executing {0}: {1}. See '
                       'debug log for more info.  Possibly a missing '
                       'arguments issue:  {2}').format(function_name,
                                                       exc,
                                                       aspec)
                log.warning(msg, exc_info=log.isEnabledFor(logging.DEBUG))
                ret['return'] = msg
                ret['out'] = 'nested'
            except Exception:
                msg = 'The minion function caused an exception'
                log.warning(msg, exc_info=log.isEnabledFor(logging.DEBUG))
                ret['return'] = '{0}: {1}'.format(msg, traceback.format_exc())
                ret['out'] = 'nested'
        else:
            ret['return'] = '{0!r} is not available.'.format(function_name)
            ret['out'] = 'nested'

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        ret['fun_args'] = data['arg']
        minion_instance._return_pub(ret)
        if data['ret']:
            ret['id'] = opts['id']
            for returner in set(data['ret'].split(',')):
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
            ret['fun'] = data['fun']
            ret['fun_args'] = data['arg']
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

        if 'out' in ret:
            if isinstance(ret['out'], string_types):
                load['out'] = ret['out']
            else:
                log.error('Invalid outputter {0}. This is likely a bug.'
                          .format(ret['out']))
        else:
            try:
                oput = self.functions[fun].__outputter__
            except (KeyError, AttributeError, TypeError):
                pass
            else:
                if isinstance(oput, string_types):
                    load['out'] = oput
        try:
            ret_val = sreq.send('aes', self.crypticle.dumps(load))
        except SaltReqTimeoutError:
            msg = ('The minion failed to return the job information for job '
                   '{0}. This is often due to the master being shut down or '
                   'overloaded. If the master is running consider incresing '
                   'the worker_threads value.').format(jid)
            log.warn(msg)
            return ''
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
            salt.utils.fopen(fn_, 'w+b').write(self.serial.dumps(ret))
        return ret_val

    def _state_run(self):
        '''
        Execute a state run based on information set in the minion config file
        '''
        if self.opts['startup_states']:
            data = {'jid': 'req', 'ret': self.opts.get('ext_job_cache', '')}
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

    def _refresh_grains_watcher(self, refresh_interval_in_minutes):
        '''
        Create a loop that will fire a pillar refresh to inform a master about a change in the grains of this minion
        :param refresh_interval_in_minutes:
        :return: None
        '''
        if '__update_grains' not in self.opts.get('schedule', {}):
            if not 'schedule' in self.opts:
                self.opts['schedule'] = {}
            self.opts['schedule'].update({
                '__update_grains':
                    {
                        'function': 'event.fire',
                        'args': [{}, "grains_refresh"],
                        'minutes': refresh_interval_in_minutes
                    }
            })

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
        self.tok = auth.gen_token('salt')
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
        self.functions, self.returners = self._load_modules()
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
        self._running = False
        exit(0)

    def _pre_tune(self):
        '''
        Set the minion running flag and issue the appropriate warnings if
        the minion cannot be started or is already running
        '''
        if self._running is None:
            self._running = True
        elif self._running is False:
            log.error(
                'This {0} was scheduled to stop. Not running '
                '{0}.tune_in()'.format(self.__class__.__name__)
            )
            return
        elif self._running is True:
            log.error(
                'This {0} is already running. Not running '
                '{0}.tune_in()'.format(self.__class__.__name__)
            )
            return

        try:
            log.info(
                '{0} is starting as user \'{1}\''.format(
                    self.__class__.__name__,
                    salt.utils.get_user()
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

    # Main Minion Tune In
    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        :rtype : None
        '''

        self._pre_tune()

        # Properly exit if a SIGTERM is signalled
        signal.signal(signal.SIGTERM, self.clean_die)

        log.debug('Minion {0!r} trying to tune in'.format(self.opts['id']))
        self.context = zmq.Context()

        # Prepare the minion event system
        #
        # Start with the publish socket
        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        id_hash = hash_type(self.opts['id']).hexdigest()
        if self.opts.get('hash_type', 'md5') == 'sha256':
            id_hash = id_hash[:10]
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

        # Check to make sure the sock_dir is available, create if not
        default_minion_sock_dir = os.path.join(
            salt.syspaths.SOCK_DIR,
            'minion'
        )
        minion_sock_dir = self.opts.get('sock_dir', default_minion_sock_dir)

        if not os.path.isdir(minion_sock_dir):
            # Let's try to create the directory defined on the configuration
            # file
            try:
                os.makedirs(minion_sock_dir, 0755)
            except OSError as exc:
                log.error('Could not create SOCK_DIR: {0}'.format(exc))
                # Let's not fail yet and try using the default path
                if minion_sock_dir == default_minion_sock_dir:
                    # We're already trying the default system path, stop now!
                    raise

            if not os.path.isdir(default_minion_sock_dir):
                try:
                    os.makedirs(default_minion_sock_dir, 0755)
                except OSError as exc:
                    log.error('Could not create SOCK_DIR: {0}'.format(exc))
                    # Let's stop at this stage
                    raise

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
        self.poller.register(self.epull_sock, zmq.POLLIN)
        # Send an event to the master that the minion is live
        self._fire_master(
            'Minion {0} started at {1}'.format(
            self.opts['id'],
            time.asctime()
            ),
            'minion_start'
        )
        self._fire_master(
            'Minion {0} started at {1}'.format(
            self.opts['id'],
            time.asctime()
            ),
            tagify([self.opts['id'], 'start'], 'minion'),
        )

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        # Make sure to gracefully handle CTRL_LOGOFF_EVENT
        salt.utils.enable_ctrl_logoff_handler()

        # On first startup execute a state run if configured to do so
        self._state_run()
        time.sleep(.5)

        loop_interval = int(self.opts['loop_interval'])

        try:
            if self.opts['grains_refresh_every']:  # If exists and is not zero. In minutes, not seconds!
                if self.opts['grains_refresh_every'] > 1:
                    log.debug(
                        'Enabling the grains refresher. Will run every {0} minutes.'.format(
                            self.opts['grains_refresh_every'])
                    )
                else:  # Clean up minute vs. minutes in log message
                    log.debug(
                        'Enabling the grains refresher. Will run every {0} minute.'.format(
                            self.opts['grains_refresh_every'])

                    )
                self._refresh_grains_watcher(
                    abs(self.opts['grains_refresh_every'])
                )
        except Exception as exc:
            log.error(
                'Exception occurred in attempt to initialize grain refresh routine during minion tune-in: {0}'.format(
                    exc)
            )

        while self._running is True:
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
                log.trace("Check main poller timeout %s" % loop_interval)
                socks = dict(self.poller.poll(
                    loop_interval * 1000)
                )
                if socks.get(self.socket) == zmq.POLLIN:
                    payload = self.serial.loads(self.socket.recv(zmq.NOBLOCK))
                    log.trace("Handling payload")
                    self._handle_payload(payload)

                # Check the event system
                if socks.get(self.epull_sock) == zmq.POLLIN:
                    package = self.epull_sock.recv(zmq.NOBLOCK)
                    log.debug("Handling event %r", package)
                    try:
                        if package.startswith('module_refresh'):
                            self.module_refresh()
                        elif package.startswith('pillar_refresh'):
                            self.pillar_refresh()
                        elif package.startswith('grains_refresh'):
                            if self.grains_cache != self.opts['grains']:
                                self.pillar_refresh()
                                self.grains_cache = self.opts['grains']
                        elif package.startswith('fire_master'):
                            tag, data = salt.utils.event.MinionEvent.unpack(package)
                            log.debug("Forwarding master event tag={tag}".format(tag=data['tag']))
                            self._fire_master(data['data'], data['tag'], data['events'], data['pretag'])

                        self.epub_sock.send(package)
                    except Exception:
                        log.debug("Exception while handling events", exc_info=True)

            except zmq.ZMQError as exc:
                # The interrupt caused by python handling the
                # SIGCHLD. Throws this error with errno == EINTR.
                # Nothing to recieve on the zmq socket throws this error
                # with EAGAIN.
                # Both are safe to ignore
                if exc.errno != errno.EAGAIN and exc.errno != errno.EINTR:
                    log.critical('Unexpected ZMQError while polling minion',
                                 exc_info=True)
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
        self._pre_tune()
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
        # dup name spaced event
        self._fire_master(
            'Minion {0} started at {1}'.format(
            self.opts['id'],
            time.asctime()
            ),
            tagify([self.opts['id'], 'start'], 'minion'),
        )
        loop_interval = int(self.opts['loop_interval'])
        while self._running is True:
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
        self._running = False
        if hasattr(self, 'poller'):
            if isinstance(self.poller.sockets, dict):
                for socket in self.poller.sockets.keys():
                    if socket.closed is False:
                        socket.close()
                    self.poller.unregister(socket)
            else:
                for socket in self.poller.sockets:
                    if socket[0].closed is False:
                        socket[0].close()
                    self.poller.unregister(socket[0])

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

    def _handle_aes(self, load, sig=None):
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
        self.local = salt.client.LocalClient(self.opts['_minion_conf_file'])
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
        self._fire_master(
            'Syndic {0} started at {1}'.format(
            self.opts['id'],
            time.asctime()
            ),
            tagify([self.opts['id'], 'start'], 'syndic'),
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
                    self._fire_master(events=raw_events, pretag=tagify(self.opts['id'], base='syndic'))
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
        if type(tgt) != str:
            return False

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

    def grain_match(self, tgt, delim=':'):
        '''
        Reads in the grains glob match
        '''
        log.debug('grains target: {0}'.format(tgt))
        if delim not in tgt:
            log.error('Got insufficient arguments for grains match '
                      'statement from master')
            return False
        return salt.utils.subdict_match(self.opts['grains'], tgt, delim=delim)

    def grain_pcre_match(self, tgt, delim=':'):
        '''
        Matches a grain based on regex
        '''
        log.debug('grains pcre target: {0}'.format(tgt))
        if delim not in tgt:
            log.error('Got insufficient arguments for grains pcre match '
                      'statement from master')
            return False
        return salt.utils.subdict_match(self.opts['grains'], tgt,
                                        delim=delim, regex_match=True)

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
        return self.functions[tgt]()

    def pillar_match(self, tgt, delim=':'):
        '''
        Reads in the pillar glob match
        '''
        log.debug('pillar target: {0}'.format(tgt))
        if delim not in tgt:
            log.error('Got insufficient arguments for pillar match '
                      'statement from master')
            return False
        return salt.utils.subdict_match(self.opts['pillar'], tgt, delim=delim)

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
            except seco.range.RangeException as exc:
                log.debug('Range exception in compound match: {0}'.format(exc))
                return False
        return False

    def compound_match(self, tgt):
        '''
        Runs the compound target check
        '''
        if not isinstance(tgt, string_types):
            log.debug('Compound target received that is not a string')
            return False
        ref = {'G': 'grain',
               'P': 'grain_pcre',
               'I': 'pillar',
               'L': 'list',
               'S': 'ipcidr',
               'E': 'pcre'}
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


class ProxyMinion(Minion):
    '''
    This class instantiates a 'proxy' minion--a minion that does not manipulate
    the host it runs on, but instead manipulates a device that cannot run a minion.
    '''
    def __init__(self, opts, timeout=60, safe=True):  # pylint: disable=W0231
        '''
        Pass in the options dict
        '''

        # Warn if ZMQ < 3.2
        if HAS_ZMQ and (not(hasattr(zmq, 'zmq_version_info')) or
                        zmq.zmq_version_info() < (3, 2)):
            # PyZMQ 2.1.9 does not have zmq_version_info
            log.warning('You have a version of ZMQ less than ZMQ 3.2! There '
                        'are known connection keep-alive issues with ZMQ < '
                        '3.2 which may result in loss of contact with '
                        'minions. Please upgrade your ZMQ!')
        # Late setup the of the opts grains, so we can log from the grains
        # module
        # print opts['proxymodule']
        fq_proxyname = 'proxy.'+opts['proxy']['proxytype']
        self.proxymodule = salt.loader.proxy(opts, fq_proxyname)
        opts['proxyobject'] = self.proxymodule[opts['proxy']['proxytype']+'.Proxyconn'](opts['proxy'])
        opts['id'] = opts['proxyobject'].id(opts)
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
        self.mod_opts = self._prep_mod_opts()
        self.functions, self.returners = self._load_modules()
        self.matcher = Matcher(self.opts, self.functions)
        self.proc_dir = get_proc_dir(opts['cachedir'])
        self.schedule = salt.utils.schedule.Schedule(
            self.opts,
            self.functions,
            self.returners)
        self.grains_cache = self.opts['grains']

    def _prep_mod_opts(self):
        '''
        Returns a copy of the opts with key bits stripped out
        '''
        return super(ProxyMinion, self)._prep_mod_opts()

    def _load_modules(self):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        return super(ProxyMinion, self)._load_modules()
