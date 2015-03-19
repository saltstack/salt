# -*- coding: utf-8 -*-
'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python libs
import os
import re
import time
import errno
import shutil
import logging
import hashlib
import resource
import multiprocessing
import sys
import tempfile

# Import third party libs
import zmq
from M2Crypto import RSA

# Import salt libs
import salt.crypt
import salt.utils
import salt.client
import salt.exitcodes
import salt.payload
import salt.pillar
import salt.state
import salt.runner
import salt.auth
import salt.wheel
import salt.minion
import salt.search
import salt.key
import salt.fileserver
import salt.daemons.masterapi
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.verify
import salt.utils.minions
import salt.utils.gzip_util
import salt.utils.process
from salt.exceptions import FileserverConfigError
from salt.utils.debug import enable_sigusr1_handler, enable_sigusr2_handler, inspect_stack
from salt.utils.event import tagify
import binascii

# Import halite libs
try:
    import halite
    HAS_HALITE = True
except ImportError:
    HAS_HALITE = False


log = logging.getLogger(__name__)


class SMaster(object):
    '''
    Create a simple salt-master, this will generate the top-level master
    '''
    def __init__(self, opts):
        '''
        Create a salt master server instance

        :param dict opts: The salt options dictionary
        '''
        self.opts = opts
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.key = self.__prep_key()
        self.crypticle = self.__prep_crypticle()

    def __prep_crypticle(self):
        '''
        Return the crypticle used for AES
        '''
        return salt.crypt.Crypticle(self.opts, self.opts['aes'])

    def __prep_key(self):
        '''
        A key needs to be placed in the filesystem with permissions 0400 so
        clients are required to run as root.
        '''
        return salt.daemons.masterapi.access_keys(self.opts)


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

    def _clear_old_jobs(self):
        '''
        The clean old jobs function is the general passive maintenance process
        controller for the Salt master. This is where any data that needs to
        be cleanly maintained from the master is maintained.
        '''
        # TODO: move to a separate class, with a better name
        salt.utils.appendproctitle('_clear_old_jobs')

        # Set up search object
        search = salt.search.Search(self.opts)
        # Make Start Times
        last = int(time.time())
        rotate = int(time.time())
        # Init fileserver manager
        fileserver = salt.fileserver.Fileserver(self.opts)
        # Load Runners
        runners = salt.loader.runner(self.opts)
        # Load Returners
        returners = salt.loader.returners(self.opts, {})
        # Init Scheduler
        schedule = salt.utils.schedule.Schedule(self.opts, runners, returners=returners)
        ckminions = salt.utils.minions.CkMinions(self.opts)
        # Make Event bus for firing
        event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        # Init any values needed by the git ext pillar
        pillargitfs = salt.daemons.masterapi.init_git_pillar(self.opts)
        # Clean out the fileserver backend cache
        salt.daemons.masterapi.clean_fsbackend(self.opts)
        # Clean out pub auth
        salt.daemons.masterapi.clean_pub_auth(self.opts)

        old_present = set()
        while True:
            now = int(time.time())
            loop_interval = int(self.opts['loop_interval'])
            if (now - last) >= loop_interval:
                salt.daemons.masterapi.clean_old_jobs(self.opts)
                salt.daemons.masterapi.clean_expired_tokens(self.opts)

            if self.opts.get('publish_session'):
                if now - rotate >= self.opts['publish_session']:
                    salt.crypt.dropfile(
                        self.opts['cachedir'],
                        self.opts['user'],
                        self.opts['sock_dir'])
                    rotate = now
                    if self.opts.get('ping_on_rotate'):
                        # Ping all minions to get them to pick up the new key
                        log.debug('Pinging all connected minions due to AES key rotation')
                        salt.utils.master.ping_all_connected_minions(self.opts)
            if self.opts.get('search'):
                if now - last >= self.opts['search_index_interval']:
                    search.index()
            salt.daemons.masterapi.fileserver_update(fileserver)

            # check how close to FD limits you are
            salt.utils.verify.check_max_open_files(self.opts)

            try:
                for pillargit in pillargitfs:
                    pillargit.update()
            except Exception as exc:
                log.error('Exception {0} occurred in file server update '
                          'for git_pillar module.'.format(exc))
            try:
                schedule.eval()
                # Check if scheduler requires lower loop interval than
                # the loop_interval setting
                if schedule.loop_interval < loop_interval:
                    loop_interval = schedule.loop_interval
            except Exception as exc:
                log.error(
                    'Exception {0} occurred in scheduled job'.format(exc)
                )
            last = now
            if self.opts.get('presence_events', False):
                present = ckminions.connected_ids()
                new = present.difference(old_present)
                lost = old_present.difference(present)
                if new or lost:
                    # Fire new minions present event
                    data = {'new': list(new),
                            'lost': list(lost)}
                    event.fire_event(data, tagify('change', 'presence'))
                data = {'present': list(present)}
                event.fire_event(data, tagify('present', 'presence'))
                old_present = present
            try:
                time.sleep(loop_interval)
            except KeyboardInterrupt:
                break

    def __set_max_open_files(self):
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
                errors.append('{0}'.format(exc))
        if not self.opts['fileserver_backend']:
            errors.append('No fileserver backends are configured')
        if errors:
            for error in errors:
                log.error(error)
            log.error('Master failed pre flight checks, exiting\n')
            sys.exit(salt.exitcodes.EX_GENERIC)

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

        process_manager = salt.utils.process.ProcessManager()

        process_manager.add_process(self._clear_old_jobs)

        process_manager.add_process(Publisher, args=(self.opts,))
        process_manager.add_process(salt.utils.event.EventPublisher, args=(self.opts,))

        if self.opts.get('reactor'):
            process_manager.add_process(salt.utils.event.Reactor, args=(self.opts,))

        if HAS_HALITE and 'halite' in self.opts:
            log.info('Halite: Starting up ...')
            process_manager.add_process(Halite, args=(self.opts['halite'],))
        elif 'halite' in self.opts:
            log.info('Halite: Not configured, skipping.')
        else:
            log.debug('Halite: Unavailable.')

        def run_reqserver():
            reqserv = ReqServer(
                self.opts,
                self.crypticle,
                self.key,
                self.master_key)
            reqserv.run()
        process_manager.add_process(run_reqserver)
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


