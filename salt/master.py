# -*- coding: utf-8 -*-
'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python libs
from __future__ import absolute_import
import os
import re
import sys
import time
import errno
import logging
import tempfile
import multiprocessing

# Import third party libs
import zmq
from Crypto.PublicKey import RSA
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves import range
# pylint: enable=import-error,no-name-in-module,redefined-builtin

import zmq.eventloop.ioloop
# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
import tornado.gen  # pylint: disable=F0401

# Import salt libs
import salt.crypt
import salt.utils
import salt.client
import salt.payload
import salt.pillar
import salt.state
import salt.runner
import salt.auth
import salt.wheel
import salt.minion
import salt.search
import salt.key
import salt.acl
import salt.engines
import salt.fileserver
import salt.daemons.masterapi
import salt.defaults.exitcodes
import salt.transport.server
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.job
import salt.utils.reactor
import salt.utils.verify
import salt.utils.minions
import salt.utils.gzip_util
import salt.utils.process
import salt.utils.zeromq
import salt.utils.jid
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import FileserverConfigError
from salt.utils.debug import (
    enable_sigusr1_handler, enable_sigusr2_handler, inspect_stack
)
from salt.utils.event import tagify
from salt.utils.master import ConnectedCache

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    # resource is not available on windows
    HAS_RESOURCE = False

# Import halite libs
try:
    import halite  # pylint: disable=import-error
    HAS_HALITE = True
except ImportError:
    HAS_HALITE = False


log = logging.getLogger(__name__)


class SMaster(object):
    '''
    Create a simple salt-master, this will generate the top-level master
    '''
    secrets = {}  # mapping of key -> {'secret': multiprocessing type, 'reload': FUNCTION}

    def __init__(self, opts):
        '''
        Create a salt master server instance

        :param dict opts: The salt options dictionary
        '''
        self.opts = opts
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.key = self.__prep_key()

    # We need __setstate__ and __getstate__ to also pickle 'SMaster.secrets'.
    # Otherwise, 'SMaster.secrets' won't be copied over to the spawned process
    # on Windows since spawning processes on Windows requires pickling.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        self.opts = state['opts']
        self.master_key = state['master_key']
        self.key = state['key']
        SMaster.secrets = state['secrets']

    def __getstate__(self):
        return {'opts': self.opts,
                'master_key': self.master_key,
                'key': self.key,
                'secrets': SMaster.secrets}

    def __prep_key(self):
        '''
        A key needs to be placed in the filesystem with permissions 0400 so
        clients are required to run as root.
        '''
        return salt.daemons.masterapi.access_keys(self.opts)


class Maintenance(multiprocessing.Process):
    '''
    A generalized maintenance process which performances maintenance
    routines.
    '''
    def __init__(self, opts):
        '''
        Create a maintenance instance

        :param dict opts: The salt options
        '''
        super(Maintenance, self).__init__()
        self.opts = opts
        # How often do we perform the maintenance tasks
        self.loop_interval = int(self.opts['loop_interval'])
        # Track key rotation intervals
        self.rotate = int(time.time())

    def _post_fork_init(self):
        '''
        Some things need to be init'd after the fork has completed
        The easiest example is that one of these module types creates a thread
        in the parent process, then once the fork happens you'll start getting
        errors like "WARNING: Mixing fork() and threads detected; memory leaked."
        '''
        # Init fileserver manager
        self.fileserver = salt.fileserver.Fileserver(self.opts)
        # Load Runners
        ropts = dict(self.opts)
        ropts['quiet'] = True
        runner_client = salt.runner.RunnerClient(ropts)
        # Load Returners
        self.returners = salt.loader.returners(self.opts, {})

        # Init Scheduler
        self.schedule = salt.utils.schedule.Schedule(self.opts,
                                                     runner_client.functions_dict(),
                                                     returners=self.returners)
        self.ckminions = salt.utils.minions.CkMinions(self.opts)
        # Make Event bus for firing
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'], listen=False)
        # Init any values needed by the git ext pillar
        self.git_pillar = salt.daemons.masterapi.init_git_pillar(self.opts)
        # Set up search object
        self.search = salt.search.Search(self.opts)

    def run(self):
        '''
        This is the general passive maintenance process controller for the Salt
        master.

        This is where any data that needs to be cleanly maintained from the
        master is maintained.
        '''
        salt.utils.appendproctitle('Maintenance')

        # init things that need to be done after the process is forked
        self._post_fork_init()

        # Make Start Times
        last = int(time.time())
        # Clean out the fileserver backend cache
        salt.daemons.masterapi.clean_fsbackend(self.opts)
        # Clean out pub auth
        salt.daemons.masterapi.clean_pub_auth(self.opts)

        old_present = set()
        while True:
            now = int(time.time())
            if (now - last) >= self.loop_interval:
                salt.daemons.masterapi.clean_old_jobs(self.opts)
                salt.daemons.masterapi.clean_expired_tokens(self.opts)
            self.handle_search(now, last)
            self.handle_git_pillar()
            self.handle_schedule()
            self.handle_presence(old_present)
            self.handle_key_rotate(now)
            salt.daemons.masterapi.fileserver_update(self.fileserver)
            salt.utils.verify.check_max_open_files(self.opts)
            last = now
            try:
                time.sleep(self.loop_interval)
            except KeyboardInterrupt:
                break

    def handle_search(self, now, last):
        '''
        Update the search index
        '''
        if self.opts.get('search'):
            if now - last >= self.opts['search_index_interval']:
                self.search.index()

    def handle_key_rotate(self, now):
        '''
        Rotate the AES key rotation
        '''
        to_rotate = False
        dfn = os.path.join(self.opts['cachedir'], '.dfn')
        try:
            stats = os.stat(dfn)
            if stats.st_mode == 0o100400:
                to_rotate = True
            else:
                log.error('Found dropfile with incorrect permissions, ignoring...')
            os.remove(dfn)
        except os.error:
            pass

        if self.opts.get('publish_session'):
            if now - self.rotate >= self.opts['publish_session']:
                to_rotate = True

        if to_rotate:
            log.info('Rotating master AES key')
            for secret_key, secret_map in six.iteritems(SMaster.secrets):
                # should be unecessary-- since no one else should be modifying
                with secret_map['secret'].get_lock():
                    secret_map['secret'].value = secret_map['reload']()
                self.event.fire_event({'rotate_{0}_key'.format(secret_key): True}, tag='key')
            self.rotate = now
            if self.opts.get('ping_on_rotate'):
                # Ping all minions to get them to pick up the new key
                log.debug('Pinging all connected minions '
                          'due to key rotation')
                salt.utils.master.ping_all_connected_minions(self.opts)

    def handle_git_pillar(self):
        '''
        Update git pillar
        '''
        try:
            for pillar in self.git_pillar:
                pillar.update()
        except Exception as exc:
            log.error(
                'Exception \'{0}\' caught while updating git_pillar'
                .format(exc),
                exc_info_on_loglevel=logging.DEBUG
            )

    def handle_schedule(self):
        '''
        Evaluate the scheduler
        '''
        try:
            self.schedule.eval()
            # Check if scheduler requires lower loop interval than
            # the loop_interval setting
            if self.schedule.loop_interval < self.loop_interval:
                self.loop_interval = self.schedule.loop_interval
        except Exception as exc:
            log.error(
                'Exception {0} occurred in scheduled job'.format(exc)
            )

    def handle_presence(self, old_present):
        '''
        Fire presence events if enabled
        '''
        if self.opts.get('presence_events', False):
            present = self.ckminions.connected_ids()
            new = present.difference(old_present)
            lost = old_present.difference(present)
            if new or lost:
                # Fire new minions present event
                data = {'new': list(new),
                        'lost': list(lost)}
                self.event.fire_event(data, tagify('change', 'presence'))
            data = {'present': list(present)}
            self.event.fire_event(data, tagify('present', 'presence'))
            old_present.clear()
            old_present.update(present)


