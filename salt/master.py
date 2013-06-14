'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python libs
import os
import re
import time
import errno
import fnmatch
import signal
import shutil
import stat
import logging
import hashlib
import datetime
try:
    import pwd
except ImportError:  # This is in case windows minion is importing
    pass
import getpass
import resource
import subprocess
import multiprocessing
import sys

# Import third party libs
import zmq
import yaml
from M2Crypto import RSA

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
import salt.fileserver
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.verify
import salt.utils.minions
import salt.utils.gzip_util
from salt.utils.debug import enable_sigusr1_handler
from salt.exceptions import SaltMasterError, MasterExit

log = logging.getLogger(__name__)


def clean_proc(proc, wait_for_kill=10):
    '''
    Generic method for cleaning up multiprocessing procs
    '''
    # NoneType and other fun stuff need not apply
    if not proc:
        return
    try:
        waited = 0
        while proc.is_alive():
            proc.terminate()
            waited += 1
            time.sleep(0.1)
            if proc.is_alive() and (waited >= wait_for_kill):
                log.error(
                    'Process did not die with terminate(): {0}'.format(
                        proc.pid
                    )
                )
                os.kill(signal.SIGKILL, proc.pid)
    except (AssertionError, AttributeError):
        # Catch AssertionError when the proc is evaluated inside the child
        # Catch AttributeError when the process dies between proc.is_alive()
        # and proc.terminate() and turns into a NoneType
        pass


class SMaster(object):
    '''
    Create a simple salt-master, this will generate the top level master
    '''
    def __init__(self, opts):
        '''
        Create a salt master server instance
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
        users = []
        keys = {}
        acl_users = set(self.opts['client_acl'].keys())
        if self.opts.get('user'):
            acl_users.add(self.opts['user'])
        acl_users.add(getpass.getuser())
        for user in pwd.getpwall():
            users.append(user.pw_name)
        for user in acl_users:
            log.info(
                'Preparing the {0} key for local communication'.format(
                    user
                )
            )
            cumask = os.umask(191)
            if user not in users:
                log.error('ACL user {0} is not available'.format(user))
                continue
            keyfile = os.path.join(
                self.opts['cachedir'], '.{0}_key'.format(user)
            )

            if os.path.exists(keyfile):
                log.debug('Removing stale keyfile: {0}'.format(keyfile))
                os.unlink(keyfile)

            key = salt.crypt.Crypticle.generate_key_string()
            with salt.utils.fopen(keyfile, 'w+') as fp_:
                fp_.write(key)
            os.umask(cumask)
            os.chmod(keyfile, 256)
            try:
                os.chown(keyfile, pwd.getpwnam(user).pw_uid, -1)
            except OSError:
                # The master is not being run as root and can therefore not
                # chown the key file
                pass
            keys[user] = key
        return keys


class Master(SMaster):
    '''
    The salt master server
    '''
    def __init__(self, opts):
        '''
        Create a salt master server instance
        '''
        SMaster.__init__(self, opts)

    def _clear_old_jobs(self):
        '''
        The clean old jobs function is the general passive maintenance process
        controller for the Salt master. This is where any data that needs to
        be cleanly maintained from the master is maintained.
        '''
        jid_root = os.path.join(self.opts['cachedir'], 'jobs')
        search = salt.search.Search(self.opts)
        last = int(time.time())
        rotate = int(time.time())
        fileserver = salt.fileserver.Fileserver(self.opts)
        runners = salt.loader.runner(self.opts)
        schedule = salt.utils.schedule.Schedule(self.opts, runners)
        while True:
            now = int(time.time())
            loop_interval = int(self.opts['loop_interval'])
            if self.opts['keep_jobs'] != 0 and (now - last) >= loop_interval:
                cur = '{0:%Y%m%d%H}'.format(datetime.datetime.now())

                if os.path.exists(jid_root):
                    for top in os.listdir(jid_root):
                        t_path = os.path.join(jid_root, top)
                        for final in os.listdir(t_path):
                            f_path = os.path.join(t_path, final)
                            jid_file = os.path.join(f_path, 'jid')
                            if not os.path.isfile(jid_file):
                                continue
                            with salt.utils.fopen(jid_file, 'r') as fn_:
                                jid = fn_.read()
                            if len(jid) < 18:
                                # Invalid jid, scrub the dir
                                shutil.rmtree(f_path)
                            elif int(cur) - int(jid[:10]) > \
                                    self.opts['keep_jobs']:
                                shutil.rmtree(f_path)

            if self.opts.get('publish_sesion'):
                if now - rotate >= self.opts['publish_session'] * 60:
                    salt.crypt.dropfile(self.opts['cachedir'])
                    rotate = now
            if self.opts.get('search'):
                if now - last >= self.opts['search_index_interval']:
                    search.index()
            try:
                if not fileserver.servers:
                    log.error('No fileservers loaded, The master will not be'
                              'able to serve files to minions')
                    raise SaltMasterError('No fileserver backends available')
                fileserver.update()
            except Exception as exc:
                log.error(
                    'Exception {0} occurred in file server update'.format(exc)
                )
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
        Run pre flight checks, if anything in this method fails then the master
        should not start up
        '''
        errors = []
        fileserver = salt.fileserver.Fileserver(self.opts)
        if not fileserver.servers:
            errors.append(
                'Failed to load fileserver backends, the configured backends '
                'are:\n{0}'.format(
                    ' '.join(self.opts['fileserver_backend'])
                )
            )
        if not self.opts['fileserver_backend']:
            errors.append('No fileserver backends are configured')
        if errors:
            for error in errors:
                log.error(error)
            log.error('Master failed pre flight checks, exiting\n')
            sys.exit(1)

    def start(self):
        '''
        Turn on the master server components
        '''
        self._pre_flight()
        log.info(
            'salt-master is starting as user \'{0}\''.format(getpass.getuser())
        )

        enable_sigusr1_handler()

        self.__set_max_open_files()
        clear_old_jobs_proc = multiprocessing.Process(
            target=self._clear_old_jobs)
        clear_old_jobs_proc.start()
        reqserv = ReqServer(
                self.opts,
                self.crypticle,
                self.key,
                self.master_key)
        reqserv.start_publisher()
        reqserv.start_event_publisher()
        reqserv.start_reactor()

        def sigterm_clean(signum, frame):
            '''
            Cleaner method for stopping multiprocessing processes when a
            SIGTERM is encountered.  This is required when running a salt
            master under a process minder like daemontools
            '''
            log.warn(
                'Caught signal {0}, stopping the Salt Master'.format(
                    signum
                )
            )
            clean_proc(clear_old_jobs_proc)
            clean_proc(reqserv.publisher)
            clean_proc(reqserv.eventpublisher)
            if hasattr(reqserv, 'reactor'):
                clean_proc(reqserv.reactor)
            for proc in reqserv.work_procs:
                clean_proc(proc)
            raise MasterExit

        signal.signal(signal.SIGTERM, sigterm_clean)

        try:
            reqserv.run()
        except KeyboardInterrupt:
            # Shut the master down gracefully on SIGINT
            log.warn('Stopping the Salt Master')
            raise SystemExit('\nExiting on Ctrl-c')


