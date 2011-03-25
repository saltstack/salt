'''
This module contains all fo the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''
# Import python modules
import os
import random
import time
import threading
import cPickle as pickle
# Import zeromq
import zmq
# Import salt modules
import salt.utils
import salt.crypt
import salt.payload
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

    def start(self):
        '''
        Turn on the master server components
        '''
        reqserv = ReqServer(self.opts)
        reqserv.start()
        while True:
            # Add something to keep the jobs dir clean
            time.sleep(1)


class Publisher(threading.Thread):
    '''
    The publihing interface, a simple zeromq publisher that sends out the
    commands.
    '''
    def __init__(self, opts):
        threading.Thread.__init__(self)
        self.opts = opts
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)

    def __bind(self):
        '''
        Bind to the interface specified in the configuration file
        '''
        binder = 'tcp://' + self.opts['interface'] + ':'\
               + self.opts['publish_port']
        print binder
        self.socket.bind(binder)

    def publish(self, package):
        '''
        Publish out a command to the minions, takes a cmd structure
        '''
        self.socket.send(package)

    def run(self):
        '''
        Start the publisher
        '''
        self.__bind()


class ReqServer(threading.Thread):
    '''
    Starts up a threaded request server, minions send results to this
    interface.
    '''
    def __init__(self, opts):
        threading.Thread.__init__(self)
        self.opts = opts
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.num_threads = self.opts['worker_threads']
        self.context = zmq.Context(1)
        # Prepare the zeromq sockets
        self.c_uri = 'tcp://' + self.opts['interface'] + ':'\
                   + self.opts['ret_port']
        self.clients = self.context.socket(zmq.XREP)
        self.workers = self.context.socket(zmq.XREQ)
        self.w_uri = 'inproc://wokers'
        # Start the publisher
        self.publisher = Publisher(opts)
        self.publisher.start()
        # Prepare the aes key
        self.key = self.__prep_key()
        self.crypticle = salt.crypt.Crypticle(self.opts['aes'])

    def __prep_key(self):
        '''
        A key needs to be placed in the filesystem with permissions 0400 so
        clients are required to run as root.
        '''
        keyfile = os.path.join(self.opts['cachedir'], '.root_key')
        key = salt.crypt.Crypticle.generate_key_string()
        if os.path.isfile(keyfile):
            os.chmod(keyfile, 384)
        open(keyfile, 'w+').write(key)
        os.chmod(keyfile, 256)
        return key

    def __worker(self):
        '''
        Starts up a worker thread
        '''
        socket = self.context.socket(zmq.REP)
        socket.connect(self.w_uri)

        while True:
            package = socket.recv()
            payload = salt.payload.unpackage(package)
            ret = salt.payload.package(self._handle_payload(payload))
            socket.send(ret)

    def __bind(self):
        '''
        Binds the reply server
        '''
        self.clients.bind(self.c_uri)

        self.workers.bind(self.w_uri)

        for ind in range(int(self.num_threads)):
            proc = threading.Thread(target=self.__worker)
            proc.start()

        zmq.device(zmq.QUEUE, self.clients, self.workers)

    def _prep_jid(self, load):
        '''
        Parses the job return directory and generates a job id and sets up the
        job id directory
        '''
        jid_root = os.path.join(self.opts['cachedir'], 'jobs')
        jid = str(time.time())
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
        return getattr(self, load['cmd'])(load)

    def _handle_pub(self, load):
        '''
        Handle a command sent via a public key pair
        '''
        pass

    def _handle_aes(self, load):
        '''
        Handle a command sent via an aes key
        '''
        data = self.crypticle.loads(load)
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
        pubfn = os.path.join(self.opts['pki_dir'],
                'minions',
                load['hostname'])
        pubfn_pend = os.path.join(self.opts['pki_dir'],
                'minions_pre',
                load['hostname'])
        if self.opts['open_mode']:
            # open mode is turned on, nuts to checks and overwrite whatever
            # is there
            pass
        elif os.path.isfile(pubfn):
            # The key has been accepted check it
            if not open(pubfn, 'r').read() == load['pub']:
                # The keys don't authenticate, return a failure
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                return ret
        elif not os.path.isfile(pubfn_pend)\
                and not self.opts['auto_accept']:
            # This is a new key, stick it in pre
            open(pubfn_pend, 'w+').write(load['pub'])
            ret = {'enc': 'clear',
                   'load': {'ret': True}}
            return ret
        elif os.path.isfile(pubfn_pend)\
                and not self.opts['auto_accept']:
            # This key is in pending, if it is the same key ret True, else
            # ret False
            if not open(pubfn_pend, 'r').read() == load['pub']:
                return {'enc': 'clear',
                        'load': {'ret': False}}
            else:
                return {'enc': 'clear',
                        'load': {'ret': True}}
        elif not os.path.isfile(pubfn_pend)\
                and self.opts['auto_accept']:
            # This is a new key and auto_accept is turned on
            pass
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
                or not load.has_key('hostname'):
            return False
        jid_dir = os.path.join(self.opts['cachedir'], 'jobs', load['jid'])
        if not os.path.isdir(jid_dir):
            return False
        hn_dir = os.path.join(jid_dir, load['hostname'])
        if not os.path.isdir(hn_dir):
            os.makedirs(hn_dir)
        pickle.dump(load['return'], open(os.path.join(hn_dir, 'return.p'), 'w+'))

    def _send_cluster(self):
        '''
        Send the cluser data out
        '''
        payload = self._cluster_load()
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        for host in self.opts['cluster_masters']:
            master_uri = 'tcp://' + host + ':' + self.opts['master_port']
            socket.connect(master_uri)
            socket.send(payload)
            socket.recv()


    def _cluster(self, load):
        '''
        Recieve the cluster data
        '''
        minion_dir = os.path.join(self.opts['pki_dir'], 'minions')
        if not os.path.isdir(minion_dir):
            os.makedirs(minion_dir)
        for host in load['minions']:
            open(os.path.join(minion_dir, host),
                'w+').write(load['minions'][host])
        return True

    def _cluster_load(self):
        '''
        Generates the data sent to the cluster nodes.
        '''
        payload['enc'] = 'clear'
        payload['load'] = {}
        payload['load']['cmd'] = '_cluster'

        minions = {}
        minion_dir = os.path.join(self.opts['pki_dir'], 'minions')
        for host in os.listdir(minion_dir):
            pub = os.path.join(minion_dir, host)
            minions[host] = open(host, 'r').read()

        payload['load']['minions'] = minions
        return payload

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
               }
        if clear_load.has_key('tgt_type'):
            load['tgt_type'] = clear_load['tgt_type']
        payload['load'] = self.crypticle.dumps(load)
        self.publisher.publish(salt.payload.package(payload))
        return {'enc': 'clear',
                'load': {'jid': jid}}

    def run(self):
        '''
        Start up the ReqServer
        '''
        self.__bind()

