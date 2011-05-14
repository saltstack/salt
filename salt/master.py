'''
This module contains all fo the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''
# Import python modules
import os
import shutil
import threading
import multiprocessing
import time
import datetime
import cPickle as pickle
# Import zeromq
import zmq
# Import salt modules
import salt.utils
import salt.crypt
import salt.payload
import salt.client
# Import cryptogrogphy modules
from M2Crypto import RSA


class Master(object):
    '''
    The salt master server
    '''
    def __init__(self, opts):
        '''
        Create a salt master server instance
        '''
        self.opts = opts

    def _clear_old_jobs(self):
        '''
        Clean out the old jobs
        '''
        if self.opts['keep_jobs'] == 0:
            return
        diff = self.opts['keep_jobs'] * 60 * 60
        keep = int(time.time()) - diff
        jid_root = os.path.join(self.opts['cachedir'], 'jobs')
        for jid in os.listdir(jid_root):
            if int(jid.split('.')[0]) < keep:
                shutil.rmtree(os.path.join(jid_root, jid))

    def start(self):
        '''
        Turn on the master server components
        '''
        self.opts['logger'].info('Starting the Salt Master')
        reqserv = ReqServer(self.opts)
        reqserv.run()
        while True:
            self._clear_old_jobs()
            time.sleep(60)


class Publisher(multiprocessing.Process):
    '''
    The publihing interface, a simple zeromq publisher that sends out the
    commands.
    '''
    def __init__(self, opts):
        multiprocessing.Process.__init__(self)
        self.opts = opts

    def run(self):
        '''
        Bind to the interface specified in the configuration file
        '''
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUB)
        pull_sock = context.socket(zmq.PULL)
        pub_uri = 'tcp://' + self.opts['interface'] + ':'\
               + self.opts['publish_port']
        pull_uri = 'tcp://127.0.0.1:' + self.opts['publish_pull_port']
        self.opts['logger'].info('Starting the Salt Publisher on ' + pub_uri)
        pub_sock.bind(pub_uri)
        pull_sock.bind(pull_uri)

        while True:
            package = pull_sock.recv()
            self.opts['logger'].info('Publishing command')
            pub_sock.send(package)


class ReqServer():
    '''
    Starts up the master request server, minions send results to this
    interface.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.context = zmq.Context(1)
        # Prepare the zeromq sockets
        self.uri = 'tcp://' + self.opts['interface'] + ':'\
                   + self.opts['ret_port']
        self.clients = self.context.socket(zmq.XREP)
        self.workers = self.context.socket(zmq.XREQ)
        self.w_uri = 'inproc://workers'
        # Start the publisher
        self.publisher = Publisher(opts)
        self.publisher.start()
        # Prepare the aes key
        self.key = self.__prep_key()
        self.crypticle = salt.crypt.Crypticle(self.opts['aes'])
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])

    def __prep_key(self):
        '''
        A key needs to be placed in the filesystem with permissions 0400 so
        clients are required to run as root.
        '''
        self.opts['logger'].info('Preparing the root key for local'\
                + ' comunication')
        keyfile = os.path.join(self.opts['cachedir'], '.root_key')
        key = salt.crypt.Crypticle.generate_key_string()
        if os.path.isfile(keyfile):
            os.chmod(keyfile, 384)
        open(keyfile, 'w+').write(key)
        os.chmod(keyfile, 256)
        return key

    def __worker(self, ind):
        '''
        Starts up a worker thread
        '''
        in_socket = self.context.socket(zmq.REP)
        in_socket.connect(self.w_uri)
        m_worker = MWorker(self.opts,
                ind,
                self.master_key,
                self.key,
                self.crypticle)
        work_port = m_worker.port
        m_worker.start()

        out_socket = self.context.socket(zmq.REQ)
        out_socket.connect('tcp://127.0.0.1:' + str(work_port))

        while True:
            package = in_socket.recv()
            out_socket.send(package)
            ret = out_socket.recv()
            in_socket.send(ret)

    def __bind(self):
        '''
        Binds the reply server
        '''
        self.opts['logger'].info('Setting up the master communication server')
        self.clients.bind(self.uri)

        self.workers.bind(self.w_uri)

        for ind in range(int(self.opts['worker_threads'])):
            threading.Thread(target=lambda: self.__worker(ind)).start()
            time.sleep(0.1)

        zmq.device(zmq.QUEUE, self.clients, self.workers)

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
    def __init__(self, opts, ind, mkey, key, crypticle):
        multiprocessing.Process.__init__(self)
        self.opts = opts
        self.master_key = mkey
        self.key = key
        self.crypticle = crypticle
        self.port = str(ind + int(self.opts['worker_start_port']))

    def __bind(self):
        '''
        Bind to the local port
        '''
        context = zmq.Context(1)
        socket = context.socket(zmq.REP)
        socket.bind('tcp://127.0.0.1:' + self.port)

        while True:
            package = socket.recv()
            payload = salt.payload.unpackage(package)
            ret = salt.payload.package(self._handle_payload(payload))
            socket.send(ret)

    def _prep_jid(self, load):
        '''
        Parses the job return directory, generates a job id and sets up the
        job id directory.
        '''
        jid_root = os.path.join(self.opts['cachedir'], 'jobs')
        jid = datetime.datetime.strftime(datetime.datetime.now(),
                '%Y%m%d%H%M%S%f')
        jid_dir = os.path.join(jid_root, jid)
        if not os.path.isdir(jid_dir):
            os.makedirs(jid_dir)
            pickle.dump(load, open(os.path.join(jid_dir, '.load.p'), 'w+'))
        else:
            return self._prep_jid(load)
        return jid

    def _handle_payload(self, payload):
        '''
        The _handle_payload method is the key method used to figure out what
        needs to be done with communication to the server
        '''
        return {'aes': self._handle_aes,
                'pub': self._handle_pub,
                'clear': self._handle_clear}[payload['enc']](payload['load'])

    def _handle_clear(self, load):
        '''
        Take care of a cleartext command
        '''
        self.opts['logger'].info('Clear payload recieved with command '\
                + load['cmd'])
        return getattr(self, load['cmd'])(load)

    def _handle_pub(self, load):
        '''
        Handle a command sent via a public key pair
        '''
        self.opts['logger'].info('Pubkey payload recieved with command '\
                + load['cmd'])

    def _handle_aes(self, load):
        '''
        Handle a command sent via an aes key
        '''
        data = self.crypticle.loads(load)
        self.opts['logger'].info('AES payload recieved with command '\
                + data['cmd'])
        return getattr(self, data['cmd'])(data)

    def _auth(self, load):
        '''
        Authenticate the client, use the sent public key to encrypt the aes key
        which was generated at start up
        '''
        # 1. Verify that the key we are recieving matches the stored key
        # 2. Store the key if it is not there
        # 3. make an rsa key with the pub key
        # 4. encrypt the aes key as an encrypted pickle
        # 5. package the return and return it
        self.opts['logger'].info('Authentication request from '\
                + load['id'])
        pubfn = os.path.join(self.opts['pki_dir'],
                'minions',
                load['id'])
        pubfn_pend = os.path.join(self.opts['pki_dir'],
                'minions_pre',
                load['id'])
        if self.opts['open_mode']:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn):
            # The key has been accepted check it
            if not open(pubfn, 'r').read() == load['pub']:
                self.opts['logger'].error('Authentication attempt from '\
                        + load['id'] + ' failed, the public keys did'\
                        + ' not match. This may be an attempt to compromise'\
                        + ' the Salt cluster.')
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                return ret
        elif not os.path.isfile(pubfn_pend)\
                and not self.opts['auto_accept']:
            # This is a new key, stick it in pre
            self.opts['logger'].info('New public key placed in pending for '\
                    + load['id'])
            open(pubfn_pend, 'w+').write(load['pub'])
            ret = {'enc': 'clear',
                   'load': {'ret': True}}
            return ret
        elif os.path.isfile(pubfn_pend)\
                and not self.opts['auto_accept']:
            # This key is in pending, if it is the same key ret True, else
            # ret False
            if not open(pubfn_pend, 'r').read() == load['pub']:
                self.opts['logger'].error('Authentication attempt from '\
                        + load['id'] + ' failed, the public keys in'\
                        + ' pending did'\
                        + ' not match. This may be an attempt to compromise'\
                        + ' the Salt cluster.')
                return {'enc': 'clear',
                        'load': {'ret': False}}
            else:
                self.opts['logger'].info('Authentication failed from host '\
                        + load['id'] + ', the key is in pending and'\
                        + ' needs to be accepted with saltkey -a '\
                        + load['id'])
                return {'enc': 'clear',
                        'load': {'ret': True}}
        elif not os.path.isfile(pubfn_pend)\
                and self.opts['auto_accept']:
            # This is a new key and auto_accept is turned on
            pass
        else:
            # Something happened that I have not accounted for, FAIL!
            return {'enc': 'clear',
                    'load': {'ret': False}}

        self.opts['logger'].info('Authentication accepted from '\
                + load['id'])
        open(pubfn, 'w+').write(load['pub'])
        key = RSA.load_pub_key(pubfn)
        ret = {'enc': 'pub',
               'pub_key': self.master_key.pub_str,
               'token': self.master_key.token,
               'publish_port': self.opts['publish_port'],
              }
        ret['aes'] = key.public_encrypt(self.opts['aes'], 4)
        if self.opts['cluster_masters']:
            self._send_cluster()
        return ret

    def _return(self, load):
        '''
        Handle the return data sent from the minions
        '''
        # If the return data is invalid, just ignore it
        if not load.has_key('return')\
                or not load.has_key('jid')\
                or not load.has_key('id'):
            return False
        self.opts['logger'].info('Got return from ' + load['id']\
                + ' for job ' + load['jid'])
        jid_dir = os.path.join(self.opts['cachedir'], 'jobs', load['jid'])
        if not os.path.isdir(jid_dir):
            self.opts['logger'].error('An inconsistency occured, a job was'\
                    + ' recieved with a job id that is not present on the'\
                    + ' master: ' + load['jid'])
            return False
        hn_dir = os.path.join(jid_dir, load['id'])
        if not os.path.isdir(hn_dir):
            os.makedirs(hn_dir)
        pickle.dump(load['return'],
                open(os.path.join(hn_dir, 'return.p'), 'w+'))

    def _send_cluster(self):
        '''
        Send the cluser data out
        '''
        self.opts['logger'].debug('Sending out cluster data')
        ret = self.local.cmd(self.opts['cluster_masters'],
                'cluster.distrib',
                self._cluster_load(),
                0,
                'list'
                )
        self.opts['logger'].debug('Cluster distributed: ' + str(ret))

    def _cluster_load(self):
        '''
        Generates the data sent to the cluster nodes.
        '''
        minions = {}
        master_pem = ''
        master_conf = open(self.opts['conf_file'], 'r').read()
        minion_dir = os.path.join(self.opts['pki_dir'], 'minions')
        for host in os.listdir(minion_dir):
            pub = os.path.join(minion_dir, host)
            minions[host] = open(pub, 'r').read()
        if self.opts['cluster_mode'] == 'full':
            master_pem = open(os.path.join(self.opts['pki_dir'],
                'master.pem')).read()
        return [minions,
                master_conf,
                master_pem,
                self.opts['conf_file']]

    def publish(self, clear_load):
        '''
        This method sends out publications to the minions
        '''
        if not clear_load.pop('key') == self.key:
            return ''
        jid = self._prep_jid(clear_load)
        payload = {'enc': 'aes'}
        load = {
                'fun': clear_load['fun'],
                'arg': clear_load['arg'],
                'tgt': clear_load['tgt'],
                'jid': jid,
                'ret': clear_load['ret'],
               }
        if clear_load.has_key('tgt_type'):
            load['tgt_type'] = clear_load['tgt_type']
        payload['load'] = self.crypticle.dumps(load)
        context = zmq.Context(1)
        pub_sock = context.socket(zmq.PUSH)
        pub_sock.connect('tcp://127.0.0.1:' + self.opts['publish_pull_port'])
        pub_sock.send(salt.payload.package(payload))
        return {'enc': 'clear',
                'load': {'jid': jid}}

    def run(self):
        '''
        Start a Master Worker
        '''
        self.__bind()