class Publisher(multiprocessing.Process):
    '''
    The publishing interface, a simple zeromq publisher that sends out the
    commands.
    '''
    def __init__(self, opts):
        super(Publisher, self).__init__()
        self.opts = opts

    def run(self):
        '''
        Bind to the interface specified in the configuration file
        '''
        # Set up the context
        context = zmq.Context(1)
        # Prepare minion publish socket
        pub_sock = context.socket(zmq.PUB)
        # if 2.1 >= zmq < 3.0, we only have one HWM setting
        try:
            pub_sock.setsockopt(zmq.HWM, 1)
        # in zmq >= 3.0, there are separate send and receive HWM settings
        except AttributeError:
            pub_sock.setsockopt(zmq.SNDHWM, 1)
            pub_sock.setsockopt(zmq.RCVHWM, 1)
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            pub_sock.setsockopt(zmq.IPV4ONLY, 0)
        pub_uri = 'tcp://{interface}:{publish_port}'.format(**self.opts)
        # Prepare minion pull socket
        pull_sock = context.socket(zmq.PULL)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
        )
        # Start the minion command publisher
        log.info('Starting the Salt Publisher on {0}'.format(pub_uri))
        pub_sock.bind(pub_uri)
        pull_sock.bind(pull_uri)
        # Restrict access to the socket
        os.chmod(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc'),
            448
        )

        try:
            while True:
                # Catch and handle EINTR from when this process is sent
                # SIGUSR1 gracefully so we don't choke and die horribly
                try:
                    package = pull_sock.recv()
                    pub_sock.send(package)
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
        self.opts = opts
        self.master_key = mkey
        self.context = zmq.Context(self.opts['worker_threads'])
        # Prepare the zeromq sockets
        self.uri = 'tcp://{interface}:{ret_port}'.format(**self.opts)
        self.clients = self.context.socket(zmq.ROUTER)
        if self.opts['ipv6'] is True and hasattr(zmq, 'IPV4ONLY'):
            # IPv6 sockets work for both IPv6 and IPv4 addresses
            self.clients.setsockopt(zmq.IPV4ONLY, 0)
        self.workers = self.context.socket(zmq.DEALER)
        self.w_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'workers.ipc')
        )
        # Prepare the AES key
        self.key = key
        self.crypticle = crypticle

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
        log.info('Setting up the master communication server')
        self.clients.bind(self.uri)
        self.work_procs = []

        for ind in range(int(self.opts['worker_threads'])):
            self.work_procs.append(MWorker(self.opts,
                    self.master_key,
                    self.key,
                    self.crypticle))

        for ind, proc in enumerate(self.work_procs):
            log.info('Starting Salt worker process {0}'.format(ind))
            proc.start()

        self.workers.bind(self.w_uri)

        while True:
            try:
                zmq.device(zmq.QUEUE, self.clients, self.workers)
            except zmq.ZMQError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise exc

    def start_publisher(self):
        '''
        Start the salt publisher interface
        '''
        # Start the publisher
        self.publisher = Publisher(self.opts)
        self.publisher.start()

    def start_event_publisher(self):
        '''
        Start the salt publisher interface
        '''
        # Start the publisher
        self.eventpublisher = salt.utils.event.EventPublisher(self.opts)
        self.eventpublisher.start()

    def start_reactor(self):
        '''
        Start the reactor, but only if the reactor interface is configured
        '''
        if self.opts.get('reactor'):
            self.reactor = salt.utils.event.Reactor(self.opts)
            self.reactor.start()

    def run(self):
        '''
        Start up the ReqServer
        '''
        self.__bind()

    def destroy(self):
        if self.clients.closed is False:
            self.clients.setsockopt(zmq.LINGER, 1)
            self.clients.close()
        if self.workers.closed is False:
            self.workers.setsockopt(zmq.LINGER, 1)
            self.workers.close()
        if self.context.closed is False:
            self.context.term()
        # Also stop the workers
        for worker in self.work_procs:
            if worker.is_alive() is True:
                worker.terminate()

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
                # Properly handle EINTR from SIGUSR1
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc
        # Changes here create a zeromq condition, check with thatch45 before
        # making any zeromq changes
        except KeyboardInterrupt:
            socket.close()

    def _handle_payload(self, payload):
        '''
        The _handle_payload method is the key method used to figure out what
        needs to be done with communication to the server
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
        Take care of a cleartext command
        '''
        log.info('Clear payload received with command {cmd}'.format(**load))
        if load['cmd'].startswith('__'):
            return False
        return getattr(self.clear_funcs, load['cmd'])(load)

    def _handle_pub(self, load):
        '''
        Handle a command sent via a public key pair
        '''
        if load['cmd'].startswith('__'):
            return False
        log.info('Pubkey payload received with command {cmd}'.format(**load))

    def _handle_aes(self, load):
        '''
        Handle a command sent via an AES key
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
            with open(dfn) as fp_:
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
        self.opts = opts
        self.event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        self.serial = salt.payload.Serial(opts)
        self.crypticle = crypticle
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Create the tops dict for loading external top data
        self.tops = salt.loader.tops(self.opts)
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])
        # Create the master minion to access the external job cache
        self.mminion = salt.minion.MasterMinion(
                self.opts,
                states=False,
                rend=False)
        self.__setup_fileserver()

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
        self._file_envs = fs_.envs

    def __verify_minion(self, id_, token):
        '''
        Take a minion id and a string signed with the minion private key
        The string needs to verify as 'salt' with the minion public key
        '''
        if not salt.utils.verify.valid_id(id_):
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
        '''
        # Verify that the load is valid
        if 'peer' not in self.opts:
            return False
        if not isinstance(self.opts['peer'], dict):
            return False
        if any(key not in clear_load for key in ('fun', 'arg', 'tgt', 'ret', 'tok', 'id')):
            return False
        # If the command will make a recursive publish don't run
        if re.match('publish.*', clear_load['fun']):
            return False
        # Check the permissions for this minion
        if not self.__verify_minion(clear_load['id'], clear_load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                ('Minion id {0} is not who it says it is and is attempting '
                 'to issue a peer command').format(
                    clear_load['id']
                )
            )
            return False
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
        good = self.ckminions.auth_check(
                perms,
                clear_load['fun'],
                clear_load['tgt'],
                clear_load.get('tgt_type', 'glob'))
        if not good:
            return False
        return True

    def _ext_nodes(self, load):
        '''
        Return the results from an external node classifier if one is
        specified
        '''
        if 'id' not in load:
            log.error('Received call for external nodes without an id')
            return {}
        if not salt.utils.verify.valid_id(load['id']):
            return {}
        ret = {}
        # The old ext_nodes method is set to be deprecated in 0.10.4
        # and should be removed within 3-5 releases in favor of the
        # "master_tops" system
        if self.opts['external_nodes']:
            if not salt.utils.which(self.opts['external_nodes']):
                log.error(('Specified external nodes controller {0} is not'
                           ' available, please verify that it is installed'
                           '').format(self.opts['external_nodes']))
                return {}
            cmd = '{0} {1}'.format(self.opts['external_nodes'], load['id'])
            ndata = yaml.safe_load(
                    subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE
                        ).communicate()[0])
            if 'environment' in ndata:
                env = ndata['environment']
            else:
                env = 'base'

            if 'classes' in ndata:
                if isinstance(ndata['classes'], dict):
                    ret[env] = list(ndata['classes'])
                elif isinstance(ndata['classes'], list):
                    ret[env] = ndata['classes']
                else:
                    return ret
        # Evaluate all configured master_tops interfaces

        opts = {}
        grains = {}
        if 'opts' in load:
            opts = load['opts']
            if 'grains' in load['opts']:
                grains = load['opts']['grains']
        for fun in self.tops:
            if fun not in self.opts.get('master_tops', {}):
                continue
            try:
                ret.update(self.tops[fun](opts=opts, grains=grains))
            except Exception as exc:
                # If anything happens in the top generation, log it and move on
                log.error(
                    'Top function {0} failed with error {1} for minion '
                    '{2}'.format(
                        fun, exc, load['id']
                    )
                )
        return ret

    def _master_opts(self, load):
        '''
        Return the master options to the minion
        '''
        mopts = {}
        file_roots = {}
        envs = self._file_envs()
        for env in envs:
            if env not in file_roots:
                file_roots[env] = []
        mopts['file_roots'] = file_roots
        if load.get('env_only'):
            return mopts
        mopts['renderer'] = self.opts['renderer']
        mopts['failhard'] = self.opts['failhard']
        mopts['state_top'] = self.opts['state_top']
        mopts['nodegroups'] = self.opts['nodegroups']
        return mopts

    def _mine_get(self, load):
        '''
        Gathers the data from the specified minions' mine
        '''
        if any(key not in load for key in ('id', 'tgt', 'fun')):
            return {}
        ret = {}
        if not salt.utils.verify.valid_id(load['id']):
            return ret
        checker = salt.utils.minions.CkMinions(self.opts)
        minions = checker.check_minions(
                load['tgt'],
                load.get('expr_form', 'glob')
                )
        for minion in minions:
            mine = os.path.join(
                    self.opts['cachedir'],
                    'minions',
                    minion,
                    'mine.p')
            try:
                with salt.utils.fopen(mine) as fp_:
                    fdata = self.serial.load(fp_).get(load['fun'])
                    if fdata:
                        ret[minion] = fdata
            except Exception:
                continue
        return ret

    def _mine(self, load):
        '''
        Return the mine data
        '''
        if 'id' not in load or 'data' not in load:
            return False
        if not salt.utils.verify.valid_id(load['id']):
            return False
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                os.makedirs(cdir)
            datap = os.path.join(cdir, 'mine.p')
            if not load.get('clear', False):
                if os.path.isfile(datap):
                    with salt.utils.fopen(datap, 'r') as fp_:
                        new = self.serial.load(fp_)
                    if isinstance(new, dict):
                        new.update(load['data'])
                        load['data'] = new
            with salt.utils.fopen(datap, 'w+') as fp_:
                fp_.write(self.serial.dumps(load['data']))
        return True

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
        if not salt.utils.verify.valid_id(load['id']):
            return False
        cpath = os.path.join(
                self.opts['cachedir'],
                'minions',
                load['id'],
                'files',
                load['path'])
        cdir = os.path.dirname(cpath)
        if not os.path.isdir(cdir):
            try:
                os.makedirs(cdir)
            except os.error:
                pass
        if os.path.isfile(cpath):
            mode = 'w'
        else:
            mode = 'w+'
        with salt.utils.fopen(cpath, mode) as fp_:
            if load['loc']:
                fp_.seek(load['loc'])
            fp_.write(load['data'])
        return True

    def _pillar(self, load):
        '''
        Return the pillar data for the minion
        '''
        if any(key not in load for key in ('id', 'grains', 'env')):
            return False
        if not salt.utils.verify.valid_id(load['id']):
            return False
        pillar = salt.pillar.Pillar(
                self.opts,
                load['grains'],
                load['id'],
                load['env'],
                load.get('ext'))
        data = pillar.compile_pillar()
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                os.makedirs(cdir)
            datap = os.path.join(cdir, 'data.p')
            with salt.utils.fopen(datap, 'w+') as fp_:
                fp_.write(
                        self.serial.dumps(
                            {'grains': load['grains'],
                             'pillar': data})
                            )
        return data

