# -*- coding: utf-8 -*-
'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python libs
from __future__ import absolute_import, with_statement
import copy
import ctypes
import os
import re
import sys
import time
import errno
import signal
import stat
import logging
import multiprocessing
import salt.serializers.msgpack

# Import third party libs
try:
    from Cryptodome.PublicKey import RSA
except ImportError:
    # Fall back to pycrypto
    from Crypto.PublicKey import RSA
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range
# pylint: enable=import-error,no-name-in-module,redefined-builtin

try:
    import zmq
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
import salt.key
import salt.acl
import salt.engines
import salt.fileserver
import salt.daemons.masterapi
import salt.defaults.exitcodes
import salt.transport.server
import salt.log.setup
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.files
import salt.utils.gitfs
import salt.utils.gzip_util
import salt.utils.jid
import salt.utils.job
import salt.utils.master
import salt.utils.minions
import salt.utils.platform
import salt.utils.process
import salt.utils.schedule
import salt.utils.verify
import salt.utils.zeromq
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.exceptions import FileserverConfigError
from salt.transport import iter_transport_opts
from salt.utils.debug import (
    enable_sigusr1_handler, enable_sigusr2_handler, inspect_stack
)
from salt.utils.event import tagify

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
        self.opts = state[u'opts']
        self.master_key = state[u'master_key']
        self.key = state[u'key']
        SMaster.secrets = state[u'secrets']

    def __getstate__(self):
        return {u'opts': self.opts,
                u'master_key': self.master_key,
                u'key': self.key,
                u'secrets': SMaster.secrets}

    def __prep_key(self):
        '''
        A key needs to be placed in the filesystem with permissions 0400 so
        clients are required to run as root.
        '''
        return salt.daemons.masterapi.access_keys(self.opts)


