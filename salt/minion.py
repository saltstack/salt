# -*- coding: utf-8 -*-
'''
Routines to set up a minion
'''
# Import python libs
from __future__ import absolute_import, print_function, with_statement
import os
import re
import sys
import copy
import time
import types
import signal
import random
import fnmatch
import logging
import threading
import traceback
import contextlib
import multiprocessing
from random import randint, shuffle
from stat import S_IMODE
import salt.serializers.msgpack
from binascii import crc32

# Import Salt Libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
from salt.ext.six.moves import range
# pylint: enable=no-name-in-module,redefined-builtin

# Import third party libs
try:
    import zmq
    # TODO: cleanup
    import zmq.eventloop.ioloop
    # support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
    if not hasattr(zmq.eventloop.ioloop, u'ZMQIOLoop'):
        zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
    LOOP_CLASS = zmq.eventloop.ioloop.ZMQIOLoop
    HAS_ZMQ = True
except ImportError:
    import tornado.ioloop
    LOOP_CLASS = tornado.ioloop.IOLoop
    HAS_ZMQ = False

HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

HAS_PSUTIL = False
try:
    import salt.utils.psutil_compat as psutil
    HAS_PSUTIL = True
except ImportError:
    pass

HAS_RESOURCE = False
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    pass

try:
    import zmq.utils.monitor
    HAS_ZMQ_MONITOR = True
except ImportError:
    HAS_ZMQ_MONITOR = False

try:
    import salt.utils.win_functions
    HAS_WIN_FUNCTIONS = True
except ImportError:
    HAS_WIN_FUNCTIONS = False
# pylint: enable=import-error

# Import salt libs
import salt
import salt.client
import salt.crypt
import salt.loader
import salt.beacons
import salt.engines
import salt.payload
import salt.pillar
import salt.syspaths
import salt.utils.args
import salt.utils.context
import salt.utils.data
import salt.utils.error
import salt.utils.event
import salt.utils.files
import salt.utils.jid
import salt.utils.minion
import salt.utils.minions
import salt.utils.network
import salt.utils.platform
import salt.utils.process
import salt.utils.schedule
import salt.utils.user
import salt.utils.zeromq
import salt.defaults.exitcodes
import salt.cli.daemons
import salt.log.setup

import salt.utils.dictupdate
from salt.config import DEFAULT_MINION_OPTS
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.utils.debug import enable_sigusr1_handler
from salt.utils.event import tagify
from salt.utils.odict import OrderedDict
from salt.utils.process import (default_signals,
                                SignalHandlingMultiprocessingProcess,
                                ProcessManager)
from salt.exceptions import (
    CommandExecutionError,
    CommandNotFoundError,
    SaltInvocationError,
    SaltReqTimeoutError,
    SaltClientError,
    SaltSystemExit,
    SaltDaemonNotRunning,
    SaltException,
)


import tornado.gen  # pylint: disable=F0401
import tornado.ioloop  # pylint: disable=F0401

log = logging.getLogger(__name__)

# To set up a minion:
# 1. Read in the configuration
# 2. Generate the function mapping dict
# 3. Authenticate with the master
# 4. Store the AES key
# 5. Connect to the publisher
# 6. Handle publications


def resolve_dns(opts, fallback=True):
    '''
    Resolves the master_ip and master_uri options
    '''
    ret = {}
    check_dns = True
    if (opts.get(u'file_client', u'remote') == u'local' and
            not opts.get(u'use_master_when_local', False)):
        check_dns = False

    if check_dns is True:
        # Because I import salt.log below I need to re-import salt.utils here
        import salt.utils
        try:
            if opts[u'master'] == u'':
                raise SaltSystemExit
            ret[u'master_ip'] = salt.utils.network.dns_check(
                opts[u'master'],
                int(opts[u'master_port']),
                True,
                opts[u'ipv6'])
        except SaltClientError:
            if opts[u'retry_dns']:
                while True:
                    import salt.log
                    msg = (u'Master hostname: \'{0}\' not found or not responsive. '
                           u'Retrying in {1} seconds').format(opts[u'master'], opts[u'retry_dns'])
                    if salt.log.setup.is_console_configured():
                        log.error(msg)
                    else:
                        print(u'WARNING: {0}'.format(msg))
                    time.sleep(opts[u'retry_dns'])
                    try:
                        ret[u'master_ip'] = salt.utils.network.dns_check(
                            opts[u'master'],
                            int(opts[u'master_port']),
                            True,
                            opts[u'ipv6'])
                        break
                    except SaltClientError:
                        pass
            else:
                if fallback:
                    ret[u'master_ip'] = u'127.0.0.1'
                else:
                    raise
        except SaltSystemExit:
            unknown_str = u'unknown address'
            master = opts.get(u'master', unknown_str)
            if master == u'':
                master = unknown_str
            if opts.get(u'__role') == u'syndic':
                err = u'Master address: \'{0}\' could not be resolved. Invalid or unresolveable address. ' \
                      u'Set \'syndic_master\' value in minion config.'.format(master)
            else:
                err = u'Master address: \'{0}\' could not be resolved. Invalid or unresolveable address. ' \
                      u'Set \'master\' value in minion config.'.format(master)
            log.error(err)
            raise SaltSystemExit(code=42, msg=err)
    else:
        ret[u'master_ip'] = u'127.0.0.1'

    if u'master_ip' in ret and u'master_ip' in opts:
        if ret[u'master_ip'] != opts[u'master_ip']:
            log.warning(
                u'Master ip address changed from %s to %s',
                opts[u'master_ip'], ret[u'master_ip']
            )
    if opts[u'source_interface_name']:
        log.trace('Custom source interface required: %s', opts[u'source_interface_name'])
        interfaces = salt.utils.network.interfaces()
        log.trace('The following interfaces are available on this Minion:')
        log.trace(interfaces)
        if opts[u'source_interface_name'] in interfaces:
            if interfaces[opts[u'source_interface_name']]['up']:
                addrs = interfaces[opts[u'source_interface_name']]['inet'] if not opts[u'ipv6'] else\
                        interfaces[opts[u'source_interface_name']]['inet6']
                ret[u'source_ip'] = addrs[0]['address']
                log.debug('Using %s as source IP address', ret[u'source_ip'])
            else:
                log.warning('The interface %s is down so it cannot be used as source to connect to the Master',
                            opts[u'source_interface_name'])
        else:
            log.warning('%s is not a valid interface. Ignoring.', opts[u'source_interface_name'])
    elif opts[u'source_address']:
        ret[u'source_ip'] = salt.utils.network.dns_check(
            opts[u'source_address'],
            int(opts[u'source_ret_port']),
            True,
            opts[u'ipv6'])
        log.debug('Using %s as source IP address', ret[u'source_ip'])
    if opts[u'source_ret_port']:
        ret[u'source_ret_port'] = int(opts[u'source_ret_port'])
        log.debug('Using %d as source port for the ret server', ret[u'source_ret_port'])
    if opts[u'source_publish_port']:
        ret[u'source_publish_port'] = int(opts[u'source_publish_port'])
        log.debug('Using %d as source port for the master pub', ret[u'source_publish_port'])
    ret[u'master_uri'] = u'tcp://{ip}:{port}'.format(
        ip=ret[u'master_ip'], port=opts[u'master_port'])
    log.debug('Master URI: %s', ret[u'master_uri'])

    return ret


def prep_ip_port(opts):
    ret = {}
    # Use given master IP if "ip_only" is set or if master_ip is an ipv6 address without
    # a port specified. The is_ipv6 check returns False if brackets are used in the IP
    # definition such as master: '[::1]:1234'.
    if opts[u'master_uri_format'] == u'ip_only' or salt.utils.network.is_ipv6(opts[u'master']):
        ret[u'master'] = opts[u'master']
    else:
        ip_port = opts[u'master'].rsplit(u':', 1)
        if len(ip_port) == 1:
            # e.g. master: mysaltmaster
            ret[u'master'] = ip_port[0]
        else:
            # e.g. master: localhost:1234
            # e.g. master: 127.0.0.1:1234
            # e.g. master: [::1]:1234
            # Strip off brackets for ipv6 support
            ret[u'master'] = ip_port[0].strip(u'[]')

            # Cast port back to an int! Otherwise a TypeError is thrown
            # on some of the socket calls elsewhere in the minion and utils code.
            ret[u'master_port'] = int(ip_port[1])
    return ret


def get_proc_dir(cachedir, **kwargs):
    '''
    Given the cache directory, return the directory that process data is
    stored in, creating it if it doesn't exist.
    The following optional Keyword Arguments are handled:

    mode: which is anything os.makedir would accept as mode.

    uid: the uid to set, if not set, or it is None or -1 no changes are
         made. Same applies if the directory is already owned by this
         uid. Must be int. Works only on unix/unix like systems.

    gid: the gid to set, if not set, or it is None or -1 no changes are
         made. Same applies if the directory is already owned by this
         gid. Must be int. Works only on unix/unix like systems.
    '''
    fn_ = os.path.join(cachedir, u'proc')
    mode = kwargs.pop(u'mode', None)

    if mode is None:
        mode = {}
    else:
        mode = {u'mode': mode}

    if not os.path.isdir(fn_):
        # proc_dir is not present, create it with mode settings
        os.makedirs(fn_, **mode)

    d_stat = os.stat(fn_)

    # if mode is not an empty dict then we have an explicit
    # dir mode. So lets check if mode needs to be changed.
    if mode:
        mode_part = S_IMODE(d_stat.st_mode)
        if mode_part != mode[u'mode']:
            os.chmod(fn_, (d_stat.st_mode ^ mode_part) | mode[u'mode'])

    if hasattr(os, u'chown'):
        # only on unix/unix like systems
        uid = kwargs.pop(u'uid', -1)
        gid = kwargs.pop(u'gid', -1)

        # if uid and gid are both -1 then go ahead with
        # no changes at all
        if (d_stat.st_uid != uid or d_stat.st_gid != gid) and \
                [i for i in (uid, gid) if i != -1]:
            os.chown(fn_, uid, gid)

    return fn_


def load_args_and_kwargs(func, args, data=None, ignore_invalid=False):
    '''
    Detect the args and kwargs that need to be passed to a function call, and
    check them against what was passed.
    '''
    argspec = salt.utils.args.get_function_argspec(func)
    _args = []
    _kwargs = {}
    invalid_kwargs = []

    for arg in args:
        if isinstance(arg, dict) and arg.pop(u'__kwarg__', False) is True:
            # if the arg is a dict with __kwarg__ == True, then its a kwarg
            for key, val in six.iteritems(arg):
                if argspec.keywords or key in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    _kwargs[key] = val
                else:
                    # **kwargs not in argspec and parsed argument name not in
                    # list of positional arguments. This keyword argument is
                    # invalid.
                    invalid_kwargs.append(u'{0}={1}'.format(key, val))
            continue

        else:
            string_kwarg = salt.utils.args.parse_input([arg], condition=False)[1]  # pylint: disable=W0632
            if string_kwarg:
                if argspec.keywords or next(six.iterkeys(string_kwarg)) in argspec.args:
                    # Function supports **kwargs or is a positional argument to
                    # the function.
                    _kwargs.update(string_kwarg)
                else:
                    # **kwargs not in argspec and parsed argument name not in
                    # list of positional arguments. This keyword argument is
                    # invalid.
                    for key, val in six.iteritems(string_kwarg):
                        invalid_kwargs.append(u'{0}={1}'.format(key, val))
            else:
                _args.append(arg)

    if invalid_kwargs and not ignore_invalid:
        salt.utils.args.invalid_kwargs(invalid_kwargs)

    if argspec.keywords and isinstance(data, dict):
        # this function accepts **kwargs, pack in the publish data
        for key, val in six.iteritems(data):
            _kwargs[u'__pub_{0}'.format(key)] = val

    return _args, _kwargs


def eval_master_func(opts):
    '''
    Evaluate master function if master type is 'func'
    and save it result in opts['master']
    '''
    if u'__master_func_evaluated' not in opts:
        # split module and function and try loading the module
        mod_fun = opts[u'master']
        mod, fun = mod_fun.split(u'.')
        try:
            master_mod = salt.loader.raw_mod(opts, mod, fun)
            if not master_mod:
                raise KeyError
            # we take whatever the module returns as master address
            opts[u'master'] = master_mod[mod_fun]()
            # Check for valid types
            if not isinstance(opts[u'master'], (six.string_types, list)):
                raise TypeError
            opts[u'__master_func_evaluated'] = True
        except KeyError:
            log.error(u'Failed to load module %s', mod_fun)
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except TypeError:
            log.error(u'%s returned from %s is not a string', opts[u'master'], mod_fun)
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        log.info(u'Evaluated master from module: %s', mod_fun)


def master_event(type, master=None):
    '''
    Centralized master event function which will return event type based on event_map
    '''
    event_map = {u'connected': u'__master_connected',
                 u'disconnected': u'__master_disconnected',
                 u'failback': u'__master_failback',
                 u'alive': u'__master_alive'}

    if type == u'alive' and master is not None:
        return u'{0}_{1}'.format(event_map.get(type), master)

    return event_map.get(type, None)


