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
import pwd
import getpass
import resource
import subprocess
import multiprocessing

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
import salt.utils
import salt.fileserver
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.verify
import salt.utils.minions
import salt.utils.gzip_util
from salt.utils.debug import enable_sigusr1_handler


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
                log.error(('Process did not die with terminate(): {0}'
                    .format(proc.pid)))
                os.kill(signal.SIGKILL, proc.pid)
    except (AssertionError, AttributeError):
        # Catch AssertionError when the proc is evaluated inside the child
        # Catch AttributeError when the process dies between proc.is_alive()
        # and proc.terminate() and turns into a NoneType
        pass


class MasterExit(SystemExit):
    '''
    Named exit exception for the master process exiting
    '''
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
            if not user in users:
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
        The clean old jobs function is the geenral passive maintinance process
        controller for the Salt master. This is where any data that needs to
        be cleanly maintained from the master is maintained.
        '''
        jid_root = os.path.join(self.opts['cachedir'], 'jobs')
        search = salt.search.Search(self.opts)
        last = time.time()
        fileserver = salt.fileserver.Fileserver(self.opts)
        while True:
            if self.opts['keep_jobs'] != 0:
                cur = '{0:%Y%m%d%H}'.format(datetime.datetime.now())

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
                        elif int(cur) - int(jid[:10]) > self.opts['keep_jobs']:
                            shutil.rmtree(f_path)
            if self.opts.get('search'):
                now = time.time()
                if now - last > self.opts['search_index_interval']:
                    search.index()
            fileserver.update()
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                break

    def __set_max_open_files(self):
        # Let's check to see how our max open files(ulimit -n) setting is
        mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
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
            log.warning(
                'The value for the \'max_open_files\' setting, {0}, is higher '
                'than what the user running salt is allowed to raise to, {1}. '
                'Defaulting to {1}.'.format(mof_c, mof_h)
            )
            mof_c = mof_h

        if mof_s < mof_c:
            # There's room to raise the value. Raise it!
            log.warning('Raising max open files value to {0}'.format(mof_c))
            resource.setrlimit(resource.RLIMIT_NOFILE, (mof_c, mof_h))
            mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
            log.warning(
                'New values for max open files soft/hard values: '
                '{0}/{1}'.format(mof_s, mof_h)
            )

    def start(self):
        '''
        Turn on the master server components
        '''
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
            log.warn(('Caught signal {0}, stopping the Salt Master'
                .format(signum)))
            clean_proc(clear_old_jobs_proc)
            clean_proc(reqserv.publisher)
            clean_proc(reqserv.eventpublisher)
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
                os.path.join(self.opts['sock_dir'],
                    'publish_pull.ipc'),
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
                pub_sock.setsockopt(zmq.LINGER, 2500)
                pub_sock.close()
            if pull_sock.closed is False:
                pull_sock.setsockopt(zmq.LINGER, 2500)
                pull_sock.close()
        finally:
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
            self.clients.setsockopt(zmq.LINGER, 2500)
            self.clients.close()
        if self.workers.closed is False:
            self.workers.setsockopt(zmq.LINGER, 2500)
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
                    payload = self.serial.loads(package)
                    ret = self.serial.dumps(self._handle_payload(payload))
                    socket.send(ret)
                # Properly handle EINTR from SIGUSR1
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EINTR:
                        continue
                    raise exc
        except KeyboardInterrupt:
            if socket.closed is False:
                socket.setsockopt(zmq.LINGER, 2500)
                socket.close()
        finally:
            if context.closed is False:
                context.term()

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
        return getattr(self.clear_funcs, load['cmd'])(load)

    def _handle_pub(self, load):
        '''
        Handle a command sent via a public key pair
        '''
        log.info('Pubkey payload received with command {cmd}'.format(**load))

    def _handle_aes(self, load):
        '''
        Handle a command sent via an aes key
        '''
        try:
            data = self.crypticle.loads(load)
        except Exception:
            return ''
        if 'cmd' not in data:
            log.error('Received malformed command {0}'.format(data))
            return {}
        log.info('AES payload received with command {0}'.format(data['cmd']))
        return self.aes_funcs.run_func(data['cmd'], data)

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
        except RSA.RSAError, err:
            log.error('Unable to decrypt token: {0}'.format(err))

        log.error('Salt minion claiming to be {0} has attempted to'
                  'communicate with the master and could not be verified'
                  .format(id_))
        return False

    def _ext_nodes(self, load):
        '''
        Return the results from an external node classifier if one is
        specified
        '''
        if not 'id' in load:
            log.error('Received call for external nodes without an id')
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
            try:
                ret.update(self.tops[fun](opts=opts, grains=grains))
            except Exception as exc:
                log.error(
                        ('Top function {0} failed with error {1} for minion '
                         '{2}').format(fun, exc, load['id'])
                        )
                # If anything happens in the top generation, log it and move on
                pass
        return ret

    def _master_opts(self, load):
        '''
        Return the master options to the minion
        '''
        mopts = dict(self.opts)
        file_roots = dict(mopts['file_roots'])
        envs = self._file_envs()
        for env in file_roots:
            if not env in envs:
                file_roots[env] = []
        mopts['file_roots'] = file_roots
        return mopts

    def _pillar(self, load):
        '''
        Return the pillar data for the minion
        '''
        if 'id' not in load or 'grains' not in load or 'env' not in load:
            return False
        pillar = salt.pillar.Pillar(
                self.opts,
                load['grains'],
                load['id'],
                load['env'])
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

    def _master_state(self, load):
        '''
        Call the master to compile a master side highstate
        '''
        if 'opts' not in load or 'grains' not in load:
            return False
        return salt.state.master_compile(
                self.opts,
                load['opts'],
                load['grains'],
                load['opts']['id'],
                load['opts']['environment'])

    def _minion_event(self, load):
        '''
        Receive an event from the minion and fire it on the master event
        interface
        '''
        if 'id' not in load or 'tag' not in load or 'data' not in load:
            return False
        tag = load['tag']
        return self.event.fire_event(load, tag)

    def _return(self, load):
        '''
        Handle the return data sent from the minions
        '''
        # If the return data is invalid, just ignore it
        if 'return' not in load or 'jid' not in load or 'id' not in load:
            return False
        if load['jid'] == 'req':
        # The minion is returning a standalone job, request a jobid
            load['jid'] = salt.utils.prep_jid(
                    self.opts['cachedir'],
                    self.opts['hash_type'])
        log.info('Got return from {id} for job {jid}'.format(**load))
        self.event.fire_event(load, load['jid'])
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
        hn_dir = os.path.join(jid_dir, load['id'])
        if not os.path.isdir(hn_dir):
            os.makedirs(hn_dir)
        # Otherwise the minion has already returned this jid and it should
        # be dropped
        else:
            log.error(
                    ('An extra return was detected from minion {0}, please'
                    ' verify the minion, this could be a replay'
                    ' attack').format(load['id'])
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
        if 'return' not in load or 'jid' not in load or 'id' not in load:
            return None
        # set the write flag
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
        wtag = os.path.join(jid_dir, 'wtag_{0}'.format(load['id']))
        try:
            with salt.utils.fopen(wtag, 'w+') as fp_:
                fp_.write('')
        except (IOError, OSError):
            log.error(
                    ('Failed to commit the write tag for the syndic return,'
                    ' are permissions correct in the cache dir:'
                    ' {0}?').format(self.opts['cachedir'])
                    )
            return False

        # Format individual return loads
        self.event.fire_event({'syndic': load['return'].keys()}, load['jid'])
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
        if 'fun' not in clear_load\
                or 'arg' not in clear_load\
                or 'id' not in clear_load\
                or 'tok' not in clear_load:
            return {}
        if not self.__verify_minion(clear_load['id'], clear_load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            msg = 'Minion id {0} is not who it says it is!'.format(
                    clear_load['id'])
            log.warn(msg)
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
                'doc': False,
                'conf_file': self.opts['conf_file']}
        opts.update(self.opts)
        runner = salt.runner.Runner(opts)
        return runner.run()

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
        # Verify that the load is valid
        if 'peer' not in self.opts:
            return {}
        if not isinstance(self.opts['peer'], dict):
            return {}
        if 'fun' not in clear_load\
                or 'arg' not in clear_load\
                or 'tgt' not in clear_load\
                or 'ret' not in clear_load\
                or 'tok' not in clear_load\
                or 'id' not in clear_load:
            return {}
        # If the command will make a recursive publish don't run
        if re.match('publish.*', clear_load['fun']):
            return {}
        # Check the permissions for this minion
        if not self.__verify_minion(clear_load['id'], clear_load['tok']):
            # The minion is not who it says it is!
            # We don't want to listen to it!
            msg = 'Minion id {0} is not who it says it is!'.format(
                    clear_load['id'])
            log.warn(msg)
            return {}
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
            return {}
        # Set up the publication payload
        jid = salt.utils.prep_jid(
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        load = {
                'fun': clear_load['fun'],
                'arg': clear_load['arg'],
                'tgt_type': clear_load.get('tgt_type', 'glob'),
                'tgt': clear_load['tgt'],
                'jid': jid,
                'ret': clear_load['ret'],
                'id': clear_load['id'],
               }
        self.serial.dump(
                load, salt.utils.fopen(
                    os.path.join(
                        salt.utils.jid_dir(
                            jid,
                            self.opts['cachedir'],
                            self.opts['hash_type']
                            ),
                        '.load.p'
                        ),
                    'w+')
                )
        # Save the load to the ext_job_cace if it is turned on
        if self.opts['ext_job_cache']:
            try:
                fstr = '{0}.save_load'.format(self.opts['ext_job_cache'])
                self.mminion.returners[fstr](clear_load['jid'], clear_load)
            except KeyError:
                msg = ('The specified returner used for the external job '
                       'cache "{0}" does not have a save_load function!'
                       ).format(self.opts['ext_job_cache'])
                log.critical(msg)
        payload = {'enc': 'aes'}
        expr_form = 'glob'
        timeout = 5
        if 'tmo' in clear_load:
            try:
                timeout = int(clear_load['tmo'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(
                        clear_load['tmo'])
                log.warn(msg)
                return {}
        if 'tgt_type' in clear_load:
            load['tgt_type'] = clear_load['tgt_type']
            expr_form = load['tgt_type']
        if 'timeout' in clear_load:
            timeout = clear_load['timeout']
        # Encrypt!
        payload['load'] = self.crypticle.dumps(load)
        # Connect to the publisher
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUSH)
        pull_uri = 'ipc://{0}'.format(
            os.path.join(self.opts['sock_dir'], 'publish_pull.ipc')
            )
        pub_sock.connect(pull_uri)
        log.info(('Publishing minion job: #{jid}, func: "{fun}", args:'
                  ' "{arg}", target: "{tgt}"').format(**load))
        pub_sock.send(self.serial.dumps(payload))
        # Run the client get_returns method based on the form data sent
        if 'form' in clear_load:
            ret_form = clear_load['form']
        else:
            ret_form = 'clean'
        if ret_form == 'clean':
            try:
                return self.local.get_returns(
                    jid,
                    self.ckminions.check_minions(
                        clear_load['tgt'],
                        expr_form
                    ),
                    timeout
                )
            finally:
                if pub_sock.closed is False:
                    pub_sock.setsockopt(zmq.LINGER, 2500)
                    pub_sock.close()
                if context.closed is False:
                    context.term()
        elif ret_form == 'full':
            ret = self.local.get_full_returns(
                    jid,
                    self.ckminions.check_minions(
                        clear_load['tgt'],
                        expr_form
                        ),
                    timeout
                    )
            ret['__jid__'] = jid
            try:
                return ret
            finally:
                if pub_sock.closed is False:
                    pub_sock.setsockopt(zmq.LINGER, 2500)
                    pub_sock.close()
                if context.closed is False:
                    context.term()

    def run_func(self, func, load):
        '''
        Wrapper for running functions executed with AES encryption
        '''
        # Don't honor private functions
        if func.startswith('__'):
            return self.crypticle.dumps({})
        # Run the func
        if hasattr(self, func):
            ret = getattr(self, func)(load)
        else:
            log.error(('Received function {0} which is unavailable on the '
                       'master, returning False').format(func))
            return self.crypticle.dumps(False)
        # Don't encrypt the return value for the _return func
        # (we don't care about the return value, so why encrypt it?)
        if func == '_return':
            return ret
        if func == '_pillar' and 'id' in load:
            if not load.get('ver') == '2' and self.opts['pillar_version'] == 1:
                # Authorized to return old pillar proto
                return self.crypticle.dumps(ret)
            # encrypt with a specific aes key
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
        check if the specified filename has correct permissions
        '''
        if 'os' in os.environ:
            if os.environ['os'].startswith('Windows'):
                return True

        import pwd  # after confirming not running Windows
        import grp
        try:
            user = self.opts['user']
            pwnam = pwd.getpwnam(user)
            uid = pwnam[2]
            gid = pwnam[3]
            groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
        except KeyError:
            err = ('Failed to determine groups for user '
            '{0}. The user is not available.\n').format(user)
            log.error(err)
            return False

        fmode = os.stat(filename)

        if os.getuid() == 0:
            if fmode.st_uid == uid or not fmode.st_gid == gid:
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

        autosign_file = self.opts.get("autosign_file", None)

        if not autosign_file or not os.path.exists(autosign_file):
            return False

        if not self._check_permissions(autosign_file):
            message = "Wrong permissions for {0}, ignoring content"
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
                    if re.match(line, keyid):
                        return True
                except re.error:
                    message = ('{0} is not a valid regular expression, '
                               'ignoring line in {1}')
                    log.warn(message.format(line, autosign_file))
                    continue

        return False

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the aes key
        which was generated at start up.

        This method fires an event over the master event manager. The event is
        tagged "auth" and returns a dict with information about the auth
        event
        '''
        # 0. Check for max open files
        # 1. Verify that the key we are receiving matches the stored key
        # 2. Store the key if it is not there
        # 3. make an rsa key with the pub key
        # 4. encrypt the aes key as an encrypted salt.payload
        # 5. package the return and return it

        salt.utils.verify.check_max_open_files(self.opts)

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
            if not salt.utils.fopen(pubfn, 'r').read() == load['pub']:
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
            if not salt.utils.fopen(pubfn_pend, 'r').read() == load['pub']:
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
                    'pending and needs to be accepted with salt-key'
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
            if not salt.utils.fopen(pubfn_pend, 'r').read() == load['pub']:
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
        except RSA.RSAError, err:
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
                    mtoken = self.master_key.key.private_decrypt(load['token'], 4)
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
        if not 'eauth' in clear_load:
            return ''
        if not clear_load['eauth'] in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            return ''
        try:
            name = self.loadauth.load_name(clear_load)
            if not name in self.opts['external_auth'][clear_load['eauth']]:
                return ''
            if not self.loadauth.time_auth(clear_load):
                return ''
            good = self.ckminions.wheel_check(
                    self.opts['external_auth'][clear_load['eauth']][name],
                    clear_load['fun'])
            if not good:
                return ''
            return self.wheel_.call_func(
                    clear_load.pop('fun'),
                    **clear_load)
        except Exception as exc:
            log.error(
                    ('Exception occurred in the wheel system: {0}'
                        ).format(exc)
                    )
            return ''

    def mk_token(self, clear_load):
        '''
        Create aand return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        '''
        if not 'eauth' in clear_load:
            return ''
        if not clear_load['eauth'] in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            return ''
        try:
            name = self.loadauth.load_name(clear_load)
            if not name in self.opts['external_auth'][clear_load['eauth']]:
                return ''
            if not self.loadauth.time_auth(clear_load):
                return ''
            return self.loadauth.mk_token(clear_load)
        except Exception as exc:
            log.error(
                    ('Exception occured while authenticating: {0}'
                        ).format(exc)
                    )
            return ''

    def publish(self, clear_load):
        '''
        This method sends out publications to the minions, it can only be used
        by the LocalClient.
        '''
        extra = clear_load.get('kwargs', {})
        # Check for external auth calls
        if extra.get('token', False):
            # A token was passwd, check it
            try:
                token = self.loadauth.get_tok(extra['token'])
            except Exception as exc:
                log.error(
                        ('Exception occured when generating auth token: {0}'
                            ).format(exc)
                        )
                return ''
            if not token:
                return ''
            if not token['eauth'] in self.opts['external_auth']:
                return ''
            if not token['name'] in self.opts['external_auth'][token['eauth']]:
                return ''
            good = self.ckminions.auth_check(
                    self.opts['external_auth'][token['eauth']][token['name']],
                    clear_load['fun'],
                    clear_load['tgt'],
                    clear_load.get('tgt_type', 'glob'))
            if not good:
                # Accept find_job so the cli will function cleanly
                if not clear_load['fun'] == 'saltutil.find_job':
                    return ''
        elif 'eauth' in extra:
            if not extra['eauth'] in self.opts['external_auth']:
                # The eauth system is not enabled, fail
                return ''
            try:
                name = self.loadauth.load_name(extra)
                if not name in self.opts['external_auth'][extra['eauth']]:
                    return ''
                if not self.loadauth.time_auth(extra):
                    return ''
            except Exception as exc:
                log.error(
                        ('Exception occured while authenticating: {0}'
                            ).format(exc)
                        )
                return ''
            good = self.ckminions.auth_check(
                    self.opts['external_auth'][extra['eauth']][name],
                    clear_load['fun'],
                    clear_load['tgt'],
                    clear_load.get('tgt_type', 'glob'))
            if not good:
                # Accept find_job so the cli will function cleanly
                if not clear_load['fun'] == 'saltutil.find_job':
                    return ''
        # Verify that the caller has root on master
        elif 'user' in clear_load:
            if clear_load['user'].startswith('sudo_'):
                if not clear_load.pop('key') == self.key[self.opts.get('user', 'root')]:
                    return ''
            elif clear_load['user'] == self.opts.get('user', 'root'):
                if not clear_load.pop('key') == self.key[self.opts.get('user', 'root')]:
                    return ''
            elif clear_load['user'] == 'root':
                if not clear_load.pop('key') == self.key.get(self.opts.get('user', 'root')):
                    return ''
            elif clear_load['user'] == getpass.getuser():
                if not clear_load.pop('key') == self.key.get(clear_load['user']):
                    return ''
            else:
                if clear_load['user'] in self.key:
                    # User is authorised, check key and check perms
                    if not clear_load.pop('key') == self.key[clear_load['user']]:
                        return ''
                    if not clear_load['user'] in self.opts['client_acl']:
                        return ''
                    good = self.ckminions.auth_check(
                            self.opts['client_acl'][clear_load['user']],
                            clear_load['fun'],
                            clear_load['tgt'],
                            clear_load.get('tgt_type', 'glob'))
                    if not good:
                        # Accept find_job so the cli will function cleanly
                        if not clear_load['fun'] == 'saltutil.find_job':
                            return ''
                else:
                    return ''
        else:
            if not clear_load.pop('key') == self.key[getpass.getuser()]:
                return ''
        if not clear_load['jid']:
            clear_load['jid'] = salt.utils.prep_jid(
                    self.opts['cachedir'],
                    self.opts['hash_type']
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
                msg = ('The specified returner used for the external job '
                       'cache "{0}" does not have a save_load function!'
                       ).format(self.opts['ext_job_cache'])
                log.critical(msg)
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

        if 'tgt_type' in clear_load:
            load['tgt_type'] = clear_load['tgt_type']
        if 'to' in clear_load:
            load['to'] = clear_load['to']

        if 'user' in clear_load:
            log.info(('User {user} Published command {fun} with jid'
                      ' {jid}').format(**clear_load))
            load['user'] = clear_load['user']
        else:
            log.info(('Published command {fun} with jid'
                      ' {jid}').format(**clear_load))
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
        minions = self.ckminions.check_minions(
                load['tgt'],
                load.get('tgt_type', 'glob')
                )
        try:
            return {
                'enc': 'clear',
                'load': {
                    'jid': clear_load['jid'],
                    'minions': minions
                }
            }
        finally:
            if pub_sock.closed is False:
                pub_sock.setsockopt(zmq.LINGER, 2500)
                pub_sock.close()
            if context.closed is False:
                context.term()