class Maintenance(salt.utils.process.SignalHandlingMultiprocessingProcess):
    '''
    A generalized maintenance process which performs maintenance routines.
    '''
    def __init__(self, opts, log_queue=None):
        '''
        Create a maintenance instance

        :param dict opts: The salt options
        '''
        super(Maintenance, self).__init__(log_queue=log_queue)
        self.opts = opts
        # How often do we perform the maintenance tasks
        self.loop_interval = int(self.opts[u'loop_interval'])
        # Track key rotation intervals
        self.rotate = int(time.time())
        # A serializer for general maint operations
        self.serial = salt.payload.Serial(self.opts)

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self._is_child = True
        self.__init__(state[u'opts'], log_queue=state[u'log_queue'])

    def __getstate__(self):
        return {u'opts': self.opts,
                u'log_queue': self.log_queue}

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
        ropts[u'quiet'] = True
        runner_client = salt.runner.RunnerClient(ropts)
        # Load Returners
        self.returners = salt.loader.returners(self.opts, {})

        # Init Scheduler
        self.schedule = salt.utils.schedule.Schedule(self.opts,
                                                     runner_client.functions_dict(),
                                                     returners=self.returners)
        self.ckminions = salt.utils.minions.CkMinions(self.opts)
        # Make Event bus for firing
        self.event = salt.utils.event.get_master_event(self.opts, self.opts[u'sock_dir'], listen=False)
        # Init any values needed by the git ext pillar
        self.git_pillar = salt.daemons.masterapi.init_git_pillar(self.opts)

        self.presence_events = False
        if self.opts.get(u'presence_events', False):
            tcp_only = True
            for transport, _ in iter_transport_opts(self.opts):
                if transport != u'tcp':
                    tcp_only = False
            if not tcp_only:
                # For a TCP only transport, the presence events will be
                # handled in the transport code.
                self.presence_events = True

    def run(self):
        '''
        This is the general passive maintenance process controller for the Salt
        master.

        This is where any data that needs to be cleanly maintained from the
        master is maintained.
        '''
        salt.utils.appendproctitle(u'Maintenance')

        # init things that need to be done after the process is forked
        self._post_fork_init()

        # Make Start Times
        last = int(time.time())
        # Clean out the fileserver backend cache
        salt.daemons.masterapi.clean_fsbackend(self.opts)

        old_present = set()
        while True:
            now = int(time.time())
            if (now - last) >= self.loop_interval:
                salt.daemons.masterapi.clean_old_jobs(self.opts)
                salt.daemons.masterapi.clean_expired_tokens(self.opts)
                salt.daemons.masterapi.clean_pub_auth(self.opts)
            self.handle_git_pillar()
            self.handle_schedule()
            self.handle_key_cache()
            self.handle_presence(old_present)
            self.handle_key_rotate(now)
            salt.daemons.masterapi.fileserver_update(self.fileserver)
            salt.utils.verify.check_max_open_files(self.opts)
            last = now
            time.sleep(self.loop_interval)

    def handle_key_cache(self):
        '''
        Evaluate accepted keys and create a msgpack file
        which contains a list
        '''
        if self.opts[u'key_cache'] == u'sched':
            keys = []
            #TODO DRY from CKMinions
            if self.opts[u'transport'] in (u'zeromq', u'tcp'):
                acc = u'minions'
            else:
                acc = u'accepted'

            for fn_ in os.listdir(os.path.join(self.opts[u'pki_dir'], acc)):
                if not fn_.startswith(u'.') and os.path.isfile(os.path.join(self.opts[u'pki_dir'], acc, fn_)):
                    keys.append(fn_)
            log.debug(u'Writing master key cache')
            # Write a temporary file securely
            with salt.utils.atomicfile.atomic_open(os.path.join(self.opts[u'pki_dir'], acc, u'.key_cache')) as cache_file:
                self.serial.dump(keys, cache_file)

    def handle_key_rotate(self, now):
        '''
        Rotate the AES key rotation
        '''
        to_rotate = False
        dfn = os.path.join(self.opts[u'cachedir'], u'.dfn')
        try:
            stats = os.stat(dfn)
            # Basic Windows permissions don't distinguish between
            # user/group/all. Check for read-only state instead.
            if salt.utils.platform.is_windows() and not os.access(dfn, os.W_OK):
                to_rotate = True
                # Cannot delete read-only files on Windows.
                os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
            elif stats.st_mode == 0o100400:
                to_rotate = True
            else:
                log.error(u'Found dropfile with incorrect permissions, ignoring...')
            os.remove(dfn)
        except os.error:
            pass

        if self.opts.get(u'publish_session'):
            if now - self.rotate >= self.opts[u'publish_session']:
                to_rotate = True

        if to_rotate:
            log.info(u'Rotating master AES key')
            for secret_key, secret_map in six.iteritems(SMaster.secrets):
                # should be unnecessary-- since no one else should be modifying
                with secret_map[u'secret'].get_lock():
                    secret_map[u'secret'].value = six.b(secret_map[u'reload']())
                self.event.fire_event({u'rotate_{0}_key'.format(secret_key): True}, tag=u'key')
            self.rotate = now
            if self.opts.get(u'ping_on_rotate'):
                # Ping all minions to get them to pick up the new key
                log.debug(u'Pinging all connected minions '
                          u'due to key rotation')
                salt.utils.master.ping_all_connected_minions(self.opts)

    def handle_git_pillar(self):
        '''
        Update git pillar
        '''
        try:
            for pillar in self.git_pillar:
                pillar.fetch_remotes()
        except Exception as exc:
            log.error(u'Exception caught while updating git_pillar',
                      exc_info=True)

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
            log.error(u'Exception %s occurred in scheduled job', exc)

    def handle_presence(self, old_present):
        '''
        Fire presence events if enabled
        '''
        if self.presence_events:
            present = self.ckminions.connected_ids()
            new = present.difference(old_present)
            lost = old_present.difference(present)
            if new or lost:
                # Fire new minions present event
                data = {u'new': list(new),
                        u'lost': list(lost)}
                self.event.fire_event(data, tagify(u'change', u'presence'))
            data = {u'present': list(present)}
            # On the first run it may need more time for the EventPublisher
            # to come up and be ready. Set the timeout to account for this.
            self.event.fire_event(data, tagify(u'present', u'presence'), timeout=3)
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
        if HAS_ZMQ:
            # Warn if ZMQ < 3.2
            try:
                zmq_version_info = zmq.zmq_version_info()
            except AttributeError:
                # PyZMQ <= 2.1.9 does not have zmq_version_info, fall back to
                # using zmq.zmq_version() and build a version info tuple.
                zmq_version_info = tuple(
                    [int(x) for x in zmq.zmq_version().split(u'.')]
                )
            if zmq_version_info < (3, 2):
                log.warning(
                    u'You have a version of ZMQ less than ZMQ 3.2! There are '
                    u'known connection keep-alive issues with ZMQ < 3.2 which '
                    u'may result in loss of contact with minions. Please '
                    u'upgrade your ZMQ!'
                )
        SMaster.__init__(self, opts)

    def __set_max_open_files(self):
        if not HAS_RESOURCE:
            return
        # Let's check to see how our max open files(ulimit -n) setting is
        mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
        if mof_h == resource.RLIM_INFINITY:
            # Unclear what to do with infinity... macOS reports RLIM_INFINITY as
            # hard limit,but raising to anything above soft limit fails...
            mof_h = mof_s
        log.info(
            u'Current values for max open files soft/hard setting: %s/%s',
            mof_s, mof_h
        )
        # Let's grab, from the configuration file, the value to raise max open
        # files to
        mof_c = self.opts[u'max_open_files']
        if mof_c > mof_h:
            # The configured value is higher than what's allowed
            log.info(
                u'The value for the \'max_open_files\' setting, %s, is higher '
                u'than the highest value the user running salt is allowed to '
                u'set (%s). Defaulting to %s.', mof_c, mof_h, mof_h
            )
            mof_c = mof_h

        if mof_s < mof_c:
            # There's room to raise the value. Raise it!
            log.info(u'Raising max open files value to %s', mof_c)
            resource.setrlimit(resource.RLIMIT_NOFILE, (mof_c, mof_h))
            try:
                mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
                log.info(
                    u'New values for max open files soft/hard values: %s/%s',
                    mof_s, mof_h
                )
            except ValueError:
                # https://github.com/saltstack/salt/issues/1991#issuecomment-13025595
                # A user under macOS reported that our 100000 default value is
                # still too high.
                log.critical(
                    u'Failed to raise max open files setting to %s. If this '
                    u'value is too low, the salt-master will most likely fail '
                    u'to run properly.', mof_c
                )

    def _pre_flight(self):
        '''
        Run pre flight checks. If anything in this method fails then the master
        should not start up.
        '''
        errors = []
        critical_errors = []

        try:
            os.chdir(u'/')
        except OSError as err:
            errors.append(
                u'Cannot change to root directory ({0})'.format(err)
            )

        if self.opts.get(u'fileserver_verify_config', True):
            fileserver = salt.fileserver.Fileserver(self.opts)
            if not fileserver.servers:
                errors.append(
                    u'Failed to load fileserver backends, the configured backends '
                    u'are: {0}'.format(u', '.join(self.opts[u'fileserver_backend']))
                )
            else:
                # Run init() for all backends which support the function, to
                # double-check configuration
                try:
                    fileserver.init()
                except FileserverConfigError as exc:
                    critical_errors.append(u'{0}'.format(exc))

        if not self.opts[u'fileserver_backend']:
            errors.append(u'No fileserver backends are configured')

        # Check to see if we need to create a pillar cache dir
        if self.opts[u'pillar_cache'] and not os.path.isdir(os.path.join(self.opts[u'cachedir'], u'pillar_cache')):
            try:
                prev_umask = os.umask(0o077)
                os.mkdir(os.path.join(self.opts[u'cachedir'], u'pillar_cache'))
                os.umask(prev_umask)
            except OSError:
                pass

        if self.opts.get(u'git_pillar_verify_config', True):
            git_pillars = [
                x for x in self.opts.get(u'ext_pillar', [])
                if u'git' in x
                and not isinstance(x[u'git'], six.string_types)
            ]
            if git_pillars:
                try:
                    new_opts = copy.deepcopy(self.opts)
                    from salt.pillar.git_pillar \
                        import PER_REMOTE_OVERRIDES as per_remote_overrides, \
                        PER_REMOTE_ONLY as per_remote_only
                    for repo in git_pillars:
                        new_opts[u'ext_pillar'] = [repo]
                        try:
                            git_pillar = salt.utils.gitfs.GitPillar(new_opts)
                            git_pillar.init_remotes(repo[u'git'],
                                                    per_remote_overrides,
                                                    per_remote_only)
                        except FileserverConfigError as exc:
                            critical_errors.append(exc.strerror)
                finally:
                    del new_opts

        if errors or critical_errors:
            for error in errors:
                log.error(error)
            for error in critical_errors:
                log.critical(error)
            log.critical(u'Master failed pre flight checks, exiting\n')
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    def start(self):
        '''
        Turn on the master server components
        '''
        self._pre_flight()
        log.info(u'salt-master is starting as user \'%s\'', salt.utils.get_user())

        enable_sigusr1_handler()
        enable_sigusr2_handler()

        self.__set_max_open_files()

        # Reset signals to default ones before adding processes to the process
        # manager. We don't want the processes being started to inherit those
        # signal handlers
        with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):

            # Setup the secrets here because the PubServerChannel may need
            # them as well.
            SMaster.secrets[u'aes'] = {
                u'secret': multiprocessing.Array(
                    ctypes.c_char,
                    six.b(salt.crypt.Crypticle.generate_key_string())
                ),
                u'reload': salt.crypt.Crypticle.generate_key_string
            }
            log.info(u'Creating master process manager')
            # Since there are children having their own ProcessManager we should wait for kill more time.
            self.process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
            pub_channels = []
            log.info(u'Creating master publisher process')
            for transport, opts in iter_transport_opts(self.opts):
                chan = salt.transport.server.PubServerChannel.factory(opts)
                chan.pre_fork(self.process_manager)
                pub_channels.append(chan)

            log.info(u'Creating master event publisher process')
            self.process_manager.add_process(salt.utils.event.EventPublisher, args=(self.opts,))

            if self.opts.get(u'reactor'):
                if isinstance(self.opts[u'engines'], list):
                    rine = False
                    for item in self.opts[u'engines']:
                        if u'reactor' in item:
                            rine = True
                            break
                    if not rine:
                        self.opts[u'engines'].append({u'reactor': {}})
                else:
                    if u'reactor' not in self.opts[u'engines']:
                        log.info(u'Enabling the reactor engine')
                        self.opts[u'engines'][u'reactor'] = {}

            salt.engines.start_engines(self.opts, self.process_manager)

            # must be after channels
            log.info(u'Creating master maintenance process')
            self.process_manager.add_process(Maintenance, args=(self.opts,))

            if self.opts.get(u'event_return'):
                log.info(u'Creating master event return process')
                self.process_manager.add_process(salt.utils.event.EventReturn, args=(self.opts,))

            ext_procs = self.opts.get(u'ext_processes', [])
            for proc in ext_procs:
                log.info(u'Creating ext_processes process: %s', proc)
                try:
                    mod = u'.'.join(proc.split(u'.')[:-1])
                    cls = proc.split(u'.')[-1]
                    _tmp = __import__(mod, globals(), locals(), [cls], -1)
                    cls = _tmp.__getattribute__(cls)
                    self.process_manager.add_process(cls, args=(self.opts,))
                except Exception:
                    log.error(u'Error creating ext_processes process: %s', proc)

            if HAS_HALITE and u'halite' in self.opts:
                log.info(u'Creating master halite process')
                self.process_manager.add_process(Halite, args=(self.opts[u'halite'],))

            # TODO: remove, or at least push into the transport stuff (pre-fork probably makes sense there)
            if self.opts[u'con_cache']:
                log.info(u'Creating master concache process')
                self.process_manager.add_process(salt.utils.master.ConnectedCache, args=(self.opts,))
                # workaround for issue #16315, race condition
                log.debug(u'Sleeping for two seconds to let concache rest')
                time.sleep(2)

            log.info(u'Creating master request server process')
            kwargs = {}
            if salt.utils.platform.is_windows():
                kwargs[u'log_queue'] = salt.log.setup.get_multiprocessing_logging_queue()
                kwargs[u'secrets'] = SMaster.secrets

            self.process_manager.add_process(
                ReqServer,
                args=(self.opts, self.key, self.master_key),
                kwargs=kwargs,
                name=u'ReqServer')

        # Install the SIGINT/SIGTERM handlers if not done so far
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGINT, self._handle_signals)

        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGTERM, self._handle_signals)

        self.process_manager.run()

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate the signals to the process manager
        self.process_manager.stop_restarting()
        self.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.process_manager.kill_children()
        time.sleep(1)
        sys.exit(0)