class Master(SMaster):
    '''
    The salt master server
    '''
    def __init__(self, opts):
        '''
        Create a salt master server instance

        :param dict: The salt options
        '''
        # Warn if ZMQ < 3.2
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
        SMaster.__init__(self, opts)

    def __set_max_open_files(self):
        if not HAS_RESOURCE:
            return
        # Let's check to see how our max open files(ulimit -n) setting is
        mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
        if mof_h == resource.RLIM_INFINITY:
            # Unclear what to do with infinity... OSX reports RLIM_INFINITY as
            # hard limit,but raising to anything above soft limit fails...
            mof_h = mof_s
        log.info(
            'Current values for max open files soft/hard setting: '
            '{0}/{1}'.format(
                mof_s, mof_h
            )
        )
        # Let's grab, from the configuration file, the value to raise max open
        # files to
        mof_c = self.opts['max_open_files']
        if mof_c > mof_h:
            # The configured value is higher than what's allowed
            log.info(
                'The value for the \'max_open_files\' setting, {0}, is higher '
                'than what the user running salt is allowed to raise to, {1}. '
                'Defaulting to {1}.'.format(mof_c, mof_h)
            )
            mof_c = mof_h

        if mof_s < mof_c:
            # There's room to raise the value. Raise it!
            log.info('Raising max open files value to {0}'.format(mof_c))
            resource.setrlimit(resource.RLIMIT_NOFILE, (mof_c, mof_h))
            try:
                mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
                log.info(
                    'New values for max open files soft/hard values: '
                    '{0}/{1}'.format(mof_s, mof_h)
                )
            except ValueError:
                # https://github.com/saltstack/salt/issues/1991#issuecomment-13025595
                # A user under OSX reported that our 100000 default value is
                # still too high.
                log.critical(
                    'Failed to raise max open files setting to {0}. If this '
                    'value is too low. The salt-master will most likely fail '
                    'to run properly.'.format(
                        mof_c
                    )
                )

    def _pre_flight(self):
        '''
        Run pre flight checks. If anything in this method fails then the master
        should not start up.
        '''
        errors = []
        critical_errors = []

        if salt.utils.is_windows() and self.opts['user'] == 'root':
            # 'root' doesn't typically exist on Windows. Use the current user
            # home directory instead.
            home = os.path.expanduser('~' + salt.utils.get_user())
        else:
            home = os.path.expanduser('~' + self.opts['user'])
        try:
            if salt.utils.is_windows() and not os.path.isdir(home):
                # On Windows, Service account home directories may not
                # initially exist. If this is the case, make sure the
                # directory exists before continuing.
                os.mkdir(home, 0o755)
            os.chdir(home)
        except OSError as err:
            errors.append(
                'Cannot change to home directory {0} ({1})'.format(home, err)
            )

        fileserver = salt.fileserver.Fileserver(self.opts)
        if not fileserver.servers:
            errors.append(
                'Failed to load fileserver backends, the configured backends '
                'are: {0}'.format(', '.join(self.opts['fileserver_backend']))
            )
        else:
            # Run init() for all backends which support the function, to
            # double-check configuration
            try:
                fileserver.init()
            except FileserverConfigError as exc:
                critical_errors.append('{0}'.format(exc))
        if not self.opts['fileserver_backend']:
            errors.append('No fileserver backends are configured')

        if any('git' in ext_pillar
               for ext_pillar in self.opts.get('ext_pillar', [])):
            try:
                # Init any values needed by the git ext pillar
                salt.utils.gitfs.GitPillar(self.opts)
            except FileserverConfigError as exc:
                critical_errors.append(exc.strerror)

        if errors or critical_errors:
            for error in errors:
                log.error(error)
            for error in critical_errors:
                log.critical(error)
            log.critical('Master failed pre flight checks, exiting\n')
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    # run_reqserver cannot be defined within a class method in order for it
    # to be picklable.
    def run_reqserver(self):
        reqserv = ReqServer(
            self.opts,
            self.key,
            self.master_key)
        reqserv.run()

    def start(self):
        '''
        Turn on the master server components
        '''
        self._pre_flight()
        log.info(
            'salt-master is starting as user {0!r}'.format(salt.utils.get_user())
        )

        enable_sigusr1_handler()
        enable_sigusr2_handler()

        self.__set_max_open_files()
        log.info('Creating master process manager')
        process_manager = salt.utils.process.ProcessManager()
        log.info('Creating master maintenance process')
        pub_channels = []
        for transport, opts in iter_transport_opts(self.opts):
            chan = salt.transport.server.PubServerChannel.factory(opts)
            chan.pre_fork(process_manager)
            pub_channels.append(chan)

        log.info('Creating master event publisher process')
        process_manager.add_process(salt.utils.event.EventPublisher, args=(self.opts,))
        salt.engines.start_engines(self.opts, process_manager)

        # must be after channels
        process_manager.add_process(Maintenance, args=(self.opts,))
        log.info('Creating master publisher process')

        if self.opts.get('reactor'):
            log.info('Creating master reactor process')
            process_manager.add_process(salt.utils.reactor.Reactor, args=(self.opts,))

        if self.opts.get('event_return'):
            log.info('Creating master event return process')
            process_manager.add_process(salt.utils.event.EventReturn, args=(self.opts,))

        ext_procs = self.opts.get('ext_processes', [])
        for proc in ext_procs:
            log.info('Creating ext_processes process: {0}'.format(proc))
            try:
                mod = '.'.join(proc.split('.')[:-1])
                cls = proc.split('.')[-1]
                _tmp = __import__(mod, globals(), locals(), [cls], -1)
                cls = _tmp.__getattribute__(cls)
                process_manager.add_process(cls, args=(self.opts,))
            except Exception:
                log.error(('Error creating ext_processes '
                           'process: {0}').format(proc))

        if HAS_HALITE and 'halite' in self.opts:
            log.info('Creating master halite process')
            process_manager.add_process(Halite, args=(self.opts['halite'],))

        # TODO: remove, or at least push into the transport stuff (pre-fork probably makes sense there)
        if self.opts['con_cache']:
            log.info('Creating master concache process')
            process_manager.add_process(ConnectedCache, args=(self.opts,))
            # workaround for issue #16315, race condition
            log.debug('Sleeping for two seconds to let concache rest')
            time.sleep(2)

        log.info('Creating master request server process')
        process_manager.add_process(self.run_reqserver)
        try:
            process_manager.run()
        except KeyboardInterrupt:
            # Shut the master down gracefully on SIGINT
            log.warn('Stopping the Salt Master')
            process_manager.kill_children()
            raise SystemExit('\nExiting on Ctrl-c')