class MinionBase(object):
    def __init__(self, opts):
        self.opts = opts

    @staticmethod
    def process_schedule(minion, loop_interval):
        try:
            if hasattr(minion, u'schedule'):
                minion.schedule.eval()
            else:
                log.error(u'Minion scheduler not initialized. Scheduled jobs will not be run.')
                return
            # Check if scheduler requires lower loop interval than
            # the loop_interval setting
            if minion.schedule.loop_interval < loop_interval:
                loop_interval = minion.schedule.loop_interval
                log.debug(
                    u'Overriding loop_interval because of scheduled jobs.'
                )
        except Exception as exc:
            log.error(u'Exception %s occurred in scheduled job', exc)
        return loop_interval

    def process_beacons(self, functions):
        '''
        Evaluate all of the configured beacons, grab the config again in case
        the pillar or grains changed
        '''
        if u'config.merge' in functions:
            b_conf = functions[u'config.merge'](u'beacons', self.opts[u'beacons'], omit_opts=True)
            if b_conf:
                return self.beacons.process(b_conf, self.opts[u'grains'])  # pylint: disable=no-member
        return []

    @tornado.gen.coroutine
    def eval_master(self,
                    opts,
                    timeout=60,
                    safe=True,
                    failed=False,
                    failback=False):
        '''
        Evaluates and returns a tuple of the current master address and the pub_channel.

        In standard mode, just creates a pub_channel with the given master address.

        With master_type=func evaluates the current master address from the given
        module and then creates a pub_channel.

        With master_type=failover takes the list of masters and loops through them.
        The first one that allows the minion to create a pub_channel is then
        returned. If this function is called outside the minions initialization
        phase (for example from the minions main event-loop when a master connection
        loss was detected), 'failed' should be set to True. The current
        (possibly failed) master will then be removed from the list of masters.
        '''
        # return early if we are not connecting to a master
        if opts[u'master_type'] == u'disable':
            log.warning(u'Master is set to disable, skipping connection')
            self.connected = False
            raise tornado.gen.Return((None, None))
        # check if master_type was altered from its default
        elif opts[u'master_type'] != u'str' and opts[u'__role'] != u'syndic':
            # check for a valid keyword
            if opts[u'master_type'] == u'func':
                eval_master_func(opts)

            # if failover or distributed is set, master has to be of type list
            elif opts[u'master_type'] in (u'failover', u'distributed'):
                if isinstance(opts[u'master'], list):
                    log.info(
                        u'Got list of available master addresses: %s',
                        opts[u'master']
                    )

                    if opts[u'master_type'] == u'distributed':
                        master_len = len(opts[u'master'])
                        if master_len > 1:
                            secondary_masters = opts[u'master'][1:]
                            master_idx = crc32(opts[u'id']) % master_len
                            try:
                                preferred_masters = opts[u'master']
                                preferred_masters[0] = opts[u'master'][master_idx]
                                preferred_masters[1:] = [m for m in opts[u'master'] if m != preferred_masters[0]]
                                opts[u'master'] = preferred_masters
                                log.info(u'Distributed to the master at \'{0}\'.'.format(opts[u'master'][0]))
                            except (KeyError, AttributeError, TypeError):
                                log.warning(u'Failed to distribute to a specific master.')
                        else:
                            log.warning(u'master_type = distributed needs more than 1 master.')

                    if opts[u'master_shuffle']:
                        if opts[u'master_failback']:
                            secondary_masters = opts[u'master'][1:]
                            shuffle(secondary_masters)
                            opts[u'master'][1:] = secondary_masters
                        else:
                            shuffle(opts[u'master'])
                    opts[u'auth_tries'] = 0
                    if opts[u'master_failback'] and opts[u'master_failback_interval'] == 0:
                        opts[u'master_failback_interval'] = opts[u'master_alive_interval']
                # if opts['master'] is a str and we have never created opts['master_list']
                elif isinstance(opts[u'master'], six.string_types) and (u'master_list' not in opts):
                    # We have a string, but a list was what was intended. Convert.
                    # See issue 23611 for details
                    opts[u'master'] = [opts[u'master']]
                elif opts[u'__role'] == u'syndic':
                    log.info(u'Syndic setting master_syndic to \'%s\'', opts[u'master'])

                # if failed=True, the minion was previously connected
                # we're probably called from the minions main-event-loop
                # because a master connection loss was detected. remove
                # the possibly failed master from the list of masters.
                elif failed:
                    if failback:
                        # failback list of masters to original config
                        opts[u'master'] = opts[u'master_list']
                    else:
                        log.info(
                            u'Moving possibly failed master %s to the end of '
                            u'the list of masters', opts[u'master']
                        )
                        if opts[u'master'] in opts[u'local_masters']:
                            # create new list of master with the possibly failed
                            # one moved to the end
                            failed_master = opts[u'master']
                            opts[u'master'] = [x for x in opts[u'local_masters'] if opts[u'master'] != x]
                            opts[u'master'].append(failed_master)
                        else:
                            opts[u'master'] = opts[u'master_list']
                else:
                    msg = (u'master_type set to \'failover\' but \'master\' '
                           u'is not of type list but of type '
                           u'{0}'.format(type(opts[u'master'])))
                    log.error(msg)
                    sys.exit(salt.defaults.exitcodes.EX_GENERIC)
                # If failover is set, minion have to failover on DNS errors instead of retry DNS resolve.
                # See issue 21082 for details
                if opts[u'retry_dns'] and opts[u'master_type'] == u'failover':
                    msg = (u'\'master_type\' set to \'failover\' but \'retry_dns\' is not 0. '
                           u'Setting \'retry_dns\' to 0 to failover to the next master on DNS errors.')
                    log.critical(msg)
                    opts[u'retry_dns'] = 0
            else:
                msg = (u'Invalid keyword \'{0}\' for variable '
                       u'\'master_type\''.format(opts[u'master_type']))
                log.error(msg)
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)

        # FIXME: if SMinion don't define io_loop, it can't switch master see #29088
        # Specify kwargs for the channel factory so that SMinion doesn't need to define an io_loop
        # (The channel factories will set a default if the kwarg isn't passed)
        factory_kwargs = {u'timeout': timeout, u'safe': safe}
        if getattr(self, u'io_loop', None):
            factory_kwargs[u'io_loop'] = self.io_loop  # pylint: disable=no-member

        tries = opts.get(u'master_tries', 1)
        attempts = 0

        # if we have a list of masters, loop through them and be
        # happy with the first one that allows us to connect
        if isinstance(opts[u'master'], list):
            conn = False
            # shuffle the masters and then loop through them
            opts[u'local_masters'] = copy.copy(opts[u'master'])
            if opts[u'random_master']:
                shuffle(opts[u'local_masters'])
            last_exc = None
            opts[u'master_uri_list'] = list()

            # This sits outside of the connection loop below because it needs to set
            # up a list of master URIs regardless of which masters are available
            # to connect _to_. This is primarily used for masterless mode, when
            # we need a list of master URIs to fire calls back to.
            for master in opts[u'local_masters']:
                opts[u'master'] = master
                opts.update(prep_ip_port(opts))
                opts[u'master_uri_list'].append(resolve_dns(opts)[u'master_uri'])

            while True:
                if attempts != 0:
                    # Give up a little time between connection attempts
                    # to allow the IOLoop to run any other scheduled tasks.
                    yield tornado.gen.sleep(opts[u'acceptance_wait_time'])
                attempts += 1
                if tries > 0:
                    log.debug(
                        u'Connecting to master. Attempt %s of %s',
                        attempts, tries
                    )
                else:
                    log.debug(
                        u'Connecting to master. Attempt %s (infinite attempts)',
                        attempts
                    )
                for master in opts[u'local_masters']:
                    opts[u'master'] = master
                    opts.update(prep_ip_port(opts))
                    opts.update(resolve_dns(opts))

                    # on first run, update self.opts with the whole master list
                    # to enable a minion to re-use old masters if they get fixed
                    if u'master_list' not in opts:
                        opts[u'master_list'] = copy.copy(opts[u'local_masters'])

                    self.opts = opts

                    try:
                        pub_channel = salt.transport.client.AsyncPubChannel.factory(opts, **factory_kwargs)
                        yield pub_channel.connect()
                        conn = True
                        break
                    except SaltClientError as exc:
                        last_exc = exc
                        log.info(
                            u'Master %s could not be reached, trying next '
                            u'next master (if any)', opts[u'master']
                        )
                        continue

                if not conn:
                    if attempts == tries:
                        # Exhausted all attempts. Return exception.
                        self.connected = False
                        self.opts[u'master'] = copy.copy(self.opts[u'local_masters'])
                        log.error(
                            u'No master could be reached or all masters '
                            u'denied the minion\'s connection attempt.'
                        )
                        # If the code reaches this point, 'last_exc'
                        # should already be set.
                        raise last_exc  # pylint: disable=E0702
                else:
                    self.tok = pub_channel.auth.gen_token(u'salt')
                    self.connected = True
                    raise tornado.gen.Return((opts[u'master'], pub_channel))

        # single master sign in
        else:
            if opts[u'random_master']:
                log.warning(u'random_master is True but there is only one master specified. Ignoring.')
            while True:
                if attempts != 0:
                    # Give up a little time between connection attempts
                    # to allow the IOLoop to run any other scheduled tasks.
                    yield tornado.gen.sleep(opts[u'acceptance_wait_time'])
                attempts += 1
                if tries > 0:
                    log.debug(
                        u'Connecting to master. Attempt %s of %s',
                        attempts, tries
                    )
                else:
                    log.debug(
                        u'Connecting to master. Attempt %s (infinite attempts)',
                        attempts
                    )
                opts.update(prep_ip_port(opts))
                opts.update(resolve_dns(opts))
                try:
                    if self.opts[u'transport'] == u'detect':
                        self.opts[u'detect_mode'] = True
                        for trans in (u'zeromq', u'tcp'):
                            if trans == u'zeromq' and not HAS_ZMQ:
                                continue
                            self.opts[u'transport'] = trans
                            pub_channel = salt.transport.client.AsyncPubChannel.factory(self.opts, **factory_kwargs)
                            yield pub_channel.connect()
                            if not pub_channel.auth.authenticated:
                                continue
                            del self.opts[u'detect_mode']
                            break
                    else:
                        pub_channel = salt.transport.client.AsyncPubChannel.factory(self.opts, **factory_kwargs)
                        yield pub_channel.connect()
                    self.tok = pub_channel.auth.gen_token(u'salt')
                    self.connected = True
                    raise tornado.gen.Return((opts[u'master'], pub_channel))
                except SaltClientError as exc:
                    if attempts == tries:
                        # Exhausted all attempts. Return exception.
                        self.connected = False
                        raise exc

    def _return_retry_timer(self):
        '''
        Based on the minion configuration, either return a randomized timer or
        just return the value of the return_retry_timer.
        '''
        msg = u'Minion return retry timer set to {0} seconds'
        # future lint: disable=str-format-in-logging
        if self.opts.get(u'return_retry_timer_max'):
            try:
                random_retry = randint(self.opts[u'return_retry_timer'], self.opts[u'return_retry_timer_max'])
                log.debug(msg.format(random_retry) + u' (randomized)')
                return random_retry
            except ValueError:
                # Catch wiseguys using negative integers here
                log.error(
                    u'Invalid value (return_retry_timer: %s or '
                    u'return_retry_timer_max: %s). Both must be positive '
                    u'integers.',
                    self.opts[u'return_retry_timer'],
                    self.opts[u'return_retry_timer_max'],
                )
                log.debug(msg.format(DEFAULT_MINION_OPTS[u'return_retry_timer']))
                return DEFAULT_MINION_OPTS[u'return_retry_timer']
        else:
            log.debug(msg.format(self.opts.get(u'return_retry_timer')))
            return self.opts.get(u'return_retry_timer')
        # future lint: enable=str-format-in-logging


class SMinion(MinionBase):
    '''
    Create an object that has loaded all of the minion module functions,
    grains, modules, returners etc.  The SMinion allows developers to
    generate all of the salt minion functions and present them with these
    functions for general use.
    '''
    def __init__(self, opts):
        # Late setup of the opts grains, so we can log from the grains module
        opts[u'grains'] = salt.loader.grains(opts)
        super(SMinion, self).__init__(opts)

        # Clean out the proc directory (default /var/cache/salt/minion/proc)
        if (self.opts.get(u'file_client', u'remote') == u'remote'
                or self.opts.get(u'use_master_when_local', False)):
            if self.opts[u'transport'] == u'zeromq' and HAS_ZMQ:
                io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
            else:
                io_loop = LOOP_CLASS.current()
            io_loop.run_sync(
                lambda: self.eval_master(self.opts, failed=True)
            )
        self.gen_modules(initial_load=True)

        # If configured, cache pillar data on the minion
        if self.opts[u'file_client'] == u'remote' and self.opts.get(u'minion_pillar_cache', False):
            import yaml
            from salt.utils.yamldumper import SafeOrderedDumper
            pdir = os.path.join(self.opts[u'cachedir'], u'pillar')
            if not os.path.isdir(pdir):
                os.makedirs(pdir, 0o700)
            ptop = os.path.join(pdir, u'top.sls')
            if self.opts[u'saltenv'] is not None:
                penv = self.opts[u'saltenv']
            else:
                penv = u'base'
            cache_top = {penv: {self.opts[u'id']: [u'cache']}}
            with salt.utils.files.fopen(ptop, u'wb') as fp_:
                fp_.write(
                    yaml.dump(
                        cache_top,
                        Dumper=SafeOrderedDumper
                    )
                )
                os.chmod(ptop, 0o600)
            cache_sls = os.path.join(pdir, u'cache.sls')
            with salt.utils.files.fopen(cache_sls, u'wb') as fp_:
                fp_.write(
                    yaml.dump(
                        self.opts[u'pillar'],
                        Dumper=SafeOrderedDumper
                    )
                )
                os.chmod(cache_sls, 0o600)

    def gen_modules(self, initial_load=False):
        '''
        Tell the minion to reload the execution modules

        CLI Example:

        .. code-block:: bash

            salt '*' sys.reload_modules
        '''
        self.opts[u'pillar'] = salt.pillar.get_pillar(
            self.opts,
            self.opts[u'grains'],
            self.opts[u'id'],
            self.opts[u'saltenv'],
            pillarenv=self.opts.get(u'pillarenv'),
        ).compile_pillar()

        self.utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(self.opts, utils=self.utils)
        self.serializers = salt.loader.serializers(self.opts)
        self.returners = salt.loader.returners(self.opts, self.functions)
        self.proxy = salt.loader.proxy(self.opts, self.functions, self.returners, None)
        # TODO: remove
        self.function_errors = {}  # Keep the funcs clean
        self.states = salt.loader.states(self.opts,
                self.functions,
                self.utils,
                self.serializers)
        self.rend = salt.loader.render(self.opts, self.functions)
        self.matcher = Matcher(self.opts, self.functions)
        self.functions[u'sys.reload_modules'] = self.gen_modules
        self.executors = salt.loader.executors(self.opts)


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
            whitelist=None,
            ignore_config_errors=True):
        self.opts = salt.config.minion_config(opts[u'conf_file'], ignore_config_errors=ignore_config_errors)
        self.opts.update(opts)
        self.whitelist = whitelist
        self.opts[u'grains'] = salt.loader.grains(opts)
        self.opts[u'pillar'] = {}
        self.mk_returners = returners
        self.mk_states = states
        self.mk_rend = rend
        self.mk_matcher = matcher
        self.gen_modules(initial_load=True)

    def gen_modules(self, initial_load=False):
        '''
        Tell the minion to reload the execution modules

        CLI Example:

        .. code-block:: bash

            salt '*' sys.reload_modules
        '''
        self.utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(
            self.opts,
            utils=self.utils,
            whitelist=self.whitelist,
            initial_load=initial_load)
        self.serializers = salt.loader.serializers(self.opts)
        if self.mk_returners:
            self.returners = salt.loader.returners(self.opts, self.functions)
        if self.mk_states:
            self.states = salt.loader.states(self.opts,
                                             self.functions,
                                             self.utils,
                                             self.serializers)
        if self.mk_rend:
            self.rend = salt.loader.render(self.opts, self.functions)
        if self.mk_matcher:
            self.matcher = Matcher(self.opts, self.functions)
        self.functions[u'sys.reload_modules'] = self.gen_modules


