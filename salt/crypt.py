'''
The crypt module manages all of the cyptogophy functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
'''

# Import python libs
import os
import hmac
import tempfile
import random
import hashlib
import string
import cPickle as pickle
# Import Cryptography libs
from M2Crypto import RSA
from Crypto.Cipher import AES
# Import zeromq libs
import zmq
# Import salt utils
import salt.utils
import salt.payload

class Auth(object):
    '''
    The Auth class provides the sequence for setting up communication with the
    master server from a minion.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'minion.pem')

    def __foo_pass(self, data=''):
        '''
        used as a workaround for the no-passphrase issue in M2Crypto.RSA
        '''
        return 'foo'

    def get_priv_key(self):
        '''
        Retruns a private key object derived from the passed host key
        '''
        key = None
        try:
            key = RSA.load_key(self.rsa_path, callback=self.__foo_pass)
        except:
            gen = RSA.gen_key(2048, 1)
            gen.save_key(self.rsa_path, callback=self.__foo_pass)
            pub_path = os.path.join(self.opts['pki_dir'], 'minion.pub')
            gen.save_pub_key(pub_path)
            key = RSA.load_key(self.rsa_path, callback=self.__foo_pass)
        return key

    def minion_sign_in_payload(self):
        '''
        Generates the payload used to autnenticate with the master server. This
        payload consists of the passed in id_ and the ssh public key to encrypt
        the AES key sent back form the master.
        '''
        payload = {}
        key = self.get_priv_key()
        tmp_pub = tempfile.mktemp()
        key.save_pub_key(tmp_pub)
        payload['enc'] = 'clear'
        payload['load'] = {}
        payload['load']['cmd'] = '_auth'
        payload['load']['hostname'] = self.opts['hostname']
        payload['load']['pub'] = open(tmp_pub, 'r').read()
        return payload

    def decrypt_auth(self, payload):
        '''
        This function is used to decrypt the aes seed phrase returned from the
        master server, the seed phrase is decrypted with the ssh rsa host key.
        Pass in the encrypted aes key.
        Returns the decrypted aes seed key, a string
        '''
        key = self.get_priv_key()
        return key.public_decrypt(payload['load'], 4)
    
    def verify_master(self, master_pub, token):
        '''
        Takes the master pubkey and compares it to the saved master pubkey,
        the token is encrypted with the master private key and must be
        decrypted sucessfully to verify that the master has been connected to.
        The token must decrypt with the public key, and it must say:
        'salty bacon'
        returns a bool
        '''
        tmp_pub = tempfile.mktemp()
        open(tmp_pub, 'w+').write(master_pub)
        m_pub_fn = os.path.join(self.opts['pki_dir'], 'master.pub')
        if os.path.isfile(m_pub_fn):
            local_master_pub = open(m_pub_fn).read()
            if not master_pub == local_master_pub:
                # This is not the last master we connected to
                return False
        else:
            open(m_pub_fn, 'w+').write(master_pub)
        pub = RSA.load_pub_key(tmp_pub)
        if pub.private_decrypt(token) == 'salty bacon':
            return True
        return False

    def sign_in(self):
        '''
        Send a sign in request to the master, sets the key information and
        returns a dict containing the master publish interface to bind to
        and the decrypted aes key for transport decryption.
        '''
        auth = {}
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(self.opts['master_uri'])
        payload = salt.payload.package(self.minion_sign_in_payload())
        socket.send(payload)
        load = self.decrypt_auth(salt.payload.unpackage(socket.recv()))
        if not self.verify_master(load['pub_key'], load['token']):
            return auth
        auth['aes'] = load['aes']
        auth['master_publish_port'] = load['master_publish_port']
        return auth


class AuthenticationError(Exception): pass


class Crypticle(object):
    '''
    Authenticated encryption class
    
    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    '''

    PICKLE_PAD = 'pickle::'
    AES_BLOCK_SIZE = 16
    SIG_SIZE = hashlib.sha256().digest_size

    def __init__(self, key_string, key_size=192):
        self.keys = self.extract_keys(key_string, key_size)
        self.key_size = key_size

    @classmethod
    def generate_key_string(cls, key_size=192):
        key = os.urandom(key_size / 8 + cls.SIG_SIZE)
        return key.encode('base64').replace('\n', '')

    @classmethod
    def extract_keys(cls, key_string, key_size):
        key = key_string.decode('base64')
        assert len(key) == key_size / 8 + cls.SIG_SIZE, 'invalid key'
        return key[:-cls.SIG_SIZE], key[-cls.SIG_SIZE:]

    def encrypt(self, data):
        '''
        encrypt data with AES-CBC and sign it with HMAC-SHA256
        '''
        aes_key, hmac_key = self.keys
        pad = self.AES_BLOCK_SIZE - len(data) % self.AES_BLOCK_SIZE
        data = data + pad * chr(pad)
        iv_bytes = os.urandom(self.AES_BLOCK_SIZE)
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = iv_bytes + cypher.encrypt(data)
        sig = hmac.new(hmac_key, data, hashlib.sha256).digest()
        return data + sig

    def decrypt(self, data):
        '''
        verify HMAC-SHA256 signature and decrypt data with AES-CBC
        '''
        aes_key, hmac_key = self.keys
        sig = data[-self.SIG_SIZE:]
        data = data[:-self.SIG_SIZE]
        if hmac.new(hmac_key, data, hashlib.sha256).digest() != sig:
            raise AuthenticationError('message authentication failed')
        iv_bytes = data[:self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE:]
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
        return data[:-ord(data[-1])]

    def dumps(self, obj, pickler=pickle):
        '''
        pickle and encrypt a python object
        '''
        return self.encrypt(self.PICKLE_PAD + pickler.dumps(obj))

    def loads(self, data, pickler=pickle):
        '''
        decrypt and unpickle a python object
        '''
        data = self.decrypt(data)
        # simple integrity check to verify that we got meaningful data
        assert data.startswith(self.PICKLE_PAD), 'unexpected header'
        return pickler.loads(data[len(self.PICKLE_PAD):])