class Publisher(multiprocessing.Process):
    '''
    The publishing interface, a simple zeromq publisher that sends out the
    commands.
    '''
    def __init__(self, opts):
        '''
        Create a publisher instance

        :param dict opts: The salt options
        '''
        super(Publisher, self).__init__()
        self.opts = opts

    def run(self):
        '''
        Bind to the interface specified in the configuration file
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        # Set up the context
        context = zmq.Context(1)
        # Prepare minion publish socket
        pub_sock = context.socket(zmq.PUB)
        # if 2.1 >= zmq < 3.0, we only have one HWM setting
        try:
            pub_sock.setsockopt(zmq.HWM, self.opts.get('pub_hwm', 1000))
        # in zmq >= 3.0, there are separate send and receive HWM settings
        except AttributeError:
            pub_sock.setsockopt(zmq.SNDHWM, self.opts.get('pub_hwm', 1000))
            pub_sock.setsockopt(zmq.RCVHWM, self.opts.get('pub_hwm', 1000))
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            pub_sock.setsockopt(zmq.IPV4ONLY, 0)
        pub_uri = 'tcp://{interface}:{publish_port}'.format(**self.opts)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
        )
        salt.utils.check_ipc_path_max_len(pull_uri)

        # Start the minion command publisher
        log.info('Starting the Salt Publisher on {0}'.format(pub_uri))
        pub_sock.bind(pub_uri)

        # Securely create socket
        log.info('Starting the Salt Puller on {0}'.format(pull_uri))
        old_umask = os.umask(0177)
        try:
            pull_sock.bind(pull_uri)
        finally:
            os.umask(old_umask)

        try:
            while True:
                # Catch and handle EINTR from when this process is sent
                # SIGUSR1 gracefully so we don't choke and die horribly
                try:
                    package = pull_sock.recv()
                    unpacked_package = salt.payload.unpackage(package)
                    payload = unpacked_package['payload']
                    if self.opts['zmq_filtering']:
                        # if you have a specific topic list, use that
                        if 'topic_lst' in unpacked_package:
                            for topic in unpacked_package['topic_lst']:
                                # zmq filters are substring match, hash the topic
                                # to avoid collisions
                                htopic = hashlib.sha1(topic).hexdigest()
                                pub_sock.send(htopic, flags=zmq.SNDMORE)
                                pub_sock.send(payload)
                                # otherwise its a broadcast
                        else:
                            # TODO: constants file for "broadcast"
                            pub_sock.send('broadcast', flags=zmq.SNDMORE)
                            pub_sock.send(payload)
                    else:
                        pub_sock.send(payload)
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc

        except KeyboardInterrupt:
            if pub_sock.closed is False:
                pub_sock.setsockopt(zmq.LINGER, 1)
                pub_sock.close()
            if pull_sock.closed is False:
                pull_sock.setsockopt(zmq.LINGER, 1)
                pull_sock.close()
            if context.closed is False:
                context.term()


class ReqServer(object):
    '''
    Starts up the master request server, minions send results to this
    interface.
    '''
    def __init__(self, opts, crypticle, key, mkey):
        '''
        Create a request server

        :param dict opts: The salt options dictionary
        :crypticle salt.crypt.Crypticle crypticle: Encryption crypticle
        :key dict: The user starting the server and the AES key
        :mkey dict: The user starting the server and the RSA key

        :rtype: ReqServer
        :returns: Request server
        '''
        self.opts = opts
        self.master_key = mkey
        # Prepare the AES key
        self.key = key
        self.crypticle = crypticle

    def zmq_device(self):
        salt.utils.appendproctitle('MWorkerQueue')
        self.context = zmq.Context(self.opts['worker_threads'])
        # Prepare the zeromq sockets
        self.uri = 'tcp://{interface}:{ret_port}'.format(**self.opts)
        self.clients = self.context.socket(zmq.ROUTER)
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.clients.setsockopt(zmq.IPV4ONLY, 0)
        try:
            self.clients.setsockopt(zmq.HWM, self.opts['rep_hwm'])
        # in zmq >= 3.0, there are separate send and receive HWM settings
        except AttributeError:
            self.clients.setsockopt(zmq.SNDHWM, self.opts['rep_hwm'])
            self.clients.setsockopt(zmq.RCVHWM, self.opts['rep_hwm'])

        self.workers = self.context.socket(zmq.DEALER)
        self.w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
        )

        log.info('Setting up the master communication server')
        self.clients.bind(self.uri)

        self.workers.bind(self.w_uri)

        while True:
            try:
                zmq.device(zmq.QUEUE, self.clients, self.workers)
            except zmq.ZMQError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise exc

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

        for ind in range(int(self.opts['worker_threads'])):
            self.process_manager.add_process(MWorker,
                                             args=(self.opts,
                                                   self.master_key,
                                                   self.key,
                                                   self.crypticle,
                                                   ),
                                             )
        self.process_manager.add_process(self.zmq_device)

        # start zmq device
        self.process_manager.run()

    def run(self):
        '''
        Start up the ReqServer
        '''
        self.__bind()

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
                 crypticle):
        '''
        Create a salt master worker process

        :param dict opts: The salt options
        :param dict mkey: The user running the salt master and the AES key
        :param dict key: The user running the salt master and the RSA key
        :param salt.crypt.Crypticle crypticle: Encryption crypticle

        :rtype: MWorker
        :return: Master worker
        '''
        multiprocessing.Process.__init__(self)
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        self.crypticle = crypticle
        self.mkey = mkey
        self.key = key
        self.k_mtime = 0

    def __bind(self):
        '''
        Bind to the local port
        '''
        context = zmq.Context(1)
        socket = context.socket(zmq.REP)
        w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
            )
        log.info('Worker binding to socket {0}'.format(w_uri))
        try:
            socket.connect(w_uri)
            while True:
                try:
                    package = socket.recv()
                    self._update_aes()
                    payload = self.serial.loads(package)
                    ret = self.serial.dumps(self._handle_payload(payload))
                    socket.send(ret)
                # don't catch keyboard interrupts, just re-raise them
                except KeyboardInterrupt:
                    raise
                # catch all other exceptions, so we don't go defunct
                except Exception as exc:
                    # Properly handle EINTR from SIGUSR1
                    if isinstance(exc, zmq.ZMQError) and exc.errno == errno.EINTR:
                        continue
                    log.critical('Unexpected Error in Mworker',
                                 exc_info=True)
                    # lets just redo the socket (since we won't know what state its in).
                    # This protects against a single minion doing a send but not
                    # recv and thereby causing an MWorker process to go defunct
                    del socket
                    socket = context.socket(zmq.REP)
                    socket.connect(w_uri)

        # Changes here create a zeromq condition, check with thatch45 before
        # making any zeromq changes
        except KeyboardInterrupt:
            socket.close()

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
        try:
            key = payload['enc']
            load = payload['load']
        except KeyError:
            return ''
        return {'aes': self._handle_aes,
                'pub': self._handle_pub,
                'clear': self._handle_clear}[key](load)

    def _handle_clear(self, load):
        '''
        Process a cleartext command

        :param dict load: Cleartext payload
        :return: The result of passing the load to a function in ClearFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        log.info('Clear payload received with command {cmd}'.format(**load))
        if load['cmd'].startswith('__'):
            return False
        return getattr(self.clear_funcs, load['cmd'])(load)

    def _handle_pub(self, load):
        '''
        Handle a command sent via a public key pair

        :param dict load: Minion payload
        '''
        if load['cmd'].startswith('__'):
            return False
        log.info('Pubkey payload received with command {cmd}'.format(**load))

    def _handle_aes(self, load):
        '''
        Process a command sent via an AES key

        :param str load: Encrypted payload
        :return: The result of passing the load to a function in AESFuncs corresponding to
                 the command specified in the load's 'cmd' key.
        '''
        try:
            data = self.crypticle.loads(load)
        except Exception:
            return ''
        if 'cmd' not in data:
            log.error('Received malformed command {0}'.format(data))
            return {}
        log.info('AES payload received with command {0}'.format(data['cmd']))
        if data['cmd'].startswith('__'):
            return False
        return self.aes_funcs.run_func(data['cmd'], data)

    def _update_aes(self):
        '''
        Check to see if a fresh AES key is available and update the components
        of the worker
        '''
        dfn = os.path.join(self.opts['cachedir'], '.dfn')
        try:
            stats = os.stat(dfn)
        except os.error:
            return
        if stats.st_mode != 0100400:
            # Invalid dfn, return
            return
        if stats.st_mtime > self.k_mtime:
            # new key, refresh crypticle
            with salt.utils.fopen(dfn) as fp_:
                aes = fp_.read()
            if len(aes) != 76:
                return
            self.crypticle = salt.crypt.Crypticle(self.opts, aes)
            self.clear_funcs.crypticle = self.crypticle
            self.clear_funcs.opts['aes'] = aes
            self.aes_funcs.crypticle = self.crypticle
            self.aes_funcs.opts['aes'] = aes
            self.k_mtime = stats.st_mtime

    def run(self):
        '''
        Start a Master Worker
        '''
        salt.utils.appendproctitle(self.__class__.__name__)
        self.clear_funcs = ClearFuncs(
            self.opts,
            self.key,
            self.mkey,
            self.crypticle)
        self.aes_funcs = AESFuncs(self.opts, self.crypticle)
        self.__bind()


