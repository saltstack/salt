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
        self.crypticle = salt.crypt.Crypticle(self.key)

    def __prep_key(self):
        '''
        A key needs to be placed in the filesystem with permissions 0400 so
        clients are required to run as root.
        '''
        keyfile = os.path.join(self.opts['cachedir'], '.root_key')
        key = salt.crypt.Crypticle.generate_key_string()
        open(keyfile, 'w+').write(key)
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
            pickle.dump(load, open(os.path.join(jid_dir, 'load.p'), 'w+'))
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
        return getattr(self, load['cmd'])(load)

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
        if os.path.isfile(pubfn):
            if not open(pubfn, 'r').read() == load['pub']:
                # The keys don't authenticate, return a failure
                ret = {'enc': 'clear',
                       'load': {'ret': False}}
                return ret
        else:
            open(pubfn, 'w+').write(load['pub'])
        key = RSA.load_pub_key(pubfn)
        ret = {'enc': 'pub',
               'pub_key': self.master_key.pub_str,
               'token': self.master_key.token,
               'publish_port': self.opts['publish_port'],
              }
        ret['aes'] = key.public_encrypt(self.opts['aes'], 4)
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
        pickle.dump(load['return'], os.path.join(hn_dir, 'return.p'))

    def publish(self, load):
        '''
        This method sends out publications to the minions
        '''
        if not load.pop('key') == self.key:
            return ''
        jid = self._prep_jid(load)
        payload = {'enc': 'aes'}
        load = {
                'fun': load['fun'],
                'arg': load['arg'],
                'tgt': load['tgt'],
                'jid': jid,
               }
        payload['load'] = self.crypticle.dumps(load)
        self.publisher.publish(salt.payload.package(payload))
        return {'enc': 'clear',
                'load': {'jid': jid}}

    def run(self):
        '''
        Start up the ReqServer
        '''
        self.__bind()

