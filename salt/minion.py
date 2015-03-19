# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''

# Import python libs
from __future__ import print_function
import copy
import errno
import fnmatch
import hashlib
import logging
import multiprocessing
import os
import re
import salt
import signal
import sys
import threading
import time
import traceback
import types
from random import randint, shuffle

# Import third party libs
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    # Running in local, zmq not needed
    HAS_ZMQ = False

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
    SaltInvocationError, SaltReqTimeoutError, SaltClientError,
    SaltSystemExit, SaltSyndicMasterError
)
import salt.client
import salt.crypt
import salt.loader
import salt.payload
import salt.utils
import salt.utils.args
import salt.utils.event
import salt.utils.minion
import salt.utils.schedule
import salt.exitcodes

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
                    msg = ('Master hostname: \'{0}\' not found. Retrying in {1} '
                           'seconds').format(opts['master'], opts['retry_dns'])
                    if salt.log.is_console_configured():
                        log.error(msg)
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

    if 'master_ip' in ret and 'master_ip' in opts:
        if ret['master_ip'] != opts['master_ip']:
            log.warning('Master ip address changed from {0} to {1}'.format(opts['master_ip'],
                                                                          ret['master_ip'])
            )
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
    Wrap load_args_and_kwargs
    '''
    salt.utils.warn_until(
        'Boron',
        'salt.minion.parse_args_and_kwargs() has been renamed to '
        'salt.minion.load_args_and_kwargs(). Please change this function call '
        'before the Boron release of Salt.'
    )
    return load_args_and_kwargs(func, args, data=data)


def load_args_and_kwargs(func, args, data=None):
    '''
    Detect the args and kwargs that need to be passed to a function call, and
    check them against what was passed.
    '''
    argspec = salt.utils.get_function_argspec(func)
    _args = []
    _kwargs = {}
    invalid_kwargs = []

    for arg in args:
        if isinstance(arg, string_types):
            string_arg, string_kwarg = salt.utils.args.parse_input([arg], condition=False)  # pylint: disable=W0632
            if string_arg:
                # Don't append the version that was just derived from parse_cli
                # above, that would result in a 2nd call to
                # salt.utils.cli.yamlify_arg(), which could mangle the input.
                _args.append(arg)
            elif string_kwarg:
                salt.utils.warn_until(
                    'Boron',
                    'The list of function args and kwargs should be parsed '
                    'by salt.utils.args.parse_input() before calling '
                    'salt.minion.load_args_and_kwargs().'
                )
                if argspec.keywords or string_kwarg.iterkeys().next() in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    _kwargs.update(string_kwarg)
                else:
                    # **kwargs not in argspec and parsed argument name not in
                    # list of positional arguments. This keyword argument is
                    # invalid.
                    for key, val in string_kwarg.iteritems():
                        invalid_kwargs.append('{0}={1}'.format(key, val))
                continue

        # if the arg is a dict with __kwarg__ == True, then its a kwarg
        elif isinstance(arg, dict) and arg.pop('__kwarg__', False) is True:
            for key, val in arg.iteritems():
                if argspec.keywords or key in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    _kwargs[key] = val
                else:
                    # **kwargs not in argspec and parsed argument name not in
                    # list of positional arguments. This keyword argument is
                    # invalid.
                    invalid_kwargs.append('{0}={1}'.format(key, val))
            continue

        else:
            _args.append(arg)

    if invalid_kwargs:
        raise SaltInvocationError(
            'The following keyword arguments are not valid: {0}'
            .format(', '.join(invalid_kwargs))
        )

    if argspec.keywords and isinstance(data, dict):
        # this function accepts **kwargs, pack in the publish data
        for key, val in data.items():
            _kwargs['__pub_{0}'.format(key)] = val

    return _args, _kwargs


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
                if self.opts['random_master'] is True:
                    shuffle(masters)
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
                if self.opts['random_master'] is True:
                    log.warning('random_master is True but there is only one master specified. Ignoring.')
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


class MinionBase(object):
    def __init__(self, opts):
        self.opts = opts

    def _init_context_and_poller(self):
        self.context = zmq.Context()
        self.poller = zmq.Poller()

    def _prepare_minion_event_system(self):
        # Prepare the minion event system
        #
        # Start with the publish socket
        self._init_context_and_poller()

        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        # Only use the first 10 chars to keep longer hashes from exceeding the
        # max socket path length.
        id_hash = hash_type(self.opts['id']).hexdigest()[:10]
        epub_sock_path = os.path.join(
            self.opts['sock_dir'],
            'minion_event_{0}_pub.ipc'.format(id_hash)
        )
        if os.path.exists(epub_sock_path):
            os.unlink(epub_sock_path)
        epull_sock_path = os.path.join(
            self.opts['sock_dir'],
            'minion_event_{0}_pull.ipc'.format(id_hash)
        )
        if os.path.exists(epull_sock_path):
            os.unlink(epull_sock_path)

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

        # Securely bind the event sockets
        if self.opts.get('ipc_mode', '') != 'tcp':
            old_umask = os.umask(0177)
        try:
            log.info('Starting pub socket on {0}'.format(epub_uri))
            self.epub_sock.bind(epub_uri)
            log.info('Starting pull socket on {0}'.format(epull_uri))
            self.epull_sock.bind(epull_uri)
        finally:
            if self.opts.get('ipc_mode', '') != 'tcp':
                os.umask(old_umask)

    @staticmethod
    def process_schedule(minion, loop_interval):
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
        return loop_interval


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


class MultiMinion(MinionBase):
    '''
    Create a multi minion interface, this creates as many minions as are
    defined in the master option and binds each minion object to a respective
    master.
    '''
    def __init__(self, opts):
        super(MultiMinion, self).__init__(opts)

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
            s_opts['multimaster'] = True
            try:
                minions.append(Minion(s_opts, 5, False))
            except SaltClientError as exc:
                log.error('Error while bringing up minion for multi-master. Is master at {0} responding?'.format(master))
        if len(minions) == 0:
            err = 'Error while bringing up minion for multi-master. All configured masters [{0}] are not responding!!!'.format(", ".join(map(str, set(self.opts['master']))))
            log.error(err)
            raise SaltClientError(err)
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
                ret[minion['multimaster']] = True
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
        self._prepare_minion_event_system()
        self.poller.register(self.epull_sock, zmq.POLLIN)

        # Prepare the minion generators
        minions = self.minions()
        loop_interval = int(self.opts['loop_interval'])
        last = time.time()
        auth_wait = self.opts['acceptance_wait_time']
        max_wait = auth_wait * 6

        while True:
            module_refresh = False
            pillar_refresh = False
            for minion in minions.itervalues():
                if isinstance(minion, dict):
                    minion = minion['minion']
                if not hasattr(minion, 'schedule'):
                    continue
                loop_interval = self.process_schedule(minion, loop_interval)
            socks = dict(self.poller.poll(1))
            if socks.get(self.epull_sock) == zmq.POLLIN:
                try:
                    while True:
                        package = self.epull_sock.recv(zmq.NOBLOCK)
                        if package.startswith('module_refresh'):
                            module_refresh = True
                        elif package.startswith('pillar_refresh'):
                            pillar_refresh = True
                        elif package.startswith('fire_master'):
                            tag, data = salt.utils.event.MinionEvent.unpack(package)
                            log.debug('Forwarding master event tag={tag}'.format(tag=data['tag']))
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


class Minion(MinionBase):
    '''
    This class instantiates a minion, runs connections for a minion,
    and loads all of the functions into the minion
    '''

    def __init__(self, opts, timeout=60, safe=True):  # pylint: disable=W0231
        '''
        Pass in the options dict
        '''
        self._running = None
        self.win_proc = []

        # Warn if ZMQ < 3.2
        if HAS_ZMQ:
            try:
                zmq_version_info = zmq.zmq_version_info()
            except AttributeError:
                # PyZMQ <= 2.1.9 does not have zmq_version_info, fall back to
                # using zmq.zmq_version() and build a version info tuple.
                zmq_version_info = tuple(
                    [int(x) for x in zmq.zmq_version().split('.')]
                )
            if zmq_version_info < (3, 2):
                log.warning(
                    'You have a version of ZMQ less than ZMQ 3.2! There are '
                    'known connection keep-alive issues with ZMQ < 3.2 which '
                    'may result in loss of contact with minions. Please '
                    'upgrade your ZMQ!'
                )
        # Late setup the of the opts grains, so we can log from the grains
        # module
        opts['grains'] = salt.loader.grains(opts)

        # evaluate the master to connect to and authenticate with it
        opts['master'] = self.eval_master(opts,
                                          timeout,
                                          safe)

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

        # add default scheduling jobs to the minions scheduler
        if 'mine.update' in self.functions:
            log.info('Added mine.update to schedular')
            self.schedule.add_job({
                '__mine_interval':
                {
                    'function': 'mine.update',
                    'minutes': opts['mine_interval'],
                    'jid_include': True,
                    'maxrunning': 2
                }
            })

        # add master_alive job if enabled
        if self.opts['master_alive_interval'] > 0:
            self.schedule.add_job({
                '__master_alive':
                {
                    'function': 'status.master',
                    'seconds': opts['master_alive_interval'],
                    'jid_include': True,
                    'maxrunning': 1,
                    'kwargs': {'master': self.opts['master'],
                               'connected': True}
                }
            })

        self.grains_cache = self.opts['grains']

        # store your hexid to subscribe to zmq, hash since zmq filters are prefix
        # matches this way we can avoid collisions
        self.hexid = hashlib.sha1(self.opts['id']).hexdigest()

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
            log.debug('I am {0} and I am not supposed to start any proxies. '
                      '(Likely not a problem)'.format(self.opts['id']))

        # __init__() from MinionBase is called in Minion.eval_master()

    def eval_master(self,
                    opts,
                    timeout=60,
                    safe=True,
                    failed=False):
        '''
        Evaluates and returns the current master address. In standard mode, just calls
        authenticate() with the given master address.

        With master_type=func evaluates the current master address from the given
        module and then calls authenticate().

        With master_type=failover takes the list of masters and loops through them.
        The first one that allows the minion to connect is used to authenticate() and
        then returned. If this function is called outside the minions initialization
        phase (for example from the minions main event-loop when a master connection
        loss was detected), 'failed' should be set to True. The current
        (possibly failed) master will then be removed from the list of masters.
        '''
        # check if master_type was altered from its default
        if opts['master_type'] != 'str':
            # check for a valid keyword
            if opts['master_type'] == 'func':
                # split module and function and try loading the module
                mod, fun = opts['master'].split('.')
                try:
                    master_mod = salt.loader.raw_mod(opts, mod, fun)
                    if not master_mod:
                        raise TypeError
                    # we take whatever the module returns as master address
                    opts['master'] = master_mod[mod + '.' + fun]()
                except TypeError:
                    msg = ('Failed to evaluate master address from '
                           'module \'{0}\''.format(opts['master']))
                    log.error(msg)
                    sys.exit(salt.exitcodes.EX_GENERIC)
                log.info('Evaluated master from module: {0}'.format(master_mod))

            # if failover is set, master has to be of type list
            elif opts['master_type'] == 'failover':
                if isinstance(opts['master'], list):
                    log.info('Got list of available master addresses:'
                             ' {0}'.format(opts['master']))
                    if opts['master_shuffle']:
                        shuffle(opts['master'])
                elif opts['__role'] == 'syndic':
                    log.info('Syndic setting master_syndic to \'{0}\''.format(opts['master']))

                # if failed=True, the minion was previously connected
                # we're probably called from the minions main-event-loop
                # because a master connection loss was detected. remove
                # the possibly failed master from the list of masters.
                elif failed:
                    log.info('Removing possibly failed master {0} from list of'
                             ' masters'.format(opts['master']))
                    # create new list of master with the possibly failed one removed
                    opts['master'] = [x for x in opts['master_list'] if opts['master'] != x]

                else:
                    msg = ('master_type set to \'failover\' but \'master\' '
                           'is not of type list but of type '
                           '{0}'.format(type(opts['master'])))
                    log.error(msg)
                    sys.exit(salt.exitcodes.EX_GENERIC)
            else:
                msg = ('Invalid keyword \'{0}\' for variable '
                       '\'master_type\''.format(opts['master_type']))
                log.error(msg)
                sys.exit(salt.exitcodes.EX_GENERIC)

        # if we have a list of masters, loop through them and be
        # happy with the first one that allows us to connect
        if isinstance(opts['master'], list):
            conn = False
            # shuffle the masters and then loop through them
            local_masters = copy.copy(opts['master'])

            for master in local_masters:
                opts['master'] = master
                opts.update(resolve_dns(opts))
                super(Minion, self).__init__(opts)

                # on first run, update self.opts with the whole master list
                # to enable a minion to re-use old masters if they get fixed
                if 'master_list' not in self.opts:
                    self.opts['master_list'] = local_masters

                try:
                    if self.authenticate(timeout, safe) != 'full':
                        conn = True
                        break
                except SaltClientError:
                    msg = ('Master {0} could not be reached, trying '
                           'next master (if any)'.format(opts['master']))
                    log.info(msg)
                    continue

            if not conn:
                self.connected = False
                msg = ('No master could be reached or all masters denied '
                       'the minions connection attempt.')
                log.error(msg)
            else:
                self.connected = True
                return opts['master']

        # single master sign in
        else:
            opts.update(resolve_dns(opts))
            super(Minion, self).__init__(opts)
            if self.authenticate(timeout, safe) == 'full':
                self.connected = False
                msg = ('master {0} rejected the minions connection because too '
                       'many minions are already connected.'.format(opts['master']))
                log.error(msg)
                sys.exit(salt.exitcodes.EX_GENERIC)
            else:
                self.connected = True
                return opts['master']

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

    def _load_modules(self, force_refresh=False):
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

        self.opts['grains'] = salt.loader.grains(self.opts, force_refresh)
        if self.opts.get('multimaster', False):
            s_opts = copy.copy(self.opts)
            functions = salt.loader.minion_mods(s_opts)
        else:
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
        elif not data and tag:
            load['data'] = {}
            load['tag'] = tag

        else:
            return
        channel = salt.transport.Channel.factory(self.opts)
        try:
            result = channel.send(load)
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
                reauth_delay = randint(0, float(self.opts['random_reauth_delay']))
                # This mitigates the issue wherein a long-running job might not return
                # on a master key rotation. However, new commands issued during the re-auth
                # splay period will still fail to return.
                if not salt.utils.minion.running(self.opts):
                    log.debug('Waiting {0} seconds to re-authenticate'.format(reauth_delay))
                    time.sleep(reauth_delay)
                else:
                    log.warning('Ignoring re-auth delay because jobs are running')

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
        else:
            self.win_proc.append(process)

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

        salt.utils.appendproctitle(data['jid'])

        sdata = {'pid': os.getpid()}
        sdata.update(data)
        log.info('Starting a new job with PID {0}'.format(sdata['pid']))
        with salt.utils.fopen(fn_, 'w+b') as fp_:
            fp_.write(minion_instance.serial.dumps(sdata))
        ret = {'success': False}
        function_name = data['fun']
        if function_name in minion_instance.functions:
            try:
                func = minion_instance.functions[data['fun']]
                args, kwargs = load_args_and_kwargs(
                    func,
                    data['arg'],
                    data)
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
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret['return'] = 'ERROR: {0}'.format(exc)
                ret['out'] = 'nested'
            except SaltInvocationError as exc:
                log.error(
                    'Problem executing {0!r}: {1}'.format(
                        function_name,
                        exc
                    ),
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret['return'] = 'ERROR executing {0!r}: {1}'.format(
                    function_name, exc
                )
                ret['out'] = 'nested'
            except TypeError as exc:
                msg = ('TypeError encountered executing {0}: {1}. See '
                       'debug log for more info.').format(function_name, exc)
                log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
                ret['return'] = msg
                ret['out'] = 'nested'
            except Exception:
                msg = 'The minion function caused an exception'
                log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
                ret['return'] = '{0}: {1}'.format(msg, traceback.format_exc())
                ret['out'] = 'nested'
        else:
            ret['return'] = '{0!r} is not available.'.format(function_name)
            ret['success'] = False
            ret['retcode'] = 254
            ret['out'] = 'nested'

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        ret['fun_args'] = data['arg']
        if 'master_id' in data:
            ret['master_id'] = data['master_id']
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
                    log.error(traceback.format_exc())

    @classmethod
    def _thread_multi_return(cls, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        salt.utils.appendproctitle(data['jid'])
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
                args, kwargs = load_args_and_kwargs(
                    func,
                    data['arg'][ind],
                    data)
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
        channel = salt.transport.Channel.factory(self.opts)
        if ret_cmd == '_syndic_return':
            load = {'cmd': ret_cmd,
                    'id': self.opts['id'],
                    'jid': jid,
                    'fun': fun,
                    'arg': ret.get('arg'),
                    'tgt': ret.get('tgt'),
                    'tgt_type': ret.get('tgt_type'),
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
        try:
            ret_val = channel.send(load)
        except SaltReqTimeoutError:
            msg = ('The minion failed to return the job information for job '
                   '{0}. This is often due to the master being shut down or '
                   'overloaded. If the master is running consider increasing '
                   'the worker_threads value.').format(jid)
            log.warn(msg)
            return ''

        log.trace('ret_val = {0}'.format(ret_val))
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
            if 'schedule' not in self.opts:
                self.opts['schedule'] = {}
            self.opts['schedule'].update({
                '__update_grains':
                    {
                        'function': 'event.fire',
                        'args': [{}, 'grains_refresh'],
                        'minutes': refresh_interval_in_minutes
                    }
            })

    def _set_tcp_keepalive(self):
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

    def _set_reconnect_ivl(self):
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

    def _set_reconnect_ivl_max(self):
        if hasattr(zmq, 'RECONNECT_IVL_MAX'):
            log.debug("Setting zmq_reconnect_ivl_max to '{0}ms'".format(
                self.opts['recon_default'] + self.opts['recon_max'])
            )

            self.socket.setsockopt(
                zmq.RECONNECT_IVL_MAX, self.opts['recon_max']
            )

    def _set_ipv4only(self):
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.socket.setsockopt(zmq.IPV4ONLY, 0)

    def _fire_master_minion_start(self):
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

    def _setsockopts(self):
        if self.opts['zmq_filtering']:
            # TODO: constants file for "broadcast"
            self.socket.setsockopt(zmq.SUBSCRIBE, 'broadcast')
            self.socket.setsockopt(zmq.SUBSCRIBE, self.hexid)
        else:
            self.socket.setsockopt(zmq.SUBSCRIBE, '')

        self.socket.setsockopt(zmq.IDENTITY, self.opts['id'])
        self._set_ipv4only()
        self._set_reconnect_ivl_max()
        self._set_tcp_keepalive()

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

        tries = self.opts.get('auth_tries', 1)
        safe = self.opts.get('auth_safemode', safe)
        while True:
            creds = auth.sign_in(timeout, safe, tries)
            if creds == 'full':
                return creds
            elif creds != 'retry':
                log.info('Authentication with master at {0} successful!'.format(self.opts['master_ip']))
                break
            log.info('Waiting for minion key to be accepted by the master.')
            if acceptance_wait_time:
                log.info('Waiting {0} seconds before retry.'.format(acceptance_wait_time))
                time.sleep(acceptance_wait_time)
            if acceptance_wait_time < acceptance_wait_time_max:
                acceptance_wait_time += acceptance_wait_time
                log.debug('Authentication wait time is {0}'.format(acceptance_wait_time))

        self.aes = creds['aes']
        if self.opts.get('syndic_master_publish_port'):
            self.publish_port = self.opts.get('syndic_master_publish_port')
        else:
            self.publish_port = creds['publish_port']
        self.crypticle = salt.crypt.Crypticle(self.opts, self.aes)

    def module_refresh(self, force_refresh=False):
        '''
        Refresh the functions and returners.
        '''
        self.functions, self.returners = self._load_modules(force_refresh)
        self.schedule.functions = self.functions
        self.schedule.returners = self.returners

    def pillar_refresh(self, force_refresh=False):
        '''
        Refresh the pillar
        '''
        self.opts['pillar'] = salt.pillar.get_pillar(
            self.opts,
            self.opts['grains'],
            self.opts['id'],
            self.opts['environment'],
        ).compile_pillar()
        self.module_refresh(force_refresh)

    def manage_schedule(self, package):
        '''
        Refresh the functions and returners.
        '''
        tag, data = salt.utils.event.MinionEvent.unpack(package)
        func = data.get('func', None)
        name = data.get('name', None)
        schedule = data.get('schedule', None)
        where = data.get('where', None)

        if func == 'delete':
            self.schedule.delete_job(name)
        elif func == 'add':
            self.schedule.add_job(schedule)
        elif func == 'modify':
            self.schedule.modify_job(name, schedule, where)
        elif func == 'enable':
            self.schedule.enable_schedule()
        elif func == 'disable':
            self.schedule.disable_schedule()
        elif func == 'enable_job':
            self.schedule.enable_job(name, where)
        elif func == 'run_job':
            self.schedule.run_job(name, where)
        elif func == 'disable_job':
            self.schedule.disable_job(name, where)
        elif func == 'reload':
            self.schedule.reload(schedule)

    def environ_setenv(self, package):
        '''
        Set the salt-minion main process environment according to
        the data contained in the minion event data
        '''
        tag, data = salt.utils.event.MinionEvent.unpack(package)
        environ = data.get('environ', None)
        if environ is None:
            return False
        false_unsets = data.get('false_unsets', False)
        clear_all = data.get('clear_all', False)
        import salt.modules.environ as mod_environ
        return mod_environ.setenv(environ, false_unsets, clear_all)

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

    def _windows_thread_cleanup(self):
        '''
        Cleanup Windows threads
        '''
        if not salt.utils.is_windows():
            return
        for thread in self.win_proc:
            if not thread.is_alive():
                thread.join()
                try:
                    self.win_proc.remove(thread)
                    del thread
                except (ValueError, NameError):
                    pass

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

        self._prepare_minion_event_system()

        self.socket = self.context.socket(zmq.SUB)

        self._set_reconnect_ivl()
        self._setsockopts()

        self.socket.connect(self.master_pub)
        self.poller.register(self.socket, zmq.POLLIN)
        self.poller.register(self.epull_sock, zmq.POLLIN)

        self._fire_master_minion_start()
        log.info('Minion is ready to receive requests!')

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        # Make sure to gracefully handle CTRL_LOGOFF_EVENT
        salt.utils.enable_ctrl_logoff_handler()

        # On first startup execute a state run if configured to do so
        self._state_run()

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

        ping_interval = self.opts.get('ping_interval', 0) * 60
        ping_at = None

        while self._running is True:
            loop_interval = self.process_schedule(self, loop_interval)
            self._windows_thread_cleanup()
            try:
                socks = self._do_poll(loop_interval)

                if ping_interval > 0:
                    if socks or not ping_at:
                        ping_at = time.time() + ping_interval
                    if ping_at < time.time():
                        log.debug('Ping master')
                        self._fire_master('ping', 'minion_ping')
                        ping_at = time.time() + ping_interval

                self._do_socket_recv(socks)

                # Check the event system
                if socks.get(self.epull_sock) == zmq.POLLIN:
                    package = self.epull_sock.recv(zmq.NOBLOCK)
                    log.debug('Handling event {0!r}'.format(package))
                    try:
                        if package.startswith('module_refresh'):
                            self.module_refresh()
                        elif package.startswith('pillar_refresh'):
                            self.pillar_refresh()
                        elif package.startswith('manage_schedule'):
                            self.manage_schedule(package)
                        elif package.startswith('grains_refresh'):
                            if self.grains_cache != self.opts['grains']:
                                self.pillar_refresh(force_refresh=True)
                                self.grains_cache = self.opts['grains']
                        elif package.startswith('environ_setenv'):
                            self.environ_setenv(package)
                        elif package.startswith('fire_master'):
                            tag, data = salt.utils.event.MinionEvent.unpack(package)
                            log.debug('Forwarding master event tag={tag}'.format(tag=data['tag']))
                            self._fire_master(data['data'], data['tag'], data['events'], data['pretag'])
                        elif package.startswith('__master_disconnected'):
                            if self.connected:
                                # we are not connected anymore
                                self.connected = False
                                # modify the scheduled job to fire only on reconnect
                                schedule = {
                                   'function': 'status.master',
                                   'seconds': self.opts['master_alive_interval'],
                                   'jid_include': True,
                                   'maxrunning': 2,
                                   'kwargs': {'master': self.opts['master'],
                                              'connected': False}
                                }
                                self.schedule.modify_job(name='__master_alive',
                                                         schedule=schedule)

                                log.info('Connection to master {0} lost'.format(self.opts['master']))

                                if self.opts['master_type'] == 'failover':
                                    log.info('Trying to tune in to next master from master-list')

                                    # if eval_master finds a new master for us, self.connected
                                    # will be True again on successful master authentication
                                    self.opts['master'] = self.eval_master(opts=self.opts,
                                                                           failed=True)
                                    if self.connected:
                                        # re-init the subsystems to work with the new master
                                        log.info('Re-initialising subsystems for new '
                                                 'master {0}'.format(self.opts['master']))
                                        del self.socket
                                        del self.context
                                        del self.poller
                                        self._init_context_and_poller()
                                        self.socket = self.context.socket(zmq.SUB)
                                        self._set_reconnect_ivl()
                                        self._setsockopts()
                                        self.socket.connect(self.master_pub)
                                        self.poller.register(self.socket, zmq.POLLIN)
                                        self.poller.register(self.epull_sock, zmq.POLLIN)
                                        self._fire_master_minion_start()
                                        log.info('Minion is ready to receive requests!')

                                        # update scheduled job to run with the new master addr
                                        schedule = {
                                           'function': 'status.master',
                                           'seconds': self.opts['master_alive_interval'],
                                           'jid_include': True,
                                           'maxrunning': 2,
                                           'kwargs': {'master': self.opts['master'],
                                                      'connected': True}
                                        }
                                        self.schedule.modify_job(name='__master_alive',
                                                                 schedule=schedule)

                        elif package.startswith('__master_connected'):
                            # handle this event only once. otherwise it will pollute the log
                            if not self.connected:
                                log.info('Connection to master {0} re-established'.format(self.opts['master']))
                                self.connected = True
                                # modify the __master_alive job to only fire,
                                # if the connection is lost again
                                schedule = {
                                   'function': 'status.master',
                                   'seconds': self.opts['master_alive_interval'],
                                   'jid_include': True,
                                   'maxrunning': 2,
                                   'kwargs': {'master': self.opts['master'],
                                              'connected': True}
                                }

                                self.schedule.modify_job(name='__master_alive',
                                                         schedule=schedule)
                        self.epub_sock.send(package)
                    except Exception:
                        log.debug('Exception while handling events', exc_info=True)
                    # Add an extra fallback in case a forked process leeks through
                    multiprocessing.active_children()

            except zmq.ZMQError as exc:
                # The interrupt caused by python handling the
                # SIGCHLD. Throws this error with errno == EINTR.
                # Nothing to receive on the zmq socket throws this error
                # with EAGAIN.
                # Both are safe to ignore
                if exc.errno != errno.EAGAIN and exc.errno != errno.EINTR:
                    log.critical('Unexpected ZMQError while polling minion',
                                 exc_info=True)
                continue
            except SaltClientError:
                raise
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
        self._init_context_and_poller()

        self.socket = self.context.socket(zmq.SUB)

        self._setsockopts()

        self.socket.connect(self.master_pub)
        self.poller.register(self.socket, zmq.POLLIN)

        self._fire_master_minion_start()

        loop_interval = int(self.opts['loop_interval'])

        # On first startup execute a state run if configured to do so
        self._state_run()

        while self._running is True:
            try:
                socks = self._do_poll(loop_interval)
                self._do_socket_recv(socks)
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

    def _do_poll(self, loop_interval):
        log.trace('Check main poller timeout {0}'.format(loop_interval))
        return dict(self.poller.poll(
            loop_interval * 1000)
        )

    def _do_socket_recv(self, socks):
        if socks.get(self.socket) == zmq.POLLIN:
            # topic filtering is done at the zmq level, so we just strip it
            messages = self.socket.recv_multipart(zmq.NOBLOCK)
            messages_len = len(messages)
            # if it was one message, then its old style
            if messages_len == 1:
                payload = self.serial.loads(messages[0])
            # 2 includes a header which says who should do it
            elif messages_len == 2:
                payload = self.serial.loads(messages[1])
            else:
                raise Exception(('Invalid number of messages ({0}) in zeromq pub'
                                 'message from master').format(len(messages_len)))

            log.trace('Handling payload')
            self._handle_payload(payload)

    def destroy(self):
        '''
        Tear down the minion
        '''
        self._running = False
        if getattr(self, 'poller', None) is not None:
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
    def __init__(self, opts, **kwargs):
        self._syndic_interface = opts.get('interface')
        self._syndic = True
        opts['loop_interval'] = 1
        super(Syndic, self).__init__(opts, **kwargs)
        self.mminion = salt.minion.MasterMinion(opts)
        self.jid_forward_cache = set()

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
           or 'arg' not in data:
            return
        data['to'] = int(data.get('to', self.opts['timeout'])) - 1
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
        kwargs = {}

        # optionally add a few fields to the publish data
        for field in ('master_id',  # which master the job came from
                      'user',  # which user ran the job
                      ):
            if field in data:
                kwargs[field] = data[field]

        # Send out the publication
        self.local.pub(data['tgt'],
                       data['fun'],
                       data['arg'],
                       data['tgt_type'],
                       data['ret'],
                       data['jid'],
                       data['to'],
                       **kwargs)

    def _setsockopts(self):
        # no filters for syndication masters, unless we want to maintain a
        # list of all connected minions and update the filter
        self.socket.setsockopt(zmq.SUBSCRIBE, '')
        self.socket.setsockopt(zmq.IDENTITY, self.opts['id'])

        self._set_reconnect_ivl_max()
        self._set_tcp_keepalive()
        self._set_ipv4only()

    def _fire_master_syndic_start(self):
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

    def tune_in_no_block(self):
        '''
        Executes the tune_in sequence but omits extra logging and the
        management of the event bus assuming that these are handled outside
        the tune_in sequence
        '''
        # Instantiate the local client
        self.local = salt.client.get_local_client(self.opts['_minion_conf_file'])
        self.local.event.subscribe('')

        self._init_context_and_poller()

        self.socket = self.context.socket(zmq.SUB)

        self._setsockopts()

        self.socket.connect(self.master_pub)
        self.poller.register(self.socket, zmq.POLLIN)

        loop_interval = int(self.opts['loop_interval'])

        self._fire_master_syndic_start()

        while True:
            try:
                socks = dict(self.poller.poll(loop_interval * 1000))
                if socks.get(self.socket) == zmq.POLLIN:
                    self._process_cmd_socket()
            except zmq.ZMQError:
                yield True
            except Exception:
                log.critical(
                    'An exception occurred while polling the minion',
                    exc_info=True
                )
            yield True

    # Syndic Tune In
    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the syndic
        '''
        signal.signal(signal.SIGTERM, self.clean_die)
        log.debug('Syndic {0!r} trying to tune in'.format(self.opts['id']))

        self._init_context_and_poller()

        # Instantiate the local client
        self.local = salt.client.get_local_client(self.opts['_minion_conf_file'])
        self.local.event.subscribe('')
        self.local.opts['interface'] = self._syndic_interface
        # register the event sub to the poller
        self.poller.register(self.local.event.sub)

        # Start with the publish socket
        # Share the poller with the event object
        self.socket = self.context.socket(zmq.SUB)

        self._setsockopts()

        self.socket.connect(self.master_pub)
        self.poller.register(self.socket, zmq.POLLIN)
        # Send an event to the master that the minion is live
        self._fire_master_syndic_start()

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        loop_interval = int(self.opts['loop_interval'])
        self._reset_event_aggregation()
        while True:
            try:
                # Do all the maths in seconds
                timeout = loop_interval
                if self.event_forward_timeout is not None:
                    timeout = min(timeout,
                                  self.event_forward_timeout - time.time())
                if timeout >= 0:
                    log.trace('Polling timeout: %f', timeout)
                    socks = dict(self.poller.poll(timeout * 1000))
                else:
                    # This shouldn't really happen.
                    # But there's no harm being defensive
                    log.warning('Negative timeout in syndic main loop')
                    socks = {}
                if socks.get(self.socket) == zmq.POLLIN:
                    self._process_cmd_socket()
                if socks.get(self.local.event.sub) == zmq.POLLIN:
                    self._process_event_socket()
                if (self.event_forward_timeout is not None and
                    self.event_forward_timeout < time.time()):
                    self._forward_events()
            # We don't handle ZMQErrors like the other minions
            # I've put explicit handling around the receive calls
            # in the process_*_socket methods. If we see any other
            # errors they may need some kind of handling so log them
            # for now.
            except Exception:
                log.critical(
                    'An exception occurred while polling the syndic',
                    exc_info=True
                )

    def _process_cmd_socket(self):
        try:
            messages = self.socket.recv_multipart(zmq.NOBLOCK)
            messages_len = len(messages)
            idx = None
            if messages_len == 1:
                idx = 0
            elif messages_len == 2:
                idx = 1
            else:
                raise SaltSyndicMasterError('Syndication master received message of invalid len ({0}/2)'.format(messages_len))

            payload = self.serial.loads(messages[idx])
        except zmq.ZMQError as e:
            # Swallow errors for bad wakeups or signals needing processing
            if e.errno != errno.EAGAIN and e.errno != errno.EINTR:
                raise
        log.trace('Handling payload')
        self._handle_payload(payload)

    def _reset_event_aggregation(self):
        self.jids = {}
        self.raw_events = []
        self.event_forward_timeout = None

    def _process_event_socket(self):
        tout = time.time() + self.opts['syndic_max_event_process_time']
        while tout > time.time():
            try:
                event = self.local.event.get_event_noblock()
            except zmq.ZMQError as e:
                # EAGAIN indicates no more events at the moment
                # EINTR some kind of signal maybe someone trying
                # to get us to quit so escape our timeout
                if e.errno == errno.EAGAIN or e.errno == errno.EINTR:
                    break
                raise
            log.trace('Got event {0}'.format(event['tag']))
            if self.event_forward_timeout is None:
                self.event_forward_timeout = (
                        time.time() + self.opts['syndic_event_forward_timeout']
                        )
            if salt.utils.is_jid(event['tag']) and 'return' in event['data']:
                if 'jid' not in event['data']:
                    # Not a job return
                    continue
                jdict = self.jids.setdefault(event['tag'], {})
                if not jdict:
                    jdict['__fun__'] = event['data'].get('fun')
                    jdict['__jid__'] = event['data']['jid']
                    jdict['__load__'] = {}
                    fstr = '{0}.get_load'.format(self.opts['master_job_cache'])
                    # Only need to forward each load once. Don't hit the disk
                    # for every minion return!
                    if event['data']['jid'] not in self.jid_forward_cache:
                        jdict['__load__'].update(
                            self.mminion.returners[fstr](event['data']['jid'])
                            )
                        self.jid_forward_cache.add(event['data']['jid'])
                        if len(self.jid_forward_cache) > self.opts['syndic_jid_forward_cache_hwm']:
                            # Pop the oldest jid from the cache
                            tmp = sorted(list(self.jid_forward_cache))
                            tmp.pop(0)
                            self.jid_forward_cache = set(tmp)
                if 'master_id' in event['data']:
                    jdict['master_id'] = event['data']['master_id']
                jdict[event['data']['id']] = event['data']['return']
            else:
                # Add generic event aggregation here
                if 'retcode' not in event['data']:
                    self.raw_events.append(event)

    def _forward_events(self):
        log.trace('Forwarding events')
        if self.raw_events:
            self._fire_master(events=self.raw_events,
                              pretag=tagify(self.opts['id'], base='syndic'),
                              )
        for jid in self.jids:
            self._return_pub(self.jids[jid], '_syndic_return')
        self._reset_event_aggregation()

    def destroy(self):
        '''
        Tear down the syndic minion
        '''
        # We borrowed the local clients poller so give it back before
        # it's destroyed. Reset the local poller reference.
        self.poller = None
        super(Syndic, self).destroy()
        if hasattr(self, 'local'):
            del self.local