class AESFuncs(object):
    '''
    Set up functions that are available when the load is encrypted with AES
    '''
    # The AES Functions:
    #
    def __init__(self, opts, crypticle):
        '''
        Create a new AESFuncs

        :param dict opts: The salt options
        :param salt.crypt.Crypticle crypticle: Encryption crypticle

        :rtype: AESFuncs
        :returns: Instance for handling AES operations
        '''
        self.opts = opts
        self.event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        self.serial = salt.payload.Serial(opts)
        self.crypticle = crypticle
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
        fs_ = salt.fileserver.Fileserver(self.opts)
        self._serve_file = fs_.serve_file
        self._file_hash = fs_.file_hash
        self._file_list = fs_.file_list
        self._file_list_emptydirs = fs_.file_list_emptydirs
        self._dir_list = fs_.dir_list
        self._symlink_list = fs_.symlink_list
        self._file_envs = fs_.envs

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
            pub = RSA.load_pub_key(tmp_pub)
        except RSA.RSAError as err:
            log.error('Unable to load temporary public key "{0}": {1}'
                      .format(tmp_pub, err))
        try:
            os.remove(tmp_pub)
            if pub.public_decrypt(token, 5) == 'salt':
                return True
        except RSA.RSAError as err:
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
        if load.get('env_only'):
            return mopts
        mopts['renderer'] = self.opts['renderer']
        mopts['failhard'] = self.opts['failhard']
        mopts['state_top'] = self.opts['state_top']
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
        mods = set()
        for func in self.mminion.functions.itervalues():
            mods.add(func.__module__)
        for mod in mods:
            sys.modules[mod].__grains__ = load['grains']

        pillar_dirs = {}
        pillar = salt.pillar.Pillar(
            self.opts,
            load['grains'],
            load['id'],
            load.get('saltenv', load.get('env')),
            load.get('ext'),
            self.mminion.functions)
        data = pillar.compile_pillar(pillar_dirs=pillar_dirs)
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
            os.rename(tmpfname, datap)
        for mod in mods:
            sys.modules[mod].__grains__ = self.opts['grains']
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
        self.masterapi._minion_event(load)

    def _return(self, load):
        '''
        Handle the return data sent from the minions.

        Takes the return, verifies it and fires it on the master event bus.
        Typically, this event is consumed by the Salt CLI waiting on the other
        end of the event bus but could be heard by any listener on the bus.

        :param dict load: The minion payload
        '''
        # If the return data is invalid, just ignore it
        if any(key not in load for key in ('return', 'jid', 'id')):
            return False
        if not salt.utils.verify.valid_id(self.opts, load['id']):
            return False
        if load['jid'] == 'req':
            # The minion is returning a standalone job, request a jobid
            load['arg'] = load.get('arg', load.get('fun_args', []))
            load['tgt_type'] = 'glob'
            load['tgt'] = load['id']
            prep_fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
            load['jid'] = self.mminion.returners[prep_fstr](nocache=load.get('nocache', False))

            # save the load, since we don't have it
            saveload_fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[saveload_fstr](load['jid'], load)
        log.info('Got return from {id} for job {jid}'.format(**load))
        self.event.fire_event(load, load['jid'])  # old dup event
        self.event.fire_event(
            load, tagify([load['jid'], 'ret', load['id']], 'job'))
        self.event.fire_ret_load(load)

        # if you have a job_cache, or an ext_job_cache, don't write to the regular master cache
        if not self.opts['job_cache'] or self.opts.get('ext_job_cache'):
            return

        # otherwise, write to the master cache
        fstr = '{0}.returner'.format(self.opts['master_job_cache'])
        self.mminion.returners[fstr](load)

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

        # Format individual return loads
        for key, item in load['return'].items():
            ret = {'jid': load['jid'],
                   'id': key,
                   'return': item}
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
            return self.masterapi.minion_publish(clear_load, skip_verify=True)

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
            return self.crypticle.dumps({})
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
            return self.crypticle.dumps(False)
        # Don't encrypt the return value for the _return func
        # (we don't care about the return value, so why encrypt it?)
        if func == '_return':
            return ret
        if func == '_pillar' and 'id' in load:
            if load.get('ver') != '2' and self.opts['pillar_version'] == 1:
                # Authorized to return old pillar proto
                return self.crypticle.dumps(ret)
            # encrypt with a specific AES key
            pubfn = os.path.join(self.opts['pki_dir'],
                                 'minions',
                                 load['id'])
            key = salt.crypt.Crypticle.generate_key_string()
            pcrypt = salt.crypt.Crypticle(
                self.opts,
                key)
            try:
                pub = RSA.load_pub_key(pubfn)
            except RSA.RSAError:
                return self.crypticle.dumps({})

            pret = {}
            pret['key'] = pub.public_encrypt(key, 4)
            pret['pillar'] = pcrypt.dumps(
                ret if ret is not False else {}
            )
            return pret
        # AES Encrypt the return
        return self.crypticle.dumps(ret)