class Halite(multiprocessing.Process):
    '''
    Manage the Halite server
    '''
    def __init__(self, hopts):
        '''
        Create a halite instance

        :param dict hopts: The halite options
        '''
        super(Halite, self).__init__()
        self.hopts = hopts

    def run(self):
        '''
        Fire up halite!
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        halite.start(self.hopts)


# TODO: move to utils??
def iter_transport_opts(opts):
    '''
    Yield transport, opts for all master configured transports
    '''
    transports = set()

    for transport, opts_overrides in six.iteritems(opts.get('transport_opts', {})):
        t_opts = dict(opts)
        t_opts.update(opts_overrides)
        t_opts['transport'] = transport
        transports.add(transport)
        yield transport, t_opts

    if opts['transport'] not in transports:
        yield opts['transport'], opts


class ReqServer(object):
    '''
    Starts up the master request server, minions send results to this
    interface.
    '''
    def __init__(self, opts, key, mkey):
        '''
        Create a request server

        :param dict opts: The salt options dictionary
        :key dict: The user starting the server and the AES key
        :mkey dict: The user starting the server and the RSA key

        :rtype: ReqServer
        :returns: Request server
        '''
        self.opts = opts
        self.master_key = mkey
        # Prepare the AES key
        self.key = key

    def __bind(self):
        '''
        Binds the reply server
        '''
        dfn = os.path.join(self.opts['cachedir'], '.dfn')
        if os.path.isfile(dfn):
            try:
                os.remove(dfn)
            except os.error:
                pass
        self.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager')

        req_channels = []
        for transport, opts in iter_transport_opts(self.opts):
            chan = salt.transport.server.ReqServerChannel.factory(opts)
            chan.pre_fork(self.process_manager)
            req_channels.append(chan)

        for ind in range(int(self.opts['worker_threads'])):
            self.process_manager.add_process(MWorker,
                                             args=(self.opts,
                                                   self.master_key,
                                                   self.key,
                                                   req_channels,
                                                   ),
                                             )
        self.process_manager.run()

    def run(self):
        '''
        Start up the ReqServer
        '''
        try:
            self.__bind()
        except KeyboardInterrupt:
            log.warn('Stopping the Salt Master')
            raise SystemExit('\nExiting on Ctrl-c')

    def destroy(self):
        if hasattr(self, 'clients') and self.clients.closed is False:
            self.clients.setsockopt(zmq.LINGER, 1)
            self.clients.close()
        if hasattr(self, 'workers') and self.workers.closed is False:
            self.workers.setsockopt(zmq.LINGER, 1)
            self.workers.close()
        if hasattr(self, 'context') and self.context.closed is False:
            self.context.term()
        # Also stop the workers
        if hasattr(self, 'process_manager'):
            self.process_manager.kill_children()

    def __del__(self):
        self.destroy()


class MWorker(multiprocessing.Process):
    '''
    The worker multiprocess instance to manage the backend operations for the
    salt master.
    '''
    def __init__(self,
                 opts,
                 mkey,
                 key,
                 req_channels):
        '''
        Create a salt master worker process

        :param dict opts: The salt options
        :param dict mkey: The user running the salt master and the AES key
        :param dict key: The user running the salt master and the RSA key

        :rtype: MWorker
        :return: Master worker
        '''
        multiprocessing.Process.__init__(self)
        self.opts = opts
        self.req_channels = req_channels

        self.mkey = mkey
        self.key = key
        self.k_mtime = 0

    # We need __setstate__ and __getstate__ to also pickle 'SMaster.secrets'.
    # Otherwise, 'SMaster.secrets' won't be copied over to the spawned process
    # on Windows since spawning processes on Windows requires pickling.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        multiprocessing.Process.__init__(self)
        self.opts = state['opts']
        self.req_channels = state['req_channels']
        self.mkey = state['mkey']
        self.key = state['key']
        self.k_mtime = state['k_mtime']
        SMaster.secrets = state['secrets']

    def __getstate__(self):
        return {'opts': self.opts,
                'req_channels': self.req_channels,
                'mkey': self.mkey,
                'key': self.key,
                'k_mtime': self.k_mtime,
                'secrets': SMaster.secrets}

    def __bind(self):
        '''
        Bind to the local port
        '''
        # using ZMQIOLoop since we *might* need zmq in there
        zmq.eventloop.ioloop.install()
        self.io_loop = zmq.eventloop.ioloop.ZMQIOLoop()
        for req_channel in self.req_channels:
            req_channel.post_fork(self._handle_payload, io_loop=self.io_loop)  # TODO: cleaner? Maybe lazily?
        self.io_loop.start()

    @tornado.gen.coroutine
    def _handle_payload(self, payload):
        '''
        The _handle_payload method is the key method used to figure out what
        needs to be done with communication to the server

        Example cleartext payload generated for 'salt myminion test.ping':

        {'enc': 'clear',
         'load': {'arg': [],
                  'cmd': 'publish',
                  'fun': 'test.ping',
                  'jid': '',
                  'key': 'alsdkjfa.,maljf-==adflkjadflkjalkjadfadflkajdflkj',
                  'kwargs': {'show_jid': False, 'show_timeout': False},
                  'ret': '',
                  'tgt': 'myminion',
                  'tgt_type': 'glob',
                  'user': 'root'}}

        :param dict payload: The payload route to the appropriate handler
        '''
        key = payload['enc']
        load = payload['load']
        ret = {'aes': self._handle_aes,
               'clear': self._handle_clear}[key](load)
        raise tornado.gen.Return(ret)

    def _handle_clear(self, load):
        '''
        Process a cleartext command

        :param dict load: Cleartext payload
        :return: The result of passing the load to a function in ClearFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        log.trace('Clear payload received with command {cmd}'.format(**load))
        if load['cmd'].startswith('__'):
            return False
        return getattr(self.clear_funcs, load['cmd'])(load), {'fun': 'send_clear'}

    def _handle_aes(self, data):
        '''
        Process a command sent via an AES key

        :param str load: Encrypted payload
        :return: The result of passing the load to a function in AESFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        if 'cmd' not in data:
            log.error('Received malformed command {0}'.format(data))
            return {}
        log.trace('AES payload received with command {0}'.format(data['cmd']))
        if data['cmd'].startswith('__'):
            return False
        return self.aes_funcs.run_func(data['cmd'], data)

    def run(self):
        '''
        Start a Master Worker
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        self.clear_funcs = ClearFuncs(
            self.opts,
            self.key,
            )
        self.aes_funcs = AESFuncs(self.opts)
        salt.utils.reinit_crypto()
        self.__bind()