class MultiSyndic(MinionBase):
    '''
    Make a MultiSyndic minion, this minion will handle relaying jobs and returns from
    all minions connected to it to the list of masters it is connected to.

    Note: jobs will be returned best-effort to the requesting master. This also means
    (since we are using zmq) that if a job was fired and the master disconnects
    between the publish and return, that the return will end up in a zmq buffer
    in this Syndic headed to that original master.

    In addition, since these classes all seem to use a mix of blocking and non-blocking
    calls (with varying timeouts along the way) this daemon does not handle failure well,
    it will (under most circumstances) stall the daemon for ~60s attempting to re-auth
    with the down master
    '''
    # time to connect to upstream master
    SYNDIC_CONNECT_TIMEOUT = 5

    def __init__(self, opts):
        opts['loop_interval'] = 1
        super(MultiSyndic, self).__init__(opts)
        self.mminion = salt.minion.MasterMinion(opts)
        self.jid_forward_cache = set()

        # create all of the syndics you need
        self.master_syndics = {}
        for master in set(self.opts['master']):
            s_opts = copy.copy(self.opts)
            s_opts['master'] = master
            self.master_syndics[master] = {'opts': s_opts,
                                           'auth_wait': s_opts['acceptance_wait_time'],
                                           'dead_until': 0}
            self._connect_to_master(master)

    # TODO: do we need all of this?
    def _connect_to_master(self, master):
        '''
        Attempt to connect to master, including back-off for each one

        return boolean of wether you connected or not
        '''
        if master not in self.master_syndics:
            log.error('Unable to connect to {0}, not in the list of masters'.format(master))
            return False

        minion = self.master_syndics[master]
        # if we need to be dead for a while, stay that way
        if minion['dead_until'] > time.time():
            return False

        if time.time() - minion['auth_wait'] > minion.get('last', 0):
            try:
                t_minion = Syndic(minion['opts'],
                                  timeout=self.SYNDIC_CONNECT_TIMEOUT,
                                  safe=False,
                                  )

                self.master_syndics[master]['syndic'] = t_minion
                self.master_syndics[master]['generator'] = t_minion.tune_in_no_block()
                self.master_syndics[master]['auth_wait'] = self.opts['acceptance_wait_time']
                self.master_syndics[master]['dead_until'] = 0

                return True
            except SaltClientError:
                log.error('Error while bring up minion for multi-syndic. Is master {0} responding?'.format(master))
                # re-use auth-wait as backoff for syndic
                minion['dead_until'] = time.time() + minion['auth_wait']
                if minion['auth_wait'] < self.opts['acceptance_wait_time_max']:
                    minion['auth_wait'] += self.opts['acceptance_wait_time']
        return False

    def _call_syndic(self, func, args=(), kwargs=None, master_id=None):
        '''
        Wrapper to call a given func on a syndic, best effort to get the one you asked for
        '''
        if kwargs is None:
            kwargs = {}
        for master, syndic_dict in self.iter_master_options(master_id):
            if 'syndic' not in syndic_dict:
                continue
            if syndic_dict['dead_until'] > time.time():
                log.error('Unable to call {0} on {1}, that syndic is dead for now'.format(func, master_id))
                continue
            try:
                getattr(syndic_dict['syndic'], func)(*args, **kwargs)
                return
            except SaltClientError:
                log.error('Unable to call {0} on {1}, trying another...'.format(func, master_id))
                # re-use auth-wait as backoff for syndic
                syndic_dict['dead_until'] = time.time() + syndic_dict['auth_wait']
                if syndic_dict['auth_wait'] < self.opts['acceptance_wait_time_max']:
                    syndic_dict['auth_wait'] += self.opts['acceptance_wait_time']
                continue
        log.critical('Unable to call {0} on any masters!'.format(func))

    def iter_master_options(self, master_id=None):
        '''
        Iterate (in order) over your options for master
        '''
        masters = self.master_syndics.keys()
        shuffle(masters)
        if master_id not in self.master_syndics:
            master_id = masters.pop(0)
        else:
            masters.remove(master_id)

        while True:
            yield master_id, self.master_syndics[master_id]
            if len(masters) == 0:
                break
            master_id = masters.pop(0)

    def _reset_event_aggregation(self):
        self.jids = {}
        self.raw_events = []
        self.event_forward_timeout = None

    # Syndic Tune In
    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the syndic
        '''
        # Instantiate the local client
        self.local = salt.client.get_local_client(self.opts['_minion_conf_file'])
        self.local.event.subscribe('')

        log.debug('MultiSyndic {0!r} trying to tune in'.format(self.opts['id']))

        # Share the poller with the event object
        self.poller = self.local.event.poller

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        loop_interval = int(self.opts['loop_interval'])
        self._reset_event_aggregation()
        while True:
            try:
                # Do all the maths in seconds
                timeout = loop_interval
                if self.event_forward_timeout is not None:
                    timeout = min(timeout,
                                  self.event_forward_timeout - time.time())
                if timeout >= 0:
                    log.trace('Polling timeout: %f', timeout)
                    socks = dict(self.poller.poll(timeout * 1000))
                else:
                    # This shouldn't really happen.
                    # But there's no harm being defensive
                    log.warning('Negative timeout in syndic main loop')
                    socks = {}
                # check all of your master_syndics, have them do their thing
                for master_id, syndic_dict in self.master_syndics.iteritems():
                    # if not connected, lets try
                    if 'generator' not in syndic_dict:
                        # if we couldn't connect, lets try later
                        if not self._connect_to_master(master_id):
                            continue
                    syndic_dict['generator'].next()

                # events
                if socks.get(self.local.event.sub) == zmq.POLLIN:
                    self._process_event_socket()

                if (self.event_forward_timeout is not None and
                    self.event_forward_timeout < time.time()):
                    self._forward_events()
            # We don't handle ZMQErrors like the other minions
            # I've put explicit handling around the receive calls
            # in the process_*_socket methods. If we see any other
            # errors they may need some kind of handling so log them
            # for now.
            except Exception:
                log.critical(
                    'An exception occurred while polling the syndic',
                    exc_info=True
                )

    def _process_event_socket(self):
        tout = time.time() + self.opts['syndic_max_event_process_time']
        while tout > time.time():
            try:
                event = self.local.event.get_event_noblock()
            except zmq.ZMQError as e:
                # EAGAIN indicates no more events at the moment
                # EINTR some kind of signal maybe someone trying
                # to get us to quit so escape our timeout
                if e.errno == errno.EAGAIN or e.errno == errno.EINTR:
                    break
                raise
            log.trace('Got event {0}'.format(event['tag']))
            if self.event_forward_timeout is None:
                self.event_forward_timeout = (
                        time.time() + self.opts['syndic_event_forward_timeout']
                        )
            if salt.utils.is_jid(event['tag']) and 'return' in event['data']:
                if 'jid' not in event['data']:
                    # Not a job return
                    continue
                jdict = self.jids.setdefault(event['tag'], {})
                if not jdict:
                    jdict['__fun__'] = event['data'].get('fun')
                    jdict['__jid__'] = event['data']['jid']
                    jdict['__load__'] = {}
                    fstr = '{0}.get_load'.format(self.opts['master_job_cache'])
                    # Only need to forward each load once. Don't hit the disk
                    # for every minion return!
                    if event['data']['jid'] not in self.jid_forward_cache:
                        jdict['__load__'].update(
                            self.mminion.returners[fstr](event['data']['jid'])
                            )
                        self.jid_forward_cache.add(event['data']['jid'])
                        if len(self.jid_forward_cache) > self.opts['syndic_jid_forward_cache_hwm']:
                            # Pop the oldest jid from the cache
                            tmp = sorted(list(self.jid_forward_cache))
                            tmp.pop(0)
                            self.jid_forward_cache = set(tmp)
                if 'master_id' in event['data']:
                    # __'s to make sure it doesn't print out on the master cli
                    jdict['__master_id__'] = event['data']['master_id']
                jdict[event['data']['id']] = event['data']['return']
            else:
                # Add generic event aggregation here
                if 'retcode' not in event['data']:
                    self.raw_events.append(event)

    def _forward_events(self):
        log.trace('Forwarding events')
        if self.raw_events:
            self._call_syndic('_fire_master',
                              kwargs={'events': self.raw_events,
                                      'pretag': tagify(self.opts['id'], base='syndic')},
                              )
        for jid, jid_ret in self.jids.iteritems():
            self._call_syndic('_return_pub', args=(jid_ret, '_syndic_return'), master_id=jid_ret.get('__master_id__'))

        self._reset_event_aggregation()


class Matcher(object):
    '''
    Use to return the value for matching calls from the master
    '''
    def __init__(self, opts, functions=None):
        self.opts = opts
        self.functions = functions

    def confirm_top(self, match, data, nodegroups=None):
        '''
        Takes the data passed to a top file environment and determines if the
        data matches this minion
        '''
        matcher = 'compound'
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
        if self.functions is None:
            self.functions = salt.loader.minion_mods(self.opts)
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

    def pillar_exact_match(self, tgt, delim=':'):
        '''
        Reads in the pillar match, no globbing
        '''
        log.debug('pillar target: {0}'.format(tgt))
        if delim not in tgt:
            log.error('Got insufficient arguments for pillar match '
                      'statement from master')
            return False
        return salt.utils.subdict_match(self.opts['pillar'],
                                        tgt,
                                        delim=delim,
                                        exact_match=True)

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
                if results or match in ['(', ')']:
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
            return eval(results)  # pylint: disable=W0123
        except Exception:
            log.error('Invalid compound target: {0} for results: {1}'.format(tgt, results))
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

        self._running = None
        # Warn if ZMQ < 3.2
        if HAS_ZMQ:
            try:
                zmq_version_info = zmq.zmq_version_info()
            except AttributeError:
                # PyZMQ <= 2.1.9 does not have zmq_version_info, fall back to
                # using zmq.zmq_version() and build a version info tuple.
                zmq_version_info = tuple(
                    [int(x) for x in zmq.zmq_version().split('.')]
                )
            if zmq_version_info < (3, 2):
                log.warning(
                    'You have a version of ZMQ less than ZMQ 3.2! There are '
                    'known connection keep-alive issues with ZMQ < 3.2 which '
                    'may result in loss of contact with minions. Please '
                    'upgrade your ZMQ!'
                )
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
        # self._running = True

    def _prep_mod_opts(self):
        '''
        Returns a copy of the opts with key bits stripped out
        '''
        return super(ProxyMinion, self)._prep_mod_opts()

    def _load_modules(self, force_refresh=False):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        return super(ProxyMinion, self)._load_modules(force_refresh=force_refresh)