class ClearFuncs(object):
    '''
    Set up functions that are safe to execute when commands sent to the master
    without encryption and authentication
    '''
    # The ClearFuncs object encapsulates the functions that can be executed in
    # the clear:
    # publish (The publish from the LocalClient)
    # _auth
    def __init__(self, opts, key, master_key, crypticle):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        self.key = key
        self.master_key = master_key
        self.crypticle = crypticle
        # Create the event manager
        self.event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
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
        self.masterapi = salt.daemons.masterapi.LocalFuncs(opts, key)
        self.auto_key = salt.daemons.masterapi.AutoKey(opts)

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the AES key
        which was generated at start up.

        This method fires an event over the master event manager. The event is
        tagged "auth" and returns a dict with information about the auth
        event

        # Verify that the key we are receiving matches the stored key
        # Store the key if it is not there
        # Make an RSA key with the pub key
        # Encrypt the AES key as an encrypted salt.payload
        # Package the return and return it
        '''

        if not salt.utils.verify.valid_id(self.opts, load['id']):
            log.info(
                'Authentication request from invalid id {id}'.format(**load)
                )
            return {'enc': 'clear',
                    'load': {'ret': False}}
        log.info('Authentication request from {id}'.format(**load))

        # 0 is default which should be 'unlimited'
        if self.opts['max_minions'] > 0:
            minions = salt.utils.minions.CkMinions(self.opts).connected_ids()
            if not len(minions) < self.opts['max_minions']:
                # we reject new minions, minions that are already
                # connected must be allowed for the mine, highstate, etc.
                if load['id'] not in minions:
                    msg = ('Too many minions connected (max_minions={0}). '
                           'Rejecting connection from id '
                           '{1}'.format(self.opts['max_minions'],
                                        load['id']))
                    log.info(msg)
                    eload = {'result': False,
                             'act': 'full',
                             'id': load['id'],
                             'pub': load['pub']}

                    self.event.fire_event(eload, tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': 'full'}}

        # Check if key is configured to be auto-rejected/signed
        auto_reject = self.auto_key.check_autoreject(load['id'])
        auto_sign = self.auto_key.check_autosign(load['id'])

        pubfn = os.path.join(self.opts['pki_dir'],
                             'minions',
                             load['id'])
        pubfn_pend = os.path.join(self.opts['pki_dir'],
                                  'minions_pre',
                                  load['id'])
        pubfn_rejected = os.path.join(self.opts['pki_dir'],
                                      'minions_rejected',
                                      load['id'])
        pubfn_denied = os.path.join(self.opts['pki_dir'],
                                    'minions_denied',
                                    load['id'])
        if self.opts['open_mode']:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn_rejected):
            # The key has been rejected, don't place it in pending
            log.info('Public key rejected for {0}. Key is present in '
                     'rejection key dir.'.format(load['id']))
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, tagify(prefix='auth'))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        elif os.path.isfile(pubfn):
            # The key has been accepted, check it
            if salt.utils.fopen(pubfn, 'r').read() != load['pub']:
                log.error(
                    'Authentication attempt from {id} failed, the public '
                    'keys did not match. This may be an attempt to compromise '
                    'the Salt cluster.'.format(**load)
                )
                # put denied minion key into minions_denied
                with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                    fp_.write(load['pub'])
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, tagify(prefix='auth'))
                return {'enc': 'clear',
                        'load': {'ret': False}}

        elif not os.path.isfile(pubfn_pend):
            # The key has not been accepted, this is a new minion
            if os.path.isdir(pubfn_pend):
                # The key path is a directory, error out
                log.info(
                    'New public key {id} is a directory'.format(**load)
                )
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, tagify(prefix='auth'))
                return {'enc': 'clear',
                        'load': {'ret': False}}

            if auto_reject:
                key_path = pubfn_rejected
                log.info('New public key for {id} rejected via autoreject_file'
                         .format(**load))
                key_act = 'reject'
                key_result = False
            elif not auto_sign:
                key_path = pubfn_pend
                log.info('New public key for {id} placed in pending'
                         .format(**load))
                key_act = 'pend'
                key_result = True
            else:
                # The key is being automatically accepted, don't do anything
                # here and let the auto accept logic below handle it.
                key_path = None

            if key_path is not None:
                # Write the key to the appropriate location
                with salt.utils.fopen(key_path, 'w+') as fp_:
                    fp_.write(load['pub'])
                ret = {'enc': 'clear',
                       'load': {'ret': key_result}}
                eload = {'result': key_result,
                         'act': key_act,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, tagify(prefix='auth'))
                return ret

        elif os.path.isfile(pubfn_pend):
            # This key is in the pending dir and is awaiting acceptance
            if auto_reject:
                # We don't care if the keys match, this minion is being
                # auto-rejected. Move the key file from the pending dir to the
                # rejected dir.
                try:
                    shutil.move(pubfn_pend, pubfn_rejected)
                except (IOError, OSError):
                    pass
                log.info('Pending public key for {id} rejected via '
                         'autoreject_file'.format(**load))
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                eload = {'result': False,
                         'act': 'reject',
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, tagify(prefix='auth'))
                return ret

            elif not auto_sign:
                # This key is in the pending dir and is not being auto-signed.
                # Check if the keys are the same and error out if this is the
                # case. Otherwise log the fact that the minion is still
                # pending.
                if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                    log.error(
                        'Authentication attempt from {id} failed, the public '
                        'key in pending did not match. This may be an '
                        'attempt to compromise the Salt cluster.'
                        .format(**load)
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                        fp_.write(load['pub'])
                    eload = {'result': False,
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': False}}
                else:
                    log.info(
                        'Authentication failed from host {id}, the key is in '
                        'pending and needs to be accepted with salt-key '
                        '-a {id}'.format(**load)
                    )
                    eload = {'result': True,
                             'act': 'pend',
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': True}}
            else:
                # This key is in pending and has been configured to be
                # auto-signed. Check to see if it is the same key, and if
                # so, pass on doing anything here, and let it get automatically
                # accepted below.
                if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                    log.error(
                        'Authentication attempt from {id} failed, the public '
                        'keys in pending did not match. This may be an '
                        'attempt to compromise the Salt cluster.'
                        .format(**load)
                    )
                    # put denied minion key into minions_denied
                    with salt.utils.fopen(pubfn_denied, 'w+') as fp_:
                        fp_.write(load['pub'])
                    eload = {'result': False,
                             'id': load['id'],
                             'pub': load['pub']}
                    self.event.fire_event(eload, tagify(prefix='auth'))
                    return {'enc': 'clear',
                            'load': {'ret': False}}
                else:
                    pass

        else:
            # Something happened that I have not accounted for, FAIL!
            log.warn('Unaccounted for authentication failure')
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, tagify(prefix='auth'))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        log.info('Authentication accepted from {id}'.format(**load))
        # only write to disk if you are adding the file, and in open mode,
        # which implies we accept any key from a minion.
        if not os.path.isfile(pubfn) and not self.opts['open_mode']:
            with salt.utils.fopen(pubfn, 'w+') as fp_:
                fp_.write(load['pub'])
        elif self.opts['open_mode']:
            disk_key = ''
            if os.path.isfile(pubfn):
                with salt.utils.fopen(pubfn, 'r') as fp_:
                    disk_key = fp_.read()
            if load['pub'] and load['pub'] != disk_key:
                log.debug('Host key change detected in open mode.')
                with salt.utils.fopen(pubfn, 'w+') as fp_:
                    fp_.write(load['pub'])

        pub = None

        # The key payload may sometimes be corrupt when using auto-accept
        # and an empty request comes in
        try:
            pub = RSA.load_pub_key(pubfn)
        except RSA.RSAError as err:
            log.error('Corrupt public key "{0}": {1}'.format(pubfn, err))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        ret = {'enc': 'pub',
               'pub_key': self.master_key.get_pub_str(),
               'publish_port': self.opts['publish_port']}

        # sign the masters pubkey (if enabled) before it is
        # send to the minion that was just authenticated
        if self.opts['master_sign_pubkey']:
            # append the pre-computed signature to the auth-reply
            if self.master_key.pubkey_signature():
                log.debug('Adding pubkey signature to auth-reply')
                log.debug(self.master_key.pubkey_signature())
                ret.update({'pub_sig': self.master_key.pubkey_signature()})
            else:
                # the master has its own signing-keypair, compute the master.pub's
                # signature and append that to the auth-reply
                log.debug("Signing master public key before sending")
                pub_sign = salt.crypt.sign_message(self.master_key.get_sign_paths()[1],
                                                   ret['pub_key'])
                ret.update({'pub_sig': binascii.b2a_base64(pub_sign)})

        if self.opts['auth_mode'] >= 2:
            if 'token' in load:
                try:
                    mtoken = self.master_key.key.private_decrypt(load['token'], 4)
                    aes = '{0}_|-{1}'.format(self.opts['aes'], mtoken)
                except Exception:
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass
            else:
                aes = self.opts['aes']

            ret['aes'] = pub.public_encrypt(aes, 4)
        else:
            if 'token' in load:
                try:
                    mtoken = self.master_key.key.private_decrypt(
                        load['token'], 4
                    )
                    ret['token'] = pub.public_encrypt(mtoken, 4)
                except Exception:
                    # Token failed to decrypt, send back the salty bacon to
                    # support older minions
                    pass

            aes = self.opts['aes']
            ret['aes'] = pub.public_encrypt(self.opts['aes'], 4)
        # Be aggressive about the signature
        digest = hashlib.sha256(aes).hexdigest()
        ret['sig'] = self.master_key.key.private_encrypt(digest, 5)
        eload = {'result': True,
                 'act': 'accept',
                 'id': load['id'],
                 'pub': load['pub']}
        self.event.fire_event(eload, tagify(prefix='auth'))
        return ret

    def runner(self, clear_load):
        '''
        Send a master control function back to the runner system
        '''
        # All runner ops pass through eauth
        if 'token' in clear_load:
            try:
                token = self.loadauth.get_tok(clear_load['token'])
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

            good = self.ckminions.runner_check(
                self.opts['external_auth'][token['eauth']][token['name']]
                if token['name'] in self.opts['external_auth'][token['eauth']]
                else self.opts['external_auth'][token['eauth']]['*'],
                clear_load['fun'])
            if not good:
                msg = ('Authentication failure of type "token" occurred for '
                       'user {0}.').format(token['name'])
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))

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

        try:
            name = self.loadauth.load_name(clear_load)
            if not (name in self.opts['external_auth'][clear_load['eauth']]) | ('*' in self.opts['external_auth'][clear_load['eauth']]):
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
            good = self.ckminions.runner_check(
                self.opts['external_auth'][clear_load['eauth']][name]
                if name in self.opts['external_auth'][clear_load['eauth']]
                else self.opts['external_auth'][clear_load['eauth']]['*'],
                clear_load['fun'])
            if not good:
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))

            try:
                fun = clear_load.pop('fun')
                runner_client = salt.runner.RunnerClient(self.opts)
                return runner_client.async(fun,
                                           clear_load.get('kwarg', {}),
                                           clear_load.get('username', 'UNKNOWN'))
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
            try:
                token = self.loadauth.get_tok(clear_load['token'])
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
            good = self.ckminions.wheel_check(
                self.opts['external_auth'][token['eauth']][token['name']]
                if token['name'] in self.opts['external_auth'][token['eauth']]
                else self.opts['external_auth'][token['eauth']]['*'],
                clear_load['fun'])
            if not good:
                msg = ('Authentication failure of type "token" occurred for '
                       'user {0}.').format(token['name'])
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))

            jid = salt.utils.gen_jid()
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

        try:
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
            good = self.ckminions.wheel_check(
                self.opts['external_auth'][clear_load['eauth']][name]
                if name in self.opts['external_auth'][clear_load['eauth']]
                else self.opts['external_auth'][clear_load['eauth']]['*'],
                clear_load['fun'])
            if not good:
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))

            jid = salt.utils.gen_jid()
            fun = clear_load.pop('fun')
            tag = tagify(jid, prefix='wheel')
            data = {'fun': "wheel.{0}".format(fun),
                    'jid': jid,
                    'tag': tag,
                    'user': clear_load.get('username', 'UNKNOWN')}
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
            if not ((name in self.opts['external_auth'][clear_load['eauth']]) |
                    ('*' in self.opts['external_auth'][clear_load['eauth']])):
                log.warning('Authentication failure of type "eauth" occurred.')
                return ''
            if not self.loadauth.time_auth(clear_load):
                log.warning('Authentication failure of type "eauth" occurred.')
                return ''
            return self.loadauth.mk_token(clear_load)
        except Exception as exc:
            log.error(
                'Exception occurred while authenticating: {0}'.format(exc)
            )
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

        # check blacklist/whitelist
        good = True
        # Check if the user is blacklisted
        for user_re in self.opts['client_acl_blacklist'].get('users', []):
            if re.match(user_re, clear_load['user']):
                good = False
                break

        # check if the cmd is blacklisted
        for module_re in self.opts['client_acl_blacklist'].get('modules', []):
            # if this is a regular command, its a single function
            if type(clear_load['fun']) == str:
                funs_to_check = [clear_load['fun']]
            # if this a compound function
            else:
                funs_to_check = clear_load['fun']
            for fun in funs_to_check:
                if re.match(module_re, fun):
                    good = False
                    break

        if good is False:
            log.error(
                '{user} does not have permissions to run {function}. Please '
                'contact your local administrator if you believe this is in '
                'error.\n'.format(
                    user=clear_load['user'],
                    function=clear_load['fun']
                )
            )
            return ''
        # to make sure we don't step on anyone else's toes
        del good

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
            if not token:
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            if token['eauth'] not in self.opts['external_auth']:
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            if not ((token['name'] in self.opts['external_auth'][token['eauth']]) |
                    ('*' in self.opts['external_auth'][token['eauth']])):
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            good = self.ckminions.auth_check(
                self.opts['external_auth'][token['eauth']][token['name']]
                if token['name'] in self.opts['external_auth'][token['eauth']]
                else self.opts['external_auth'][token['eauth']]['*'],
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
                group_perm_keys = filter(lambda(item): item.endswith('%'), self.opts['external_auth'][extra['eauth']])  # The configured auth groups

                # First we need to know if the user is allowed to proceed via any of their group memberships.
                group_auth_match = False
                for group_config in group_perm_keys:
                    group_config = group_config.rstrip('%')
                    for group in groups:
                        if group == group_config:
                            group_auth_match = True
                # If a group_auth_match is set it means only that we have a user which matches at least one or more
                # of the groups defined in the configuration file.

                external_auth_in_db = False
                for d in self.opts['external_auth'][extra['eauth']]:
                    if d.startswith('^'):
                        external_auth_in_db = True

                # If neither a catchall, a named membership or a group membership is found, there is no need
                # to continue. Simply deny the user access.
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

                # Perform the actual authentication. If we fail here, do not continue.
                if not self.loadauth.time_auth(extra):
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''

            except Exception as exc:
                log.error(
                    'Exception occurred while authenticating: {0}'.format(exc)
                )
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
            if clear_load['user'].startswith('sudo_'):
                # If someone can sudo, allow them to act as root
                if clear_load.get('key', 'invalid') == self.key.get('root'):
                    clear_load.pop('key')
                elif clear_load.pop('key') != self.key[self.opts.get('user', 'root')]:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif clear_load['user'] == self.opts.get('user', 'root'):
                if clear_load.pop('key') != self.key[self.opts.get('user', 'root')]:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif clear_load['user'] == 'root':
                if clear_load.pop('key') != self.key.get(self.opts.get('user', 'root')):
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif clear_load['user'] == salt.utils.get_user():
                if clear_load.pop('key') != self.key.get(clear_load['user']):
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
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
        # Retrieve the minions list
        minions = self.ckminions.check_minions(
            clear_load['tgt'],
            clear_load.get('tgt_type', 'glob')
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
        # Retrieve the jid
        fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
        clear_load['jid'] = self.mminion.returners[fstr](nocache=extra.get('nocache', False),
                                                         # the jid in clear_load can be None, '', or something else.
                                                         # this is an attempt to clean up the value before passing to plugins
                                                         passed_jid=clear_load['jid'] if clear_load.get('jid') else None)
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
        self.event.fire_event(new_job_load, 'new_job')  # old dup event
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
        elif 'master_id' in extra:
            load['master_id'] = extra['master_id']

        if 'id' in extra:
            load['id'] = extra['id']
        if 'tgt_type' in clear_load:
            load['tgt_type'] = clear_load['tgt_type']
        if 'to' in clear_load:
            load['to'] = clear_load['to']

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

        payload['load'] = self.crypticle.dumps(load)
        if self.opts['sign_pub_messages']:
            master_pem_path = os.path.join(self.opts['pki_dir'], 'master.pem')
            log.debug("Signing data packet")
            payload['sig'] = salt.crypt.sign_message(master_pem_path, payload['load'])
        # Send 0MQ to the publisher
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUSH)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
            )
        pub_sock.connect(pull_uri)
        int_payload = {'payload': self.serial.dumps(payload)}

        # add some targeting stuff for lists only (for now)
        if load['tgt_type'] == 'list':
            int_payload['topic_lst'] = load['tgt']

        pub_sock.send(self.serial.dumps(int_payload))
        return {
            'enc': 'clear',
            'load': {
                'jid': clear_load['jid'],
                'minions': minions
            }
        }