class MinionManager(MinionBase):
    '''
    Create a multi minion interface, this creates as many minions as are
    defined in the master option and binds each minion object to a respective
    master.
    '''
    def __init__(self, opts):
        super(MinionManager, self).__init__(opts)
        self.auth_wait = self.opts[u'acceptance_wait_time']
        self.max_auth_wait = self.opts[u'acceptance_wait_time_max']
        self.minions = []
        self.jid_queue = []
        if HAS_ZMQ:
            zmq.eventloop.ioloop.install()
        if 'standalone_proxy' in opts and opts['standalone_proxy']:
            self.io_loop = tornado.ioloop.IOLoop.instance()
        else:
            self.io_loop = LOOP_CLASS.current()
        self.process_manager = ProcessManager(name=u'MultiMinionProcessManager')
        self.io_loop.spawn_callback(self.process_manager.run, async=True)

    def __del__(self):
        self.destroy()

    def _bind(self):
        # start up the event publisher, so we can see events during startup
        self.event_publisher = salt.utils.event.AsyncEventPublisher(
            self.opts,
            io_loop=self.io_loop,
        )
        self.event = salt.utils.event.get_event(u'minion', opts=self.opts, io_loop=self.io_loop)
        self.event.subscribe(u'')
        self.event.set_event_handler(self.handle_event)

    @tornado.gen.coroutine
    def handle_event(self, package):
        yield [minion.handle_event(package) for minion in self.minions]

    def _create_minion_object(self, opts, timeout, safe,
                              io_loop=None, loaded_base_name=None,
                              jid_queue=None):
        '''
        Helper function to return the correct type of object
        '''
        return Minion(opts,
                      timeout,
                      safe,
                      io_loop=io_loop,
                      loaded_base_name=loaded_base_name,
                      jid_queue=jid_queue)

    def _spawn_minions(self):
        '''
        Spawn all the coroutines which will sign in to masters
        '''
        masters = self.opts[u'master']
        if (self.opts[u'master_type'] in (u'failover', u'distributed')) or not isinstance(self.opts[u'master'], list):
            masters = [masters]

        for master in masters:
            s_opts = copy.deepcopy(self.opts)
            s_opts[u'master'] = master
            s_opts[u'multimaster'] = True
            minion = self._create_minion_object(s_opts,
                                                s_opts[u'auth_timeout'],
                                                False,
                                                io_loop=self.io_loop,
                                                loaded_base_name=u'salt.loader.{0}'.format(s_opts[u'master']),
                                                jid_queue=self.jid_queue,
                                               )
            self.minions.append(minion)
            self.io_loop.spawn_callback(self._connect_minion, minion)

    @tornado.gen.coroutine
    def _connect_minion(self, minion):
        '''
        Create a minion, and asynchronously connect it to a master
        '''
        last = 0  # never have we signed in
        auth_wait = minion.opts[u'acceptance_wait_time']
        failed = False
        while True:
            try:
                yield minion.connect_master(failed=failed)
                minion.tune_in(start=False)
                break
            except SaltClientError as exc:
                failed = True
                log.error(
                    u'Error while bringing up minion for multi-master. Is '
                    u'master at %s responding?', minion.opts[u'master']
                )
                last = time.time()
                if auth_wait < self.max_auth_wait:
                    auth_wait += self.auth_wait
                yield tornado.gen.sleep(auth_wait)  # TODO: log?
            except Exception as e:
                failed = True
                log.critical(
                    u'Unexpected error while connecting to %s',
                    minion.opts[u'master'], exc_info=True
                )

    # Multi Master Tune In
    def tune_in(self):
        '''
        Bind to the masters

        This loop will attempt to create connections to masters it hasn't connected
        to yet, but once the initial connection is made it is up to ZMQ to do the
        reconnect (don't know of an API to get the state here in salt)
        '''
        self._bind()

        # Fire off all the minion coroutines
        self._spawn_minions()

        # serve forever!
        self.io_loop.start()

    @property
    def restart(self):
        for minion in self.minions:
            if minion.restart:
                return True
        return False

    def stop(self, signum):
        for minion in self.minions:
            minion.process_manager.stop_restarting()
            minion.process_manager.send_signal_to_processes(signum)
            # kill any remaining processes
            minion.process_manager.kill_children()
            minion.destroy()

    def destroy(self):
        for minion in self.minions:
            minion.destroy()