class Halite(salt.utils.process.SignalHandlingMultiprocessingProcess):
    '''
    Manage the Halite server
    '''
    def __init__(self, hopts, log_queue=None):
        '''
        Create a halite instance

        :param dict hopts: The halite options
        '''
        super(Halite, self).__init__(log_queue=log_queue)
        self.hopts = hopts

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self._is_child = True
        self.__init__(state[u'hopts'], log_queue=state[u'log_queue'])

    def __getstate__(self):
        return {u'hopts': self.hopts,
                u'log_queue': self.log_queue}

    def run(self):
        '''
        Fire up halite!
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        halite.start(self.hopts)


class ReqServer(salt.utils.process.SignalHandlingMultiprocessingProcess):
    '''
    Starts up the master request server, minions send results to this
    interface.
    '''
    def __init__(self, opts, key, mkey, log_queue=None, secrets=None):
        '''
        Create a request server

        :param dict opts: The salt options dictionary
        :key dict: The user starting the server and the AES key
        :mkey dict: The user starting the server and the RSA key

        :rtype: ReqServer
        :returns: Request server
        '''
        super(ReqServer, self).__init__(log_queue=log_queue)
        self.opts = opts
        self.master_key = mkey
        # Prepare the AES key
        self.key = key
        self.secrets = secrets

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self._is_child = True
        self.__init__(state[u'opts'], state[u'key'], state[u'mkey'],
                      log_queue=state[u'log_queue'], secrets=state[u'secrets'])

    def __getstate__(self):
        return {u'opts': self.opts,
                u'key': self.key,
                u'mkey': self.master_key,
                u'log_queue': self.log_queue,
                u'secrets': self.secrets}

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        self.destroy(signum)
        super(ReqServer, self)._handle_signals(signum, sigframe)

    def __bind(self):
        '''
        Binds the reply server
        '''
        if self.log_queue is not None:
            salt.log.setup.set_multiprocessing_logging_queue(self.log_queue)
        salt.log.setup.setup_multiprocessing_logging(self.log_queue)
        if self.secrets is not None:
            SMaster.secrets = self.secrets

        dfn = os.path.join(self.opts[u'cachedir'], u'.dfn')
        if os.path.isfile(dfn):
            try:
                if salt.utils.platform.is_windows() and not os.access(dfn, os.W_OK):
                    # Cannot delete read-only files on Windows.
                    os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
                os.remove(dfn)
            except os.error:
                pass

        # Wait for kill should be less then parent's ProcessManager.
        self.process_manager = salt.utils.process.ProcessManager(name=u'ReqServer_ProcessManager',
                                                                 wait_for_kill=1)

        req_channels = []
        tcp_only = True
        for transport, opts in iter_transport_opts(self.opts):
            chan = salt.transport.server.ReqServerChannel.factory(opts)
            chan.pre_fork(self.process_manager)
            req_channels.append(chan)
            if transport != u'tcp':
                tcp_only = False

        kwargs = {}
        if salt.utils.platform.is_windows():
            kwargs[u'log_queue'] = self.log_queue
            # Use one worker thread if only the TCP transport is set up on
            # Windows and we are using Python 2. There is load balancer
            # support on Windows for the TCP transport when using Python 3.
            if tcp_only and six.PY2 and int(self.opts[u'worker_threads']) != 1:
                log.warning(u'TCP transport supports only 1 worker on Windows '
                            u'when using Python 2.')
                self.opts[u'worker_threads'] = 1

        # Reset signals to default ones before adding processes to the process
        # manager. We don't want the processes being started to inherit those
        # signal handlers
        with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):
            for ind in range(int(self.opts[u'worker_threads'])):
                name = u'MWorker-{0}'.format(ind)
                self.process_manager.add_process(MWorker,
                                                 args=(self.opts,
                                                       self.master_key,
                                                       self.key,
                                                       req_channels,
                                                       name),
                                                 kwargs=kwargs,
                                                 name=name)
        self.process_manager.run()

    def run(self):
        '''
        Start up the ReqServer
        '''
        self.__bind()

    def destroy(self, signum=signal.SIGTERM):
        if hasattr(self, u'process_manager'):
            self.process_manager.stop_restarting()
            self.process_manager.send_signal_to_processes(signum)
            self.process_manager.kill_children()

    def __del__(self):
        self.destroy()


class MWorker(salt.utils.process.SignalHandlingMultiprocessingProcess):
    '''
    The worker multiprocess instance to manage the backend operations for the
    salt master.
    '''
    def __init__(self,
                 opts,
                 mkey,
                 key,
                 req_channels,
                 name,
                 **kwargs):
        '''
        Create a salt master worker process

        :param dict opts: The salt options
        :param dict mkey: The user running the salt master and the AES key
        :param dict key: The user running the salt master and the RSA key

        :rtype: MWorker
        :return: Master worker
        '''
        kwargs[u'name'] = name
        super(MWorker, self).__init__(**kwargs)
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
        self._is_child = True
        super(MWorker, self).__init__(log_queue=state[u'log_queue'])
        self.opts = state[u'opts']
        self.req_channels = state[u'req_channels']
        self.mkey = state[u'mkey']
        self.key = state[u'key']
        self.k_mtime = state[u'k_mtime']
        SMaster.secrets = state[u'secrets']

    def __getstate__(self):
        return {u'opts': self.opts,
                u'req_channels': self.req_channels,
                u'mkey': self.mkey,
                u'key': self.key,
                u'k_mtime': self.k_mtime,
                u'log_queue': self.log_queue,
                u'secrets': SMaster.secrets}

    def _handle_signals(self, signum, sigframe):
        for channel in getattr(self, u'req_channels', ()):
            channel.close()
        super(MWorker, self)._handle_signals(signum, sigframe)

    def __bind(self):
        '''
        Bind to the local port
        '''
        # using ZMQIOLoop since we *might* need zmq in there
        if HAS_ZMQ:
            zmq.eventloop.ioloop.install()
        self.io_loop = LOOP_CLASS()
        self.io_loop.make_current()
        for req_channel in self.req_channels:
            req_channel.post_fork(self._handle_payload, io_loop=self.io_loop)  # TODO: cleaner? Maybe lazily?
        try:
            self.io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            # Tornado knows what to do
            pass

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
        key = payload[u'enc']
        load = payload[u'load']
        ret = {u'aes': self._handle_aes,
               u'clear': self._handle_clear}[key](load)
        raise tornado.gen.Return(ret)

    def _handle_clear(self, load):
        '''
        Process a cleartext command

        :param dict load: Cleartext payload
        :return: The result of passing the load to a function in ClearFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        log.trace(u'Clear payload received with command %s', load[u'cmd'])
        if load[u'cmd'].startswith(u'__'):
            return False
        return getattr(self.clear_funcs, load[u'cmd'])(load), {u'fun': u'send_clear'}

    def _handle_aes(self, data):
        '''
        Process a command sent via an AES key

        :param str load: Encrypted payload
        :return: The result of passing the load to a function in AESFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        if u'cmd' not in data:
            log.error(u'Received malformed command %s', data)
            return {}
        log.trace(u'AES payload received with command %s', data[u'cmd'])
        if data[u'cmd'].startswith(u'__'):
            return False
        return self.aes_funcs.run_func(data[u'cmd'], data)

    def run(self):
        '''
        Start a Master Worker
        '''
        salt.utils.appendproctitle(self.name)
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
        self.event = salt.utils.event.get_master_event(self.opts, self.opts[u'sock_dir'], listen=False)
        self.serial = salt.payload.Serial(opts)
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Make a client
        self.local = salt.client.get_local_client(self.opts[u'conf_file'])
        # Create the master minion to access the external job cache
        self.mminion = salt.minion.MasterMinion(
            self.opts,
            states=False,
            rend=False,
            ignore_config_errors=True
        )
        self.__setup_fileserver()
        self.masterapi = salt.daemons.masterapi.RemoteFuncs(opts)

    def __setup_fileserver(self):
        '''
        Set the local file objects from the file server interface
        '''
        self.fs_ = salt.fileserver.Fileserver(self.opts)
        self._serve_file = self.fs_.serve_file
        self._file_find = self.fs_._find_file
        self._file_hash = self.fs_.file_hash
        self._file_hash_and_stat = self.fs_.file_hash_and_stat
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
        pub_path = os.path.join(self.opts[u'pki_dir'], u'minions', id_)

        try:
            with salt.utils.files.fopen(pub_path, u'r') as fp_:
                minion_pub = fp_.read()
                pub = RSA.importKey(minion_pub)
        except (IOError, OSError):
            log.warning(
                u'Salt minion claiming to be %s attempted to communicate with '
                u'master, but key could not be read and verification was denied.',
                id_
            )
            return False
        except (ValueError, IndexError, TypeError) as err:
            log.error(u'Unable to load public key "%s": %s', pub_path, err)
        try:
            if salt.crypt.public_decrypt(pub, token) == b'salt':  # future lint: disable=non-unicode-string
                return True
        except ValueError as err:
            log.error(u'Unable to decrypt token: %s', err)

        log.error(
            u'Salt minion claiming to be %s has attempted to communicate with '
            u'the master and could not be verified', id_
        )
        return False

    def verify_minion(self, id_, token):
        '''
        Take a minion id and a string signed with the minion private key
        The string needs to verify as 'salt' with the minion public key

        :param str id_: A minion ID
        :param str token: A string signed with the minion private key

        :rtype: bool
        :return: Boolean indicating whether or not the token can be verified.
        '''
        return self.__verify_minion(id_, token)

    def __verify_minion_publish(self, clear_load):
        '''
        Verify that the passed information authorized a minion to execute

        :param dict clear_load: A publication load from a minion

        :rtype: bool
        :return: A boolean indicating if the minion is allowed to publish the command in the load
        '''
        # Verify that the load is valid
        if u'peer' not in self.opts:
            return False
        if not isinstance(self.opts[u'peer'], dict):
            return False
        if any(key not in clear_load for key in (u'fun', u'arg', u'tgt', u'ret', u'tok', u'id')):
            return False
        # If the command will make a recursive publish don't run
        if clear_load[u'fun'].startswith(u'publish.'):
            return False
        # Check the permissions for this minion
        if not self.__verify_minion(clear_load[u'id'], clear_load[u'tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning(
                u'Minion id %s is not who it says it is and is attempting '
                u'to issue a peer command', clear_load[u'id']
            )
            return False
        clear_load.pop(u'tok')
        perms = []
        for match in self.opts[u'peer']:
            if re.match(match, clear_load[u'id']):
                # This is the list of funcs/modules!
                if isinstance(self.opts[u'peer'][match], list):
                    perms.extend(self.opts[u'peer'][match])
        if u',' in clear_load[u'fun']:
            # 'arg': [['cat', '/proc/cpuinfo'], [], ['foo']]
            clear_load[u'fun'] = clear_load[u'fun'].split(u',')
            arg_ = []
            for arg in clear_load[u'arg']:
                arg_.append(arg.split())
            clear_load[u'arg'] = arg_

        # finally, check the auth of the load
        return self.ckminions.auth_check(
            perms,
            clear_load[u'fun'],
            clear_load[u'arg'],
            clear_load[u'tgt'],
            clear_load.get(u'tgt_type', u'glob'),
            publish_validate=True)

    def __verify_load(self, load, verify_keys):
        '''
        A utility function to perform common verification steps.

        :param dict load: A payload received from a minion
        :param list verify_keys: A list of strings that should be present in a
        given load

        :rtype: bool
        :rtype: dict
        :return: The original load (except for the token) if the load can be
        verified. False if the load is invalid.
        '''
        if any(key not in load for key in verify_keys):
            return False
        if u'tok' not in load:
            log.error(
                u'Received incomplete call from %s for \'%s\', missing \'%s\'',
                load[u'id'], inspect_stack()[u'co_name'], u'tok'
            )
            return False
        if not self.__verify_minion(load[u'id'], load[u'tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning(u'Minion id %s is not who it says it is!', load[u'id'])
            return False

        if u'tok' in load:
            load.pop(u'tok')

        return load

    def _master_tops(self, load):
        '''
        Return the results from an external node classifier if one is
        specified

        :param dict load: A payload received from a minion
        :return: The results from an external node classifier
        '''
        load = self.__verify_load(load, (u'id', u'tok'))
        if load is False:
            return {}
        return self.masterapi._master_tops(load, skip_verify=True)

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
        mopts[u'file_roots'] = file_roots
        mopts[u'top_file_merging_strategy'] = self.opts[u'top_file_merging_strategy']
        mopts[u'env_order'] = self.opts[u'env_order']
        mopts[u'default_top'] = self.opts[u'default_top']
        if load.get(u'env_only'):
            return mopts
        mopts[u'renderer'] = self.opts[u'renderer']
        mopts[u'failhard'] = self.opts[u'failhard']
        mopts[u'state_top'] = self.opts[u'state_top']
        mopts[u'state_top_saltenv'] = self.opts[u'state_top_saltenv']
        mopts[u'nodegroups'] = self.opts[u'nodegroups']
        mopts[u'state_auto_order'] = self.opts[u'state_auto_order']
        mopts[u'state_events'] = self.opts[u'state_events']
        mopts[u'state_aggregate'] = self.opts[u'state_aggregate']
        mopts[u'jinja_lstrip_blocks'] = self.opts[u'jinja_lstrip_blocks']
        mopts[u'jinja_trim_blocks'] = self.opts[u'jinja_trim_blocks']
        return mopts

    def _mine_get(self, load):
        '''
        Gathers the data from the specified minions' mine

        :param dict load: A payload received from a minion

        :rtype: dict
        :return: Mine data from the specified minions
        '''
        load = self.__verify_load(load, (u'id', u'tgt', u'fun', u'tok'))
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
        load = self.__verify_load(load, (u'id', u'data', u'tok'))
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
        load = self.__verify_load(load, (u'id', u'fun', u'tok'))
        if load is False:
            return {}
        else:
            return self.masterapi._mine_delete(load)

    def _mine_flush(self, load):
        '''
        Allow the minion to delete all of its own mine contents

        :param dict load: A payload received from a minion
        '''
        load = self.__verify_load(load, (u'id', u'tok'))
        if load is False:
            return {}
        else:
            return self.masterapi._mine_flush(load, skip_verify=True)

    def _file_recv(self, load):
        '''
        Allows minions to send files to the master, files are sent to the
        master file cache
        '''
        if any(key not in load for key in (u'id', u'path', u'loc')):
            return False
        if not isinstance(load[u'path'], list):
            return False
        if not self.opts[u'file_recv']:
            return False
        if not salt.utils.verify.valid_id(self.opts, load[u'id']):
            return False
        file_recv_max_size = 1024*1024 * self.opts[u'file_recv_max_size']

        if u'loc' in load and load[u'loc'] < 0:
            log.error(u'Invalid file pointer: load[loc] < 0')
            return False

        if len(load[u'data']) + load.get(u'loc', 0) > file_recv_max_size:
            log.error(
                u'file_recv_max_size limit of %d MB exceeded! %s will be '
                u'truncated. To successfully push this file, adjust '
                u'file_recv_max_size to an integer (in MB) large enough to '
                u'accommodate it.', file_recv_max_size, load[u'path']
            )
            return False
        if u'tok' not in load:
            log.error(
                u'Received incomplete call from %s for \'%s\', missing \'%s\'',
                load[u'id'], inspect_stack()[u'co_name'], u'tok'
            )
            return False
        if not self.__verify_minion(load[u'id'], load[u'tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning(u'Minion id %s is not who it says it is!', load[u'id'])
            return {}
        load.pop(u'tok')

        # Join path
        sep_path = os.sep.join(load[u'path'])

        # Path normalization should have been done by the sending
        # minion but we can't guarantee it. Re-do it here.
        normpath = os.path.normpath(sep_path)

        # Ensure that this safety check is done after the path
        # have been normalized.
        if os.path.isabs(normpath) or u'../' in load[u'path']:
            # Can overwrite master files!!
            return False

        cpath = os.path.join(
            self.opts[u'cachedir'],
            u'minions',
            load[u'id'],
            u'files',
            normpath)
        # One last safety check here
        if not os.path.normpath(cpath).startswith(self.opts[u'cachedir']):
            log.warning(
                u'Attempt to write received file outside of master cache '
                u'directory! Requested path: %s. Access denied.', cpath
            )
            return False
        cdir = os.path.dirname(cpath)
        if not os.path.isdir(cdir):
            try:
                os.makedirs(cdir)
            except os.error:
                pass
        if os.path.isfile(cpath) and load[u'loc'] != 0:
            mode = u'ab'
        else:
            mode = u'wb'
        with salt.utils.files.fopen(cpath, mode) as fp_:
            if load[u'loc']:
                fp_.seek(load[u'loc'])

            fp_.write(load[u'data'])
        return True

    def _pillar(self, load):
        '''
        Return the pillar data for the minion

        :param dict load: Minion payload

        :rtype: dict
        :return: The pillar data for the minion
        '''
        if any(key not in load for key in (u'id', u'grains')):
            return False
        if not salt.utils.verify.valid_id(self.opts, load[u'id']):
            return False
        load[u'grains'][u'id'] = load[u'id']

        pillar = salt.pillar.get_pillar(
            self.opts,
            load[u'grains'],
            load[u'id'],
            load.get(u'saltenv', load.get(u'env')),
            ext=load.get(u'ext'),
            pillar_override=load.get(u'pillar_override', {}),
            pillarenv=load.get(u'pillarenv'),
            extra_minion_data=load.get(u'extra_minion_data'))
        data = pillar.compile_pillar()
        self.fs_.update_opts()
        if self.opts.get(u'minion_data_cache', False):
            self.masterapi.cache.store(u'minions/{0}'.format(load[u'id']),
                                       u'data',
                                       {u'grains': load[u'grains'],
                                        u'pillar': data})
            self.event.fire_event({u'Minion data cache refresh': load[u'id']}, tagify(load[u'id'], u'refresh', u'minion'))
        return data

    def _minion_event(self, load):
        '''
        Receive an event from the minion and fire it on the master event
        interface

        :param dict load: The minion payload
        '''
        load = self.__verify_load(load, (u'id', u'tok'))
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
        id_ = load[u'id']
        if load.get(u'tag', u'') == u'_salt_error':
            log.error(
                u'Received minion error from [%s]: %s',
                id_, load[u'data'][u'message']
            )

        for event in load.get(u'events', []):
            event_data = event.get(u'data', {})
            if u'minions' in event_data:
                jid = event_data.get(u'jid')
                if not jid:
                    continue
                minions = event_data[u'minions']
                try:
                    salt.utils.job.store_minions(
                        self.opts,
                        jid,
                        minions,
                        mminion=self.mminion,
                        syndic_id=id_)
                except (KeyError, salt.exceptions.SaltCacheError) as exc:
                    log.error(
                        u'Could not add minion(s) %s for job %s: %s',
                        minions, jid, exc
                    )

    def _return(self, load):
        '''
        Handle the return data sent from the minions.

        Takes the return, verifies it and fires it on the master event bus.
        Typically, this event is consumed by the Salt CLI waiting on the other
        end of the event bus but could be heard by any listener on the bus.

        :param dict load: The minion payload
        '''
        if self.opts[u'require_minion_sign_messages'] and u'sig' not in load:
            log.critical(
                u'_return: Master is requiring minions to sign their '
                u'messages, but there is no signature in this payload from '
                u'%s.', load[u'id']
            )
            return False

        if u'sig' in load:
            log.trace(u'Verifying signed event publish from minion')
            sig = load.pop(u'sig')
            this_minion_pubkey = os.path.join(self.opts[u'pki_dir'], u'minions/{0}'.format(load[u'id']))
            serialized_load = salt.serializers.msgpack.serialize(load)
            if not salt.crypt.verify_signature(this_minion_pubkey, serialized_load, sig):
                log.info(u'Failed to verify event signature from minion %s.', load[u'id'])
                if self.opts[u'drop_messages_signature_fail']:
                    log.critical(
                        u'Drop_messages_signature_fail is enabled, dropping '
                        u'message from %s', load[u'id']
                    )
                    return False
                else:
                    log.info(u'But \'drop_message_signature_fail\' is disabled, so message is still accepted.')
            load[u'sig'] = sig

        try:
            salt.utils.job.store_job(
                self.opts, load, event=self.event, mminion=self.mminion)
        except salt.exceptions.SaltCacheError:
            log.error(u'Could not store job information for load: %s', load)

    def _syndic_return(self, load):
        '''
        Receive a syndic minion return and format it to look like returns from
        individual minions.

        :param dict load: The minion payload
        '''
        # Verify the load
        if any(key not in load for key in (u'return', u'jid', u'id')):
            return None
        # if we have a load, save it
        if load.get(u'load'):
            fstr = u'{0}.save_load'.format(self.opts[u'master_job_cache'])
            self.mminion.returners[fstr](load[u'jid'], load[u'load'])

        # Register the syndic
        syndic_cache_path = os.path.join(self.opts[u'cachedir'], u'syndics', load[u'id'])
        if not os.path.exists(syndic_cache_path):
            path_name = os.path.split(syndic_cache_path)[0]
            if not os.path.exists(path_name):
                os.makedirs(path_name)
            with salt.utils.files.fopen(syndic_cache_path, u'w') as wfh:
                wfh.write(u'')

        # Format individual return loads
        for key, item in six.iteritems(load[u'return']):
            ret = {u'jid': load[u'jid'],
                   u'id': key}
            ret.update(item)
            if u'master_id' in load:
                ret[u'master_id'] = load[u'master_id']
            if u'fun' in load:
                ret[u'fun'] = load[u'fun']
            if u'arg' in load:
                ret[u'fun_args'] = load[u'arg']
            if u'out' in load:
                ret[u'out'] = load[u'out']
            if u'sig' in load:
                ret[u'sig'] = load[u'sig']

            self._return(ret)

    def minion_runner(self, clear_load):
        '''
        Execute a runner from a minion, return the runner's function data

        :param dict clear_load: The minion payload

        :rtype: dict
        :return: The runner function data
        '''
        load = self.__verify_load(clear_load, (u'fun', u'arg', u'id', u'tok'))
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
        load = self.__verify_load(load, (u'jid', u'id', u'tok'))
        if load is False:
            return {}
        # Check that this minion can access this data
        auth_cache = os.path.join(
            self.opts[u'cachedir'],
            u'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, str(load[u'jid']))
        with salt.utils.files.fopen(jid_fn, u'r') as fp_:
            if not load[u'id'] == fp_.read():
                return {}
        # Grab the latest and return
        return self.local.get_cache_returns(load[u'jid'])

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
        load = self.__verify_load(load, (u'id', u'tok'))

        if not self.opts.get(u'allow_minion_key_revoke', False):
            log.warning(
                u'Minion %s requested key revoke, but allow_minion_key_revoke '
                u'is set to False', load[u'id']
            )
            return load

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
        if func.startswith(u'__'):
            # TODO: return some error? Seems odd to return {}
            return {}, {u'fun': u'send'}
        # Run the func
        if hasattr(self, func):
            try:
                start = time.time()
                ret = getattr(self, func)(load)
                log.trace(
                    u'Master function call %s took %s seconds',
                    func, time.time() - start
                )
            except Exception:
                ret = u''
                log.error(u'Error in function %s:\n', func, exc_info=True)
        else:
            log.error(
                u'Received function %s which is unavailable on the master, '
                u'returning False', func
            )
            return False, {u'fun': u'send'}
        # Don't encrypt the return value for the _return func
        # (we don't care about the return value, so why encrypt it?)
        if func == u'_return':
            return ret, {u'fun': u'send'}
        if func == u'_pillar' and u'id' in load:
            if load.get(u'ver') != u'2' and self.opts[u'pillar_version'] == 1:
                # Authorized to return old pillar proto
                return ret, {u'fun': u'send'}
            return ret, {u'fun': u'send_private', u'key': u'pillar', u'tgt': load[u'id']}
        # Encrypt the return
        return ret, {u'fun': u'send'}


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
        self.event = salt.utils.event.get_master_event(self.opts, self.opts[u'sock_dir'], listen=False)
        # Make a client
        self.local = salt.client.get_local_client(self.opts[u'conf_file'])
        # Make an minion checker object
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Make an Auth object
        self.loadauth = salt.auth.LoadAuth(opts)
        # Stand up the master Minion to access returner data
        self.mminion = salt.minion.MasterMinion(
            self.opts,
            states=False,
            rend=False,
            ignore_config_errors=True
        )
        # Make a wheel object
        self.wheel_ = salt.wheel.Wheel(opts)
        # Make a masterapi object
        self.masterapi = salt.daemons.masterapi.LocalFuncs(opts, key)

    def runner(self, clear_load):
        '''
        Send a master control function back to the runner system
        '''
        # All runner ops pass through eauth
        auth_type, err_name, key, sensitive_load_keys = self._prep_auth_info(clear_load)

        # Authenticate
        auth_check = self.loadauth.check_authentication(clear_load, auth_type, key=key)
        error = auth_check.get(u'error')

        if error:
            # Authentication error occurred: do not continue.
            return {u'error': error}

        # Authorize
        username = auth_check.get(u'username')
        if auth_type != u'user':
            runner_check = self.ckminions.runner_check(
                auth_check.get(u'auth_list', []),
                clear_load[u'fun'],
                clear_load.get(u'kwarg', {})
            )
            if not runner_check:
                return {u'error': {u'name': err_name,
                                   u'message': u'Authentication failure of type "{0}" occurred for '
                                             u'user {1}.'.format(auth_type, username)}}
            elif isinstance(runner_check, dict) and u'error' in runner_check:
                # A dictionary with an error name/message was handled by ckminions.runner_check
                return runner_check

            # No error occurred, consume sensitive settings from the clear_load if passed.
            for item in sensitive_load_keys:
                clear_load.pop(item, None)
        else:
            if u'user' in clear_load:
                username = clear_load[u'user']
                if salt.auth.AuthUser(username).is_sudo():
                    username = self.opts.get(u'user', u'root')
            else:
                username = salt.utils.get_user()

        # Authorized. Do the job!
        try:
            fun = clear_load.pop(u'fun')
            runner_client = salt.runner.RunnerClient(self.opts)
            return runner_client.async(fun,
                                       clear_load.get(u'kwarg', {}),
                                       username)
        except Exception as exc:
            log.error(u'Exception occurred while introspecting %s: %s', fun, exc)
            return {u'error': {u'name': exc.__class__.__name__,
                               u'args': exc.args,
                               u'message': str(exc)}}

    def wheel(self, clear_load):
        '''
        Send a master control function back to the wheel system
        '''
        # All wheel ops pass through eauth
        auth_type, err_name, key, sensitive_load_keys = self._prep_auth_info(clear_load)

        # Authenticate
        auth_check = self.loadauth.check_authentication(clear_load, auth_type, key=key)
        error = auth_check.get(u'error')

        if error:
            # Authentication error occurred: do not continue.
            return {u'error': error}

        # Authorize
        username = auth_check.get(u'username')
        if auth_type != u'user':
            wheel_check = self.ckminions.wheel_check(
                auth_check.get(u'auth_list', []),
                clear_load[u'fun'],
                clear_load.get(u'kwarg', {})
            )
            if not wheel_check:
                return {u'error': {u'name': err_name,
                                   u'message': u'Authentication failure of type "{0}" occurred for '
                                               u'user {1}.'.format(auth_type, username)}}
            elif isinstance(wheel_check, dict) and u'error' in wheel_check:
                # A dictionary with an error name/message was handled by ckminions.wheel_check
                return wheel_check

            # No error occurred, consume sensitive settings from the clear_load if passed.
            for item in sensitive_load_keys:
                clear_load.pop(item, None)
        else:
            if u'user' in clear_load:
                username = clear_load[u'user']
                if salt.auth.AuthUser(username).is_sudo():
                    username = self.opts.get(u'user', u'root')
            else:
                username = salt.utils.get_user()

        # Authorized. Do the job!
        try:
            jid = salt.utils.jid.gen_jid(self.opts)
            fun = clear_load.pop(u'fun')
            tag = tagify(jid, prefix=u'wheel')
            data = {u'fun': u"wheel.{0}".format(fun),
                    u'jid': jid,
                    u'tag': tag,
                    u'user': username}

            self.event.fire_event(data, tagify([jid, u'new'], u'wheel'))
            ret = self.wheel_.call_func(fun, full_return=True, **clear_load)
            data[u'return'] = ret[u'return']
            data[u'success'] = ret[u'success']
            self.event.fire_event(data, tagify([jid, u'ret'], u'wheel'))
            return {u'tag': tag,
                    u'data': data}
        except Exception as exc:
            log.error(u'Exception occurred while introspecting %s: %s', fun, exc)
            data[u'return'] = u'Exception occurred in wheel {0}: {1}: {2}'.format(
                             fun,
                             exc.__class__.__name__,
                             exc,
            )
            data[u'success'] = False
            self.event.fire_event(data, tagify([jid, u'ret'], u'wheel'))
            return {u'tag': tag,
                    u'data': data}

    def mk_token(self, clear_load):
        '''
        Create and return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        '''
        token = self.loadauth.mk_token(clear_load)
        if not token:
            log.warning(u'Authentication failure of type "eauth" occurred.')
            return u''
        return token

    def get_token(self, clear_load):
        '''
        Return the name associated with a token or False if the token is invalid
        '''
        if u'token' not in clear_load:
            return False
        return self.loadauth.get_tok(clear_load[u'token'])

    def publish(self, clear_load):
        '''
        This method sends out publications to the minions, it can only be used
        by the LocalClient.
        '''
        extra = clear_load.get(u'kwargs', {})

        publisher_acl = salt.acl.PublisherACL(self.opts[u'publisher_acl_blacklist'])

        if publisher_acl.user_is_blacklisted(clear_load[u'user']) or \
                publisher_acl.cmd_is_blacklisted(clear_load[u'fun']):
            log.error(
                u'%s does not have permissions to run %s. Please contact '
                u'your local administrator if you believe this is in '
                u'error.\n', clear_load[u'user'], clear_load[u'fun']
            )
            return u''

        # Retrieve the minions list
        delimiter = clear_load.get(u'kwargs', {}).get(u'delimiter', DEFAULT_TARGET_DELIM)
        _res = self.ckminions.check_minions(
            clear_load[u'tgt'],
            clear_load.get(u'tgt_type', u'glob'),
            delimiter
        )
        minions = _res.get('minions', list())
        missing = _res.get('missing', list())

        # Check for external auth calls
        if extra.get(u'token', False):
            # Authenticate.
            token = self.loadauth.authenticate_token(extra)
            if not token:
                return u''

            # Get acl
            auth_list = self.loadauth.get_auth_list(extra, token)

            # Authorize the request
            if not self.ckminions.auth_check(
                    auth_list,
                    clear_load[u'fun'],
                    clear_load[u'arg'],
                    clear_load[u'tgt'],
                    clear_load.get(u'tgt_type', u'glob'),
                    minions=minions,
                    # always accept find_job
                    whitelist=[u'saltutil.find_job'],
                    ):
                log.warning(u'Authentication failure of type "token" occurred.')
                return u''
            clear_load[u'user'] = token[u'name']
            log.debug(u'Minion tokenized user = "%s"', clear_load[u'user'])
        elif u'eauth' in extra:
            # Authenticate.
            if not self.loadauth.authenticate_eauth(extra):
                return u''

            # Get acl from eauth module.
            auth_list = self.loadauth.get_auth_list(extra)

            # Authorize the request
            if not self.ckminions.auth_check(
                    auth_list,
                    clear_load[u'fun'],
                    clear_load[u'arg'],
                    clear_load[u'tgt'],
                    clear_load.get(u'tgt_type', u'glob'),
                    minions=minions,
                    # always accept find_job
                    whitelist=[u'saltutil.find_job'],
                    ):
                log.warning(u'Authentication failure of type "eauth" occurred.')
                return u''
            clear_load[u'user'] = self.loadauth.load_name(extra)  # The username we are attempting to auth with
        # Verify that the caller has root on master
        else:
            auth_ret = self.loadauth.authenticate_key(clear_load, self.key)
            if auth_ret is False:
                return u''

            if auth_ret is not True:
                if salt.auth.AuthUser(clear_load[u'user']).is_sudo():
                    if not self.opts[u'sudo_acl'] or not self.opts[u'publisher_acl']:
                        auth_ret = True

            if auth_ret is not True:
                auth_list = salt.utils.get_values_of_matching_keys(
                        self.opts[u'publisher_acl'],
                        auth_ret)
                if not auth_list:
                    log.warning(
                        u'Authentication failure of type "user" occurred.'
                    )
                    return u''

                if not self.ckminions.auth_check(
                        auth_list,
                        clear_load[u'fun'],
                        clear_load[u'arg'],
                        clear_load[u'tgt'],
                        clear_load.get(u'tgt_type', u'glob'),
                        minions=minions,
                        # always accept find_job
                        whitelist=[u'saltutil.find_job'],
                        ):
                    log.warning(u'Authentication failure of type "user" occurred.')
                    return u''

        # If we order masters (via a syndic), don't short circuit if no minions
        # are found
        if not self.opts.get(u'order_masters'):
            # Check for no minions
            if not minions:
                return {
                    u'enc': u'clear',
                    u'load': {
                        u'jid': None,
                        u'minions': minions,
                        u'error': u'Master could not resolve minions for target {0}'.format(clear_load[u'tgt'])
                    }
                }
        jid = self._prep_jid(clear_load, extra)
        if jid is None:
            return {u'enc': u'clear',
                    u'load': {u'error': u'Master failed to assign jid'}}
        payload = self._prep_pub(minions, jid, clear_load, extra, missing)

        # Send it!
        self._send_pub(payload)

        return {
            u'enc': u'clear',
            u'load': {
                u'jid': clear_load[u'jid'],
                u'minions': minions,
                u'missing': missing
            }
        }

    def _prep_auth_info(self, clear_load):
        sensitive_load_keys = []
        key = None
        if u'token' in clear_load:
            auth_type = u'token'
            err_name = u'TokenAuthenticationError'
            sensitive_load_keys = [u'token']
        elif u'eauth' in clear_load:
            auth_type = u'eauth'
            err_name = u'EauthAuthenticationError'
            sensitive_load_keys = [u'username', u'password']
        else:
            auth_type = u'user'
            err_name = u'UserAuthenticationError'
            key = self.key

        return auth_type, err_name, key, sensitive_load_keys

    def _prep_jid(self, clear_load, extra):
        '''
        Return a jid for this publication
        '''
        # the jid in clear_load can be None, '', or something else. this is an
        # attempt to clean up the value before passing to plugins
        passed_jid = clear_load[u'jid'] if clear_load.get(u'jid') else None
        nocache = extra.get(u'nocache', False)

        # Retrieve the jid
        fstr = u'{0}.prep_jid'.format(self.opts[u'master_job_cache'])
        try:
            # Retrieve the jid
            jid = self.mminion.returners[fstr](nocache=nocache,
                                               passed_jid=passed_jid)
        except (KeyError, TypeError):
            # The returner is not present
            msg = (
                u'Failed to allocate a jid. The requested returner \'{0}\' '
                u'could not be loaded.'.format(fstr.split(u'.')[0])
            )
            log.error(msg)
            return {u'error': msg}
        return jid

    def _send_pub(self, load):
        '''
        Take a load and send it across the network to connected minions
        '''
        for transport, opts in iter_transport_opts(self.opts):
            chan = salt.transport.server.PubServerChannel.factory(opts)
            chan.publish(load)

    def _prep_pub(self, minions, jid, clear_load, extra, missing):
        '''
        Take a given load and perform the necessary steps
        to prepare a publication.

        TODO: This is really only bound by temporal cohesion
        and thus should be refactored even further.
        '''
        clear_load[u'jid'] = jid
        delimiter = clear_load.get(u'kwargs', {}).get(u'delimiter', DEFAULT_TARGET_DELIM)

        # TODO Error reporting over the master event bus
        self.event.fire_event({u'minions': minions}, clear_load[u'jid'])
        new_job_load = {
            u'jid': clear_load[u'jid'],
            u'tgt_type': clear_load[u'tgt_type'],
            u'tgt': clear_load[u'tgt'],
            u'user': clear_load[u'user'],
            u'fun': clear_load[u'fun'],
            u'arg': clear_load[u'arg'],
            u'minions': minions,
            u'missing': missing,
            }

        # Announce the job on the event bus
        self.event.fire_event(new_job_load, tagify([clear_load[u'jid'], u'new'], u'job'))

        if self.opts[u'ext_job_cache']:
            fstr = u'{0}.save_load'.format(self.opts[u'ext_job_cache'])
            save_load_func = True

            # Get the returner's save_load arg_spec.
            try:
                arg_spec = salt.utils.args.get_function_argspec(self.mminion.returners[fstr])

                # Check if 'minions' is included in returner's save_load arg_spec.
                # This may be missing in custom returners, which we should warn about.
                if u'minions' not in arg_spec.args:
                    log.critical(
                        u'The specified returner used for the external job cache '
                        u'\'%s\' does not have a \'minions\' kwarg in the returner\'s '
                        u'save_load function.', self.opts[u'ext_job_cache']
                    )
            except (AttributeError, KeyError):
                save_load_func = False
                log.critical(
                    u'The specified returner used for the external job cache '
                    u'"%s" does not have a save_load function!',
                    self.opts[u'ext_job_cache']
                )

            if save_load_func:
                try:
                    self.mminion.returners[fstr](clear_load[u'jid'], clear_load, minions=minions)
                except Exception:
                    log.critical(
                        u'The specified returner threw a stack trace:\n',
                        exc_info=True
                    )

        # always write out to the master job caches
        try:
            fstr = u'{0}.save_load'.format(self.opts[u'master_job_cache'])
            self.mminion.returners[fstr](clear_load[u'jid'], clear_load, minions)
        except KeyError:
            log.critical(
                u'The specified returner used for the master job cache '
                u'"%s" does not have a save_load function!',
                self.opts[u'master_job_cache']
            )
        except Exception:
            log.critical(
                u'The specified returner threw a stack trace:\n',
                exc_info=True
            )
        # Set up the payload
        payload = {u'enc': u'aes'}
        # Altering the contents of the publish load is serious!! Changes here
        # break compatibility with minion/master versions and even tiny
        # additions can have serious implications on the performance of the
        # publish commands.
        #
        # In short, check with Thomas Hatch before you even think about
        # touching this stuff, we can probably do what you want to do another
        # way that won't have a negative impact.
        load = {
            u'fun': clear_load[u'fun'],
            u'arg': clear_load[u'arg'],
            u'tgt': clear_load[u'tgt'],
            u'jid': clear_load[u'jid'],
            u'ret': clear_load[u'ret'],
        }
        # if you specified a master id, lets put that in the load
        if u'master_id' in self.opts:
            load[u'master_id'] = self.opts[u'master_id']
        # if someone passed us one, use that
        if u'master_id' in extra:
            load[u'master_id'] = extra[u'master_id']
        # Only add the delimiter to the pub data if it is non-default
        if delimiter != DEFAULT_TARGET_DELIM:
            load[u'delimiter'] = delimiter

        if u'id' in extra:
            load[u'id'] = extra[u'id']
        if u'tgt_type' in clear_load:
            load[u'tgt_type'] = clear_load[u'tgt_type']
        if u'to' in clear_load:
            load[u'to'] = clear_load[u'to']

        if u'kwargs' in clear_load:
            if u'ret_config' in clear_load[u'kwargs']:
                load[u'ret_config'] = clear_load[u'kwargs'].get(u'ret_config')

            if u'metadata' in clear_load[u'kwargs']:
                load[u'metadata'] = clear_load[u'kwargs'].get(u'metadata')

            if u'module_executors' in clear_load[u'kwargs']:
                load[u'module_executors'] = clear_load[u'kwargs'].get(u'module_executors')

            if u'executor_opts' in clear_load[u'kwargs']:
                load[u'executor_opts'] = clear_load[u'kwargs'].get(u'executor_opts')

            if u'ret_kwargs' in clear_load[u'kwargs']:
                load[u'ret_kwargs'] = clear_load[u'kwargs'].get(u'ret_kwargs')

        if u'user' in clear_load:
            log.info(
                u'User %s Published command %s with jid %s',
                clear_load[u'user'], clear_load[u'fun'], clear_load[u'jid']
            )
            load[u'user'] = clear_load[u'user']
        else:
            log.info(
                u'Published command %s with jid %s',
                clear_load[u'fun'], clear_load[u'jid']
            )
        log.debug(u'Published command details %s', load)
        return load

    def ping(self, clear_load):
        '''
        Send the load back to the sender.
        '''
        return clear_load


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
        if self.opts.get(u'ipc_mode', u'') == u'tcp':
            self.w_uri = u'tcp://127.0.0.1:{0}'.format(
                self.opts.get(u'tcp_master_workers', 4515)
                )
        else:
            self.w_uri = u'ipc://{0}'.format(
                os.path.join(self.opts[u'sock_dir'], u'workers.ipc')
                )
        log.info(u'ZMQ Worker binding to socket %s', self.w_uri)
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