# TODO: rename? No longer tied to "AES", just "encrypted" or "private" requests
class AESFuncs(object):
    '''
    Set up functions that are available when the load is encrypted with AES
    '''
    # The AES Functions:
    #
    def __init__(self, opts):
        '''
        Create a new AESFuncs

        :param dict opts: The salt options

        :rtype: AESFuncs
        :returns: Instance for handling AES operations
        '''
        self.opts = opts
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'], listen=False)
        self.serial = salt.payload.Serial(opts)
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Make a client
        self.local = salt.client.get_local_client(self.opts['conf_file'])
        # Create the master minion to access the external job cache
        self.mminion = salt.minion.MasterMinion(
            self.opts,
            states=False,
            rend=False)
        self.__setup_fileserver()
        self.masterapi = salt.daemons.masterapi.RemoteFuncs(opts)

    def __setup_fileserver(self):
        '''
        Set the local file objects from the file server interface
        '''
        self.fs_ = salt.fileserver.Fileserver(self.opts)
        self._serve_file = self.fs_.serve_file
        self._file_hash = self.fs_.file_hash
        self._file_list = self.fs_.file_list
        self._file_list_emptydirs = self.fs_.file_list_emptydirs
        self._dir_list = self.fs_.dir_list
        self._symlink_list = self.fs_.symlink_list
        self._file_envs = self.fs_.envs

    def __verify_minion(self, id_, token):
        '''
        Take a minion id and a string signed with the minion private key
        The string needs to verify as 'salt' with the minion public key

        :param str id_: A minion ID
        :param str token: A string signed with the minion private key

        :rtype: bool
        :return: Boolean indicating whether or not the token can be verified.
        '''
        if not salt.utils.verify.valid_id(self.opts, id_):
            return False
        pub_path = os.path.join(self.opts['pki_dir'], 'minions', id_)
        with salt.utils.fopen(pub_path, 'r') as fp_:
            minion_pub = fp_.read()
        tmp_pub = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_pub, 'w+') as fp_:
            fp_.write(minion_pub)

        pub = None
        try:
            with salt.utils.fopen(tmp_pub) as fp_:
                pub = RSA.importKey(fp_.read())
        except (ValueError, IndexError, TypeError) as err:
            log.error('Unable to load temporary public key "{0}": {1}'
                      .format(tmp_pub, err))
        try:
            os.remove(tmp_pub)
            if salt.crypt.public_decrypt(pub, token) == 'salt':
                return True
        except ValueError as err:
            log.error('Unable to decrypt token: {0}'.format(err))

        log.error('Salt minion claiming to be {0} has attempted to'
                  'communicate with the master and could not be verified'
                  .format(id_))
        return False

    def __verify_minion_publish(self, clear_load):
        '''
        Verify that the passed information authorized a minion to execute

        :param dict clear_load: A publication load from a minion

        :rtype: bool
        :return: A boolean indicating if the minion is allowed to publish the command in the load
        '''
        # Verify that the load is valid
        if 'peer' not in self.opts:
            return False
        if not isinstance(self.opts['peer'], dict):
            return False
        if any(key not in clear_load for key in ('fun', 'arg', 'tgt', 'ret', 'tok', 'id')):
            return False
        # If the command will make a recursive publish don't run
        if clear_load['fun'].startswith('publish.'):
            return False
        # Check the permissions for this minion
        if not self.__verify_minion(clear_load['id'], clear_load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                (
                    'Minion id {0} is not who it says it is and is attempting '
                    'to issue a peer command'
                ).format(clear_load['id'])
            )
            return False
        clear_load.pop('tok')
        perms = []
        for match in self.opts['peer']:
            if re.match(match, clear_load['id']):
                # This is the list of funcs/modules!
                if isinstance(self.opts['peer'][match], list):
                    perms.extend(self.opts['peer'][match])
        if ',' in clear_load['fun']:
            # 'arg': [['cat', '/proc/cpuinfo'], [], ['foo']]
            clear_load['fun'] = clear_load['fun'].split(',')
            arg_ = []
            for arg in clear_load['arg']:
                arg_.append(arg.split())
            clear_load['arg'] = arg_

        # finally, check the auth of the load
        return self.ckminions.auth_check(
            perms,
            clear_load['fun'],
            clear_load['tgt'],
            clear_load.get('tgt_type', 'glob'),
            publish_validate=True)

    def __verify_load(self, load, verify_keys):
        '''
        A utility function to perform common verification steps.

        :param dict load: A payload received from a minion
        :param list verify_keys: A list of strings that should be present in a given load

        :rtype: bool
        :rtype: dict
        :return: The original load (except for the token) if the load can be verified. False if the load is invalid.
        '''
        if any(key not in load for key in verify_keys):
            return False
        if 'tok' not in load:
            log.error(
                'Received incomplete call from {0} for {1!r}, missing {2!r}'
                .format(
                    load['id'],
                    inspect_stack()['co_name'],
                    'tok'
                ))
            return False
        if not self.__verify_minion(load['id'], load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                'Minion id {0} is not who it says it is!'.format(
                    load['id']
                )
            )
            return False
        if 'tok' in load:
            load.pop('tok')
        return load

    def _ext_nodes(self, load):
        '''
        Return the results from an external node classifier if one is
        specified

        :param dict load: A payload received from a minion
        :return: The results from an external node classifier
        '''
        load = self.__verify_load(load, ('id', 'tok'))
        if load is False:
            return {}
        return self.masterapi._ext_nodes(load, skip_verify=True)

    def _master_opts(self, load):
        '''
        Return the master options to the minion

        :param dict load: A payload received from a minion

        :rtype: dict
        :return: The master options
        '''
        mopts = {}
        file_roots = {}
        envs = self._file_envs()
        for saltenv in envs:
            if saltenv not in file_roots:
                file_roots[saltenv] = []
        mopts['file_roots'] = file_roots
        mopts['env_order'] = self.opts['env_order']
        mopts['top_file_merging_strategy'] = self.opts['top_file_merging_strategy']
        if load.get('env_only'):
            return mopts
        mopts['renderer'] = self.opts['renderer']
        mopts['failhard'] = self.opts['failhard']
        mopts['state_top'] = self.opts['state_top']
        mopts['state_top_saltenv'] = self.opts['state_top_saltenv']
        mopts['nodegroups'] = self.opts['nodegroups']
        mopts['state_auto_order'] = self.opts['state_auto_order']
        mopts['state_events'] = self.opts['state_events']
        mopts['state_aggregate'] = self.opts['state_aggregate']
        mopts['jinja_lstrip_blocks'] = self.opts['jinja_lstrip_blocks']
        mopts['jinja_trim_blocks'] = self.opts['jinja_trim_blocks']
        return mopts

    def _mine_get(self, load):
        '''
        Gathers the data from the specified minions' mine

        :param dict load: A payload received from a minion

        :rtype: dict
        :return: Mine data from the specified minions
        '''
        load = self.__verify_load(load, ('id', 'tgt', 'fun', 'tok'))
        if load is False:
            return {}
        else:
            return self.masterapi._mine_get(load, skip_verify=True)

    def _mine(self, load):
        '''
        Store the mine data

        :param dict load: A payload received from a minion

        :rtype: bool
        :return: True if the data has been stored in the mine
        '''
        load = self.__verify_load(load, ('id', 'data', 'tok'))
        if load is False:
            return {}
        return self.masterapi._mine(load, skip_verify=True)

    def _mine_delete(self, load):
        '''
        Allow the minion to delete a specific function from its own mine

        :param dict load: A payload received from a minion

        :rtype: bool
        :return: Boolean indicating whether or not the given function was deleted from the mine
        '''
        load = self.__verify_load(load, ('id', 'fun', 'tok'))
        if load is False:
            return {}
        else:
            return self.masterapi._mine_delete(load)

    def _mine_flush(self, load):
        '''
        Allow the minion to delete all of its own mine contents

        :param dict load: A payload received from a minion
        '''
        load = self.__verify_load(load, ('id', 'tok'))
        if load is False:
            return {}
        else:
            return self.masterapi._mine_flush(load, skip_verify=True)

    def _file_recv(self, load):
        '''
        Allows minions to send files to the master, files are sent to the
        master file cache
        '''
        if any(key not in load for key in ('id', 'path', 'loc')):
            return False
        if not self.opts['file_recv'] or os.path.isabs(load['path']):
            return False
        if os.path.isabs(load['path']) or '../' in load['path']:
            # Can overwrite master files!!
            return False
        if not salt.utils.verify.valid_id(self.opts, load['id']):
            return False
        file_recv_max_size = 1024*1024 * self.opts['file_recv_max_size']

        if 'loc' in load and load['loc'] < 0:
            log.error('Invalid file pointer: load[loc] < 0')
            return False

        if len(load['data']) + load.get('loc', 0) > file_recv_max_size:
            log.error(
                'Exceeding file_recv_max_size limit: {0}'.format(
                    file_recv_max_size
                )
            )
            return False
        if 'tok' not in load:
            log.error(
                'Received incomplete call from {0} for {1!r}, missing {2!r}'
                .format(
                    load['id'],
                    inspect_stack()['co_name'],
                    'tok'
                ))
            return False
        if not self.__verify_minion(load['id'], load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                'Minion id {0} is not who it says it is!'.format(
                    load['id']
                )
            )
            return {}
        load.pop('tok')
        # Normalize Windows paths
        normpath = load['path']
        if ':' in normpath:
            # make sure double backslashes are normalized
            normpath = normpath.replace('\\', '/')
            normpath = os.path.normpath(normpath)
        cpath = os.path.join(
            self.opts['cachedir'],
            'minions',
            load['id'],
            'files',
            normpath)
        cdir = os.path.dirname(cpath)
        if not os.path.isdir(cdir):
            try:
                os.makedirs(cdir)
            except os.error:
                pass
        if os.path.isfile(cpath) and load['loc'] != 0:
            mode = 'ab'
        else:
            mode = 'wb'
        with salt.utils.fopen(cpath, mode) as fp_:
            if load['loc']:
                fp_.seek(load['loc'])
            fp_.write(load['data'])
        return True

    def _pillar(self, load):
        '''
        Return the pillar data for the minion

        :param dict load: Minion payload

        :rtype: dict
        :return: The pillar data for the minion
        '''
        if any(key not in load for key in ('id', 'grains')):
            return False
        if not salt.utils.verify.valid_id(self.opts, load['id']):
            return False
        load['grains']['id'] = load['id']

        pillar_dirs = {}
        pillar = salt.pillar.Pillar(
            self.opts,
            load['grains'],
            load['id'],
            load.get('saltenv', load.get('env')),
            ext=load.get('ext'),
            pillar=load.get('pillar_override', {}),
            pillarenv=load.get('pillarenv'))
        data = pillar.compile_pillar(pillar_dirs=pillar_dirs)
        self.fs_.update_opts()
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                os.makedirs(cdir)
            datap = os.path.join(cdir, 'data.p')
            tmpfh, tmpfname = tempfile.mkstemp(dir=cdir)
            os.close(tmpfh)
            with salt.utils.fopen(tmpfname, 'w+b') as fp_:
                fp_.write(
                    self.serial.dumps(
                        {'grains': load['grains'],
                         'pillar': data})
                    )
            # On Windows, os.rename will fail if the destination file exists.
            salt.utils.atomicfile.atomic_rename(tmpfname, datap)
        return data

    def _minion_event(self, load):
        '''
        Receive an event from the minion and fire it on the master event
        interface

        :param dict load: The minion payload
        '''
        load = self.__verify_load(load, ('id', 'tok'))
        if load is False:
            return {}
        # Route to master event bus
        self.masterapi._minion_event(load)
        # Process locally
        self._handle_minion_event(load)

    def _handle_minion_event(self, load):
        '''
        Act on specific events from minions
        '''
        if load.get('tag', '') == '_salt_error':
            log.error('Received minion error from [{minion}]: '
                      '{data}'.format(minion=load['id'],
                                      data=load['data']['message']))

    def _return(self, load):
        '''
        Handle the return data sent from the minions.

        Takes the return, verifies it and fires it on the master event bus.
        Typically, this event is consumed by the Salt CLI waiting on the other
        end of the event bus but could be heard by any listener on the bus.

        :param dict load: The minion payload
        '''
        salt.utils.job.store_job(
            self.opts, load, event=self.event, mminion=self.mminion)

    def _syndic_return(self, load):
        '''
        Receive a syndic minion return and format it to look like returns from
        individual minions.

        :param dict load: The minion payload
        '''
        # Verify the load
        if any(key not in load for key in ('return', 'jid', 'id')):
            return None
        # if we have a load, save it
        if load.get('load'):
            fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[fstr](load['jid'], load['load'])

        # Register the syndic
        syndic_cache_path = os.path.join(self.opts['cachedir'], 'syndics', load['id'])
        if not os.path.exists(syndic_cache_path):
            path_name = os.path.split(syndic_cache_path)[0]
            if not os.path.exists(path_name):
                os.makedirs(path_name)
            with salt.utils.fopen(syndic_cache_path, 'w') as f:
                f.write('')

        # Format individual return loads
        for key, item in six.iteritems(load['return']):
            ret = {'jid': load['jid'],
                   'id': key,
                   'return': item}
            if 'master_id' in load:
                ret['master_id'] = load['master_id']
            if 'fun' in load:
                ret['fun'] = load['fun']
            if 'arg' in load:
                ret['fun_args'] = load['arg']
            if 'out' in load:
                ret['out'] = load['out']
            self._return(ret)

    def minion_runner(self, clear_load):
        '''
        Execute a runner from a minion, return the runner's function data

        :param dict clear_load: The minion payload

        :rtype: dict
        :return: The runner function data
        '''
        load = self.__verify_load(clear_load, ('fun', 'arg', 'id', 'tok'))
        if load is False:
            return {}
        else:
            return self.masterapi.minion_runner(clear_load)

    def pub_ret(self, load):
        '''
        Request the return data from a specific jid, only allowed
        if the requesting minion also initialted the execution.

        :param dict load: The minion payload

        :rtype: dict
        :return: Return data corresponding to a given JID
        '''
        load = self.__verify_load(load, ('jid', 'id', 'tok'))
        if load is False:
            return {}
        # Check that this minion can access this data
        auth_cache = os.path.join(
            self.opts['cachedir'],
            'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, str(load['jid']))
        with salt.utils.fopen(jid_fn, 'r') as fp_:
            if not load['id'] == fp_.read():
                return {}
        # Grab the latest and return
        return self.local.get_cache_returns(load['jid'])

    def minion_pub(self, clear_load):
        '''
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.

        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions

        The config will look like this:

        .. code-block:: bash

            peer:
                .*:
                    - .*

        This configuration will enable all minions to execute all commands:

        .. code-block:: bash

            peer:
                foo.example.com:
                    - test.*

        The above configuration will only allow the minion foo.example.com to
        execute commands from the test module.

        :param dict clear_load: The minion pay
        '''
        if not self.__verify_minion_publish(clear_load):
            return {}
        else:
            return self.masterapi.minion_pub(clear_load)

    def minion_publish(self, clear_load):
        '''
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.

        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions

        The config will look like this:

        .. code-block:: bash

            peer:
                .*:
                    - .*

        This configuration will enable all minions to execute all commands.
        peer:

        .. code-block:: bash

            foo.example.com:
                - test.*

        The above configuration will only allow the minion foo.example.com to
        execute commands from the test module.

        :param dict clear_load: The minion payload
        '''
        if not self.__verify_minion_publish(clear_load):
            return {}
        else:
            return self.masterapi.minion_publish(clear_load)

    def revoke_auth(self, load):
        '''
        Allow a minion to request revocation of its own key

        :param dict load: The minion payload

        :rtype: dict
        :return: If the load is invalid, it may be returned. No key operation is performed.

        :rtype: bool
        :return: True if key was revoked, False if not
        '''
        load = self.__verify_load(load, ('id', 'tok'))
        if load is False:
            return load
        else:
            return self.masterapi.revoke_auth(load)

    def run_func(self, func, load):
        '''
        Wrapper for running functions executed with AES encryption

        :param function func: The function to run
        :return: The result of the master function that was called
        '''
        # Don't honor private functions
        if func.startswith('__'):
            # TODO: return some error? Seems odd to return {}
            return {}, {'fun': 'send'}
        # Run the func
        if hasattr(self, func):
            try:
                start = time.time()
                ret = getattr(self, func)(load)
                log.trace(
                    'Master function call {0} took {1} seconds'.format(
                        func, time.time() - start
                    )
                )
            except Exception:
                ret = ''
                log.error(
                    'Error in function {0}:\n'.format(func),
                    exc_info=True
                )
        else:
            log.error(
                'Received function {0} which is unavailable on the master, '
                'returning False'.format(
                    func
                )
            )
            return False, {'fun': 'send'}
        # Don't encrypt the return value for the _return func
        # (we don't care about the return value, so why encrypt it?)
        if func == '_return':
            return ret, {'fun': 'send'}
        if func == '_pillar' and 'id' in load:
            if load.get('ver') != '2' and self.opts['pillar_version'] == 1:
                # Authorized to return old pillar proto
                return ret, {'fun': 'send'}
            return ret, {'fun': 'send_private', 'key': 'pillar', 'tgt': load['id']}
        # Encrypt the return
        return ret, {'fun': 'send'}


class ClearFuncs(object):
    '''
    Set up functions that are safe to execute when commands sent to the master
    without encryption and authentication
    '''
    # The ClearFuncs object encapsulates the functions that can be executed in
    # the clear:
    # publish (The publish from the LocalClient)
    # _auth
    def __init__(self, opts, key):
        self.opts = opts
        self.key = key
        # Create the event manager
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'], listen=False)
        # Make a client
        self.local = salt.client.get_local_client(self.opts['conf_file'])
        # Make an minion checker object
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Make an Auth object
        self.loadauth = salt.auth.LoadAuth(opts)
        # Stand up the master Minion to access returner data
        self.mminion = salt.minion.MasterMinion(
            self.opts,
            states=False,
            rend=False)
        # Make a wheel object
        self.wheel_ = salt.wheel.Wheel(opts)
        # Make a masterapi object
        self.masterapi = salt.daemons.masterapi.LocalFuncs(opts, key)

    def process_token(self, tok, fun, auth_type):
        '''
        Process a token and determine if a command is authorized
        '''
        try:
            token = self.loadauth.get_tok(tok)
        except Exception as exc:
            msg = 'Exception occurred when generating auth token: {0}'.format(
                  exc)
            log.error(msg)
            return dict(error=dict(name='TokenAuthenticationError',
                                   message=msg))
        if not token:
            msg = 'Authentication failure of type "token" occurred.'
            log.warning(msg)
            return dict(error=dict(name='TokenAuthenticationError',
                                   message=msg))
        if token['eauth'] not in self.opts['external_auth']:
            msg = 'Authentication failure of type "token" occurred.'
            log.warning(msg)
            return dict(error=dict(name='TokenAuthenticationError',
                                   message=msg))

        check_fun = getattr(self.ckminions,
                            '{auth}_check'.format(auth=auth_type))
        if token['name'] in self.opts['external_auth'][token['eauth']]:
            good = check_fun(self.opts['external_auth'][token['eauth']][token['name']], fun)
        elif any(key.endswith('%') for key in self.opts['external_auth'][token['eauth']]):
            for group in self.opts['external_auth'][token['eauth']]:
                if group.endswith('%'):
                    for group in self.opts['external_auth'][token['eauth']]:
                        good = check_fun(self.opts['external_auth'][token['eauth']][group], fun)
                        if good:
                            break
        else:
            good = check_fun(self.opts['external_auth'][token['eauth']]['*'], fun)
        if not good:
            msg = ('Authentication failure of type "token" occurred for '
                   'user {0}.').format(token['name'])
            log.warning(msg)
            return dict(error=dict(name='TokenAuthenticationError',
                                   message=msg))
        return None

    def process_eauth(self, clear_load, auth_type):
        '''
        Process a clear load to determine eauth perms

        Any return other than None is an eauth failure
        '''

        if 'eauth' not in clear_load:
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))
        if clear_load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))

        name = self.loadauth.load_name(clear_load)
        if not ((name in self.opts['external_auth'][clear_load['eauth']]) |
                ('*' in self.opts['external_auth'][clear_load['eauth']])):
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))
        if not self.loadauth.time_auth(clear_load):
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))

        check_fun = getattr(self.ckminions,
                            '{auth}_check'.format(auth=auth_type))
        if name in self.opts['external_auth'][clear_load['eauth']]:
            good = check_fun(self.opts['external_auth'][clear_load['eauth']][name], clear_load['fun'])
        elif any(key.endswith('%') for key in self.opts['external_auth'][clear_load['eauth']]):
            for group in self.opts['external_auth'][clear_load['eauth']]:
                if group.endswith('%'):
                    good = check_fun(self.opts['external_auth'][clear_load['eauth']][group], clear_load['fun'])
                    if good:
                        break
        else:
            good = check_fun(self.opts['external_auth'][clear_load['eauth']]['*'], clear_load['fun'])
        if not good:
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))
        return None

    def runner(self, clear_load):
        '''
        Send a master control function back to the runner system
        '''
        # All runner ops pass through eauth
        if 'token' in clear_load:
            auth_error = self.process_token(clear_load['token'],
                                            clear_load['fun'],
                                            'runner')
            if auth_error:
                return auth_error
            else:
                token = self.loadauth.get_tok(clear_load.pop('token'))
            try:
                fun = clear_load.pop('fun')
                runner_client = salt.runner.RunnerClient(self.opts)
                return runner_client.async(
                    fun,
                    clear_load.get('kwarg', {}),
                    token['name'])
            except Exception as exc:
                log.error('Exception occurred while '
                          'introspecting {0}: {1}'.format(fun, exc))
                return dict(error=dict(name=exc.__class__.__name__,
                                       args=exc.args,
                                       message=str(exc)))

        try:
            eauth_error = self.process_eauth(clear_load, 'runner')
            if eauth_error:
                return eauth_error
            # No error occurred, consume the password from the clear_load if
            # passed
            clear_load.pop('password', None)
            try:
                fun = clear_load.pop('fun')
                runner_client = salt.runner.RunnerClient(self.opts)
                return runner_client.async(fun,
                                           clear_load.get('kwarg', {}),
                                           clear_load.pop('username', 'UNKNOWN'))
            except Exception as exc:
                log.error('Exception occurred while '
                          'introspecting {0}: {1}'.format(fun, exc))
                return dict(error=dict(name=exc.__class__.__name__,
                                       args=exc.args,
                                       message=str(exc)))

        except Exception as exc:
            log.error(
                'Exception occurred in the runner system: {0}'.format(exc)
            )
            return dict(error=dict(name=exc.__class__.__name__,
                                   args=exc.args,
                                   message=str(exc)))

    def wheel(self, clear_load):
        '''
        Send a master control function back to the wheel system
        '''
        # All wheel ops pass through eauth
        if 'token' in clear_load:
            auth_error = self.process_token(clear_load['token'],
                                            clear_load['fun'],
                                            'wheel')
            if auth_error:
                return auth_error
            else:
                token = self.loadauth.get_tok(clear_load.pop('token'))

            jid = salt.utils.jid.gen_jid()
            fun = clear_load.pop('fun')
            tag = tagify(jid, prefix='wheel')
            data = {'fun': "wheel.{0}".format(fun),
                    'jid': jid,
                    'tag': tag,
                    'user': token['name']}
            try:
                self.event.fire_event(data, tagify([jid, 'new'], 'wheel'))
                ret = self.wheel_.call_func(fun, **clear_load)
                data['return'] = ret
                data['success'] = True
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}
            except Exception as exc:
                log.error(exc)
                log.error('Exception occurred while '
                          'introspecting {0}: {1}'.format(fun, exc))
                data['return'] = 'Exception occurred in wheel {0}: {1}: {2}'.format(
                    fun,
                    exc.__class__.__name__,
                    exc,
                    )
                data['success'] = False
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}
        try:
            eauth_error = self.process_eauth(clear_load, 'wheel')
            if eauth_error:
                return eauth_error

            # No error occurred, consume the password from the clear_load if
            # passed
            clear_load.pop('password', None)
            jid = salt.utils.jid.gen_jid()
            fun = clear_load.pop('fun')
            tag = tagify(jid, prefix='wheel')
            data = {'fun': "wheel.{0}".format(fun),
                    'jid': jid,
                    'tag': tag,
                    'user': clear_load.pop('username', 'UNKNOWN')}
            try:
                self.event.fire_event(data, tagify([jid, 'new'], 'wheel'))
                ret = self.wheel_.call_func(fun, **clear_load)
                data['return'] = ret
                data['success'] = True
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}
            except Exception as exc:
                log.error('Exception occurred while '
                          'introspecting {0}: {1}'.format(fun, exc))
                data['return'] = 'Exception occurred in wheel {0}: {1}: {2}'.format(
                                 fun,
                                 exc.__class__.__name__,
                                 exc,
                )
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}

        except Exception as exc:
            log.error(
                'Exception occurred in the wheel system: {0}'.format(exc)
            )
            return dict(error=dict(name=exc.__class__.__name__,
                                   args=exc.args,
                                   message=str(exc)))

    def mk_token(self, clear_load):
        '''
        Create and return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        '''

        if 'eauth' not in clear_load:
            log.warning('Authentication failure of type "eauth" occurred.')
            return ''
        if clear_load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            log.warning('Authentication failure of type "eauth" occurred.')
            return ''
        try:
            name = self.loadauth.load_name(clear_load)
            groups = self.loadauth.get_groups(clear_load)
            eauth_config = self.opts['external_auth'][clear_load['eauth']]
            if '*' not in eauth_config and name not in eauth_config:
                found = False
                for group in groups:
                    if "{0}%".format(group) in eauth_config:
                        found = True
                        break
                if not found:
                    log.warning('Authentication failure of type "eauth" occurred.')
                    return ''
            if not self.loadauth.time_auth(clear_load):
                log.warning('Authentication failure of type "eauth" occurred.')
                return ''

            clear_load['groups'] = groups
            return self.loadauth.mk_token(clear_load)
        except Exception as exc:
            import sys
            import traceback

            type_, value_, traceback_ = sys.exc_info()
            log.error(
                'Exception occurred while authenticating: {0}'.format(exc)
            )
            log.error(traceback.format_exception(type_, value_, traceback_))
            return ''

    def get_token(self, clear_load):
        '''
        Return the name associated with a token or False if the token is invalid
        '''
        if 'token' not in clear_load:
            return False
        return self.loadauth.get_tok(clear_load['token'])

    def publish(self, clear_load):
        '''
        This method sends out publications to the minions, it can only be used
        by the LocalClient.
        '''
        extra = clear_load.get('kwargs', {})

        client_acl = salt.acl.ClientACL(self.opts['client_acl_blacklist'])

        if client_acl.user_is_blacklisted(clear_load['user']) or \
                client_acl.cmd_is_blacklisted(clear_load['fun']):
            log.error(
                '{user} does not have permissions to run {function}. Please '
                'contact your local administrator if you believe this is in '
                'error.\n'.format(
                    user=clear_load['user'],
                    function=clear_load['fun']
                )
            )
            return ''

        # Check for external auth calls
        if extra.get('token', False):
            # A token was passed, check it
            try:
                token = self.loadauth.get_tok(extra['token'])
            except Exception as exc:
                log.error(
                    'Exception occurred when generating auth token: {0}'.format(
                        exc
                    )
                )
                return ''

            # Bail if the token is empty or if the eauth type specified is not allowed
            if not token or token['eauth'] not in self.opts['external_auth']:
                log.warning('Authentication failure of type "token" occurred.')
                return ''

            # Fetch eauth config and collect users and groups configured for access
            eauth_config = self.opts['external_auth'][token['eauth']]
            eauth_users = []
            eauth_groups = []
            for entry in eauth_config:
                if entry.endswith('%'):
                    eauth_groups.append(entry.rstrip('%'))
                else:
                    eauth_users.append(entry)

            # If there are groups in the token, check if any of them are listed in the eauth config
            group_auth_match = False
            try:
                for group in token['groups']:
                    if group in eauth_groups:
                        group_auth_match = True
                        break
            except KeyError:
                pass
            if '*' not in eauth_users and token['name'] not in eauth_users and not group_auth_match:
                log.warning('Authentication failure of type "token" occurred.')
                return ''

            # Compile list of authorized actions for the user
            auth_list = []
            # Add permissions for '*' or user-specific to the auth list
            for user_key in ('*', token['name']):
                auth_list.extend(eauth_config.get(user_key, []))
            # Add any add'l permissions allowed by group membership
            if group_auth_match:
                auth_list = self.ckminions.fill_auth_list_from_groups(eauth_config, token['groups'], auth_list)

            log.trace("Compiled auth_list: {0}".format(auth_list))

            good = self.ckminions.auth_check(
                auth_list,
                clear_load['fun'],
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob'))
            if not good:
                # Accept find_job so the CLI will function cleanly
                if clear_load['fun'] != 'saltutil.find_job':
                    log.warning(
                        'Authentication failure of type "token" occurred.'
                    )
                    return ''
            clear_load['user'] = token['name']
            log.debug('Minion tokenized user = "{0}"'.format(clear_load['user']))
        elif 'eauth' in extra:
            if extra['eauth'] not in self.opts['external_auth']:
                # The eauth system is not enabled, fail
                log.warning(
                    'Authentication failure of type "eauth" occurred.'
                )
                return ''
            try:
                name = self.loadauth.load_name(extra)  # The username we are attempting to auth with
                groups = self.loadauth.get_groups(extra)  # The groups this user belongs to
                if groups is None:
                    groups = []
                group_perm_keys = filter(lambda(item): item.endswith('%'), self.opts['external_auth'][extra['eauth']])  # The configured auth groups

                # First we need to know if the user is allowed to proceed via any of their group memberships.
                group_auth_match = False
                for group_config in group_perm_keys:
                    group_config = group_config.rstrip('%')
                    for group in groups:
                        if group == group_config:
                            group_auth_match = True
                # If a group_auth_match is set it means only that we have a
                # user which matches at least one or more of the groups defined
                # in the configuration file.

                external_auth_in_db = False
                for d in self.opts['external_auth'][extra['eauth']]:
                    if d.startswith('^'):
                        external_auth_in_db = True

                # If neither a catchall, a named membership or a group
                # membership is found, there is no need to continue. Simply
                # deny the user access.
                if not ((name in self.opts['external_auth'][extra['eauth']]) |
                        ('*' in self.opts['external_auth'][extra['eauth']]) |
                        group_auth_match | external_auth_in_db):

                        # A group def is defined and the user is a member
                        #[group for groups in ['external_auth'][extra['eauth']]]):
                    # Auth successful, but no matching user found in config
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''

                # Perform the actual authentication. If we fail here, do not
                # continue.
                if not self.loadauth.time_auth(extra):
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''

            except Exception as exc:
                import sys
                import traceback

                type_, value_, traceback_ = sys.exc_info()
                log.error(
                    'Exception occurred while authenticating: {0}'.format(exc)
                )
                log.error(traceback.format_exception(
                    type_, value_, traceback_))
                return ''

#            auth_list = self.opts['external_auth'][extra['eauth']][name] if name in self.opts['external_auth'][extra['eauth']] else self.opts['external_auth'][extra['eauth']]['*']

            # We now have an authenticated session and it is time to determine
            # what the user has access to.

            auth_list = []
            if name in self.opts['external_auth'][extra['eauth']]:
                auth_list = self.opts['external_auth'][extra['eauth']][name]
            if group_auth_match:
                auth_list = self.ckminions.fill_auth_list_from_groups(self.opts['external_auth'][extra['eauth']], groups, auth_list)

            good = self.ckminions.auth_check(
                auth_list,
                clear_load['fun'],
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob')
                )
            if not good:
                # Accept find_job so the CLI will function cleanly
                if clear_load['fun'] != 'saltutil.find_job':
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''
            clear_load['user'] = name
        # Verify that the caller has root on master
        elif 'user' in clear_load:
            auth_user = salt.auth.AuthUser(clear_load['user'])
            if auth_user.is_sudo():
                # If someone sudos check to make sure there is no ACL's around their username
                if clear_load.get('key', 'invalid') == self.key.get('root'):
                    clear_load.pop('key')
                elif clear_load.pop('key') != self.key[self.opts.get('user', 'root')]:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
                if self.opts['sudo_acl'] and self.opts['client_acl']:
                    good = self.ckminions.auth_check(
                                self.opts['client_acl'].get(clear_load['user'].split('_', 1)[-1]),
                                clear_load['fun'],
                                clear_load['tgt'],
                                clear_load.get('tgt_type', 'glob'))
                    if not good:
                        # Accept find_job so the CLI will function cleanly
                        if clear_load['fun'] != 'saltutil.find_job':
                            log.warning(
                                'Authentication failure of type "user" '
                                'occurred.'
                            )
                            return ''
            elif clear_load['user'] == self.opts.get('user', 'root') or clear_load['user'] == 'root':
                if clear_load.pop('key') != self.key[self.opts.get('user', 'root')]:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif auth_user.is_running_user():
                if clear_load.pop('key') != self.key.get(clear_load['user']):
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif clear_load.get('key', 'invalid') == self.key.get('root'):
                clear_load.pop('key')
            else:
                if clear_load['user'] in self.key:
                    # User is authorised, check key and check perms
                    if clear_load.pop('key') != self.key[clear_load['user']]:
                        log.warning(
                            'Authentication failure of type "user" occurred.'
                        )
                        return ''
                    if clear_load['user'] not in self.opts['client_acl']:
                        log.warning(
                            'Authentication failure of type "user" occurred.'
                        )
                        return ''
                    good = self.ckminions.auth_check(
                        self.opts['client_acl'][clear_load['user']],
                        clear_load['fun'],
                        clear_load['tgt'],
                        clear_load.get('tgt_type', 'glob'))
                    if not good:
                        # Accept find_job so the CLI will function cleanly
                        if clear_load['fun'] != 'saltutil.find_job':
                            log.warning(
                                'Authentication failure of type "user" '
                                'occurred.'
                            )
                            return ''
                else:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
        else:
            if clear_load.pop('key') != self.key[salt.utils.get_user()]:
                log.warning(
                    'Authentication failure of type "other" occurred.'
                )
                return ''
        # FIXME Needs additional refactoring
        # Retrieve the minions list
        delimiter = clear_load.get('kwargs', {}).get('delimiter', DEFAULT_TARGET_DELIM)
        minions = self.ckminions.check_minions(
            clear_load['tgt'],
            clear_load.get('tgt_type', 'glob'),
            delimiter
        )
        # If we order masters (via a syndic), don't short circuit if no minions
        # are found
        if not self.opts.get('order_masters'):
            # Check for no minions
            if not minions:
                return {
                    'enc': 'clear',
                    'load': {
                        'jid': None,
                        'minions': minions
                    }
                }
        jid = self._prep_jid(clear_load, extra)
        if jid is None:
            return {}
        payload = self._prep_pub(minions, jid, clear_load, extra)

        # Send it!
        self._send_pub(payload)

        return {
            'enc': 'clear',
            'load': {
                'jid': clear_load['jid'],
                'minions': minions
            }
        }

    def _prep_jid(self, clear_load, extra):
        '''
        Return a jid for this publication
        '''
        # the jid in clear_load can be None, '', or something else. this is an
        # attempt to clean up the value before passing to plugins
        passed_jid = clear_load['jid'] if clear_load.get('jid') else None
        nocache = extra.get('nocache', False)

        # Retrieve the jid
        fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
        try:
            # Retrieve the jid
            jid = self.mminion.returners[fstr](nocache=nocache,
                                               passed_jid=passed_jid)
        except (KeyError, TypeError):
            # The returner is not present
            msg = (
                'Failed to allocate a jid. The requested returner \'{0}\' '
                'could not be loaded.'.format(fstr.split('.')[0])
            )
            log.error(msg)
            return {'error': msg}
        return jid

    def _send_pub(self, load):
        '''
        Take a load and send it across the network to connected minions
        '''
        for transport, opts in iter_transport_opts(self.opts):
            chan = salt.transport.server.PubServerChannel.factory(opts)
            chan.publish(load)

    def _prep_pub(self, minions, jid, clear_load, extra):
        '''
        Take a given load and perform the necessary steps
        to prepare a publication.

        TODO: This is really only bound by temporal cohesion
        and thus should be refactored even further.
        '''
        clear_load['jid'] = jid
        delimiter = clear_load.get('kwargs', {}).get('delimiter', DEFAULT_TARGET_DELIM)

        # TODO Error reporting over the master event bus
        self.event.fire_event({'minions': minions}, clear_load['jid'])
        new_job_load = {
            'jid': clear_load['jid'],
            'tgt_type': clear_load['tgt_type'],
            'tgt': clear_load['tgt'],
            'user': clear_load['user'],
            'fun': clear_load['fun'],
            'arg': clear_load['arg'],
            'minions': minions,
            }

        # Announce the job on the event bus
        self.event.fire_event(new_job_load, tagify([clear_load['jid'], 'new'], 'job'))

        if self.opts['ext_job_cache']:
            try:
                fstr = '{0}.save_load'.format(self.opts['ext_job_cache'])
                self.mminion.returners[fstr](clear_load['jid'], clear_load)
            except KeyError:
                log.critical(
                    'The specified returner used for the external job cache '
                    '"{0}" does not have a save_load function!'.format(
                        self.opts['ext_job_cache']
                    )
                )
            except Exception:
                log.critical(
                    'The specified returner threw a stack trace:\n',
                    exc_info=True
                )

        # always write out to the master job caches
        try:
            fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[fstr](clear_load['jid'], clear_load)
        except KeyError:
            log.critical(
                'The specified returner used for the master job cache '
                '"{0}" does not have a save_load function!'.format(
                    self.opts['master_job_cache']
                )
            )
        except Exception:
            log.critical(
                'The specified returner threw a stack trace:\n',
                exc_info=True
            )
        # Set up the payload
        payload = {'enc': 'aes'}
        # Altering the contents of the publish load is serious!! Changes here
        # break compatibility with minion/master versions and even tiny
        # additions can have serious implications on the performance of the
        # publish commands.
        #
        # In short, check with Thomas Hatch before you even think about
        # touching this stuff, we can probably do what you want to do another
        # way that won't have a negative impact.
        load = {
            'fun': clear_load['fun'],
            'arg': clear_load['arg'],
            'tgt': clear_load['tgt'],
            'jid': clear_load['jid'],
            'ret': clear_load['ret'],
        }
        # if you specified a master id, lets put that in the load
        if 'master_id' in self.opts:
            load['master_id'] = self.opts['master_id']
        # if someone passed us one, use that
        if 'master_id' in extra:
            load['master_id'] = extra['master_id']
        # Only add the delimiter to the pub data if it is non-default
        if delimiter != DEFAULT_TARGET_DELIM:
            load['delimiter'] = delimiter

        if 'id' in extra:
            load['id'] = extra['id']
        if 'tgt_type' in clear_load:
            load['tgt_type'] = clear_load['tgt_type']
        if 'to' in clear_load:
            load['to'] = clear_load['to']

        if 'kwargs' in clear_load:
            if 'ret_config' in clear_load['kwargs']:
                load['ret_config'] = clear_load['kwargs'].get('ret_config')

            if 'metadata' in clear_load['kwargs']:
                load['metadata'] = clear_load['kwargs'].get('metadata')

        if 'user' in clear_load:
            log.info(
                'User {user} Published command {fun} with jid {jid}'.format(
                    **clear_load
                )
            )
            load['user'] = clear_load['user']
        else:
            log.info(
                'Published command {fun} with jid {jid}'.format(
                    **clear_load
                )
            )
        log.debug('Published command details {0}'.format(load))
        return load


class FloMWorker(MWorker):
    '''
    Change the run and bind to be ioflo friendly
    '''
    def __init__(self,
                 opts,
                 key,
                 ):
        MWorker.__init__(self, opts, key)

    def setup(self):
        '''
        Prepare the needed objects and socket for iteration within ioflo
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        self.clear_funcs = salt.master.ClearFuncs(
                self.opts,
                self.key,
                )
        self.aes_funcs = salt.master.AESFuncs(self.opts)
        self.context = zmq.Context(1)
        self.socket = self.context.socket(zmq.REP)
        if self.opts.get('ipc_mode', '') == 'tcp':
            self.w_uri = 'tcp://127.0.0.1:{0}'.format(
                self.opts.get('tcp_master_workers', 4515)
                )
        else:
            self.w_uri = 'ipc://{0}'.format(
                os.path.join(self.opts['sock_dir'], 'workers.ipc')
                )
        log.info('ZMQ Worker binding to socket {0}'.format(self.w_uri))
        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self.socket.connect(self.w_uri)

    def handle_request(self):
        '''
        Handle a single request
        '''
        try:
            polled = self.poller.poll(1)
            if polled:
                package = self.socket.recv()
                self._update_aes()
                payload = self.serial.loads(package)
                ret = self.serial.dumps(self._handle_payload(payload))
                self.socket.send(ret)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            # Properly handle EINTR from SIGUSR1
            if isinstance(exc, zmq.ZMQError) and exc.errno == errno.EINTR:
                return