class Minion(MinionBase):
    '''
    This class instantiates a minion, runs connections for a minion,
    and loads all of the functions into the minion
    '''
    def __init__(self, opts, timeout=60, safe=True, loaded_base_name=None, io_loop=None, jid_queue=None):  # pylint: disable=W0231
        '''
        Pass in the options dict
        '''
        # this means that the parent class doesn't know *which* master we connect to
        super(Minion, self).__init__(opts)
        self.timeout = timeout
        self.safe = safe

        self._running = None
        self.win_proc = []
        self.loaded_base_name = loaded_base_name
        self.connected = False
        self.restart = False
        # Flag meaning minion has finished initialization including first connect to the master.
        # True means the Minion is fully functional and ready to handle events.
        self.ready = False
        self.jid_queue = jid_queue or []

        if io_loop is None:
            if HAS_ZMQ:
                zmq.eventloop.ioloop.install()
            self.io_loop = LOOP_CLASS.current()
        else:
            self.io_loop = io_loop

        # Warn if ZMQ < 3.2
        if HAS_ZMQ:
            try:
                zmq_version_info = zmq.zmq_version_info()
            except AttributeError:
                # PyZMQ <= 2.1.9 does not have zmq_version_info, fall back to
                # using zmq.zmq_version() and build a version info tuple.
                zmq_version_info = tuple(
                    [int(x) for x in zmq.zmq_version().split(u'.')]  # pylint: disable=no-member
                )
            if zmq_version_info < (3, 2):
                log.warning(
                    u'You have a version of ZMQ less than ZMQ 3.2! There are '
                    u'known connection keep-alive issues with ZMQ < 3.2 which '
                    u'may result in loss of contact with minions. Please '
                    u'upgrade your ZMQ!'
                )
        # Late setup of the opts grains, so we can log from the grains
        # module.  If this is a proxy, however, we need to init the proxymodule
        # before we can get the grains.  We do this for proxies in the
        # post_master_init
        if not salt.utils.platform.is_proxy():
            self.opts[u'grains'] = salt.loader.grains(opts)

        log.info(u'Creating minion process manager')

        if self.opts[u'random_startup_delay']:
            sleep_time = random.randint(0, self.opts[u'random_startup_delay'])
            log.info(
                u'Minion sleeping for %s seconds due to configured '
                u'startup_delay between 0 and %s seconds',
                sleep_time, self.opts[u'random_startup_delay']
            )
            time.sleep(sleep_time)

        self.process_manager = ProcessManager(name=u'MinionProcessManager')
        self.io_loop.spawn_callback(self.process_manager.run, async=True)
        # We don't have the proxy setup yet, so we can't start engines
        # Engines need to be able to access __proxy__
        if not salt.utils.platform.is_proxy():
            self.io_loop.spawn_callback(salt.engines.start_engines, self.opts,
                                        self.process_manager)

        # Install the SIGINT/SIGTERM handlers if not done so far
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGINT, self._handle_signals)

        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGTERM, self._handle_signals)

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        self._running = False
        # escalate the signals to the process manager
        self.process_manager.stop_restarting()
        self.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.process_manager.kill_children()
        time.sleep(1)
        sys.exit(0)

    def sync_connect_master(self, timeout=None, failed=False):
        '''
        Block until we are connected to a master
        '''
        self._sync_connect_master_success = False
        log.debug(u"sync_connect_master")

        def on_connect_master_future_done(future):
            self._sync_connect_master_success = True
            self.io_loop.stop()

        self._connect_master_future = self.connect_master(failed=failed)
        # finish connecting to master
        self._connect_master_future.add_done_callback(on_connect_master_future_done)
        if timeout:
            self.io_loop.call_later(timeout, self.io_loop.stop)
        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            self.destroy()
        # I made the following 3 line oddity to preserve traceback.
        # Please read PR #23978 before changing, hopefully avoiding regressions.
        # Good luck, we're all counting on you.  Thanks.
        future_exception = self._connect_master_future.exc_info()
        if future_exception:
            # This needs to be re-raised to preserve restart_on_error behavior.
            raise six.reraise(*future_exception)
        if timeout and self._sync_connect_master_success is False:
            raise SaltDaemonNotRunning(u'Failed to connect to the salt-master')

    @tornado.gen.coroutine
    def connect_master(self, failed=False):
        '''
        Return a future which will complete when you are connected to a master
        '''
        master, self.pub_channel = yield self.eval_master(self.opts, self.timeout, self.safe, failed)
        yield self._post_master_init(master)

    # TODO: better name...
    @tornado.gen.coroutine
    def _post_master_init(self, master):
        '''
        Function to finish init after connecting to a master

        This is primarily loading modules, pillars, etc. (since they need
        to know which master they connected to)

        If this function is changed, please check ProxyMinion._post_master_init
        to see if those changes need to be propagated.

        Minions and ProxyMinions need significantly different post master setups,
        which is why the differences are not factored out into separate helper
        functions.
        '''
        if self.connected:
            self.opts[u'master'] = master

            # Initialize pillar before loader to make pillar accessible in modules
            self.opts[u'pillar'] = yield salt.pillar.get_async_pillar(
                self.opts,
                self.opts[u'grains'],
                self.opts[u'id'],
                self.opts[u'saltenv'],
                pillarenv=self.opts.get(u'pillarenv')
            ).compile_pillar()

        self.functions, self.returners, self.function_errors, self.executors = self._load_modules()
        self.serial = salt.payload.Serial(self.opts)
        self.mod_opts = self._prep_mod_opts()
        self.matcher = Matcher(self.opts, self.functions)
        self.beacons = salt.beacons.Beacon(self.opts, self.functions)
        uid = salt.utils.user.get_uid(user=self.opts.get(u'user', None))
        self.proc_dir = get_proc_dir(self.opts[u'cachedir'], uid=uid)

        self.schedule = salt.utils.schedule.Schedule(
            self.opts,
            self.functions,
            self.returners,
            cleanup=[master_event(type=u'alive')])

        # add default scheduling jobs to the minions scheduler
        if self.opts[u'mine_enabled'] and u'mine.update' in self.functions:
            self.schedule.add_job({
                u'__mine_interval':
                {
                    u'function': u'mine.update',
                    u'minutes': self.opts[u'mine_interval'],
                    u'jid_include': True,
                    u'maxrunning': 2,
                    u'return_job': self.opts.get(u'mine_return_job', False)
                }
            }, persist=True)
            log.info(u'Added mine.update to scheduler')
        else:
            self.schedule.delete_job(u'__mine_interval', persist=True)

        # add master_alive job if enabled
        if (self.opts[u'transport'] != u'tcp' and
                self.opts[u'master_alive_interval'] > 0 and
                self.connected):
            self.schedule.add_job({
                master_event(type=u'alive', master=self.opts[u'master']):
                {
                    u'function': u'status.master',
                    u'seconds': self.opts[u'master_alive_interval'],
                    u'jid_include': True,
                    u'maxrunning': 1,
                    u'return_job': False,
                    u'kwargs': {u'master': self.opts[u'master'],
                                u'connected': True}
                }
            }, persist=True)
            if self.opts[u'master_failback'] and \
                    u'master_list' in self.opts and \
                    self.opts[u'master'] != self.opts[u'master_list'][0]:
                self.schedule.add_job({
                    master_event(type=u'failback'):
                    {
                        u'function': u'status.ping_master',
                        u'seconds': self.opts[u'master_failback_interval'],
                        u'jid_include': True,
                        u'maxrunning': 1,
                        u'return_job': False,
                        u'kwargs': {u'master': self.opts[u'master_list'][0]}
                    }
                }, persist=True)
            else:
                self.schedule.delete_job(master_event(type=u'failback'), persist=True)
        else:
            self.schedule.delete_job(master_event(type=u'alive', master=self.opts[u'master']), persist=True)
            self.schedule.delete_job(master_event(type=u'failback'), persist=True)

        self.grains_cache = self.opts[u'grains']
        self.ready = True

    def _prep_mod_opts(self):
        '''
        Returns a copy of the opts with key bits stripped out
        '''
        mod_opts = {}
        for key, val in six.iteritems(self.opts):
            if key == u'logger':
                continue
            mod_opts[key] = val
        return mod_opts

    def _load_modules(self, force_refresh=False, notify=False, grains=None):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        # if this is a *nix system AND modules_max_memory is set, lets enforce
        # a memory limit on module imports
        # this feature ONLY works on *nix like OSs (resource module doesn't work on windows)
        modules_max_memory = False
        if self.opts.get(u'modules_max_memory', -1) > 0 and HAS_PSUTIL and HAS_RESOURCE:
            log.debug(
                u'modules_max_memory set, enforcing a maximum of %s',
                self.opts[u'modules_max_memory']
            )
            modules_max_memory = True
            old_mem_limit = resource.getrlimit(resource.RLIMIT_AS)
            rss, vms = psutil.Process(os.getpid()).memory_info()[:2]
            mem_limit = rss + vms + self.opts[u'modules_max_memory']
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        elif self.opts.get(u'modules_max_memory', -1) > 0:
            if not HAS_PSUTIL:
                log.error(u'Unable to enforce modules_max_memory because psutil is missing')
            if not HAS_RESOURCE:
                log.error(u'Unable to enforce modules_max_memory because resource is missing')

        # This might be a proxy minion
        if hasattr(self, u'proxy'):
            proxy = self.proxy
        else:
            proxy = None

        if grains is None:
            self.opts[u'grains'] = salt.loader.grains(self.opts, force_refresh, proxy=proxy)
        self.utils = salt.loader.utils(self.opts, proxy=proxy)

        if self.opts.get(u'multimaster', False):
            s_opts = copy.deepcopy(self.opts)
            functions = salt.loader.minion_mods(s_opts, utils=self.utils, proxy=proxy,
                                                loaded_base_name=self.loaded_base_name, notify=notify)
        else:
            functions = salt.loader.minion_mods(self.opts, utils=self.utils, notify=notify, proxy=proxy)
        returners = salt.loader.returners(self.opts, functions, proxy=proxy)
        errors = {}
        if u'_errors' in functions:
            errors = functions[u'_errors']
            functions.pop(u'_errors')

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)

        executors = salt.loader.executors(self.opts, functions, proxy=proxy)

        return functions, returners, errors, executors

    def _send_req_sync(self, load, timeout):

        if self.opts[u'minion_sign_messages']:
            log.trace(u'Signing event to be published onto the bus.')
            minion_privkey_path = os.path.join(self.opts[u'pki_dir'], u'minion.pem')
            sig = salt.crypt.sign_message(minion_privkey_path, salt.serializers.msgpack.serialize(load))
            load[u'sig'] = sig

        channel = salt.transport.Channel.factory(self.opts)
        return channel.send(load, timeout=timeout)

    @tornado.gen.coroutine
    def _send_req_async(self, load, timeout):

        if self.opts[u'minion_sign_messages']:
            log.trace(u'Signing event to be published onto the bus.')
            minion_privkey_path = os.path.join(self.opts[u'pki_dir'], u'minion.pem')
            sig = salt.crypt.sign_message(minion_privkey_path, salt.serializers.msgpack.serialize(load))
            load[u'sig'] = sig

        channel = salt.transport.client.AsyncReqChannel.factory(self.opts)
        ret = yield channel.send(load, timeout=timeout)
        raise tornado.gen.Return(ret)

    def _fire_master(self, data=None, tag=None, events=None, pretag=None, timeout=60, sync=True, timeout_handler=None):
        '''
        Fire an event on the master, or drop message if unable to send.
        '''
        load = {u'id': self.opts[u'id'],
                u'cmd': u'_minion_event',
                u'pretag': pretag,
                u'tok': self.tok}
        if events:
            load[u'events'] = events
        elif data and tag:
            load[u'data'] = data
            load[u'tag'] = tag
        elif not data and tag:
            load[u'data'] = {}
            load[u'tag'] = tag
        else:
            return

        if sync:
            try:
                self._send_req_sync(load, timeout)
            except salt.exceptions.SaltReqTimeoutError:
                log.info(u'fire_master failed: master could not be contacted. Request timed out.')
                return False
            except Exception:
                log.info(u'fire_master failed: %s', traceback.format_exc())
                return False
        else:
            if timeout_handler is None:
                def handle_timeout(*_):
                    log.info(u'fire_master failed: master could not be contacted. Request timed out.')
                    return True
                timeout_handler = handle_timeout

            with tornado.stack_context.ExceptionStackContext(timeout_handler):
                self._send_req_async(load, timeout, callback=lambda f: None)  # pylint: disable=unexpected-keyword-arg
        return True

    @tornado.gen.coroutine
    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle the decoded data
        differently.
        '''
        if u'user' in data:
            log.info(
                u'User %s Executing command %s with jid %s',
                data[u'user'], data[u'fun'], data[u'jid']
            )
        else:
            log.info(
                u'Executing command %s with jid %s',
                data[u'fun'], data[u'jid']
            )
        log.debug(u'Command details %s', data)

        # Don't duplicate jobs
        log.trace(u'Started JIDs: %s', self.jid_queue)
        if self.jid_queue is not None:
            if data[u'jid'] in self.jid_queue:
                return
            else:
                self.jid_queue.append(data[u'jid'])
                if len(self.jid_queue) > self.opts[u'minion_jid_queue_hwm']:
                    self.jid_queue.pop(0)

        if isinstance(data[u'fun'], six.string_types):
            if data[u'fun'] == u'sys.reload_modules':
                self.functions, self.returners, self.function_errors, self.executors = self._load_modules()
                self.schedule.functions = self.functions
                self.schedule.returners = self.returners

        process_count_max = self.opts.get('process_count_max')
        if process_count_max > 0:
            process_count = len(salt.utils.minion.running(self.opts))
            while process_count >= process_count_max:
                log.warn("Maximum number of processes reached while executing jid {0}, waiting...".format(data['jid']))
                yield tornado.gen.sleep(10)
                process_count = len(salt.utils.minion.running(self.opts))

        # We stash an instance references to allow for the socket
        # communication in Windows. You can't pickle functions, and thus
        # python needs to be able to reconstruct the reference on the other
        # side.
        instance = self
        multiprocessing_enabled = self.opts.get(u'multiprocessing', True)
        if multiprocessing_enabled:
            if sys.platform.startswith(u'win'):
                # let python reconstruct the minion on the other side if we're
                # running on windows
                instance = None
            with default_signals(signal.SIGINT, signal.SIGTERM):
                process = SignalHandlingMultiprocessingProcess(
                    target=self._target, args=(instance, self.opts, data, self.connected)
                )
        else:
            process = threading.Thread(
                target=self._target,
                args=(instance, self.opts, data, self.connected),
                name=data[u'jid']
            )

        if multiprocessing_enabled:
            with default_signals(signal.SIGINT, signal.SIGTERM):
                # Reset current signals before starting the process in
                # order not to inherit the current signal handlers
                process.start()
        else:
            process.start()

        # TODO: remove the windows specific check?
        if multiprocessing_enabled and not salt.utils.platform.is_windows():
            # we only want to join() immediately if we are daemonizing a process
            process.join()
        else:
            self.win_proc.append(process)

    def ctx(self):
        '''
        Return a single context manager for the minion's data
        '''
        if six.PY2:
            return contextlib.nested(
                self.functions.context_dict.clone(),
                self.returners.context_dict.clone(),
                self.executors.context_dict.clone(),
            )
        else:
            exitstack = contextlib.ExitStack()
            exitstack.enter_context(self.functions.context_dict.clone())
            exitstack.enter_context(self.returners.context_dict.clone())
            exitstack.enter_context(self.executors.context_dict.clone())
            return exitstack

    @classmethod
    def _target(cls, minion_instance, opts, data, connected):
        if not minion_instance:
            minion_instance = cls(opts)
            minion_instance.connected = connected
            if not hasattr(minion_instance, u'functions'):
                functions, returners, function_errors, executors = (
                    minion_instance._load_modules(grains=opts[u'grains'])
                    )
                minion_instance.functions = functions
                minion_instance.returners = returners
                minion_instance.function_errors = function_errors
                minion_instance.executors = executors
            if not hasattr(minion_instance, u'serial'):
                minion_instance.serial = salt.payload.Serial(opts)
            if not hasattr(minion_instance, u'proc_dir'):
                uid = salt.utils.user.get_uid(user=opts.get(u'user', None))
                minion_instance.proc_dir = (
                    get_proc_dir(opts[u'cachedir'], uid=uid)
                    )

        with tornado.stack_context.StackContext(minion_instance.ctx):
            if isinstance(data[u'fun'], tuple) or isinstance(data[u'fun'], list):
                Minion._thread_multi_return(minion_instance, opts, data)
            else:
                Minion._thread_return(minion_instance, opts, data)

    @classmethod
    def _thread_return(cls, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        fn_ = os.path.join(minion_instance.proc_dir, data[u'jid'])

        if opts[u'multiprocessing'] and not salt.utils.platform.is_windows():
            # Shutdown the multiprocessing before daemonizing
            salt.log.setup.shutdown_multiprocessing_logging()

            salt.utils.process.daemonize_if(opts)

            # Reconfigure multiprocessing logging after daemonizing
            salt.log.setup.setup_multiprocessing_logging()

        salt.utils.process.appendproctitle(u'{0}._thread_return {1}'.format(cls.__name__, data[u'jid']))

        sdata = {u'pid': os.getpid()}
        sdata.update(data)
        log.info(u'Starting a new job with PID %s', sdata[u'pid'])
        with salt.utils.files.fopen(fn_, u'w+b') as fp_:
            fp_.write(minion_instance.serial.dumps(sdata))
        ret = {u'success': False}
        function_name = data[u'fun']
        if function_name in minion_instance.functions:
            try:
                minion_blackout_violation = False
                if minion_instance.connected and minion_instance.opts[u'pillar'].get(u'minion_blackout', False):
                    whitelist = minion_instance.opts[u'pillar'].get(u'minion_blackout_whitelist', [])
                    # this minion is blacked out. Only allow saltutil.refresh_pillar and the whitelist
                    if function_name != u'saltutil.refresh_pillar' and function_name not in whitelist:
                        minion_blackout_violation = True
                elif minion_instance.opts[u'grains'].get(u'minion_blackout', False):
                    whitelist = minion_instance.opts[u'grains'].get(u'minion_blackout_whitelist', [])
                    if function_name != u'saltutil.refresh_pillar' and function_name not in whitelist:
                        minion_blackout_violation = True
                if minion_blackout_violation:
                    raise SaltInvocationError(u'Minion in blackout mode. Set \'minion_blackout\' '
                                             u'to False in pillar or grains to resume operations. Only '
                                             u'saltutil.refresh_pillar allowed in blackout mode.')

                func = minion_instance.functions[function_name]
                args, kwargs = load_args_and_kwargs(
                    func,
                    data[u'arg'],
                    data)
                minion_instance.functions.pack[u'__context__'][u'retcode'] = 0

                executors = data.get(u'module_executors') or opts.get(u'module_executors', [u'direct_call'])
                if isinstance(executors, six.string_types):
                    executors = [executors]
                elif not isinstance(executors, list) or not executors:
                    raise SaltInvocationError(u"Wrong executors specification: {0}. String or non-empty list expected".
                        format(executors))
                if opts.get(u'sudo_user', u'') and executors[-1] != u'sudo':
                    executors[-1] = u'sudo'  # replace the last one with sudo
                log.trace(u'Executors list %s', executors)  # pylint: disable=no-member

                for name in executors:
                    fname = u'{0}.execute'.format(name)
                    if fname not in minion_instance.executors:
                        raise SaltInvocationError(u"Executor '{0}' is not available".format(name))
                    return_data = minion_instance.executors[fname](opts, data, func, args, kwargs)
                    if return_data is not None:
                        break

                if isinstance(return_data, types.GeneratorType):
                    ind = 0
                    iret = {}
                    for single in return_data:
                        if isinstance(single, dict) and isinstance(iret, dict):
                            iret.update(single)
                        else:
                            if not iret:
                                iret = []
                            iret.append(single)
                        tag = tagify([data[u'jid'], u'prog', opts[u'id'], str(ind)], u'job')
                        event_data = {u'return': single}
                        minion_instance._fire_master(event_data, tag)
                        ind += 1
                    ret[u'return'] = iret
                else:
                    ret[u'return'] = return_data
                ret[u'retcode'] = minion_instance.functions.pack[u'__context__'].get(
                    u'retcode',
                    0
                )
                ret[u'success'] = True
            except CommandNotFoundError as exc:
                msg = u'Command required for \'{0}\' not found'.format(
                    function_name
                )
                log.debug(msg, exc_info=True)
                ret[u'return'] = u'{0}: {1}'.format(msg, exc)
                ret[u'out'] = u'nested'
            except CommandExecutionError as exc:
                log.error(
                    u'A command in \'%s\' had a problem: %s',
                    function_name, exc,
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret[u'return'] = u'ERROR: {0}'.format(exc)
                ret[u'out'] = u'nested'
            except SaltInvocationError as exc:
                log.error(
                    u'Problem executing \'%s\': %s',
                    function_name, exc,
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret[u'return'] = u'ERROR executing \'{0}\': {1}'.format(
                    function_name, exc
                )
                ret[u'out'] = u'nested'
            except TypeError as exc:
                msg = u'Passed invalid arguments to {0}: {1}\n{2}'.format(function_name, exc, func.__doc__)
                log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
                ret[u'return'] = msg
                ret[u'out'] = u'nested'
            except Exception:
                msg = u'The minion function caused an exception'
                log.warning(msg, exc_info_on_loglevel=True)
                salt.utils.error.fire_exception(salt.exceptions.MinionError(msg), opts, job=data)
                ret[u'return'] = u'{0}: {1}'.format(msg, traceback.format_exc())
                ret[u'out'] = u'nested'
        else:
            docs = minion_instance.functions[u'sys.doc'](u'{0}*'.format(function_name))
            if docs:
                docs[function_name] = minion_instance.functions.missing_fun_string(function_name)
                ret[u'return'] = docs
            else:
                ret[u'return'] = minion_instance.functions.missing_fun_string(function_name)
                mod_name = function_name.split('.')[0]
                if mod_name in minion_instance.function_errors:
                    ret[u'return'] += u' Possible reasons: \'{0}\''.format(
                        minion_instance.function_errors[mod_name]
                    )
            ret[u'success'] = False
            ret[u'retcode'] = 254
            ret[u'out'] = u'nested'

        ret[u'jid'] = data[u'jid']
        ret[u'fun'] = data[u'fun']
        ret[u'fun_args'] = data[u'arg']
        if u'master_id' in data:
            ret[u'master_id'] = data[u'master_id']
        if u'metadata' in data:
            if isinstance(data[u'metadata'], dict):
                ret[u'metadata'] = data[u'metadata']
            else:
                log.warning(u'The metadata parameter must be a dictionary. Ignoring.')
        if minion_instance.connected:
            minion_instance._return_pub(
                ret,
                timeout=minion_instance._return_retry_timer()
            )

        # Add default returners from minion config
        # Should have been coverted to comma-delimited string already
        if isinstance(opts.get(u'return'), six.string_types):
            if data[u'ret']:
                data[u'ret'] = u','.join((data[u'ret'], opts[u'return']))
            else:
                data[u'ret'] = opts[u'return']

        log.debug(u'minion return: %s', ret)
        # TODO: make a list? Seems odd to split it this late :/
        if data[u'ret'] and isinstance(data[u'ret'], six.string_types):
            if u'ret_config' in data:
                ret[u'ret_config'] = data[u'ret_config']
            if u'ret_kwargs' in data:
                ret[u'ret_kwargs'] = data[u'ret_kwargs']
            ret[u'id'] = opts[u'id']
            for returner in set(data[u'ret'].split(u',')):
                try:
                    returner_str = u'{0}.returner'.format(returner)
                    if returner_str in minion_instance.returners:
                        minion_instance.returners[returner_str](ret)
                    else:
                        returner_err = minion_instance.returners.missing_fun_string(returner_str)
                        log.error(
                            u'Returner %s could not be loaded: %s',
                            returner_str, returner_err
                        )
                except Exception as exc:
                    log.exception(
                        u'The return failed for job %s: %s', data[u'jid'], exc
                    )

    @classmethod
    def _thread_multi_return(cls, minion_instance, opts, data):
        '''
        This method should be used as a threading target, start the actual
        minion side execution.
        '''
        fn_ = os.path.join(minion_instance.proc_dir, data[u'jid'])

        if opts[u'multiprocessing'] and not salt.utils.platform.is_windows():
            # Shutdown the multiprocessing before daemonizing
            salt.log.setup.shutdown_multiprocessing_logging()

            salt.utils.process.daemonize_if(opts)

            # Reconfigure multiprocessing logging after daemonizing
            salt.log.setup.setup_multiprocessing_logging()

        salt.utils.process.appendproctitle(u'{0}._thread_multi_return {1}'.format(cls.__name__, data[u'jid']))

        sdata = {u'pid': os.getpid()}
        sdata.update(data)
        log.info(u'Starting a new job with PID %s', sdata[u'pid'])
        with salt.utils.files.fopen(fn_, u'w+b') as fp_:
            fp_.write(minion_instance.serial.dumps(sdata))

        multifunc_ordered = opts.get(u'multifunc_ordered', False)
        num_funcs = len(data[u'fun'])
        if multifunc_ordered:
            ret = {
                u'return': [None] * num_funcs,
                u'retcode': [None] * num_funcs,
                u'success': [False] * num_funcs
            }
        else:
            ret = {
                u'return': {},
                u'retcode': {},
                u'success': {}
            }

        for ind in range(0, num_funcs):
            if not multifunc_ordered:
                ret[u'success'][data[u'fun'][ind]] = False
            try:
                minion_blackout_violation = False
                if minion_instance.connected and minion_instance.opts[u'pillar'].get(u'minion_blackout', False):
                    whitelist = minion_instance.opts[u'pillar'].get(u'minion_blackout_whitelist', [])
                    # this minion is blacked out. Only allow saltutil.refresh_pillar and the whitelist
                    if data[u'fun'][ind] != u'saltutil.refresh_pillar' and data[u'fun'][ind] not in whitelist:
                        minion_blackout_violation = True
                elif minion_instance.opts[u'grains'].get(u'minion_blackout', False):
                    whitelist = minion_instance.opts[u'grains'].get(u'minion_blackout_whitelist', [])
                    if data[u'fun'][ind] != u'saltutil.refresh_pillar' and data[u'fun'][ind] not in whitelist:
                        minion_blackout_violation = True
                if minion_blackout_violation:
                    raise SaltInvocationError(u'Minion in blackout mode. Set \'minion_blackout\' '
                                             u'to False in pillar or grains to resume operations. Only '
                                             u'saltutil.refresh_pillar allowed in blackout mode.')

                func = minion_instance.functions[data[u'fun'][ind]]

                args, kwargs = load_args_and_kwargs(
                    func,
                    data[u'arg'][ind],
                    data)
                minion_instance.functions.pack[u'__context__'][u'retcode'] = 0
                if multifunc_ordered:
                    ret[u'return'][ind] = func(*args, **kwargs)
                    ret[u'retcode'][ind] = minion_instance.functions.pack[u'__context__'].get(
                        u'retcode',
                        0
                    )
                    ret[u'success'][ind] = True
                else:
                    ret[u'return'][data[u'fun'][ind]] = func(*args, **kwargs)
                    ret[u'retcode'][data[u'fun'][ind]] = minion_instance.functions.pack[u'__context__'].get(
                        u'retcode',
                        0
                    )
                    ret[u'success'][data[u'fun'][ind]] = True
            except Exception as exc:
                trb = traceback.format_exc()
                log.warning(u'The minion function caused an exception: %s', exc)
                if multifunc_ordered:
                    ret[u'return'][ind] = trb
                else:
                    ret[u'return'][data[u'fun'][ind]] = trb
            ret[u'jid'] = data[u'jid']
            ret[u'fun'] = data[u'fun']
            ret[u'fun_args'] = data[u'arg']
        if u'metadata' in data:
            ret[u'metadata'] = data[u'metadata']
        if minion_instance.connected:
            minion_instance._return_pub(
                ret,
                timeout=minion_instance._return_retry_timer()
            )
        if data[u'ret']:
            if u'ret_config' in data:
                ret[u'ret_config'] = data[u'ret_config']
            if u'ret_kwargs' in data:
                ret[u'ret_kwargs'] = data[u'ret_kwargs']
            for returner in set(data[u'ret'].split(u',')):
                ret[u'id'] = opts[u'id']
                try:
                    minion_instance.returners[u'{0}.returner'.format(
                        returner
                    )](ret)
                except Exception as exc:
                    log.error(
                        u'The return failed for job %s: %s',
                        data[u'jid'], exc
                    )

    def _return_pub(self, ret, ret_cmd=u'_return', timeout=60, sync=True):
        '''
        Return the data from the executed command to the master server
        '''
        jid = ret.get(u'jid', ret.get(u'__jid__'))
        fun = ret.get(u'fun', ret.get(u'__fun__'))
        if self.opts[u'multiprocessing']:
            fn_ = os.path.join(self.proc_dir, jid)
            if os.path.isfile(fn_):
                try:
                    os.remove(fn_)
                except (OSError, IOError):
                    # The file is gone already
                    pass
        log.info(u'Returning information for job: %s', jid)
        if ret_cmd == u'_syndic_return':
            load = {u'cmd': ret_cmd,
                    u'id': self.opts[u'uid'],
                    u'jid': jid,
                    u'fun': fun,
                    u'arg': ret.get(u'arg'),
                    u'tgt': ret.get(u'tgt'),
                    u'tgt_type': ret.get(u'tgt_type'),
                    u'load': ret.get(u'__load__')}
            if u'__master_id__' in ret:
                load[u'master_id'] = ret[u'__master_id__']
            load[u'return'] = {}
            for key, value in six.iteritems(ret):
                if key.startswith(u'__'):
                    continue
                load[u'return'][key] = value
        else:
            load = {u'cmd': ret_cmd,
                    u'id': self.opts[u'id']}
            for key, value in six.iteritems(ret):
                load[key] = value

        if u'out' in ret:
            if isinstance(ret[u'out'], six.string_types):
                load[u'out'] = ret[u'out']
            else:
                log.error(
                    u'Invalid outputter %s. This is likely a bug.',
                    ret[u'out']
                )
        else:
            try:
                oput = self.functions[fun].__outputter__
            except (KeyError, AttributeError, TypeError):
                pass
            else:
                if isinstance(oput, six.string_types):
                    load[u'out'] = oput
        if self.opts[u'cache_jobs']:
            # Local job cache has been enabled
            salt.utils.minion.cache_jobs(self.opts, load[u'jid'], ret)

        if not self.opts[u'pub_ret']:
            return u''

        def timeout_handler(*_):
            log.warning(
               u'The minion failed to return the job information for job %s. '
               u'This is often due to the master being shut down or '
               u'overloaded. If the master is running, consider increasing '
               u'the worker_threads value.', jid
            )
            return True

        if sync:
            try:
                ret_val = self._send_req_sync(load, timeout=timeout)
            except SaltReqTimeoutError:
                timeout_handler()
                return u''
        else:
            with tornado.stack_context.ExceptionStackContext(timeout_handler):
                ret_val = self._send_req_async(load, timeout=timeout, callback=lambda f: None)  # pylint: disable=unexpected-keyword-arg

        log.trace(u'ret_val = %s', ret_val)  # pylint: disable=no-member
        return ret_val

    def _return_pub_multi(self, rets, ret_cmd='_return', timeout=60, sync=True):
        '''
        Return the data from the executed command to the master server
        '''
        if not isinstance(rets, list):
            rets = [rets]
        jids = {}
        for ret in rets:
            jid = ret.get(u'jid', ret.get(u'__jid__'))
            fun = ret.get(u'fun', ret.get(u'__fun__'))
            if self.opts[u'multiprocessing']:
                fn_ = os.path.join(self.proc_dir, jid)
                if os.path.isfile(fn_):
                    try:
                        os.remove(fn_)
                    except (OSError, IOError):
                        # The file is gone already
                        pass
            log.info(u'Returning information for job: %s', jid)
            load = jids.setdefault(jid, {})
            if ret_cmd == u'_syndic_return':
                if not load:
                    load.update({u'id': self.opts[u'id'],
                                 u'jid': jid,
                                 u'fun': fun,
                                 u'arg': ret.get(u'arg'),
                                 u'tgt': ret.get(u'tgt'),
                                 u'tgt_type': ret.get(u'tgt_type'),
                                 u'load': ret.get(u'__load__'),
                                 u'return': {}})
                if u'__master_id__' in ret:
                    load[u'master_id'] = ret[u'__master_id__']
                for key, value in six.iteritems(ret):
                    if key.startswith(u'__'):
                        continue
                    load[u'return'][key] = value
            else:
                load.update({u'id': self.opts[u'id']})
                for key, value in six.iteritems(ret):
                    load[key] = value

            if u'out' in ret:
                if isinstance(ret[u'out'], six.string_types):
                    load[u'out'] = ret[u'out']
                else:
                    log.error(
                        u'Invalid outputter %s. This is likely a bug.',
                        ret[u'out']
                    )
            else:
                try:
                    oput = self.functions[fun].__outputter__
                except (KeyError, AttributeError, TypeError):
                    pass
                else:
                    if isinstance(oput, six.string_types):
                        load[u'out'] = oput
            if self.opts[u'cache_jobs']:
                # Local job cache has been enabled
                salt.utils.minion.cache_jobs(self.opts, load[u'jid'], ret)

        load = {u'cmd': ret_cmd,
                u'load': jids.values()}

        def timeout_handler(*_):
            log.warning(
               u'The minion failed to return the job information for job %s. '
               u'This is often due to the master being shut down or '
               u'overloaded. If the master is running, consider increasing '
               u'the worker_threads value.', jid
            )
            return True

        if sync:
            try:
                ret_val = self._send_req_sync(load, timeout=timeout)
            except SaltReqTimeoutError:
                timeout_handler()
                return u''
        else:
            with tornado.stack_context.ExceptionStackContext(timeout_handler):
                ret_val = self._send_req_async(load, timeout=timeout, callback=lambda f: None)  # pylint: disable=unexpected-keyword-arg

        log.trace(u'ret_val = %s', ret_val)  # pylint: disable=no-member
        return ret_val

    def _state_run(self):
        '''
        Execute a state run based on information set in the minion config file
        '''
        if self.opts[u'startup_states']:
            if self.opts.get(u'master_type', u'str') == u'disable' and \
                        self.opts.get(u'file_client', u'remote') == u'remote':
                log.warning(
                    u'Cannot run startup_states when \'master_type\' is set '
                    u'to \'disable\' and \'file_client\' is set to '
                    u'\'remote\'. Skipping.'
                )
            else:
                data = {u'jid': u'req', u'ret': self.opts.get(u'ext_job_cache', u'')}
                if self.opts[u'startup_states'] == u'sls':
                    data[u'fun'] = u'state.sls'
                    data[u'arg'] = [self.opts[u'sls_list']]
                elif self.opts[u'startup_states'] == u'top':
                    data[u'fun'] = u'state.top'
                    data[u'arg'] = [self.opts[u'top_file']]
                else:
                    data[u'fun'] = u'state.highstate'
                    data[u'arg'] = []
                self._handle_decoded_payload(data)

    def _refresh_grains_watcher(self, refresh_interval_in_minutes):
        '''
        Create a loop that will fire a pillar refresh to inform a master about a change in the grains of this minion
        :param refresh_interval_in_minutes:
        :return: None
        '''
        if u'__update_grains' not in self.opts.get(u'schedule', {}):
            if u'schedule' not in self.opts:
                self.opts[u'schedule'] = {}
            self.opts[u'schedule'].update({
                u'__update_grains':
                    {
                        u'function': u'event.fire',
                        u'args': [{}, u'grains_refresh'],
                        u'minutes': refresh_interval_in_minutes
                    }
            })

    def _fire_master_minion_start(self):
        # Send an event to the master that the minion is live
        self._fire_master(
            u'Minion {0} started at {1}'.format(
            self.opts[u'id'],
            time.asctime()
            ),
            u'minion_start'
        )
        # dup name spaced event
        self._fire_master(
            u'Minion {0} started at {1}'.format(
            self.opts[u'id'],
            time.asctime()
            ),
            tagify([self.opts[u'id'], u'start'], u'minion'),
        )

    def module_refresh(self, force_refresh=False, notify=False):
        '''
        Refresh the functions and returners.
        '''
        log.debug(u'Refreshing modules. Notify=%s', notify)
        self.functions, self.returners, _, self.executors = self._load_modules(force_refresh, notify=notify)

        if not self.opts.get('standalone_proxy', False):
            self.schedule.functions = self.functions
            self.schedule.returners = self.returners

    def beacons_refresh(self):
        '''
        Refresh the functions and returners.
        '''
        log.debug(u'Refreshing beacons.')
        self.beacons = salt.beacons.Beacon(self.opts, self.functions)

    # TODO: only allow one future in flight at a time?
    @tornado.gen.coroutine
    def pillar_refresh(self, force_refresh=False):
        '''
        Refresh the pillar
        '''
        if self.connected:
            log.debug(u'Refreshing pillar')
            try:
                self.opts[u'pillar'] = yield salt.pillar.get_async_pillar(
                    self.opts,
                    self.opts[u'grains'],
                    self.opts[u'id'],
                    self.opts[u'saltenv'],
                    pillarenv=self.opts.get(u'pillarenv'),
                ).compile_pillar()
            except SaltClientError:
                # Do not exit if a pillar refresh fails.
                log.error(u'Pillar data could not be refreshed. '
                          u'One or more masters may be down!')
        self.module_refresh(force_refresh)

    def manage_schedule(self, tag, data):
        '''
        Refresh the functions and returners.
        '''
        func = data.get(u'func', None)
        name = data.get(u'name', None)
        schedule = data.get(u'schedule', None)
        where = data.get(u'where', None)
        persist = data.get(u'persist', None)

        if func == u'delete':
            self.schedule.delete_job(name, persist)
        elif func == u'add':
            self.schedule.add_job(schedule, persist)
        elif func == u'modify':
            self.schedule.modify_job(name, schedule, persist)
        elif func == u'enable':
            self.schedule.enable_schedule()
        elif func == u'disable':
            self.schedule.disable_schedule()
        elif func == u'enable_job':
            self.schedule.enable_job(name, persist)
        elif func == u'run_job':
            self.schedule.run_job(name)
        elif func == u'disable_job':
            self.schedule.disable_job(name, persist)
        elif func == u'postpone_job':
            self.schedule.postpone_job(name, data)
        elif func == u'reload':
            self.schedule.reload(schedule)
        elif func == u'list':
            self.schedule.list(where)
        elif func == u'save_schedule':
            self.schedule.save_schedule()
        elif func == u'get_next_fire_time':
            self.schedule.get_next_fire_time(name)

    def manage_beacons(self, tag, data):
        '''
        Manage Beacons
        '''
        func = data.get(u'func', None)
        name = data.get(u'name', None)
        beacon_data = data.get(u'beacon_data', None)
        include_pillar = data.get(u'include_pillar', None)
        include_opts = data.get(u'include_opts', None)

        if func == u'add':
            self.beacons.add_beacon(name, beacon_data)
        elif func == u'modify':
            self.beacons.modify_beacon(name, beacon_data)
        elif func == u'delete':
            self.beacons.delete_beacon(name)
        elif func == u'enable':
            self.beacons.enable_beacons()
        elif func == u'disable':
            self.beacons.disable_beacons()
        elif func == u'enable_beacon':
            self.beacons.enable_beacon(name)
        elif func == u'disable_beacon':
            self.beacons.disable_beacon(name)
        elif func == u'list':
            self.beacons.list_beacons(include_opts, include_pillar)
        elif func == u'list_available':
            self.beacons.list_available_beacons()
        elif func == u'validate_beacon':
            self.beacons.validate_beacon(name, beacon_data)

    def environ_setenv(self, tag, data):
        '''
        Set the salt-minion main process environment according to
        the data contained in the minion event data
        '''
        environ = data.get(u'environ', None)
        if environ is None:
            return False
        false_unsets = data.get(u'false_unsets', False)
        clear_all = data.get(u'clear_all', False)
        import salt.modules.environ as mod_environ
        return mod_environ.setenv(environ, false_unsets, clear_all)

    def _pre_tune(self):
        '''
        Set the minion running flag and issue the appropriate warnings if
        the minion cannot be started or is already running
        '''
        if self._running is None:
            self._running = True
        elif self._running is False:
            log.error(
                u'This %s was scheduled to stop. Not running %s.tune_in()',
                self.__class__.__name__, self.__class__.__name__
            )
            return
        elif self._running is True:
            log.error(
                u'This %s is already running. Not running %s.tune_in()',
                self.__class__.__name__, self.__class__.__name__
            )
            return

        try:
            log.info(
                u'%s is starting as user \'%s\'',
                self.__class__.__name__, salt.utils.user.get_user()
            )
        except Exception as err:
            # Only windows is allowed to fail here. See #3189. Log as debug in
            # that case. Else, error.
            log.log(
                salt.utils.platform.is_windows() and logging.DEBUG or logging.ERROR,
                u'Failed to get the user who is starting %s',
                self.__class__.__name__,
                exc_info=err
            )

    def _mine_send(self, tag, data):
        '''
        Send mine data to the master
        '''
        channel = salt.transport.Channel.factory(self.opts)
        data[u'tok'] = self.tok
        try:
            ret = channel.send(data)
            return ret
        except SaltReqTimeoutError:
            log.warning(u'Unable to send mine data to master.')
            return None

    @tornado.gen.coroutine
    def handle_event(self, package):
        '''
        Handle an event from the epull_sock (all local minion events)
        '''
        if not self.ready:
            raise tornado.gen.Return()
        tag, data = salt.utils.event.SaltEvent.unpack(package)
        log.debug(
            u'Minion of \'%s\' is handling event tag \'%s\'',
            self.opts[u'master'], tag
        )
        if tag.startswith(u'module_refresh'):
            self.module_refresh(
                force_refresh=data.get(u'force_refresh', False),
                notify=data.get(u'notify', False)
            )
        elif tag.startswith(u'pillar_refresh'):
            yield self.pillar_refresh(
                force_refresh=data.get(u'force_refresh', False)
            )
        elif tag.startswith(u'beacons_refresh'):
            self.beacons_refresh()
        elif tag.startswith(u'manage_schedule'):
            self.manage_schedule(tag, data)
        elif tag.startswith(u'manage_beacons'):
            self.manage_beacons(tag, data)
        elif tag.startswith(u'grains_refresh'):
            if (data.get(u'force_refresh', False) or
                    self.grains_cache != self.opts[u'grains']):
                self.pillar_refresh(force_refresh=True)
                self.grains_cache = self.opts[u'grains']
        elif tag.startswith(u'environ_setenv'):
            self.environ_setenv(tag, data)
        elif tag.startswith(u'_minion_mine'):
            self._mine_send(tag, data)
        elif tag.startswith(u'fire_master'):
            if self.connected:
                log.debug(u'Forwarding master event tag=%s', data[u'tag'])
                self._fire_master(data[u'data'], data[u'tag'], data[u'events'], data[u'pretag'])
        elif tag.startswith(master_event(type=u'disconnected')) or tag.startswith(master_event(type=u'failback')):
            # if the master disconnect event is for a different master, raise an exception
            if tag.startswith(master_event(type=u'disconnected')) and data[u'master'] != self.opts[u'master']:
                # not mine master, ignore
                return
            if tag.startswith(master_event(type=u'failback')):
                # if the master failback event is not for the top master, raise an exception
                if data[u'master'] != self.opts[u'master_list'][0]:
                    raise SaltException(u'Bad master \'{0}\' when mine failback is \'{1}\''.format(
                        data[u'master'], self.opts[u'master']))
                # if the master failback event is for the current master, raise an exception
                elif data[u'master'] == self.opts[u'master'][0]:
                    raise SaltException(u'Already connected to \'{0}\''.format(data[u'master']))

            if self.connected:
                # we are not connected anymore
                self.connected = False
                log.info(u'Connection to master %s lost', self.opts[u'master'])

                if self.opts[u'master_type'] != u'failover':
                    # modify the scheduled job to fire on reconnect
                    if self.opts[u'transport'] != u'tcp':
                        schedule = {
                           u'function': u'status.master',
                           u'seconds': self.opts[u'master_alive_interval'],
                           u'jid_include': True,
                           u'maxrunning': 1,
                           u'return_job': False,
                           u'kwargs': {u'master': self.opts[u'master'],
                                       u'connected': False}
                        }
                        self.schedule.modify_job(name=master_event(type=u'alive', master=self.opts[u'master']),
                                                 schedule=schedule)
                else:
                    # delete the scheduled job to don't interfere with the failover process
                    if self.opts[u'transport'] != u'tcp':
                        self.schedule.delete_job(name=master_event(type=u'alive'))

                    log.info(u'Trying to tune in to next master from master-list')

                    if hasattr(self, u'pub_channel'):
                        self.pub_channel.on_recv(None)
                        if hasattr(self.pub_channel, u'auth'):
                            self.pub_channel.auth.invalidate()
                        if hasattr(self.pub_channel, u'close'):
                            self.pub_channel.close()
                        del self.pub_channel

                    # if eval_master finds a new master for us, self.connected
                    # will be True again on successful master authentication
                    try:
                        master, self.pub_channel = yield self.eval_master(
                                                            opts=self.opts,
                                                            failed=True,
                                                            failback=tag.startswith(master_event(type=u'failback')))
                    except SaltClientError:
                        pass

                    if self.connected:
                        self.opts[u'master'] = master

                        # re-init the subsystems to work with the new master
                        log.info(
                            u'Re-initialising subsystems for new master %s',
                            self.opts[u'master']
                        )
                        # put the current schedule into the new loaders
                        self.opts[u'schedule'] = self.schedule.option(u'schedule')
                        self.functions, self.returners, self.function_errors, self.executors = self._load_modules()
                        # make the schedule to use the new 'functions' loader
                        self.schedule.functions = self.functions
                        self.pub_channel.on_recv(self._handle_payload)
                        self._fire_master_minion_start()
                        log.info(u'Minion is ready to receive requests!')

                        # update scheduled job to run with the new master addr
                        if self.opts[u'transport'] != u'tcp':
                            schedule = {
                               u'function': u'status.master',
                               u'seconds': self.opts[u'master_alive_interval'],
                               u'jid_include': True,
                               u'maxrunning': 1,
                               u'return_job': False,
                               u'kwargs': {u'master': self.opts[u'master'],
                                           u'connected': True}
                            }
                            self.schedule.modify_job(name=master_event(type=u'alive', master=self.opts[u'master']),
                                                     schedule=schedule)

                            if self.opts[u'master_failback'] and u'master_list' in self.opts:
                                if self.opts[u'master'] != self.opts[u'master_list'][0]:
                                    schedule = {
                                       u'function': u'status.ping_master',
                                       u'seconds': self.opts[u'master_failback_interval'],
                                       u'jid_include': True,
                                       u'maxrunning': 1,
                                       u'return_job': False,
                                       u'kwargs': {u'master': self.opts[u'master_list'][0]}
                                    }
                                    self.schedule.modify_job(name=master_event(type=u'failback'),
                                                             schedule=schedule)
                                else:
                                    self.schedule.delete_job(name=master_event(type=u'failback'), persist=True)
                    else:
                        self.restart = True
                        self.io_loop.stop()

        elif tag.startswith(master_event(type=u'connected')):
            # handle this event only once. otherwise it will pollute the log
            # also if master type is failover all the reconnection work is done
            # by `disconnected` event handler and this event must never happen,
            # anyway check it to be sure
            if not self.connected and self.opts[u'master_type'] != u'failover':
                log.info(u'Connection to master %s re-established', self.opts[u'master'])
                self.connected = True
                # modify the __master_alive job to only fire,
                # if the connection is lost again
                if self.opts[u'transport'] != u'tcp':
                    schedule = {
                       u'function': u'status.master',
                       u'seconds': self.opts[u'master_alive_interval'],
                       u'jid_include': True,
                       u'maxrunning': 1,
                       u'return_job': False,
                       u'kwargs': {u'master': self.opts[u'master'],
                                   u'connected': True}
                    }

                    self.schedule.modify_job(name=master_event(type=u'alive', master=self.opts[u'master']),
                                             schedule=schedule)
        elif tag.startswith(u'__schedule_return'):
            # reporting current connection with master
            if data[u'schedule'].startswith(master_event(type=u'alive', master=u'')):
                if data[u'return']:
                    log.debug(
                        u'Connected to master %s',
                        data[u'schedule'].split(master_event(type=u'alive', master=u''))[1]
                    )
            self._return_pub(data, ret_cmd=u'_return', sync=False)
        elif tag.startswith(u'_salt_error'):
            if self.connected:
                log.debug(u'Forwarding salt error event tag=%s', tag)
                self._fire_master(data, tag)
        elif tag.startswith(u'salt/auth/creds'):
            key = tuple(data[u'key'])
            log.debug(
                u'Updating auth data for %s: %s -> %s',
                key, salt.crypt.AsyncAuth.creds_map.get(key), data[u'creds']
            )
            salt.crypt.AsyncAuth.creds_map[tuple(data[u'key'])] = data[u'creds']

    def _fallback_cleanups(self):
        '''
        Fallback cleanup routines, attempting to fix leaked processes, threads, etc.
        '''
        # Add an extra fallback in case a forked process leaks through
        multiprocessing.active_children()

        # Cleanup Windows threads
        if not salt.utils.platform.is_windows():
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
    def tune_in(self, start=True):
        '''
        Lock onto the publisher. This is the main event loop for the minion
        :rtype : None
        '''
        self._pre_tune()

        log.debug(u'Minion \'%s\' trying to tune in', self.opts[u'id'])

        if start:
            self.sync_connect_master()
        if self.connected:
            self._fire_master_minion_start()
            log.info(u'Minion is ready to receive requests!')

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        # Make sure to gracefully handle CTRL_LOGOFF_EVENT
        if HAS_WIN_FUNCTIONS:
            salt.utils.win_functions.enable_ctrl_logoff_handler()

        # On first startup execute a state run if configured to do so
        self._state_run()

        loop_interval = self.opts[u'loop_interval']

        try:
            if self.opts[u'grains_refresh_every']:  # If exists and is not zero. In minutes, not seconds!
                log.debug(
                    u'Enabling the grains refresher. Will run every %s '
                    u'minute%s.',
                    self.opts[u'grains_refresh_every'],
                    u's' if self.opts[u'grains_refresh_every'] > 1 else u''
                )
                self._refresh_grains_watcher(
                    abs(self.opts[u'grains_refresh_every'])
                )
        except Exception as exc:
            log.error(
                u'Exception occurred in attempt to initialize grain refresh '
                u'routine during minion tune-in: %s', exc
            )

        self.periodic_callbacks = {}
        # schedule the stuff that runs every interval
        ping_interval = self.opts.get(u'ping_interval', 0) * 60
        if ping_interval > 0 and self.connected:
            def ping_master():
                try:
                    def ping_timeout_handler(*_):
                        if not self.opts.get(u'auth_safemode', True):
                            log.error(u'** Master Ping failed. Attempting to restart minion**')
                            delay = self.opts.get(u'random_reauth_delay', 5)
                            log.info(u'delaying random_reauth_delay %ss', delay)
                            # regular sys.exit raises an exception -- which isn't sufficient in a thread
                            os._exit(salt.defaults.exitcodes.SALT_KEEPALIVE)

                    self._fire_master('ping', 'minion_ping', sync=False, timeout_handler=ping_timeout_handler)
                except Exception:
                    log.warning(u'Attempt to ping master failed.', exc_on_loglevel=logging.DEBUG)
            self.periodic_callbacks[u'ping'] = tornado.ioloop.PeriodicCallback(ping_master, ping_interval * 1000, io_loop=self.io_loop)

        self.periodic_callbacks[u'cleanup'] = tornado.ioloop.PeriodicCallback(self._fallback_cleanups, loop_interval * 1000, io_loop=self.io_loop)

        def handle_beacons():
            # Process Beacons
            beacons = None
            try:
                beacons = self.process_beacons(self.functions)
            except Exception:
                log.critical(u'The beacon errored: ', exc_info=True)
            if beacons and self.connected:
                self._fire_master(events=beacons, sync=False)

        self.periodic_callbacks[u'beacons'] = tornado.ioloop.PeriodicCallback(handle_beacons, loop_interval * 1000, io_loop=self.io_loop)

        # TODO: actually listen to the return and change period
        def handle_schedule():
            self.process_schedule(self, loop_interval)
        if hasattr(self, u'schedule'):
            self.periodic_callbacks[u'schedule'] = tornado.ioloop.PeriodicCallback(handle_schedule, 1000, io_loop=self.io_loop)

        # start all the other callbacks
        for periodic_cb in six.itervalues(self.periodic_callbacks):
            periodic_cb.start()

        # add handler to subscriber
        if hasattr(self, u'pub_channel') and self.pub_channel is not None:
            self.pub_channel.on_recv(self._handle_payload)
        elif self.opts.get(u'master_type') != u'disable':
            log.error(u'No connection to master found. Scheduled jobs will not run.')

        if start:
            try:
                self.io_loop.start()
                if self.restart:
                    self.destroy()
            except (KeyboardInterrupt, RuntimeError):  # A RuntimeError can be re-raised by Tornado on shutdown
                self.destroy()

    def _handle_payload(self, payload):
        if payload is not None and payload[u'enc'] == u'aes':
            if self._target_load(payload[u'load']):
                self._handle_decoded_payload(payload[u'load'])
            elif self.opts[u'zmq_filtering']:
                # In the filtering enabled case, we'd like to know when minion sees something it shouldnt
                log.trace(
                    u'Broadcast message received not for this minion, Load: %s',
                    payload[u'load']
                )
        # If it's not AES, and thus has not been verified, we do nothing.
        # In the future, we could add support for some clearfuncs, but
        # the minion currently has no need.

    def _target_load(self, load):
        # Verify that the publication is valid
        if u'tgt' not in load or u'jid' not in load or u'fun' not in load \
           or u'arg' not in load:
            return False
        # Verify that the publication applies to this minion

        # It's important to note that the master does some pre-processing
        # to determine which minions to send a request to. So for example,
        # a "salt -G 'grain_key:grain_val' test.ping" will invoke some
        # pre-processing on the master and this minion should not see the
        # publication if the master does not determine that it should.

        if u'tgt_type' in load:
            match_func = getattr(self.matcher,
                                 u'{0}_match'.format(load[u'tgt_type']), None)
            if match_func is None:
                return False
            if load[u'tgt_type'] in (u'grain', u'grain_pcre', u'pillar'):
                delimiter = load.get(u'delimiter', DEFAULT_TARGET_DELIM)
                if not match_func(load[u'tgt'], delimiter=delimiter):
                    return False
            elif not match_func(load[u'tgt']):
                return False
        else:
            if not self.matcher.glob_match(load[u'tgt']):
                return False

        return True

    def destroy(self):
        '''
        Tear down the minion
        '''
        self._running = False
        if hasattr(self, u'schedule'):
            del self.schedule
        if hasattr(self, u'pub_channel') and self.pub_channel is not None:
            self.pub_channel.on_recv(None)
            if hasattr(self.pub_channel, u'close'):
                self.pub_channel.close()
            del self.pub_channel
        if hasattr(self, u'periodic_callbacks'):
            for cb in six.itervalues(self.periodic_callbacks):
                cb.stop()

    def __del__(self):
        self.destroy()


class Syndic(Minion):
    '''
    Make a Syndic minion, this minion will use the minion keys on the
    master to authenticate with a higher level master.
    '''
    def __init__(self, opts, **kwargs):
        self._syndic_interface = opts.get(u'interface')
        self._syndic = True
        # force auth_safemode True because Syndic don't support autorestart
        opts[u'auth_safemode'] = True
        opts[u'loop_interval'] = 1
        super(Syndic, self).__init__(opts, **kwargs)
        self.mminion = salt.minion.MasterMinion(opts)
        self.jid_forward_cache = set()
        self.jids = {}
        self.raw_events = []
        self.pub_future = None

    def _handle_decoded_payload(self, data):
        '''
        Override this method if you wish to handle the decoded data
        differently.
        '''
        # TODO: even do this??
        data[u'to'] = int(data.get(u'to', self.opts[u'timeout'])) - 1
        # Only forward the command if it didn't originate from ourselves
        if data.get(u'master_id', 0) != self.opts.get(u'master_id', 1):
            self.syndic_cmd(data)

    def syndic_cmd(self, data):
        '''
        Take the now clear load and forward it on to the client cmd
        '''
        # Set up default tgt_type
        if u'tgt_type' not in data:
            data[u'tgt_type'] = u'glob'
        kwargs = {}

        # optionally add a few fields to the publish data
        for field in (u'master_id',  # which master the job came from
                      u'user',  # which user ran the job
                      ):
            if field in data:
                kwargs[field] = data[field]

        def timeout_handler(*args):
            log.warning(u'Unable to forward pub data: %s', args[1])
            return True

        with tornado.stack_context.ExceptionStackContext(timeout_handler):
            self.local.pub_async(data[u'tgt'],
                                 data[u'fun'],
                                 data[u'arg'],
                                 data[u'tgt_type'],
                                 data[u'ret'],
                                 data[u'jid'],
                                 data[u'to'],
                                 io_loop=self.io_loop,
                                 callback=lambda _: None,
                                 **kwargs)

    def fire_master_syndic_start(self):
        # Send an event to the master that the minion is live
        self._fire_master(
            u'Syndic {0} started at {1}'.format(
                self.opts[u'id'],
                time.asctime()
            ),
            u'syndic_start',
            sync=False,
        )
        self._fire_master(
            u'Syndic {0} started at {1}'.format(
                self.opts[u'id'],
                time.asctime()
            ),
            tagify([self.opts[u'id'], u'start'], u'syndic'),
            sync=False,
        )

    # TODO: clean up docs
    def tune_in_no_block(self):
        '''
        Executes the tune_in sequence but omits extra logging and the
        management of the event bus assuming that these are handled outside
        the tune_in sequence
        '''
        # Instantiate the local client
        self.local = salt.client.get_local_client(
                self.opts[u'_minion_conf_file'], io_loop=self.io_loop)

        # add handler to subscriber
        self.pub_channel.on_recv(self._process_cmd_socket)

    def _process_cmd_socket(self, payload):
        if payload is not None and payload[u'enc'] == u'aes':
            log.trace(u'Handling payload')
            self._handle_decoded_payload(payload[u'load'])
        # If it's not AES, and thus has not been verified, we do nothing.
        # In the future, we could add support for some clearfuncs, but
        # the syndic currently has no need.

    @tornado.gen.coroutine
    def reconnect(self):
        if hasattr(self, u'pub_channel'):
            self.pub_channel.on_recv(None)
            if hasattr(self.pub_channel, u'close'):
                self.pub_channel.close()
            del self.pub_channel

        # if eval_master finds a new master for us, self.connected
        # will be True again on successful master authentication
        master, self.pub_channel = yield self.eval_master(opts=self.opts)

        if self.connected:
            self.opts[u'master'] = master
            self.pub_channel.on_recv(self._process_cmd_socket)
            log.info(u'Minion is ready to receive requests!')

        raise tornado.gen.Return(self)

    def destroy(self):
        '''
        Tear down the syndic minion
        '''
        # We borrowed the local clients poller so give it back before
        # it's destroyed. Reset the local poller reference.
        super(Syndic, self).destroy()
        if hasattr(self, u'local'):
            del self.local

        if hasattr(self, u'forward_events'):
            self.forward_events.stop()


# TODO: need a way of knowing if the syndic connection is busted
class SyndicManager(MinionBase):
    '''
    Make a MultiMaster syndic minion, this minion will handle relaying jobs and returns from
    all minions connected to it to the list of masters it is connected to.

    Modes (controlled by `syndic_mode`:
        sync: This mode will synchronize all events and publishes from higher level masters
        cluster: This mode will only sync job publishes and returns

    Note: jobs will be returned best-effort to the requesting master. This also means
    (since we are using zmq) that if a job was fired and the master disconnects
    between the publish and return, that the return will end up in a zmq buffer
    in this Syndic headed to that original master.

    In addition, since these classes all seem to use a mix of blocking and non-blocking
    calls (with varying timeouts along the way) this daemon does not handle failure well,
    it will (under most circumstances) stall the daemon for ~15s trying to forward events
    to the down master
    '''
    # time to connect to upstream master
    SYNDIC_CONNECT_TIMEOUT = 5
    SYNDIC_EVENT_TIMEOUT = 5

    def __init__(self, opts, io_loop=None):
        opts[u'loop_interval'] = 1
        super(SyndicManager, self).__init__(opts)
        self.mminion = salt.minion.MasterMinion(opts)
        # sync (old behavior), cluster (only returns and publishes)
        self.syndic_mode = self.opts.get(u'syndic_mode', u'sync')
        self.syndic_failover = self.opts.get(u'syndic_failover', u'random')

        self.auth_wait = self.opts[u'acceptance_wait_time']
        self.max_auth_wait = self.opts[u'acceptance_wait_time_max']

        self._has_master = threading.Event()
        self.jid_forward_cache = set()

        if io_loop is None:
            if HAS_ZMQ:
                zmq.eventloop.ioloop.install()
            self.io_loop = LOOP_CLASS.current()
        else:
            self.io_loop = io_loop

        # List of events
        self.raw_events = []
        # Dict of rets: {master_id: {event_tag: job_ret, ...}, ...}
        self.job_rets = {}
        # List of delayed job_rets which was unable to send for some reason and will be resend to
        # any available master
        self.delayed = []
        # Active pub futures: {master_id: (future, [job_ret, ...]), ...}
        self.pub_futures = {}

    def _spawn_syndics(self):
        '''
        Spawn all the coroutines which will sign in the syndics
        '''
        self._syndics = OrderedDict()  # mapping of opts['master'] -> syndic
        masters = self.opts[u'master']
        if not isinstance(masters, list):
            masters = [masters]
        for master in masters:
            s_opts = copy.copy(self.opts)
            s_opts[u'master'] = master
            self._syndics[master] = self._connect_syndic(s_opts)

    @tornado.gen.coroutine
    def _connect_syndic(self, opts):
        '''
        Create a syndic, and asynchronously connect it to a master
        '''
        last = 0  # never have we signed in
        auth_wait = opts[u'acceptance_wait_time']
        failed = False
        while True:
            log.debug(
                u'Syndic attempting to connect to %s',
                opts[u'master']
            )
            try:
                syndic = Syndic(opts,
                                timeout=self.SYNDIC_CONNECT_TIMEOUT,
                                safe=False,
                                io_loop=self.io_loop,
                                )
                yield syndic.connect_master(failed=failed)
                # set up the syndic to handle publishes (specifically not event forwarding)
                syndic.tune_in_no_block()

                # Send an event to the master that the minion is live
                syndic.fire_master_syndic_start()

                log.info(
                    u'Syndic successfully connected to %s',
                    opts[u'master']
                )
                break
            except SaltClientError as exc:
                failed = True
                log.error(
                    u'Error while bringing up syndic for multi-syndic. Is the '
                    u'master at %s responding?', opts[u'master']
                )
                last = time.time()
                if auth_wait < self.max_auth_wait:
                    auth_wait += self.auth_wait
                yield tornado.gen.sleep(auth_wait)  # TODO: log?
            except KeyboardInterrupt:
                raise
            except:  # pylint: disable=W0702
                failed = True
                log.critical(
                    u'Unexpected error while connecting to %s',
                    opts[u'master'], exc_info=True
                )

        raise tornado.gen.Return(syndic)

    def _mark_master_dead(self, master):
        '''
        Mark a master as dead. This will start the sign-in routine
        '''
        # if its connected, mark it dead
        if self._syndics[master].done():
            syndic = self._syndics[master].result()  # pylint: disable=no-member
            self._syndics[master] = syndic.reconnect()
        else:
            # TODO: debug?
            log.info(
                u'Attempting to mark %s as dead, although it is already '
                u'marked dead', master
            )

    def _call_syndic(self, func, args=(), kwargs=None, master_id=None):
        '''
        Wrapper to call a given func on a syndic, best effort to get the one you asked for
        '''
        if kwargs is None:
            kwargs = {}
        successful = False
        # Call for each master
        for master, syndic_future in self.iter_master_options(master_id):
            if not syndic_future.done() or syndic_future.exception():
                log.error(
                    u'Unable to call %s on %s, that syndic is not connected',
                    func, master
                )
                continue

            try:
                getattr(syndic_future.result(), func)(*args, **kwargs)
                successful = True
            except SaltClientError:
                log.error(
                    u'Unable to call %s on %s, trying another...',
                    func, master
                )
                self._mark_master_dead(master)
        if not successful:
            log.critical(u'Unable to call %s on any masters!', func)

    def _return_pub_syndic(self, values, master_id=None):
        '''
        Wrapper to call the '_return_pub_multi' a syndic, best effort to get the one you asked for
        '''
        func = u'_return_pub_multi'
        for master, syndic_future in self.iter_master_options(master_id):
            if not syndic_future.done() or syndic_future.exception():
                log.error(
                    u'Unable to call %s on %s, that syndic is not connected',
                    func, master
                )
                continue

            future, data = self.pub_futures.get(master, (None, None))
            if future is not None:
                if not future.done():
                    if master == master_id:
                        # Targeted master previous send not done yet, call again later
                        return False
                    else:
                        # Fallback master is busy, try the next one
                        continue
                elif future.exception():
                    # Previous execution on this master returned an error
                    log.error(
                        u'Unable to call %s on %s, trying another...',
                        func, master
                    )
                    self._mark_master_dead(master)
                    del self.pub_futures[master]
                    # Add not sent data to the delayed list and try the next master
                    self.delayed.extend(data)
                    continue
            future = getattr(syndic_future.result(), func)(values,
                                                           u'_syndic_return',
                                                           timeout=self._return_retry_timer(),
                                                           sync=False)
            self.pub_futures[master] = (future, values)
            return True
        # Loop done and didn't exit: wasn't sent, try again later
        return False

    def iter_master_options(self, master_id=None):
        '''
        Iterate (in order) over your options for master
        '''
        masters = list(self._syndics.keys())
        if self.opts[u'syndic_failover'] == u'random':
            shuffle(masters)
        if master_id not in self._syndics:
            master_id = masters.pop(0)
        else:
            masters.remove(master_id)

        while True:
            yield master_id, self._syndics[master_id]
            if len(masters) == 0:
                break
            master_id = masters.pop(0)

    def _reset_event_aggregation(self):
        self.job_rets = {}
        self.raw_events = []

    def reconnect_event_bus(self, something):
        future = self.local.event.set_event_handler(self._process_event)
        self.io_loop.add_future(future, self.reconnect_event_bus)

    # Syndic Tune In
    def tune_in(self):
        '''
        Lock onto the publisher. This is the main event loop for the syndic
        '''
        self._spawn_syndics()
        # Instantiate the local client
        self.local = salt.client.get_local_client(
            self.opts[u'_minion_conf_file'], io_loop=self.io_loop)
        self.local.event.subscribe(u'')

        log.debug(u'SyndicManager \'%s\' trying to tune in', self.opts[u'id'])

        # register the event sub to the poller
        self.job_rets = {}
        self.raw_events = []
        self._reset_event_aggregation()
        future = self.local.event.set_event_handler(self._process_event)
        self.io_loop.add_future(future, self.reconnect_event_bus)

        # forward events every syndic_event_forward_timeout
        self.forward_events = tornado.ioloop.PeriodicCallback(self._forward_events,
                                                              self.opts[u'syndic_event_forward_timeout'] * 1000,
                                                              io_loop=self.io_loop)
        self.forward_events.start()

        # Make sure to gracefully handle SIGUSR1
        enable_sigusr1_handler()

        self.io_loop.start()

    def _process_event(self, raw):
        # TODO: cleanup: Move down into event class
        mtag, data = self.local.event.unpack(raw, self.local.event.serial)
        log.trace(u'Got event %s', mtag)  # pylint: disable=no-member

        tag_parts = mtag.split(u'/')
        if len(tag_parts) >= 4 and tag_parts[1] == u'job' and \
            salt.utils.jid.is_jid(tag_parts[2]) and tag_parts[3] == u'ret' and \
            u'return' in data:
            if u'jid' not in data:
                # Not a job return
                return
            if self.syndic_mode == u'cluster' and data.get(u'master_id', 0) == self.opts.get(u'master_id', 1):
                log.debug(u'Return received with matching master_id, not forwarding')
                return

            master = data.get(u'master_id')
            jdict = self.job_rets.setdefault(master, {}).setdefault(mtag, {})
            if not jdict:
                jdict[u'__fun__'] = data.get(u'fun')
                jdict[u'__jid__'] = data[u'jid']
                jdict[u'__load__'] = {}
                fstr = u'{0}.get_load'.format(self.opts[u'master_job_cache'])
                # Only need to forward each load once. Don't hit the disk
                # for every minion return!
                if data[u'jid'] not in self.jid_forward_cache:
                    jdict[u'__load__'].update(
                        self.mminion.returners[fstr](data[u'jid'])
                        )
                    self.jid_forward_cache.add(data[u'jid'])
                    if len(self.jid_forward_cache) > self.opts[u'syndic_jid_forward_cache_hwm']:
                        # Pop the oldest jid from the cache
                        tmp = sorted(list(self.jid_forward_cache))
                        tmp.pop(0)
                        self.jid_forward_cache = set(tmp)
            if master is not None:
                # __'s to make sure it doesn't print out on the master cli
                jdict[u'__master_id__'] = master
            ret = {}
            for key in u'return', u'retcode', u'success':
                if key in data:
                    ret[key] = data[key]
            jdict[data[u'id']] = ret
        else:
            # TODO: config to forward these? If so we'll have to keep track of who
            # has seen them
            # if we are the top level masters-- don't forward all the minion events
            if self.syndic_mode == u'sync':
                # Add generic event aggregation here
                if u'retcode' not in data:
                    self.raw_events.append({u'data': data, u'tag': mtag})

    def _forward_events(self):
        log.trace(u'Forwarding events')  # pylint: disable=no-member
        if self.raw_events:
            events = self.raw_events
            self.raw_events = []
            self._call_syndic(u'_fire_master',
                              kwargs={u'events': events,
                                      u'pretag': tagify(self.opts[u'id'], base=u'syndic'),
                                      u'timeout': self._return_retry_timer(),
                                      u'sync': False,
                                      },
                              )
        if self.delayed:
            res = self._return_pub_syndic(self.delayed)
            if res:
                self.delayed = []
        for master in list(six.iterkeys(self.job_rets)):
            values = self.job_rets[master].values()
            res = self._return_pub_syndic(values, master_id=master)
            if res:
                del self.job_rets[master]


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
        matcher = u'compound'
        if not data:
            log.error(u'Received bad data when setting the match from the top '
                      u'file')
            return False
        for item in data:
            if isinstance(item, dict):
                if u'match' in item:
                    matcher = item[u'match']
        if hasattr(self, matcher + u'_match'):
            funcname = u'{0}_match'.format(matcher)
            if matcher == u'nodegroup':
                return getattr(self, funcname)(match, nodegroups)
            return getattr(self, funcname)(match)
        else:
            log.error(u'Attempting to match with unknown matcher: %s', matcher)
            return False

    def glob_match(self, tgt):
        '''
        Returns true if the passed glob matches the id
        '''
        if not isinstance(tgt, six.string_types):
            return False

        return fnmatch.fnmatch(self.opts[u'id'], tgt)

    def pcre_match(self, tgt):
        '''
        Returns true if the passed pcre regex matches
        '''
        return bool(re.match(tgt, self.opts[u'id']))

    def list_match(self, tgt):
        '''
        Determines if this host is on the list
        '''
        if isinstance(tgt, six.string_types):
            tgt = tgt.split(u',')
        return bool(self.opts[u'id'] in tgt)

    def grain_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
        '''
        Reads in the grains glob match
        '''
        log.debug(u'grains target: %s', tgt)
        if delimiter not in tgt:
            log.error(u'Got insufficient arguments for grains match '
                      u'statement from master')
            return False
        return salt.utils.data.subdict_match(
            self.opts[u'grains'], tgt, delimiter=delimiter
        )

    def grain_pcre_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
        '''
        Matches a grain based on regex
        '''
        log.debug(u'grains pcre target: %s', tgt)
        if delimiter not in tgt:
            log.error(u'Got insufficient arguments for grains pcre match '
                      u'statement from master')
            return False
        return salt.utils.data.subdict_match(
            self.opts[u'grains'], tgt, delimiter=delimiter, regex_match=True)

    def data_match(self, tgt):
        '''
        Match based on the local data store on the minion
        '''
        if self.functions is None:
            utils = salt.loader.utils(self.opts)
            self.functions = salt.loader.minion_mods(self.opts, utils=utils)
        comps = tgt.split(u':')
        if len(comps) < 2:
            return False
        val = self.functions[u'data.getval'](comps[0])
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

    def pillar_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
        '''
        Reads in the pillar glob match
        '''
        log.debug(u'pillar target: %s', tgt)
        if delimiter not in tgt:
            log.error(u'Got insufficient arguments for pillar match '
                      u'statement from master')
            return False
        return salt.utils.data.subdict_match(
            self.opts[u'pillar'], tgt, delimiter=delimiter
        )

    def pillar_pcre_match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
        '''
        Reads in the pillar pcre match
        '''
        log.debug(u'pillar PCRE target: %s', tgt)
        if delimiter not in tgt:
            log.error(u'Got insufficient arguments for pillar PCRE match '
                      u'statement from master')
            return False
        return salt.utils.data.subdict_match(
            self.opts[u'pillar'], tgt, delimiter=delimiter, regex_match=True
        )

    def pillar_exact_match(self, tgt, delimiter=u':'):
        '''
        Reads in the pillar match, no globbing, no PCRE
        '''
        log.debug(u'pillar target: %s', tgt)
        if delimiter not in tgt:
            log.error(u'Got insufficient arguments for pillar match '
                      u'statement from master')
            return False
        return salt.utils.data.subdict_match(self.opts[u'pillar'],
                                        tgt,
                                        delimiter=delimiter,
                                        exact_match=True)

    def ipcidr_match(self, tgt):
        '''
        Matches based on IP address or CIDR notation
        '''
        try:
            # Target is an address?
            tgt = ipaddress.ip_address(tgt)
        except:  # pylint: disable=bare-except
            try:
                # Target is a network?
                tgt = ipaddress.ip_network(tgt)
            except:  # pylint: disable=bare-except
                log.error(u'Invalid IP/CIDR target: %s', tgt)
                return []
        proto = u'ipv{0}'.format(tgt.version)

        grains = self.opts[u'grains']

        if proto not in grains:
            match = False
        elif isinstance(tgt, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            match = str(tgt) in grains[proto]
        else:
            match = salt.utils.network.in_subnet(tgt, grains[proto])

        return match

    def range_match(self, tgt):
        '''
        Matches based on range cluster
        '''
        if HAS_RANGE:
            range_ = seco.range.Range(self.opts[u'range_server'])
            try:
                return self.opts[u'grains'][u'fqdn'] in range_.expand(tgt)
            except seco.range.RangeException as exc:
                log.debug(u'Range exception in compound match: %s', exc)
                return False
        return False

    def compound_match(self, tgt):
        '''
        Runs the compound target check
        '''
        if not isinstance(tgt, six.string_types) and not isinstance(tgt, (list, tuple)):
            log.error(u'Compound target received that is neither string, list nor tuple')
            return False
        log.debug(u'compound_match: %s ? %s', self.opts[u'id'], tgt)
        ref = {u'G': u'grain',
               u'P': u'grain_pcre',
               u'I': u'pillar',
               u'J': u'pillar_pcre',
               u'L': u'list',
               u'N': None,      # Nodegroups should already be expanded
               u'S': u'ipcidr',
               u'E': u'pcre'}
        if HAS_RANGE:
            ref[u'R'] = u'range'

        results = []
        opers = [u'and', u'or', u'not', u'(', u')']

        if isinstance(tgt, six.string_types):
            words = tgt.split()
        else:
            words = tgt

        for word in words:
            target_info = salt.utils.minions.parse_target(word)

            # Easy check first
            if word in opers:
                if results:
                    if results[-1] == u'(' and word in (u'and', u'or'):
                        log.error(u'Invalid beginning operator after "(": %s', word)
                        return False
                    if word == u'not':
                        if not results[-1] in (u'and', u'or', u'('):
                            results.append(u'and')
                    results.append(word)
                else:
                    # seq start with binary oper, fail
                    if word not in [u'(', u'not']:
                        log.error(u'Invalid beginning operator: %s', word)
                        return False
                    results.append(word)

            elif target_info and target_info[u'engine']:
                if u'N' == target_info[u'engine']:
                    # Nodegroups should already be expanded/resolved to other engines
                    log.error(
                        u'Detected nodegroup expansion failure of "%s"', word)
                    return False
                engine = ref.get(target_info[u'engine'])
                if not engine:
                    # If an unknown engine is called at any time, fail out
                    log.error(
                        u'Unrecognized target engine "%s" for target '
                        u'expression "%s"', target_info[u'engine'], word
                    )
                    return False

                engine_args = [target_info[u'pattern']]
                engine_kwargs = {}
                if target_info[u'delimiter']:
                    engine_kwargs[u'delimiter'] = target_info[u'delimiter']

                results.append(
                    str(getattr(self, u'{0}_match'.format(engine))(*engine_args, **engine_kwargs))
                )

            else:
                # The match is not explicitly defined, evaluate it as a glob
                results.append(str(self.glob_match(word)))

        results = u' '.join(results)
        log.debug(u'compound_match %s ? "%s" => "%s"', self.opts[u'id'], tgt, results)
        try:
            return eval(results)  # pylint: disable=W0123
        except Exception:
            log.error(
                u'Invalid compound target: %s for results: %s', tgt, results)
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


class ProxyMinionManager(MinionManager):
    '''
    Create the multi-minion interface but for proxy minions
    '''
    def _create_minion_object(self, opts, timeout, safe,
                              io_loop=None, loaded_base_name=None,
                              jid_queue=None):
        '''
        Helper function to return the correct type of object
        '''
        return ProxyMinion(opts,
                           timeout,
                           safe,
                           io_loop=io_loop,
                           loaded_base_name=loaded_base_name,
                           jid_queue=jid_queue)


class ProxyMinion(Minion):
    '''
    This class instantiates a u'proxy' minion--a minion that does not manipulate
    the host it runs on, but instead manipulates a device that cannot run a minion.
    '''

    # TODO: better name...
    @tornado.gen.coroutine
    def _post_master_init(self, master):
        '''
        Function to finish init after connecting to a master

        This is primarily loading modules, pillars, etc. (since they need
        to know which master they connected to)

        If this function is changed, please check Minion._post_master_init
        to see if those changes need to be propagated.

        ProxyMinions need a significantly different post master setup,
        which is why the differences are not factored out into separate helper
        functions.
        '''
        log.debug(u"subclassed _post_master_init")

        if self.connected:
            self.opts[u'master'] = master

            self.opts[u'pillar'] = yield salt.pillar.get_async_pillar(
                self.opts,
                self.opts[u'grains'],
                self.opts[u'id'],
                saltenv=self.opts[u'saltenv'],
                pillarenv=self.opts.get(u'pillarenv'),
            ).compile_pillar()

        if u'proxy' not in self.opts[u'pillar'] and u'proxy' not in self.opts:
            errmsg = u'No proxy key found in pillar or opts for id ' + self.opts[u'id'] + u'. ' + \
                     u'Check your pillar/opts configuration and contents.  Salt-proxy aborted.'
            log.error(errmsg)
            self._running = False
            raise SaltSystemExit(code=-1, msg=errmsg)

        if u'proxy' not in self.opts:
            self.opts[u'proxy'] = self.opts[u'pillar'][u'proxy']

        if self.opts.get(u'proxy_merge_pillar_in_opts'):
            # Override proxy opts with pillar data when the user required.
            self.opts = salt.utils.dictupdate.merge(self.opts,
                                                    self.opts[u'pillar'],
                                                    strategy=self.opts.get(u'proxy_merge_pillar_in_opts_strategy'),
                                                    merge_lists=self.opts.get(u'proxy_deep_merge_pillar_in_opts', False))
        elif self.opts.get(u'proxy_mines_pillar'):
            # Even when not required, some details such as mine configuration
            # should be merged anyway whenever possible.
            if u'mine_interval' in self.opts[u'pillar']:
                self.opts[u'mine_interval'] = self.opts[u'pillar'][u'mine_interval']
            if u'mine_functions' in self.opts[u'pillar']:
                general_proxy_mines = self.opts.get(u'mine_functions', [])
                specific_proxy_mines = self.opts[u'pillar'][u'mine_functions']
                try:
                    self.opts[u'mine_functions'] = general_proxy_mines + specific_proxy_mines
                except TypeError as terr:
                    log.error(u'Unable to merge mine functions from the pillar in the opts, for proxy {}'.format(
                        self.opts[u'id']))

        fq_proxyname = self.opts[u'proxy'][u'proxytype']

        # Need to load the modules so they get all the dunder variables
        self.functions, self.returners, self.function_errors, self.executors = self._load_modules()

        # we can then sync any proxymodules down from the master
        # we do a sync_all here in case proxy code was installed by
        # SPM or was manually placed in /srv/salt/_modules etc.
        self.functions[u'saltutil.sync_all'](saltenv=self.opts[u'saltenv'])

        # Pull in the utils
        self.utils = salt.loader.utils(self.opts)

        # Then load the proxy module
        self.proxy = salt.loader.proxy(self.opts, utils=self.utils)

        # And re-load the modules so the __proxy__ variable gets injected
        self.functions, self.returners, self.function_errors, self.executors = self._load_modules()
        self.functions.pack[u'__proxy__'] = self.proxy
        self.proxy.pack[u'__salt__'] = self.functions
        self.proxy.pack[u'__ret__'] = self.returners
        self.proxy.pack[u'__pillar__'] = self.opts[u'pillar']

        # Reload utils as well (chicken and egg, __utils__ needs __proxy__ and __proxy__ needs __utils__
        self.utils = salt.loader.utils(self.opts, proxy=self.proxy)
        self.proxy.pack[u'__utils__'] = self.utils

        # Reload all modules so all dunder variables are injected
        self.proxy.reload_modules()

        # Start engines here instead of in the Minion superclass __init__
        # This is because we need to inject the __proxy__ variable but
        # it is not setup until now.
        self.io_loop.spawn_callback(salt.engines.start_engines, self.opts,
                                    self.process_manager, proxy=self.proxy)

        if (u'{0}.init'.format(fq_proxyname) not in self.proxy
                or u'{0}.shutdown'.format(fq_proxyname) not in self.proxy):
            errmsg = u'Proxymodule {0} is missing an init() or a shutdown() or both. '.format(fq_proxyname) + \
                     u'Check your proxymodule.  Salt-proxy aborted.'
            log.error(errmsg)
            self._running = False
            raise SaltSystemExit(code=-1, msg=errmsg)

        proxy_init_fn = self.proxy[fq_proxyname + u'.init']
        proxy_init_fn(self.opts)

        self.opts[u'grains'] = salt.loader.grains(self.opts, proxy=self.proxy)

        self.serial = salt.payload.Serial(self.opts)
        self.mod_opts = self._prep_mod_opts()
        self.matcher = Matcher(self.opts, self.functions)
        if self.opts.get('standalone_proxy', False):
            log.info('Dont need Beacons for this standalone proxy (%s)', self.opts['id'])
            self.beacons = {}
        else:
            self.beacons = salt.beacons.Beacon(self.opts, self.functions)
        uid = salt.utils.user.get_uid(user=self.opts.get(u'user', None))
        self.proc_dir = get_proc_dir(self.opts[u'cachedir'], uid=uid)

        if not self.opts.get('standalone_proxy', False):
            if self.connected and self.opts[u'pillar']:
                # The pillar has changed due to the connection to the master.
                # Reload the functions so that they can use the new pillar data.
                self.functions, self.returners, self.function_errors, self.executors = self._load_modules()
                if hasattr(self, u'schedule'):
                    self.schedule.functions = self.functions
                    self.schedule.returners = self.returners

            if not hasattr(self, u'schedule'):
                self.schedule = salt.utils.schedule.Schedule(
                    self.opts,
                    self.functions,
                    self.returners,
                    cleanup=[master_event(type=u'alive')],
                    proxy=self.proxy)


            # add default scheduling jobs to the minions scheduler
            if self.opts[u'mine_enabled'] and u'mine.update' in self.functions:
                self.schedule.add_job({
                    u'__mine_interval':
                        {
                            u'function': u'mine.update',
                            u'minutes': self.opts[u'mine_interval'],
                            u'jid_include': True,
                            u'maxrunning': 2,
                            u'return_job': self.opts.get(u'mine_return_job', False)
                        }
                }, persist=True)
                log.info(u'Added mine.update to scheduler')
            else:
                self.schedule.delete_job(u'__mine_interval', persist=True)

            # add master_alive job if enabled
            if (self.opts[u'transport'] != u'tcp' and
                    self.opts[u'master_alive_interval'] > 0):
                self.schedule.add_job({
                    master_event(type=u'alive', master=self.opts[u'master']):
                        {
                            u'function': u'status.master',
                            u'seconds': self.opts[u'master_alive_interval'],
                            u'jid_include': True,
                            u'maxrunning': 1,
                            u'return_job': False,
                            u'kwargs': {u'master': self.opts[u'master'],
                                        u'connected': True}
                        }
                }, persist=True)
                if self.opts[u'master_failback'] and \
                        u'master_list' in self.opts and \
                        self.opts[u'master'] != self.opts[u'master_list'][0]:
                    self.schedule.add_job({
                        master_event(type=u'failback'):
                        {
                            u'function': u'status.ping_master',
                            u'seconds': self.opts[u'master_failback_interval'],
                            u'jid_include': True,
                            u'maxrunning': 1,
                            u'return_job': False,
                            u'kwargs': {u'master': self.opts[u'master_list'][0]}
                        }
                    }, persist=True)
                else:
                    self.schedule.delete_job(master_event(type=u'failback'), persist=True)
            else:
                self.schedule.delete_job(master_event(type=u'alive', master=self.opts[u'master']), persist=True)
                self.schedule.delete_job(master_event(type=u'failback'), persist=True)

            # proxy keepalive
            proxy_alive_fn = fq_proxyname+u'.alive'
            if (proxy_alive_fn in self.proxy
                and u'status.proxy_reconnect' in self.functions
                and self.opts.get(u'proxy_keep_alive', True)):
                # if `proxy_keep_alive` is either not specified, either set to False does not retry reconnecting
                self.schedule.add_job({
                    u'__proxy_keepalive':
                    {
                        u'function': u'status.proxy_reconnect',
                        u'minutes': self.opts.get(u'proxy_keep_alive_interval', 1),  # by default, check once per minute
                        u'jid_include': True,
                        u'maxrunning': 1,
                        u'return_job': False,
                        u'kwargs': {
                            u'proxy_name': fq_proxyname
                        }
                    }
                }, persist=True)
                self.schedule.enable_schedule()
            else:
                self.schedule.delete_job(u'__proxy_keepalive', persist=True)

        #  Sync the grains here so the proxy can communicate them to the master
        self.functions[u'saltutil.sync_grains'](saltenv=u'base')
        self.grains_cache = self.opts[u'grains']
        self.ready = True

    @classmethod
    def _target(cls, minion_instance, opts, data, connected):
        if not minion_instance:
            minion_instance = cls(opts)
            minion_instance.connected = connected
            if not hasattr(minion_instance, u'functions'):
                # Need to load the modules so they get all the dunder variables
                functions, returners, function_errors, executors = (
                    minion_instance._load_modules(grains=opts[u'grains'])
                    )
                minion_instance.functions = functions
                minion_instance.returners = returners
                minion_instance.function_errors = function_errors
                minion_instance.executors = executors

                # Pull in the utils
                minion_instance.utils = salt.loader.utils(minion_instance.opts)

                # Then load the proxy module
                minion_instance.proxy = salt.loader.proxy(minion_instance.opts, utils=minion_instance.utils)

                # And re-load the modules so the __proxy__ variable gets injected
                functions, returners, function_errors, executors = (
                    minion_instance._load_modules(grains=opts[u'grains'])
                    )
                minion_instance.functions = functions
                minion_instance.returners = returners
                minion_instance.function_errors = function_errors
                minion_instance.executors = executors

                minion_instance.functions.pack[u'__proxy__'] = minion_instance.proxy
                minion_instance.proxy.pack[u'__salt__'] = minion_instance.functions
                minion_instance.proxy.pack[u'__ret__'] = minion_instance.returners
                minion_instance.proxy.pack[u'__pillar__'] = minion_instance.opts[u'pillar']

                # Reload utils as well (chicken and egg, __utils__ needs __proxy__ and __proxy__ needs __utils__
                minion_instance.utils = salt.loader.utils(minion_instance.opts, proxy=minion_instance.proxy)
                minion_instance.proxy.pack[u'__utils__'] = minion_instance.utils

                # Reload all modules so all dunder variables are injected
                minion_instance.proxy.reload_modules()

                fq_proxyname = opts[u'proxy'][u'proxytype']
                proxy_init_fn = minion_instance.proxy[fq_proxyname + u'.init']
                proxy_init_fn(opts)
            if not hasattr(minion_instance, u'serial'):
                minion_instance.serial = salt.payload.Serial(opts)
            if not hasattr(minion_instance, u'proc_dir'):
                uid = salt.utils.user.get_uid(user=opts.get(u'user', None))
                minion_instance.proc_dir = (
                    get_proc_dir(opts[u'cachedir'], uid=uid)
                    )

        with tornado.stack_context.StackContext(minion_instance.ctx):
            if isinstance(data[u'fun'], tuple) or isinstance(data[u'fun'], list):
                Minion._thread_multi_return(minion_instance, opts, data)
            else:
                Minion._thread_return(minion_instance, opts, data)