# This broken method makes the master die, pulling out until we can
# finish the masterstate system
#    def _master_state(self, load):
#        '''
#        Call the master to compile a master side highstate
#        '''
#        if 'opts' not in load or 'grains' not in load:
#            return False
#        return salt.state.master_compile(
#                self.opts,
#                load['opts'],
#                load['grains'],
#                load['opts']['id'],
#                load['opts']['environment'])

    def _minion_event(self, load):
        '''
        Receive an event from the minion and fire it on the master event
        interface
        '''
        if 'id' not in load:
            return False
        if not salt.utils.verify.valid_id(load['id']):
            return False
        if 'events' not in load and ('tag' not in load or 'data' not in load):
            return False
        if 'events' in load:
            for event in load['events']:
                self.event.fire_event(event, event['tag'])
        else:
            tag = load['tag']
            self.event.fire_event(load, tag)
        return True

    def _return(self, load):
        '''
        Handle the return data sent from the minions
        '''
        # If the return data is invalid, just ignore it
        if any(key not in load for key in ('return', 'jid', 'id')):
            return False
        if not salt.utils.verify.valid_id(load['id']):
            return False
        if load['jid'] == 'req':
        # The minion is returning a standalone job, request a jobid
            load['jid'] = salt.utils.prep_jid(
                    self.opts['cachedir'],
                    self.opts['hash_type'],
                    load.get('nocache', False))
        log.info('Got return from {id} for job {jid}'.format(**load))
        self.event.fire_event(load, load['jid'])
        self.event.fire_ret_load(load)
        if self.opts['master_ext_job_cache']:
            fstr = '{0}.returner'.format(self.opts['master_ext_job_cache'])
            self.mminion.returners[fstr](load)
            return
        if not self.opts['job_cache'] or self.opts.get('ext_job_cache'):
            return
        jid_dir = salt.utils.jid_dir(
                load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        if not os.path.isdir(jid_dir):
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present on the master: {jid}'.format(**load)
            )
            return False
        if os.path.exists(os.path.join(jid_dir, 'nocache')):
            return
        hn_dir = os.path.join(jid_dir, load['id'])
        if not os.path.isdir(hn_dir):
            os.makedirs(hn_dir)
        # Otherwise the minion has already returned this jid and it should
        # be dropped
        else:
            log.error(
                'An extra return was detected from minion {0}, please verify '
                'the minion, this could be a replay attack'.format(
                    load['id']
                )
            )
            return False

        self.serial.dump(
            load['return'],
            # Use atomic open here to avoid the file being read before it's
            # completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(
                os.path.join(hn_dir, 'return.p'), 'w+'
            )
        )
        if 'out' in load:
            self.serial.dump(
                load['out'],
                # Use atomic open here to avoid the file being read before
                # it's completely written to. Refs #1935
                salt.utils.atomicfile.atomic_open(
                    os.path.join(hn_dir, 'out.p'), 'w+'
                )
            )

    def _syndic_return(self, load):
        '''
        Receive a syndic minion return and format it to look like returns from
        individual minions.
        '''
        # Verify the load
        if any(key not in load for key in ('return', 'jid', 'id')):
            return None
        if not salt.utils.verify.valid_id(load['id']):
            return False
        # set the write flag
        jid_dir = salt.utils.jid_dir(
                load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        if not os.path.isdir(jid_dir):
            os.makedirs(jid_dir)
            if 'load' in load:
                with open(os.path.join(jid_dir, '.load.p'), 'w+') as fp_:
                    self.serial.dump(load['load'], fp_)
        wtag = os.path.join(jid_dir, 'wtag_{0}'.format(load['id']))
        try:
            with salt.utils.fopen(wtag, 'w+') as fp_:
                fp_.write('')
        except (IOError, OSError):
            log.error(
                'Failed to commit the write tag for the syndic return, are '
                'permissions correct in the cache dir: {0}?'.format(
                    self.opts['cachedir']
                )
            )
            return False

        # Format individual return loads
        for key, item in load['return'].items():
            ret = {'jid': load['jid'],
                   'id': key,
                   'return': item}
            if 'out' in load:
                ret['out'] = load['out']
            self._return(ret)
        if os.path.isfile(wtag):
            os.remove(wtag)

    def minion_runner(self, clear_load):
        '''
        Execute a runner from a minion, return the runner's function data
        '''
        if 'peer_run' not in self.opts:
            return {}
        if not isinstance(self.opts['peer_run'], dict):
            return {}
        if any(key not in clear_load for key in ('fun', 'arg', 'id', 'tok')):
            return {}
        if not self.__verify_minion(clear_load['id'], clear_load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                'Minion id {0} is not who it says it is!'.format(
                    clear_load['id']
                )
            )
            return {}
        perms = set()
        for match in self.opts['peer_run']:
            if re.match(match, clear_load['id']):
                # This is the list of funcs/modules!
                if isinstance(self.opts['peer_run'][match], list):
                    perms.update(self.opts['peer_run'][match])
        good = False
        for perm in perms:
            if re.match(perm, clear_load['fun']):
                good = True
        if not good:
            return {}
        # Prepare the runner object
        opts = {'fun': clear_load['fun'],
                'arg': clear_load['arg'],
                'id': clear_load['id'],
                'doc': False,
                'conf_file': self.opts['conf_file']}
        opts.update(self.opts)
        runner = salt.runner.Runner(opts)
        return runner.run()

    def pub_ret(self, load):
        '''
        Request the return data from a specific jid, only allowed
        if the requesting minion also initialted the execution.
        '''
        if any(key not in load for key in ('jid', 'id', 'tok')):
            return {}
        if not self.__verify_minion(load['id'], load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                'Minion id {0} is not who it says it is!'.format(
                    load['id']
                )
            )
            return {}
        # Check that this minion can access this data
        auth_cache = os.path.join(
                self.opts['cachedir'],
                'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, load['jid'])
        with open(jid_fn, 'r') as fp_:
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
        peer:
            .*:
                - .*
        This configuration will enable all minions to execute all commands.
        peer:
            foo.example.com:
                - test.*
        This configuration will only allow the minion foo.example.com to
        execute commands from the test module
        '''
        if not self.__verify_minion_publish(clear_load):
            return {}
        # Set up the publication payload
        load = {
                'fun': clear_load['fun'],
                'arg': clear_load['arg'],
                'expr_form': clear_load.get('tgt_type', 'glob'),
                'tgt': clear_load['tgt'],
                'ret': clear_load['ret'],
                'id': clear_load['id'],
               }
        if 'tgt_type' in clear_load:
            if clear_load['tgt_type'].startswith('node'):
                if clear_load['tgt'] in self.opts['nodegroups']:
                    load['tgt'] = self.opts['nodegroups'][clear_load['tgt']]
                    load['expr_form_type'] = 'compound'
                    load['expr_form'] = clear_load['tgt_type']
                else:
                    return {}
            else:
                load['expr_form'] = clear_load['tgt_type']
        ret = {}
        ret['jid'] = self.local.cmd_async(**load)
        ret['minions'] = self.ckminions.check_minions(
                clear_load['tgt'],
                load['expr_form'])
        auth_cache = os.path.join(
                self.opts['cachedir'],
                'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, ret['jid'])
        with open(jid_fn, 'w+') as fp_:
            fp_.write(clear_load['id'])
        return ret

    def minion_publish(self, clear_load):
        '''
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.
        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions
        The config will look like this:
        peer:
            .*:
                - .*
        This configuration will enable all minions to execute all commands.
        peer:
            foo.example.com:
                - test.*
        This configuration will only allow the minion foo.example.com to
        execute commands from the test module
        '''
        if not self.__verify_minion_publish(clear_load):
            return {}
        # Set up the publication payload
        load = {
                'fun': clear_load['fun'],
                'arg': clear_load['arg'],
                'expr_form': clear_load.get('tgt_type', 'glob'),
                'tgt': clear_load['tgt'],
                'ret': clear_load['ret'],
                'id': clear_load['id'],
               }
        if 'tmo' in clear_load:
            try:
                load['timeout'] = int(clear_load['tmo'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(
                        clear_load['tmo'])
                log.warn(msg)
                return {}
        if 'timeout' in clear_load:
            try:
                load['timeout'] = int(clear_load['timeout'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(
                        clear_load['tmo'])
                log.warn(msg)
                return {}
        if 'tgt_type' in clear_load:
            if clear_load['tgt_type'].startswith('node'):
                if clear_load['tgt'] in self.opts['nodegroups']:
                    load['tgt'] = self.opts['nodegroups'][clear_load['tgt']]
                    load['expr_form_type'] = 'compound'
                else:
                    return {}
            else:
                load['expr_form'] = clear_load['tgt_type']
        load['raw'] = True
        ret = {}
        for minion in self.local.cmd_iter(**load):
            if clear_load.get('form', '') == 'full':
                data = minion
                if 'jid' in minion:
                    ret['__jid__'] = minion['jid']
                data['ret'] = data.pop('return')
                ret[minion['id']] = data
            else:
                ret[minion['id']] = minion['return']
                if 'jid' in minion:
                    ret['__jid__'] = minion['jid']
        for key, val in self.local.get_cache_returns(ret['__jid__']).items():
            if not key in ret:
                ret[key] = val
        if clear_load.get('form', '') != 'full':
            ret.pop('__jid__')
        return ret

    def revoke_auth(self, load):
        '''
        Allow a minion to request revocation of its own key
        '''
        if 'id' not in load or 'tok' not in load:
            return False
        if not self.__verify_minion(load['id'], load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warn(
                ('Minion id {0} is not who it says it is and is attempting '
                 'to revoke the key for {0}').format(
                    load['id']
                )
            )
            return False
        keyapi = salt.key.Key(self.opts)
        keyapi.delete_key(load['id'])
        return True

    def run_func(self, func, load):
        '''
        Wrapper for running functions executed with AES encryption
        '''
        # Don't honor private functions
        if func.startswith('__'):
            return self.crypticle.dumps({})
        # Run the func
        if hasattr(self, func):
            try:
                ret = getattr(self, func)(load)
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
            pret['pillar'] = pcrypt.dumps(ret)
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
        self.local = salt.client.LocalClient(self.opts['conf_file'])
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

    def _send_cluster(self):
        '''
        Send the cluster data out
        '''
        log.debug('Sending out cluster data')
        ret = self.local.cmd(self.opts['cluster_masters'],
                'cluster.distrib',
                self._cluster_load(),
                0,
                'list'
                )
        log.debug('Cluster distributed: {0}'.format(ret))

    def _cluster_load(self):
        '''
        Generates the data sent to the cluster nodes.
        '''
        minions = {}
        master_pem = ''
        with salt.utils.fopen(self.opts['conf_file'], 'r') as fp_:
            master_conf = fp_.read()
        minion_dir = os.path.join(self.opts['pki_dir'], 'minions')
        for host in os.listdir(minion_dir):
            pub = os.path.join(minion_dir, host)
            minions[host] = salt.utils.fopen(pub, 'r').read()
        if self.opts['cluster_mode'] == 'full':
            master_pem_path = os.path.join(self.opts['pki_dir'], 'master.pem')
            with salt.utils.fopen(master_pem_path) as fp_:
                master_pem = fp_.read()
        return [minions,
                master_conf,
                master_pem,
                self.opts['conf_file']]

    def _check_permissions(self, filename):
        '''
        Check if the specified filename has correct permissions
        '''
        if salt.utils.is_windows():
            return True

        # After we've ascertained we're not on windows
        import grp
        try:
            user = self.opts['user']
            pwnam = pwd.getpwnam(user)
            uid = pwnam[2]
            gid = pwnam[3]
            groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
        except KeyError:
            log.error(
                'Failed to determine groups for user {0}. The user is not '
                'available.\n'.format(
                    user
                )
            )
            return False

        fmode = os.stat(filename)

        if os.getuid() == 0:
            if fmode.st_uid == uid or fmode.st_gid != gid:
                return True
            elif self.opts.get('permissive_pki_access', False) \
                    and fmode.st_gid in groups:
                return True
        else:
            if stat.S_IWOTH & fmode.st_mode:
                # don't allow others to write to the file
                return False

            # check group flags
            if self.opts.get('permissive_pki_access', False) \
              and stat.S_IWGRP & fmode.st_mode:
                return True
            elif stat.S_IWGRP & fmode.st_mode:
                return False

            # check if writable by group or other
            if not (stat.S_IWGRP & fmode.st_mode or
                    stat.S_IWOTH & fmode.st_mode):
                return True

        return False

    def _check_autosign(self, keyid):
        '''
        Checks if the specified keyid should automatically be signed.
        '''

        if self.opts['auto_accept']:
            return True

        autosign_file = self.opts.get('autosign_file', None)

        if not autosign_file or not os.path.exists(autosign_file):
            return False

        if not self._check_permissions(autosign_file):
            message = 'Wrong permissions for {0}, ignoring content'
            log.warn(message.format(autosign_file))
            return False

        with salt.utils.fopen(autosign_file, 'r') as fp_:
            for line in fp_:
                line = line.strip()

                if line.startswith('#'):
                    continue

                if line == keyid:
                    return True
                if fnmatch.fnmatch(keyid, line):
                    return True
                try:
                    if re.match(r'\A{0}\z'.format(line), keyid):
                        return True
                except re.error:
                    log.warn(
                        '{0} is not a valid regular expression, ignoring line '
                        'in {1}'.format(
                            line, autosign_file
                        )
                    )
                    continue

        return False

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the AES key
        which was generated at start up.

        This method fires an event over the master event manager. The event is
        tagged "auth" and returns a dict with information about the auth
        event
        '''
        # 0. Check for max open files
        # 1. Verify that the key we are receiving matches the stored key
        # 2. Store the key if it is not there
        # 3. make an RSA key with the pub key
        # 4. encrypt the AES key as an encrypted salt.payload
        # 5. package the return and return it

        salt.utils.verify.check_max_open_files(self.opts)

        if not salt.utils.verify.valid_id(load['id']):
            log.info(
                'Authentication request from invalid id {id}'.format(**load)
                )
            return {'enc': 'clear',
                    'load': {'ret': False}}
        log.info('Authentication request from {id}'.format(**load))
        pubfn = os.path.join(self.opts['pki_dir'],
                'minions',
                load['id'])
        pubfn_pend = os.path.join(self.opts['pki_dir'],
                'minions_pre',
                load['id'])
        pubfn_rejected = os.path.join(self.opts['pki_dir'],
                'minions_rejected',
                load['id'])
        if self.opts['open_mode']:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn_rejected):
            # The key has been rejected, don't place it in pending
            log.info('Public key rejected for {id}'.format(**load))
            ret = {'enc': 'clear',
                   'load': {'ret': False}}
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, 'auth')
            return ret
        elif os.path.isfile(pubfn):
            # The key has been accepted check it
            if salt.utils.fopen(pubfn, 'r').read() != load['pub']:
                log.error(
                    'Authentication attempt from {id} failed, the public '
                    'keys did not match. This may be an attempt to compromise '
                    'the Salt cluster.'.format(**load)
                )
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
                return ret
        elif not os.path.isfile(pubfn_pend)\
                and not self._check_autosign(load['id']):
            if os.path.isdir(pubfn_pend):
                # The key path is a directory, error out
                log.info(
                    'New public key id is a directory {id}'.format(**load)
                )
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
                return ret
            # This is a new key, stick it in pre
            log.info(
                'New public key placed in pending for {id}'.format(**load)
            )
            with salt.utils.fopen(pubfn_pend, 'w+') as fp_:
                fp_.write(load['pub'])
            ret = {'enc': 'clear',
                   'load': {'ret': True}}
            eload = {'result': True,
                     'act': 'pend',
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, 'auth')
            return ret
        elif os.path.isfile(pubfn_pend)\
                and not self._check_autosign(load['id']):
            # This key is in pending, if it is the same key ret True, else
            # ret False
            if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                log.error(
                    'Authentication attempt from {id} failed, the public '
                    'keys in pending did not match. This may be an attempt to '
                    'compromise the Salt cluster.'.format(**load)
                )
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
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
                self.event.fire_event(eload, 'auth')
                return {'enc': 'clear',
                        'load': {'ret': True}}
        elif os.path.isfile(pubfn_pend)\
                and self._check_autosign(load['id']):
            # This key is in pending, if it is the same key auto accept it
            if salt.utils.fopen(pubfn_pend, 'r').read() != load['pub']:
                log.error(
                    'Authentication attempt from {id} failed, the public '
                    'keys in pending did not match. This may be an attempt to '
                    'compromise the Salt cluster.'.format(**load)
                )
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
                return {'enc': 'clear',
                        'load': {'ret': False}}
            else:
                pass
        elif not os.path.isfile(pubfn_pend)\
                and self._check_autosign(load['id']):
            # This is a new key and it should be automatically be accepted
            pass
        else:
            # Something happened that I have not accounted for, FAIL!
            log.warn('Unaccounted for authentication failure')
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, 'auth')
            return {'enc': 'clear',
                    'load': {'ret': False}}

        log.info('Authentication accepted from {id}'.format(**load))
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
               'publish_port': self.opts['publish_port'],
              }
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
        self.event.fire_event(eload, 'auth')
        return ret

    def wheel(self, clear_load):
        '''
        Send a master control function back to the wheel system
        '''
        # All wheel ops pass through eauth
        if 'token' in clear_load:
            try:
                token = self.loadauth.get_tok(clear_load['token'])
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
            if token['name'] not in self.opts['external_auth'][token['eauth']]:
                log.warning('Authentication failure of type "token" occurred.')
                return ''

            try:
                fun = clear_load.pop('fun')
                return self.wheel_.call_func(fun, **clear_load)
            except Exception as exc:
                log.error('Exception occurred while '
                        'introspecting {0}: {1}'.format(fun, exc))
                return ''

        if 'eauth' not in clear_load:
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return ''
        if clear_load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return ''

        try:
            name = self.loadauth.load_name(clear_load)
            if not ((name in self.opts['external_auth'][clear_load['eauth']]) | ('*' in self.opts['external_auth'][clear_load['eauth']])):
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return ''
            if not self.loadauth.time_auth(clear_load):
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return ''
            good = self.ckminions.wheel_check(
                    self.opts['external_auth'][clear_load['eauth']][name] if name in self.opts['external_auth'][clear_load['eauth']] else self.opts['external_auth'][token['eauth']]['*'],
                    clear_load['fun'])
            if not good:
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(clear_load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return ''

            try:
                fun = clear_load.pop('fun')
                return self.wheel_.call_func(fun, **clear_load)
            except Exception as exc:
                log.error('Exception occurred while '
                        'introspecting {0}: {1}'.format(fun, exc))
                return ''

        except Exception as exc:
            log.error(
                'Exception occurred in the wheel system: {0}'.format(exc)
            )
            return ''

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
            if not ((name in self.opts['external_auth'][clear_load['eauth']]) | ('*' in self.opts['external_auth'][clear_load['eauth']])):
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
            if re.match(module_re, clear_load['fun']):
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
            if not ((token['name'] in self.opts['external_auth'][token['eauth']]) | ('*' in self.opts['external_auth'][token['eauth']])):
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            good = self.ckminions.auth_check(
                    self.opts['external_auth'][token['eauth']][token['name']] if token['name'] in self.opts['external_auth'][token['eauth']] else self.opts['external_auth'][token['eauth']]['*'],
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
        elif 'eauth' in extra:
            if extra['eauth'] not in self.opts['external_auth']:
                # The eauth system is not enabled, fail
                log.warning(
                    'Authentication failure of type "eauth" occurred.'
                )
                return ''
            try:
                name = self.loadauth.load_name(extra)
                if not ((name in self.opts['external_auth'][extra['eauth']]) | ('*' in self.opts['external_auth'][extra['eauth']])):
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''
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
            good = self.ckminions.auth_check(
                    self.opts['external_auth'][extra['eauth']][name] if name in self.opts['external_auth'][extra['eauth']] else self.opts['external_auth'][extra['eauth']]['*'],
                    clear_load['fun'],
                    clear_load['tgt'],
                    clear_load.get('tgt_type', 'glob'))
            if not good:
                # Accept find_job so the CLI will function cleanly
                if clear_load['fun'] != 'saltutil.find_job':
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''
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
            elif clear_load['user'] == getpass.getuser():
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
            if clear_load.pop('key') != self.key[getpass.getuser()]:
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
        self.event.fire_event({'minions': minions}, clear_load['jid'])
        # Retrieve the jid
        if not clear_load['jid']:
            clear_load['jid'] = salt.utils.prep_jid(
                    self.opts['cachedir'],
                    self.opts['hash_type'],
                    extra.get('nocache', False)
                    )
        jid_dir = salt.utils.jid_dir(
                clear_load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        # Verify the jid dir
        if not os.path.isdir(jid_dir):
            os.makedirs(jid_dir)
        # Save the invocation information
        self.serial.dump(
                clear_load,
                salt.utils.fopen(os.path.join(jid_dir, '.load.p'), 'w+')
                )
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
        # Send 0MQ to the publisher
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUSH)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
            )
        pub_sock.connect(pull_uri)
        pub_sock.send(self.serial.dumps(payload))
        return {
            'enc': 'clear',
            'load': {
                'jid': clear_load['jid'],
                'minions': minions
            }
        }
