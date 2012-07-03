'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python modules
import os
import re
import time
import errno
import signal
import shutil
import logging
import hashlib
import tempfile
import datetime
import subprocess
import multiprocessing

# Import zeromq
import zmq

# Import Third Party Libs
import yaml

# RSA Support
from M2Crypto import RSA

# Import salt modules
import salt.crypt
import salt.utils
import salt.client
import salt.payload
import salt.pillar
import salt.state
import salt.runner
import salt.utils.event
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
    except (AssertionError, AttributeError) as e:
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
        log.info('Preparing the root key for local communication')
        keyfile = os.path.join(self.opts['cachedir'], '.root_key')
        if os.path.isfile(keyfile):
            with open(keyfile, 'r') as fp_:
                return fp_.read()
        else:
            key = salt.crypt.Crypticle.generate_key_string()
            cumask = os.umask(191)
            with open(keyfile, 'w+') as fp_:
                fp_.write(key)
            os.umask(cumask)
            os.chmod(keyfile, 256)
            return key


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
        Clean out the old jobs
        '''
        if self.opts['keep_jobs'] == 0:
            return
        jid_root = os.path.join(self.opts['cachedir'], 'jobs')
        while True:
            cur = "{0:%Y%m%d%H}".format(datetime.datetime.now())

            for top in os.listdir(jid_root):
                t_path = os.path.join(jid_root, top)
                for final in os.listdir(t_path):
                    f_path = os.path.join(t_path, final)
                    jid_file = os.path.join(f_path, 'jid')
                    if not os.path.isfile(jid_file):
                        continue
                    with open(jid_file, 'r') as fn_:
                        jid = fn_.read()
                    if len(jid) < 18:
                        # Invalid jid, scrub the dir
                        shutil.rmtree(f_path)
                    elif int(cur) - int(jid[:10]) > self.opts['keep_jobs']:
                        shutil.rmtree(f_path)
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                break

    def start(self):
        '''
        Turn on the master server components
        '''
        enable_sigusr1_handler()

        log.warn('Starting the Salt Master')
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

        def sigterm_clean(signum, frame):
            '''
            Cleaner method for stopping multiprocessing processes when a
            SIGTERM is encountered.  This is required when running a salt
            master under a process minder like daemontools
            '''
            mypid = os.getpid()
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
        pub_uri = 'tcp://{0[interface]}:{0[publish_port]}'.format(self.opts)
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
            pub_sock.close()
            pull_sock.close()


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
        self.uri = 'tcp://%(interface)s:%(ret_port)s' % self.opts
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

    def run(self):
        '''
        Start up the ReqServer
        '''
        self.__bind()


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
            socket.close()

    def _handle_payload(self, payload):
        '''
        The _handle_payload method is the key method used to figure out what
        needs to be done with communication to the server
        '''
        key = load = None
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
        log.info('Clear payload received with command %(cmd)s', load)
        return getattr(self.clear_funcs, load['cmd'])(load)

    def _handle_pub(self, load):
        '''
        Handle a command sent via a public key pair
        '''
        log.info('Pubkey payload received with command %(cmd)s', load)

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
        self.event = salt.utils.event.SaltEvent(
                self.opts['sock_dir'],
                'master'
                )
        self.serial = salt.payload.Serial(opts)
        self.crypticle = crypticle
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])

    def __find_file(self, path, env='base'):
        '''
        Search the environment for the relative path
        '''
        fnd = {'path': '',
               'rel': ''}
        if env not in self.opts['file_roots']:
            return fnd
        for root in self.opts['file_roots'][env]:
            full = os.path.join(root, path)
            if os.path.isfile(full):
                fnd['path'] = full
                fnd['rel'] = path
                return fnd
        return fnd

    def __verify_minion(self, id_, token):
        '''
        Take a minion id and a string signed with the minion private key
        The string needs to verify as 'salt' with the minion public key
        '''
        pub_path = os.path.join(self.opts['pki_dir'], 'minions', id_)
        with open(pub_path, 'r') as fp_:
            minion_pub = fp_.read()
        fd_, tmp_pub = tempfile.mkstemp()
        os.close(fd_)
        with open(tmp_pub, 'w+') as fp_:
            fp_.write(minion_pub)

        pub = None
        try:
            pub = RSA.load_pub_key(tmp_pub)
        except RSA.RSAError, e:
            log.error('Unable to load temporary public key "{0}": {1}'
                      .format(tmp_pub, e))
        try:
            os.remove(tmp_pub)
            if pub.public_decrypt(token, 5) == 'salt':
                return True
        except RSA.RSAError, e:
            log.error('Unable to decrypt token: {0}'.format(e))

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
        if not self.opts['external_nodes']:
            return {}
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
        ret = {}
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
        return ret

    def _serve_file(self, load):
        '''
        Return a chunk from a file based on the data received
        '''
        ret = {'data': '',
               'dest': ''}
        if 'path' not in load or 'loc' not in load or 'env' not in load:
            return ret
        fnd = self.__find_file(load['path'], load['env'])
        if not fnd['path']:
            return ret
        ret['dest'] = fnd['rel']
        with open(fnd['path'], 'rb') as fp_:
            fp_.seek(load['loc'])
            ret['data'] = fp_.read(self.opts['file_buffer_size'])
        return ret

    def _file_hash(self, load):
        '''
        Return a file hash, the hash type is set in the master config file
        '''
        if 'path' not in load or 'env' not in load:
            return ''
        path = self.__find_file(load['path'], load['env'])['path']
        if not path:
            return {}
        ret = {}
        with open(path, 'rb') as fp_:
            ret['hsum'] = getattr(hashlib, self.opts['hash_type'])(
                    fp_.read()).hexdigest()
        ret['hash_type'] = self.opts['hash_type']
        return ret

    def _file_list(self, load):
        '''
        Return a list of all files on the file server in a specified
        environment
        '''
        ret = []
        if load['env'] not in self.opts['file_roots']:
            return ret
        for path in self.opts['file_roots'][load['env']]:
            for root, dirs, files in os.walk(path, followlinks=True):
                for fn in files:
                    ret.append(
                        os.path.relpath(
                            os.path.join(
                                root,
                                fn
                                ),
                            path
                            )
                        )
        return ret

    def _file_list_emptydirs(self, load):
        '''
        Return a list of all empty directories on the master
        '''
        ret = []
        if load['env'] not in self.opts['file_roots']:
            return ret
        for path in self.opts['file_roots'][load['env']]:
            for root, dirs, files in os.walk(path, followlinks=True):
                if len(dirs) == 0 and len(files) == 0:
                    ret.append(os.path.relpath(root, path))
        return ret

    def _master_opts(self, load):
        '''
        Return the master options to the minion
        '''
        return self.opts

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
        return pillar.compile_pillar()

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
        tag = '{0}_{1}'.format(load['tag'], load['id'])
        return self.event.fire_event(load['data'], tag)

    def _return(self, load):
        '''
        Handle the return data sent from the minions
        '''
        # If the return data is invalid, just ignore it
        if 'return' not in load or 'jid' not in load or 'id' not in load:
            return False
        log.info('Got return from {0[id]} for job {0[jid]}'.format(load))
        self.event.fire_event(load, load['jid'])
        if not self.opts['job_cache']:
            return
        jid_dir = salt.utils.jid_dir(
                load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        if not os.path.isdir(jid_dir):
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present on the master: %(jid)s', load
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
        self.serial.dump(load['return'],
                open(os.path.join(hn_dir, 'return.p'), 'w+'))
        if 'out' in load:
            self.serial.dump(load['out'],
                    open(os.path.join(hn_dir, 'out.p'), 'w+'))

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
                'that is not present on the master: %(jid)s', load
            )
            return False
        wtag = os.path.join(jid_dir, 'wtag_{0}'.format(load['id']))
        try:
            with open(wtag, 'w+') as fp_:
                fp_.write('')
        except (IOError, OSError):
            log.error(
                    ('Failed to commit the write tag for the syndic return,'
                    ' are permissions correct in the cache dir:'
                    ' {0}?').format(self.opts['cachedir'])
                    )
            return False

        # Format individual return loads
        for key, item in load['return'].items():
            ret = {'jid': load['jid'],
                   'id': key,
                   'return': item}
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
        perms = set()
        for match in self.opts['peer']:
            if re.match(match, clear_load['id']):
                # This is the list of funcs/modules!
                if isinstance(self.opts['peer'][match], list):
                    perms.update(self.opts['peer'][match])
        good = False
        if ',' in clear_load['fun']:
            # 'arg': [['cat', '/proc/cpuinfo'], [], ['foo']]
            clear_load['fun'] = clear_load['fun'].split(',')
            arg_ = []
            for arg in clear_load['arg']:
                arg_.append(arg.split())
            clear_load['arg'] = arg_
        for perm in perms:
            if isinstance(clear_load['fun'], list):
                good = True
                for fun in clear_load['fun']:
                    if not re.match(perm, fun):
                        good = False
            else:
                if re.match(perm, clear_load['fun']):
                    good = True
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
                load, open(
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
        payload = {'enc': 'aes'}
        expr_form = 'glob'
        timeout = 5
        if 'tmo' in clear_load:
            try:
                timeout = int(clear_load['tmo'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(clear_load['tmo'])
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
        log.info(('Publishing minion job: #{0[jid]}, func: "{0[fun]}", args:'
                  ' "{0[arg]}", target: "{0[tgt]}"').format(load))
        pub_sock.send(self.serial.dumps(payload))
        # Run the client get_returns method based on the form data sent
        if 'form' in clear_load:
            ret_form = clear_load['form']
        else:
            ret_form = 'clean'
        if ret_form == 'clean':
            return self.local.get_returns(
                    jid,
                    self.local.check_minions(
                        clear_load['tgt'],
                        expr_form
                        ),
                    timeout
                    )
        elif ret_form == 'full':
            ret = self.local.get_full_returns(
                    jid,
                    self.local.check_minions(
                        clear_load['tgt'],
                        expr_form
                        ),
                    timeout
                    )
            ret['__jid__'] = jid
            return ret

    def run_func(self, func, load):
        '''
        Wrapper for running functions executed with AES encryption
        '''
        # Don't honor private functions
        if func.startswith('__'):
            return self.crypticle.dumps({})
        # Run the func
        try:
            ret = getattr(self, func)(load)
        except AttributeError as exc:
            log.error(('Received function {0} which in unavailable on the '
                       'master, returning False').format(exc))
            return self.crypticle.dumps(False)
        # Don't encrypt the return value for the _return func
        # (we don't care about the return value, so why encrypt it?)
        if func == '_return':
            return ret
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
        self.event = salt.utils.event.SaltEvent(
                self.opts['sock_dir'],
                'master'
                )
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])

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
        log.debug('Cluster distributed: %s', ret)

    def _cluster_load(self):
        '''
        Generates the data sent to the cluster nodes.
        '''
        minions = {}
        master_pem = ''
        with open(self.opts['conf_file'], 'r') as fp_:
            master_conf = fp_.read()
        minion_dir = os.path.join(self.opts['pki_dir'], 'minions')
        for host in os.listdir(minion_dir):
            pub = os.path.join(minion_dir, host)
            minions[host] = open(pub, 'r').read()
        if self.opts['cluster_mode'] == 'full':
            with open(os.path.join(self.opts['pki_dir'], 'master.pem')) as fp_:
                master_pem = fp_.read()
        return [minions,
                master_conf,
                master_pem,
                self.opts['conf_file']]

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the aes key
        which was generated at start up.

        This method fires an event over the master event manager. The evnt is
        tagged "auth" and returns a dict with information about the auth
        event
        '''
        # 1. Verify that the key we are receiving matches the stored key
        # 2. Store the key if it is not there
        # 3. make an rsa key with the pub key
        # 4. encrypt the aes key as an encrypted salt.payload
        # 5. package the return and return it
        log.info('Authentication request from %(id)s', load)
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
        elif os.path.isfile(pubfn):
            # The key has been accepted check it
            if not open(pubfn, 'r').read() == load['pub']:
                log.error(
                    'Authentication attempt from %(id)s failed, the public '
                    'keys did not match. This may be an attempt to compromise '
                    'the Salt cluster.', load
                )
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
                return ret
        elif os.path.isfile(pubfn_rejected):
            # The key has been rejected, don't place it in pending
            log.info('Public key rejected for %(id)s', load)
            ret = {'enc': 'clear',
                   'load': {'ret': False}}
            eload = {'result': False,
                     'id': load['id'],
                     'pub': load['pub']}
            self.event.fire_event(eload, 'auth')
            return ret
        elif not os.path.isfile(pubfn_pend)\
                and not self.opts['auto_accept']:
            # This is a new key, stick it in pre
            log.info('New public key placed in pending for %(id)s', load)
            with open(pubfn_pend, 'w+') as fp_:
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
                and not self.opts['auto_accept']:
            # This key is in pending, if it is the same key ret True, else
            # ret False
            if not open(pubfn_pend, 'r').read() == load['pub']:
                log.error(
                    'Authentication attempt from %(id)s failed, the public '
                    'keys in pending did not match. This may be an attempt to '
                    'compromise the Salt cluster.', load
                )
                eload = {'result': False,
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
                return {'enc': 'clear',
                        'load': {'ret': False}}
            else:
                log.info(
                    'Authentication failed from host %(id)s, the key is in '
                    'pending and needs to be accepted with salt-key -a %(id)s',
                    load
                )
                eload = {'result': True,
                         'act': 'pend',
                         'id': load['id'],
                         'pub': load['pub']}
                self.event.fire_event(eload, 'auth')
                return {'enc': 'clear',
                        'load': {'ret': True}}
        elif not os.path.isfile(pubfn_pend)\
                and self.opts['auto_accept']:
            # This is a new key and auto_accept is turned on
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

        log.info('Authentication accepted from %(id)s', load)
        with open(pubfn, 'w+') as fp_:
            fp_.write(load['pub'])
        pub = None

        # The key payload may sometimes be corrupt when using auto-accept
        # and an empty request comes in
        try:
            pub = RSA.load_pub_key(pubfn)
        except RSA.RSAError, e:
            log.error('Corrupt public key "{0}": {1}'.format(pubfn, e))
            return {'enc': 'clear',
                    'load': {'ret': False}}

        ret = {'enc': 'pub',
               'pub_key': self.master_key.get_pub_str(),
               'token': self.master_key.token,
               'publish_port': self.opts['publish_port'],
              }
        ret['aes'] = pub.public_encrypt(self.opts['aes'], 4)
        eload = {'result': True,
                 'act': 'accept',
                 'id': load['id'],
                 'pub': load['pub']}
        self.event.fire_event(eload, 'auth')
        return ret

    def publish(self, clear_load):
        '''
        This method sends out publications to the minions, it can only be used
        by the LocalClient.
        '''
        # Verify that the caller has root on master
        if not clear_load.pop('key') == self.key:
            return ''
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
                open(os.path.join(jid_dir, '.load.p'), 'w+')
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

        if 'tgt_type' in clear_load:
            load['tgt_type'] = clear_load['tgt_type']
        if 'to' in clear_load:
            load['to'] = clear_load['to']

        if 'user' in clear_load:
            log.info(('User {0[user]} Published command {0[fun]} with jid'
                      ' {0[jid]}').format(clear_load))
            load['user'] = clear_load['user']
        else:
            log.info(('Published command {0[fun]} with jid'
                      ' {0[jid]}').format(clear_load))
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
        return {'enc': 'clear',
                'load': {'jid': clear_load['jid']}}
