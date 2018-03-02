# -*- coding: utf-8 -*-
'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python libs
from __future__ import absolute_import, with_statement, print_function, unicode_literals
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
import collections
import multiprocessing
import threading
import salt.serializers.msgpack

# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range
from salt.utils.zeromq import zmq, ZMQDefaultLoop, install_zmq, ZMQ_VERSION_INFO
# pylint: enable=import-error,no-name-in-module,redefined-builtin

import tornado.gen  # pylint: disable=F0401

# Import salt libs
import salt.crypt
import salt.client
import salt.client.ssh.client
import salt.exceptions
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
import salt.daemons.masterapi
import salt.defaults.exitcodes
import salt.transport.server
import salt.log.setup
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.crypt
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
import salt.utils.ssdp
import salt.utils.stringutils
import salt.utils.user
import salt.utils.verify
import salt.utils.zeromq
from salt.config import DEFAULT_INTERVAL
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.transport import iter_transport_opts
from salt.utils.debug import (
    enable_sigusr1_handler, enable_sigusr2_handler, inspect_stack
)
from salt.utils.event import tagify
from salt.utils.odict import OrderedDict

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
        self.loop_interval = int(self.opts['loop_interval'])
        # Track key rotation intervals
        self.rotate = int(time.time())
        # A serializer for general maint operations
        self.serial = salt.payload.Serial(self.opts)

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self._is_child = True
        self.__init__(state['opts'], log_queue=state['log_queue'])

    def __getstate__(self):
        return {'opts': self.opts,
                'log_queue': self.log_queue}

    def _post_fork_init(self):
        '''
        Some things need to be init'd after the fork has completed
        The easiest example is that one of these module types creates a thread
        in the parent process, then once the fork happens you'll start getting
        errors like "WARNING: Mixing fork() and threads detected; memory leaked."
        '''
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

        self.presence_events = False
        if self.opts.get('presence_events', False):
            tcp_only = True
            for transport, _ in iter_transport_opts(self.opts):
                if transport != 'tcp':
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
        salt.utils.process.appendproctitle(self.__class__.__name__)

        # init things that need to be done after the process is forked
        self._post_fork_init()

        # Make Start Times
        last = int(time.time())

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
            salt.utils.verify.check_max_open_files(self.opts)
            last = now
            time.sleep(self.loop_interval)

    def handle_key_cache(self):
        '''
        Evaluate accepted keys and create a msgpack file
        which contains a list
        '''
        if self.opts['key_cache'] == 'sched':
            keys = []
            #TODO DRY from CKMinions
            if self.opts['transport'] in ('zeromq', 'tcp'):
                acc = 'minions'
            else:
                acc = 'accepted'

            for fn_ in os.listdir(os.path.join(self.opts['pki_dir'], acc)):
                if not fn_.startswith('.') and os.path.isfile(os.path.join(self.opts['pki_dir'], acc, fn_)):
                    keys.append(fn_)
            log.debug('Writing master key cache')
            # Write a temporary file securely
            with salt.utils.atomicfile.atomic_open(os.path.join(self.opts['pki_dir'], acc, '.key_cache')) as cache_file:
                self.serial.dump(keys, cache_file)

    def handle_key_rotate(self, now):
        '''
        Rotate the AES key rotation
        '''
        to_rotate = False
        dfn = os.path.join(self.opts['cachedir'], '.dfn')
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
                # should be unnecessary-- since no one else should be modifying
                with secret_map['secret'].get_lock():
                    secret_map['secret'].value = salt.utils.stringutils.to_bytes(secret_map['reload']())
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
                pillar.fetch_remotes()
        except Exception as exc:
            log.error('Exception caught while updating git_pillar',
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
            log.error('Exception %s occurred in scheduled job', exc)

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
                data = {'new': list(new),
                        'lost': list(lost)}
                self.event.fire_event(data, tagify('change', 'presence'))
            data = {'present': list(present)}
            # On the first run it may need more time for the EventPublisher
            # to come up and be ready. Set the timeout to account for this.
            self.event.fire_event(data, tagify('present', 'presence'), timeout=3)
            old_present.clear()
            old_present.update(present)


class FileserverUpdate(salt.utils.process.SignalHandlingMultiprocessingProcess):
    '''
    A process from which to update any dynamic fileserver backends
    '''
    def __init__(self, opts, log_queue=None):
        super(FileserverUpdate, self).__init__(log_queue=log_queue)
        self.opts = opts
        self.update_threads = {}
        # Avoid circular import
        import salt.fileserver
        self.fileserver = salt.fileserver.Fileserver(self.opts)
        self.fill_buckets()

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self._is_child = True
        self.__init__(state['opts'], log_queue=state['log_queue'])

    def __getstate__(self):
        return {'opts': self.opts,
                'log_queue': self.log_queue}

    def fill_buckets(self):
        '''
        Get the configured backends and the intervals for any backend which
        supports them, and set up the update "buckets". There will be one
        bucket for each thing being updated at a given interval.
        '''
        update_intervals = self.fileserver.update_intervals()
        self.buckets = {}
        for backend in self.fileserver.backends():
            fstr = '{0}.update'.format(backend)
            try:
                update_func = self.fileserver.servers[fstr]
            except KeyError:
                log.debug(
                    'No update function for the %s filserver backend',
                    backend
                )
                continue
            if backend in update_intervals:
                # Variable intervals are supported for this backend
                for id_, interval in six.iteritems(update_intervals[backend]):
                    if not interval:
                        # Don't allow an interval of 0
                        interval = DEFAULT_INTERVAL
                        log.debug(
                            'An update_interval of 0 is not supported, '
                            'falling back to %s', interval
                        )
                    i_ptr = self.buckets.setdefault(interval, OrderedDict())
                    # Backend doesn't technically need to be present in the
                    # key, all we *really* need is the function reference, but
                    # having it there makes it easier to provide meaningful
                    # debug logging in the update threads.
                    i_ptr.setdefault((backend, update_func), []).append(id_)
            else:
                # Variable intervals are not supported for this backend, so
                # fall back to the global interval for that fileserver. Since
                # this backend doesn't support variable updates, we have
                # nothing to pass to the backend's update func, so we'll just
                # set the value to None.
                try:
                    interval_key = '{0}_update_interval'.format(backend)
                    interval = self.opts[interval_key]
                except KeyError:
                    interval = DEFAULT_INTERVAL
                    log.error(
                        '%s key missing from master configuration. This is '
                        'a bug, please report it. Falling back to default '
                        'interval of %d seconds', interval_key, interval
                    )
                self.buckets.setdefault(
                    interval, OrderedDict())[(backend, update_func)] = None

    def update_fileserver(self, interval, backends):
        '''
        Threading target which handles all updates for a given wait interval
        '''
        def _do_update():
            log.debug(
                'Performing fileserver updates for items with an update '
                'interval of %d', interval
            )
            for backend, update_args in six.iteritems(backends):
                backend_name, update_func = backend
                try:
                    if update_args:
                        log.debug(
                            'Updating %s fileserver cache for the following '
                            'targets: %s', backend_name, update_args
                        )
                        args = (update_args,)
                    else:
                        log.debug('Updating %s fileserver cache', backend_name)
                        args = ()

                    update_func(*args)
                except Exception as exc:
                    log.exception(
                        'Uncaught exception while updating %s fileserver '
                        'cache', backend_name
                    )

            log.debug(
                'Completed fileserver updates for items with an update '
                'interval of %d, waiting %d seconds', interval, interval
            )

        condition = threading.Condition()
        _do_update()
        while True:
            with condition:
                condition.wait(interval)
            _do_update()

    def run(self):
        '''
        Start the update threads
        '''
        salt.utils.process.appendproctitle(self.__class__.__name__)
        # Clean out the fileserver backend cache
        salt.daemons.masterapi.clean_fsbackend(self.opts)

        for interval in self.buckets:
            self.update_threads[interval] = threading.Thread(
                target=self.update_fileserver,
                args=(interval, self.buckets[interval]),
            )
            self.update_threads[interval].start()

        # Keep the process alive
        while True:
            time.sleep(60)


class Master(SMaster):
    '''
    The salt master server
    '''
    def __init__(self, opts):
        '''
        Create a salt master server instance

        :param dict: The salt options
        '''
        if zmq and ZMQ_VERSION_INFO < (3, 2):
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
            # Unclear what to do with infinity... macOS reports RLIM_INFINITY as
            # hard limit,but raising to anything above soft limit fails...
            mof_h = mof_s
        log.info(
            'Current values for max open files soft/hard setting: %s/%s',
            mof_s, mof_h
        )
        # Let's grab, from the configuration file, the value to raise max open
        # files to
        mof_c = self.opts['max_open_files']
        if mof_c > mof_h:
            # The configured value is higher than what's allowed
            log.info(
                'The value for the \'max_open_files\' setting, %s, is higher '
                'than the highest value the user running salt is allowed to '
                'set (%s). Defaulting to %s.', mof_c, mof_h, mof_h
            )
            mof_c = mof_h

        if mof_s < mof_c:
            # There's room to raise the value. Raise it!
            log.info('Raising max open files value to %s', mof_c)
            resource.setrlimit(resource.RLIMIT_NOFILE, (mof_c, mof_h))
            try:
                mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
                log.info(
                    'New values for max open files soft/hard values: %s/%s',
                    mof_s, mof_h
                )
            except ValueError:
                # https://github.com/saltstack/salt/issues/1991#issuecomment-13025595
                # A user under macOS reported that our 100000 default value is
                # still too high.
                log.critical(
                    'Failed to raise max open files setting to %s. If this '
                    'value is too low, the salt-master will most likely fail '
                    'to run properly.', mof_c
                )

    def _pre_flight(self):
        '''
        Run pre flight checks. If anything in this method fails then the master
        should not start up.
        '''
        errors = []
        critical_errors = []

        try:
            os.chdir('/')
        except OSError as err:
            errors.append(
                'Cannot change to root directory ({0})'.format(err)
            )

        if self.opts.get('fileserver_verify_config', True):
            # Avoid circular import
            import salt.fileserver
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
                except salt.exceptions.FileserverConfigError as exc:
                    critical_errors.append('{0}'.format(exc))

        if not self.opts['fileserver_backend']:
            errors.append('No fileserver backends are configured')

        # Check to see if we need to create a pillar cache dir
        if self.opts['pillar_cache'] and not os.path.isdir(os.path.join(self.opts['cachedir'], 'pillar_cache')):
            try:
                prev_umask = os.umask(0o077)
                os.mkdir(os.path.join(self.opts['cachedir'], 'pillar_cache'))
                os.umask(prev_umask)
            except OSError:
                pass

        if self.opts.get('git_pillar_verify_config', True):
            git_pillars = [
                x for x in self.opts.get('ext_pillar', [])
                if 'git' in x
                and not isinstance(x['git'], six.string_types)
            ]
            if git_pillars:
                try:
                    new_opts = copy.deepcopy(self.opts)
                    import salt.pillar.git_pillar
                    for repo in git_pillars:
                        new_opts['ext_pillar'] = [repo]
                        try:
                            git_pillar = salt.utils.gitfs.GitPillar(
                                new_opts,
                                repo['git'],
                                per_remote_overrides=salt.pillar.git_pillar.PER_REMOTE_OVERRIDES,
                                per_remote_only=salt.pillar.git_pillar.PER_REMOTE_ONLY)
                        except salt.exceptions.FileserverConfigError as exc:
                            critical_errors.append(exc.strerror)
                finally:
                    del new_opts

        if errors or critical_errors:
            for error in errors:
                log.error(error)
            for error in critical_errors:
                log.critical(error)
            log.critical('Master failed pre flight checks, exiting\n')
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)

    def start(self):
        '''
        Turn on the master server components
        '''
        self._pre_flight()
        log.info('salt-master is starting as user \'%s\'', salt.utils.user.get_user())

        enable_sigusr1_handler()
        enable_sigusr2_handler()

        self.__set_max_open_files()

        # Reset signals to default ones before adding processes to the process
        # manager. We don't want the processes being started to inherit those
        # signal handlers
        with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):

            # Setup the secrets here because the PubServerChannel may need
            # them as well.
            SMaster.secrets['aes'] = {
                'secret': multiprocessing.Array(
                    ctypes.c_char,
                    salt.utils.stringutils.to_bytes(
                        salt.crypt.Crypticle.generate_key_string()
                    )
                ),
                'reload': salt.crypt.Crypticle.generate_key_string
            }
            log.info('Creating master process manager')
            # Since there are children having their own ProcessManager we should wait for kill more time.
            self.process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
            pub_channels = []
            log.info('Creating master publisher process')
            for transport, opts in iter_transport_opts(self.opts):
                chan = salt.transport.server.PubServerChannel.factory(opts)
                chan.pre_fork(self.process_manager)
                pub_channels.append(chan)

            log.info('Creating master event publisher process')
            self.process_manager.add_process(salt.utils.event.EventPublisher, args=(self.opts,))

            if self.opts.get('reactor'):
                if isinstance(self.opts['engines'], list):
                    rine = False
                    for item in self.opts['engines']:
                        if 'reactor' in item:
                            rine = True
                            break
                    if not rine:
                        self.opts['engines'].append({'reactor': {}})
                else:
                    if 'reactor' not in self.opts['engines']:
                        log.info('Enabling the reactor engine')
                        self.opts['engines']['reactor'] = {}

            salt.engines.start_engines(self.opts, self.process_manager)

            # must be after channels
            log.info('Creating master maintenance process')
            self.process_manager.add_process(Maintenance, args=(self.opts,))

            if self.opts.get('event_return'):
                log.info('Creating master event return process')
                self.process_manager.add_process(salt.utils.event.EventReturn, args=(self.opts,))

            ext_procs = self.opts.get('ext_processes', [])
            for proc in ext_procs:
                log.info('Creating ext_processes process: %s', proc)
                try:
                    mod = '.'.join(proc.split('.')[:-1])
                    cls = proc.split('.')[-1]
                    _tmp = __import__(mod, globals(), locals(), [cls], -1)
                    cls = _tmp.__getattribute__(cls)
                    self.process_manager.add_process(cls, args=(self.opts,))
                except Exception:
                    log.error('Error creating ext_processes process: %s', proc)

            if HAS_HALITE and 'halite' in self.opts:
                log.info('Creating master halite process')
                self.process_manager.add_process(Halite, args=(self.opts['halite'],))

            # TODO: remove, or at least push into the transport stuff (pre-fork probably makes sense there)
            if self.opts['con_cache']:
                log.info('Creating master concache process')
                self.process_manager.add_process(salt.utils.master.ConnectedCache, args=(self.opts,))
                # workaround for issue #16315, race condition
                log.debug('Sleeping for two seconds to let concache rest')
                time.sleep(2)

            log.info('Creating master request server process')
            kwargs = {}
            if salt.utils.platform.is_windows():
                kwargs['log_queue'] = salt.log.setup.get_multiprocessing_logging_queue()
                kwargs['secrets'] = SMaster.secrets

            self.process_manager.add_process(
                ReqServer,
                args=(self.opts, self.key, self.master_key),
                kwargs=kwargs,
                name='ReqServer')

            self.process_manager.add_process(
                FileserverUpdate,
                args=(self.opts,))

            # Fire up SSDP discovery publisher
            if self.opts['discovery']:
                if salt.utils.ssdp.SSDPDiscoveryServer.is_available():
                    self.process_manager.add_process(salt.utils.ssdp.SSDPDiscoveryServer(
                        port=self.opts['discovery']['port'],
                        listen_ip=self.opts['interface'],
                        answer={'mapping': self.opts['discovery'].get('mapping', {})}).run)
                else:
                    log.error('Unable to load SSDP: asynchronous IO is not available.')
                    if sys.version_info.major == 2:
                        log.error('You are using Python 2, please install "trollius" module to enable SSDP discovery.')

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
        self.__init__(state['hopts'], log_queue=state['log_queue'])

    def __getstate__(self):
        return {'hopts': self.hopts,
                'log_queue': self.log_queue}

    def run(self):
        '''
        Fire up halite!
        '''
        salt.utils.process.appendproctitle(self.__class__.__name__)
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
        self.__init__(state['opts'], state['key'], state['mkey'],
                      log_queue=state['log_queue'], secrets=state['secrets'])

    def __getstate__(self):
        return {'opts': self.opts,
                'key': self.key,
                'mkey': self.master_key,
                'log_queue': self.log_queue,
                'secrets': self.secrets}

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

        dfn = os.path.join(self.opts['cachedir'], '.dfn')
        if os.path.isfile(dfn):
            try:
                if salt.utils.platform.is_windows() and not os.access(dfn, os.W_OK):
                    # Cannot delete read-only files on Windows.
                    os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
                os.remove(dfn)
            except os.error:
                pass

        # Wait for kill should be less then parent's ProcessManager.
        self.process_manager = salt.utils.process.ProcessManager(name='ReqServer_ProcessManager',
                                                                 wait_for_kill=1)

        req_channels = []
        tcp_only = True
        for transport, opts in iter_transport_opts(self.opts):
            chan = salt.transport.server.ReqServerChannel.factory(opts)
            chan.pre_fork(self.process_manager)
            req_channels.append(chan)
            if transport != 'tcp':
                tcp_only = False

        kwargs = {}
        if salt.utils.platform.is_windows():
            kwargs['log_queue'] = self.log_queue
            # Use one worker thread if only the TCP transport is set up on
            # Windows and we are using Python 2. There is load balancer
            # support on Windows for the TCP transport when using Python 3.
            if tcp_only and six.PY2 and int(self.opts['worker_threads']) != 1:
                log.warning('TCP transport supports only 1 worker on Windows '
                            'when using Python 2.')
                self.opts['worker_threads'] = 1

        # Reset signals to default ones before adding processes to the process
        # manager. We don't want the processes being started to inherit those
        # signal handlers
        with salt.utils.process.default_signals(signal.SIGINT, signal.SIGTERM):
            for ind in range(int(self.opts['worker_threads'])):
                name = 'MWorker-{0}'.format(ind)
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
        if hasattr(self, 'process_manager'):
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
        kwargs['name'] = name
        self.name = name
        super(MWorker, self).__init__(**kwargs)
        self.opts = opts
        self.req_channels = req_channels

        self.mkey = mkey
        self.key = key
        self.k_mtime = 0
        self.stats = collections.defaultdict(lambda: {'mean': 0, 'runs': 0})
        self.stat_clock = time.time()

    # We need __setstate__ and __getstate__ to also pickle 'SMaster.secrets'.
    # Otherwise, 'SMaster.secrets' won't be copied over to the spawned process
    # on Windows since spawning processes on Windows requires pickling.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        self._is_child = True
        super(MWorker, self).__init__(log_queue=state['log_queue'])
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
                'log_queue': self.log_queue,
                'secrets': SMaster.secrets}

    def _handle_signals(self, signum, sigframe):
        for channel in getattr(self, 'req_channels', ()):
            channel.close()
        super(MWorker, self)._handle_signals(signum, sigframe)

    def __bind(self):
        '''
        Bind to the local port
        '''
        # using ZMQIOLoop since we *might* need zmq in there
        install_zmq()
        self.io_loop = ZMQDefaultLoop()
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
        key = payload['enc']
        load = payload['load']
        ret = {'aes': self._handle_aes,
               'clear': self._handle_clear}[key](load)
        raise tornado.gen.Return(ret)

    def _post_stats(self, start, cmd):
        '''
        Calculate the master stats and fire events with stat info
        '''
        end = time.time()
        duration = end - start
        self.stats[cmd]['mean'] = (self.stats[cmd]['mean'] * (self.stats[cmd]['runs'] - 1) + duration) / self.stats[cmd]['runs']
        if end - self.stat_clock > self.opts['master_stats_event_iter']:
            # Fire the event with the stats and wipe the tracker
            self.aes_funcs.event.fire_event({'time': end - self.stat_clock, 'worker': self.name, 'stats': self.stats}, tagify(self.name, 'stats'))
            self.stats = collections.defaultdict(lambda: {'mean': 0, 'runs': 0})
            self.stat_clock = end

    def _handle_clear(self, load):
        '''
        Process a cleartext command

        :param dict load: Cleartext payload
        :return: The result of passing the load to a function in ClearFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        log.trace('Clear payload received with command %s', load['cmd'])
        cmd = load['cmd']
        if cmd.startswith('__'):
            return False
        if self.opts['master_stats']:
            start = time.time()
            self.stats[cmd]['runs'] += 1
        ret = getattr(self.clear_funcs, cmd)(load), {'fun': 'send_clear'}
        if self.opts['master_stats']:
            self._post_stats(start, cmd)
        return ret

    def _handle_aes(self, data):
        '''
        Process a command sent via an AES key

        :param str load: Encrypted payload
        :return: The result of passing the load to a function in AESFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        if 'cmd' not in data:
            log.error('Received malformed command %s', data)
            return {}
        cmd = data['cmd']
        log.trace('AES payload received with command %s', data['cmd'])
        if cmd.startswith('__'):
            return False
        if self.opts['master_stats']:
            start = time.time()
            self.stats[cmd]['runs'] += 1
        ret = self.aes_funcs.run_func(data['cmd'], data)
        if self.opts['master_stats']:
            self._post_stats(start, cmd)
        return ret

    def run(self):
        '''
        Start a Master Worker
        '''
        salt.utils.process.appendproctitle(self.name)
        self.clear_funcs = ClearFuncs(
           self.opts,
           self.key,
           )
        self.aes_funcs = AESFuncs(self.opts)
        salt.utils.crypt.reinit_crypto()
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
            rend=False,
            ignore_config_errors=True
        )
        self.__setup_fileserver()
        self.masterapi = salt.daemons.masterapi.RemoteFuncs(opts)

    def __setup_fileserver(self):
        '''
        Set the local file objects from the file server interface
        '''
        # Avoid circular import
        import salt.fileserver
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
        pub_path = os.path.join(self.opts['pki_dir'], 'minions', id_)

        try:
            pub = salt.crypt.get_rsa_pub_key(pub_path)
        except (IOError, OSError):
            log.warning(
                'Salt minion claiming to be %s attempted to communicate with '
                'master, but key could not be read and verification was denied.',
                id_
            )
            return False
        except (ValueError, IndexError, TypeError) as err:
            log.error('Unable to load public key "%s": %s', pub_path, err)
        try:
            if salt.crypt.public_decrypt(pub, token) == b'salt':
                return True
        except ValueError as err:
            log.error('Unable to decrypt token: %s', err)

        log.error(
            'Salt minion claiming to be %s has attempted to communicate with '
            'the master and could not be verified', id_
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
            log.warning(
                'Minion id %s is not who it says it is and is attempting '
                'to issue a peer command', clear_load['id']
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
            clear_load['arg'],
            clear_load['tgt'],
            clear_load.get('tgt_type', 'glob'),
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
        if 'tok' not in load:
            log.error(
                'Received incomplete call from %s for \'%s\', missing \'%s\'',
                load['id'], inspect_stack()['co_name'], 'tok'
            )
            return False
        if not self.__verify_minion(load['id'], load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning('Minion id %s is not who it says it is!', load['id'])
            return False

        if 'tok' in load:
            load.pop('tok')

        return load

    def _master_tops(self, load):
        '''
        Return the results from an external node classifier if one is
        specified

        :param dict load: A payload received from a minion
        :return: The results from an external node classifier
        '''
        load = self.__verify_load(load, ('id', 'tok'))
        if load is False:
            return {}
        return self.masterapi._master_tops(load, skip_verify=True)

    # Needed so older minions can request master_tops
    _ext_nodes = _master_tops

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
        mopts['top_file_merging_strategy'] = self.opts['top_file_merging_strategy']
        mopts['env_order'] = self.opts['env_order']
        mopts['default_top'] = self.opts['default_top']
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
        mopts['jinja_env'] = self.opts['jinja_env']
        mopts['jinja_sls_env'] = self.opts['jinja_sls_env']
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
        if not isinstance(load['path'], list):
            return False
        if not self.opts['file_recv']:
            return False
        if not salt.utils.verify.valid_id(self.opts, load['id']):
            return False
        file_recv_max_size = 1024*1024 * self.opts['file_recv_max_size']

        if 'loc' in load and load['loc'] < 0:
            log.error('Invalid file pointer: load[loc] < 0')
            return False

        if len(load['data']) + load.get('loc', 0) > file_recv_max_size:
            log.error(
                'file_recv_max_size limit of %d MB exceeded! %s will be '
                'truncated. To successfully push this file, adjust '
                'file_recv_max_size to an integer (in MB) large enough to '
                'accommodate it.', file_recv_max_size, load['path']
            )
            return False
        if 'tok' not in load:
            log.error(
                'Received incomplete call from %s for \'%s\', missing \'%s\'',
                load['id'], inspect_stack()['co_name'], 'tok'
            )
            return False
        if not self.__verify_minion(load['id'], load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning('Minion id %s is not who it says it is!', load['id'])
            return {}
        load.pop('tok')

        # Join path
        sep_path = os.sep.join(load['path'])

        # Path normalization should have been done by the sending
        # minion but we can't guarantee it. Re-do it here.
        normpath = os.path.normpath(sep_path)

        # Ensure that this safety check is done after the path
        # have been normalized.
        if os.path.isabs(normpath) or '../' in load['path']:
            # Can overwrite master files!!
            return False

        cpath = os.path.join(
            self.opts['cachedir'],
            'minions',
            load['id'],
            'files',
            normpath)
        # One last safety check here
        if not os.path.normpath(cpath).startswith(self.opts['cachedir']):
            log.warning(
                'Attempt to write received file outside of master cache '
                'directory! Requested path: %s. Access denied.', cpath
            )
            return False
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
        with salt.utils.files.fopen(cpath, mode) as fp_:
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

        pillar = salt.pillar.get_pillar(
            self.opts,
            load['grains'],
            load['id'],
            load.get('saltenv', load.get('env')),
            ext=load.get('ext'),
            pillar_override=load.get('pillar_override', {}),
            pillarenv=load.get('pillarenv'),
            extra_minion_data=load.get('extra_minion_data'))
        data = pillar.compile_pillar()
        self.fs_.update_opts()
        if self.opts.get('minion_data_cache', False):
            self.masterapi.cache.store('minions/{0}'.format(load['id']),
                                       'data',
                                       {'grains': load['grains'],
                                        'pillar': data})
            if self.opts.get('minion_data_cache_events') is True:
                self.event.fire_event({'Minion data cache refresh': load['id']}, tagify(load['id'], 'refresh', 'minion'))
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
        id_ = load['id']
        if load.get('tag', '') == '_salt_error':
            log.error(
                'Received minion error from [%s]: %s',
                id_, load['data']['message']
            )

        for event in load.get('events', []):
            event_data = event.get('data', {})
            if 'minions' in event_data:
                jid = event_data.get('jid')
                if not jid:
                    continue
                minions = event_data['minions']
                try:
                    salt.utils.job.store_minions(
                        self.opts,
                        jid,
                        minions,
                        mminion=self.mminion,
                        syndic_id=id_)
                except (KeyError, salt.exceptions.SaltCacheError) as exc:
                    log.error(
                        'Could not add minion(s) %s for job %s: %s',
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
        if self.opts['require_minion_sign_messages'] and 'sig' not in load:
            log.critical(
                '_return: Master is requiring minions to sign their '
                'messages, but there is no signature in this payload from '
                '%s.', load['id']
            )
            return False

        if 'sig' in load:
            log.trace('Verifying signed event publish from minion')
            sig = load.pop('sig')
            this_minion_pubkey = os.path.join(self.opts['pki_dir'], 'minions/{0}'.format(load['id']))
            serialized_load = salt.serializers.msgpack.serialize(load)
            if not salt.crypt.verify_signature(this_minion_pubkey, serialized_load, sig):
                log.info('Failed to verify event signature from minion %s.', load['id'])
                if self.opts['drop_messages_signature_fail']:
                    log.critical(
                        'Drop_messages_signature_fail is enabled, dropping '
                        'message from %s', load['id']
                    )
                    return False
                else:
                    log.info('But \'drop_message_signature_fail\' is disabled, so message is still accepted.')
            load['sig'] = sig

        try:
            salt.utils.job.store_job(
                self.opts, load, event=self.event, mminion=self.mminion)
        except salt.exceptions.SaltCacheError:
            log.error('Could not store job information for load: %s', load)

    def _syndic_return(self, load):
        '''
        Receive a syndic minion return and format it to look like returns from
        individual minions.

        :param dict load: The minion payload
        '''
        loads = load.get('load')
        if not isinstance(loads, list):
            loads = [load]  # support old syndics not aggregating returns
        for load in loads:
            # Verify the load
            if any(key not in load for key in ('return', 'jid', 'id')):
                continue
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
                with salt.utils.files.fopen(syndic_cache_path, 'w') as wfh:
                    wfh.write('')

            # Format individual return loads
            for key, item in six.iteritems(load['return']):
                ret = {'jid': load['jid'],
                       'id': key}
                ret.update(item)
                if 'master_id' in load:
                    ret['master_id'] = load['master_id']
                if 'fun' in load:
                    ret['fun'] = load['fun']
                if 'arg' in load:
                    ret['fun_args'] = load['arg']
                if 'out' in load:
                    ret['out'] = load['out']
                if 'sig' in load:
                    ret['sig'] = load['sig']
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
        jid_fn = os.path.join(auth_cache, six.text_type(load['jid']))
        with salt.utils.files.fopen(jid_fn, 'r') as fp_:
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

        if not self.opts.get('allow_minion_key_revoke', False):
            log.warning(
                'Minion %s requested key revoke, but allow_minion_key_revoke '
                'is set to False', load['id']
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
        if func.startswith('__'):
            # TODO: return some error? Seems odd to return {}
            return {}, {'fun': 'send'}
        # Run the func
        if hasattr(self, func):
            try:
                start = time.time()
                ret = getattr(self, func)(load)
                log.trace(
                    'Master function call %s took %s seconds',
                    func, time.time() - start
                )
            except Exception:
                ret = ''
                log.error('Error in function %s:\n', func, exc_info=True)
        else:
            log.error(
                'Received function %s which is unavailable on the master, '
                'returning False', func
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
        error = auth_check.get('error')

        if error:
            # Authentication error occurred: do not continue.
            return {'error': error}

        # Authorize
        username = auth_check.get('username')
        if auth_type != 'user':
            runner_check = self.ckminions.runner_check(
                auth_check.get('auth_list', []),
                clear_load['fun'],
                clear_load.get('kwarg', {})
            )
            if not runner_check:
                return {'error': {'name': err_name,
                                   'message': 'Authentication failure of type "{0}" occurred for '
                                             'user {1}.'.format(auth_type, username)}}
            elif isinstance(runner_check, dict) and 'error' in runner_check:
                # A dictionary with an error name/message was handled by ckminions.runner_check
                return runner_check

            # No error occurred, consume sensitive settings from the clear_load if passed.
            for item in sensitive_load_keys:
                clear_load.pop(item, None)
        else:
            if 'user' in clear_load:
                username = clear_load['user']
                if salt.auth.AuthUser(username).is_sudo():
                    username = self.opts.get('user', 'root')
            else:
                username = salt.utils.user.get_user()

        # Authorized. Do the job!
        try:
            fun = clear_load.pop('fun')
            runner_client = salt.runner.RunnerClient(self.opts)
            return runner_client.async(fun,
                                       clear_load.get('kwarg', {}),
                                       username)
        except Exception as exc:
            log.error('Exception occurred while introspecting %s: %s', fun, exc)
            return {'error': {'name': exc.__class__.__name__,
                              'args': exc.args,
                              'message': six.text_type(exc)}}

    def wheel(self, clear_load):
        '''
        Send a master control function back to the wheel system
        '''
        # All wheel ops pass through eauth
        auth_type, err_name, key, sensitive_load_keys = self._prep_auth_info(clear_load)

        # Authenticate
        auth_check = self.loadauth.check_authentication(clear_load, auth_type, key=key)
        error = auth_check.get('error')

        if error:
            # Authentication error occurred: do not continue.
            return {'error': error}

        # Authorize
        username = auth_check.get('username')
        if auth_type != 'user':
            wheel_check = self.ckminions.wheel_check(
                auth_check.get('auth_list', []),
                clear_load['fun'],
                clear_load.get('kwarg', {})
            )
            if not wheel_check:
                return {'error': {'name': err_name,
                                  'message': 'Authentication failure of type "{0}" occurred for '
                                             'user {1}.'.format(auth_type, username)}}
            elif isinstance(wheel_check, dict) and 'error' in wheel_check:
                # A dictionary with an error name/message was handled by ckminions.wheel_check
                return wheel_check

            # No error occurred, consume sensitive settings from the clear_load if passed.
            for item in sensitive_load_keys:
                clear_load.pop(item, None)
        else:
            if 'user' in clear_load:
                username = clear_load['user']
                if salt.auth.AuthUser(username).is_sudo():
                    username = self.opts.get('user', 'root')
            else:
                username = salt.utils.user.get_user()

        # Authorized. Do the job!
        try:
            jid = salt.utils.jid.gen_jid(self.opts)
            fun = clear_load.pop('fun')
            tag = tagify(jid, prefix='wheel')
            data = {'fun': "wheel.{0}".format(fun),
                    'jid': jid,
                    'tag': tag,
                    'user': username}

            self.event.fire_event(data, tagify([jid, 'new'], 'wheel'))
            ret = self.wheel_.call_func(fun, full_return=True, **clear_load)
            data['return'] = ret['return']
            data['success'] = ret['success']
            self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
            return {'tag': tag,
                    'data': data}
        except Exception as exc:
            log.error('Exception occurred while introspecting %s: %s', fun, exc)
            data['return'] = 'Exception occurred in wheel {0}: {1}: {2}'.format(
                             fun,
                             exc.__class__.__name__,
                             exc,
            )
            data['success'] = False
            self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
            return {'tag': tag,
                    'data': data}

    def mk_token(self, clear_load):
        '''
        Create and return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        '''
        token = self.loadauth.mk_token(clear_load)
        if not token:
            log.warning('Authentication failure of type "eauth" occurred.')
            return ''
        return token

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

        publisher_acl = salt.acl.PublisherACL(self.opts['publisher_acl_blacklist'])

        if publisher_acl.user_is_blacklisted(clear_load['user']) or \
                publisher_acl.cmd_is_blacklisted(clear_load['fun']):
            log.error(
                '%s does not have permissions to run %s. Please contact '
                'your local administrator if you believe this is in '
                'error.\n', clear_load['user'], clear_load['fun']
            )
            return {'error': {'name': 'AuthorizationError',
                              'message': 'Authorization error occurred.'}}

        # Retrieve the minions list
        delimiter = clear_load.get('kwargs', {}).get('delimiter', DEFAULT_TARGET_DELIM)
        _res = self.ckminions.check_minions(
            clear_load['tgt'],
            clear_load.get('tgt_type', 'glob'),
            delimiter
        )
        minions = _res.get('minions', list())
        missing = _res.get('missing', list())
        ssh_minions = _res.get('ssh_minions', False)

        # Check for external auth calls and authenticate
        auth_type, err_name, key, sensitive_load_keys = self._prep_auth_info(extra)
        if auth_type == 'user':
            auth_check = self.loadauth.check_authentication(clear_load, auth_type, key=key)
        else:
            auth_check = self.loadauth.check_authentication(extra, auth_type)

        # Setup authorization list variable and error information
        auth_list = auth_check.get('auth_list', [])
        err_msg = 'Authentication failure of type "{0}" occurred.'.format(auth_type)

        if auth_check.get('error'):
            # Authentication error occurred: do not continue.
            log.warning(err_msg)
            return {'error': {'name': 'AuthenticationError',
                              'message': 'Authentication error occurred.'}}

        # All Token, Eauth, and non-root users must pass the authorization check
        if auth_type != 'user' or (auth_type == 'user' and auth_list):
            # Authorize the request
            authorized = self.ckminions.auth_check(
                auth_list,
                clear_load['fun'],
                clear_load['arg'],
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob'),
                minions=minions,
                # always accept find_job
                whitelist=['saltutil.find_job'],
            )

            if not authorized:
                # Authorization error occurred. Do not continue.
                log.warning(err_msg)
                return {'error': {'name': 'AuthorizationError',
                                  'message': 'Authorization error occurred.'}}

            # Perform some specific auth_type tasks after the authorization check
            if auth_type == 'token':
                username = auth_check.get('username')
                clear_load['user'] = username
                log.debug('Minion tokenized user = "%s"', username)
            elif auth_type == 'eauth':
                # The username we are attempting to auth with
                clear_load['user'] = self.loadauth.load_name(extra)

        # If we order masters (via a syndic), don't short circuit if no minions
        # are found
        if not self.opts.get('order_masters'):
            # Check for no minions
            if not minions:
                return {
                    'enc': 'clear',
                    'load': {
                        'jid': None,
                        'minions': minions,
                        'error': 'Master could not resolve minions for target {0}'.format(clear_load['tgt'])
                    }
                }
        jid = self._prep_jid(clear_load, extra)
        if jid is None:
            return {'enc': 'clear',
                    'load': {'error': 'Master failed to assign jid'}}
        payload = self._prep_pub(minions, jid, clear_load, extra, missing)

        # Send it!
        self._send_ssh_pub(payload, ssh_minions=ssh_minions)
        self._send_pub(payload)

        return {
            'enc': 'clear',
            'load': {
                'jid': clear_load['jid'],
                'minions': minions,
                'missing': missing
            }
        }

    def _prep_auth_info(self, clear_load):
        sensitive_load_keys = []
        key = None
        if 'token' in clear_load:
            auth_type = 'token'
            err_name = 'TokenAuthenticationError'
            sensitive_load_keys = ['token']
        elif 'eauth' in clear_load:
            auth_type = 'eauth'
            err_name = 'EauthAuthenticationError'
            sensitive_load_keys = ['username', 'password']
        else:
            auth_type = 'user'
            err_name = 'UserAuthenticationError'
            key = self.key

        return auth_type, err_name, key, sensitive_load_keys

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

    @property
    def ssh_client(self):
        if not hasattr(self, '_ssh_client'):
            self._ssh_client = salt.client.ssh.client.SSHClient(mopts=self.opts)
        return self._ssh_client

    def _send_ssh_pub(self, load, ssh_minions=False):
        '''
        Take a load and send it across the network to ssh minions
        '''
        if self.opts['enable_ssh_minions'] is True and ssh_minions is True:
            log.debug('Send payload to ssh minions')
            threading.Thread(target=self.ssh_client.cmd, kwargs=load).start()

    def _prep_pub(self, minions, jid, clear_load, extra, missing):
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
            'missing': missing,
            }

        # Announce the job on the event bus
        self.event.fire_event(new_job_load, tagify([clear_load['jid'], 'new'], 'job'))

        if self.opts['ext_job_cache']:
            fstr = '{0}.save_load'.format(self.opts['ext_job_cache'])
            save_load_func = True

            # Get the returner's save_load arg_spec.
            try:
                arg_spec = salt.utils.args.get_function_argspec(self.mminion.returners[fstr])

                # Check if 'minions' is included in returner's save_load arg_spec.
                # This may be missing in custom returners, which we should warn about.
                if 'minions' not in arg_spec.args:
                    log.critical(
                        'The specified returner used for the external job cache '
                        '\'%s\' does not have a \'minions\' kwarg in the returner\'s '
                        'save_load function.', self.opts['ext_job_cache']
                    )
            except (AttributeError, KeyError):
                save_load_func = False
                log.critical(
                    'The specified returner used for the external job cache '
                    '"%s" does not have a save_load function!',
                    self.opts['ext_job_cache']
                )

            if save_load_func:
                try:
                    self.mminion.returners[fstr](clear_load['jid'], clear_load, minions=minions)
                except Exception:
                    log.critical(
                        'The specified returner threw a stack trace:\n',
                        exc_info=True
                    )

        # always write out to the master job caches
        try:
            fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[fstr](clear_load['jid'], clear_load, minions)
        except KeyError:
            log.critical(
                'The specified returner used for the master job cache '
                '"%s" does not have a save_load function!',
                self.opts['master_job_cache']
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

            if 'module_executors' in clear_load['kwargs']:
                load['module_executors'] = clear_load['kwargs'].get('module_executors')

            if 'executor_opts' in clear_load['kwargs']:
                load['executor_opts'] = clear_load['kwargs'].get('executor_opts')

            if 'ret_kwargs' in clear_load['kwargs']:
                load['ret_kwargs'] = clear_load['kwargs'].get('ret_kwargs')

        if 'user' in clear_load:
            log.info(
                'User %s Published command %s with jid %s',
                clear_load['user'], clear_load['fun'], clear_load['jid']
            )
            load['user'] = clear_load['user']
        else:
            log.info(
                'Published command %s with jid %s',
                clear_load['fun'], clear_load['jid']
            )
        log.debug('Published command details %s', load)
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
        salt.utils.crypt.appendproctitle(self.__class__.__name__)
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
        log.info('ZMQ Worker binding to socket %s', self.w_uri)
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
