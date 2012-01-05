'''
The crypt module manages all of the cryptography functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
'''

# Import python libs
import hashlib
import hmac
import logging
import os
import sys
import tempfile

# Import Cryptography libs
from Crypto.Cipher import AES
from M2Crypto import RSA

# Import zeromq libs
import zmq

# Import salt utils
import salt.payload
import salt.utils
from salt.exceptions import AuthenticationError

log = logging.getLogger(__name__)


def foo_pass(self, data=''):
    '''
    used as a workaround for the no-passphrase issue in M2Crypto.RSA
    '''
    return 'foo'


def gen_keys(keydir, keyname, keysize):
    '''
    Generate a keypair for use with salt
    '''
    base = os.path.join(keydir, keyname)
    priv = '{0}.pem'.format(base)
    pub = '{0}.pub'.format(base)
    gen = RSA.gen_key(keysize, 1)
    cumask = os.umask(191)
    gen.save_key(priv, callback=foo_pass)
    os.umask(cumask)
    gen.save_pub_key(pub)
    key = RSA.load_key(priv, callback=foo_pass)
    os.chmod(priv, 256)
    return key


class MasterKeys(dict):
    '''
    The Master Keys class is used to manage the public key pair used for
    authentication by the master.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.pub_path = os.path.join(self.opts['pki_dir'], 'master.pub')
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'master.pem')
        self.key = self.__get_priv_key()
        self.pub_str = self.__get_pub_str()
        self.token = self.__gen_token()

    def __get_priv_key(self):
        '''
        Returns a private key object for the master
        '''
        key = None
        try:
            key = RSA.load_key(self.rsa_path, callback=foo_pass)
            log.debug('Loaded master key: {0}'.format(self.rsa_path))
        except:
            log.info('Generating master key: {0}'.format(self.rsa_path))
            key = gen_keys(self.opts['pki_dir'], 'master', 4096)
        return key

    def __get_pub_str(self):
        '''
        Returns the string contents of the public key
        '''
        if not os.path.isfile(self.pub_path):
            key = self.__get_priv_key()
            key.save_pub_key(self.pub_path)
        return open(self.pub_path, 'r').read()

    def __gen_token(self):
        '''
        Generate the authentication token
        '''
        return self.key.private_encrypt('salty bacon', 5)


class Auth(object):
    '''
    The Auth class provides the sequence for setting up communication with the
    master server from a minion.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'minion.pem')
        if 'syndic_master' in self.opts:
            self.mpub = 'syndic_master.pub'
        elif 'alert_master' in self.opts:
            self.mpub = 'monitor_master.pub'
        else:
            self.mpub = 'minion_master.pub'

    def get_priv_key(self):
        '''
        Returns a private key object for the minion
        '''
        key = None
        try:
            key = RSA.load_key(self.rsa_path, callback=foo_pass)
            log.debug('Loaded minion key: {0}'.format(self.rsa_path))
        except:
            log.info('Generating minion key: {0}'.format(self.rsa_path))
            key = gen_keys(self.opts['pki_dir'], 'minion', 4096)
        return key

    def minion_sign_in_payload(self):
        '''
        Generates the payload used to authenticate with the master server. This
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
        payload['load']['id'] = self.opts['id']
        payload['load']['pub'] = open(tmp_pub, 'r').read()
        os.remove(tmp_pub)
        return payload

    def decrypt_aes(self, aes):
        '''
        This function is used to decrypt the aes seed phrase returned from the
        master server, the seed phrase is decrypted with the ssh rsa host key.
        Pass in the encrypted aes key.
        Returns the decrypted aes seed key, a string
        '''
        log.debug('Decrypting the current master AES key')
        key = self.get_priv_key()
        return key.private_decrypt(aes, 4)

    def verify_master(self, master_pub, token):
        '''
        Takes the master pubkey and compares it to the saved master pubkey,
        the token is encrypted with the master private key and must be
        decrypted successfully to verify that the master has been connected to.
        The token must decrypt with the public key, and it must say:
        'salty bacon'
        returns a bool
        '''
        tmp_pub = tempfile.mktemp()
        open(tmp_pub, 'w+').write(master_pub)
        m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)
        pub = RSA.load_pub_key(tmp_pub)
        os.remove(tmp_pub)
        if os.path.isfile(m_pub_fn) and not self.opts['open_mode']:
            local_master_pub = open(m_pub_fn).read()
            if not master_pub == local_master_pub:
                # This is not the last master we connected to
                log.error('The master key has changed, the salt master could '
                          'have been subverted, verify salt master\'s public '
                          'key')
                return False
        else:
            open(m_pub_fn, 'w+').write(master_pub)
        if pub.public_decrypt(token, 5) == 'salty bacon':
            return True
        log.error('The salt master has failed verification for an unknown '
                  'reason, verify your salt keys')
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
        payload = self.serial.dumps(self.minion_sign_in_payload())
        socket.send(payload)
        payload = self.serial.loads(socket.recv())
        if 'load' in payload:
            if 'ret' in payload['load']:
                if not payload['load']['ret']:
                    log.critical(
                        'The Salt Master has rejected this minion\'s public '
                        'key!\nTo repair this issue, delete the public key '
                        'for this minion on the Salt Master and restart this '
                        'minion.\nOr restart the Salt Master in open mode to '
                        'clean out the keys. The Salt Minion will now exit.'
                    )
                    sys.exit(42)
                else:
                    log.error(
                        'The Salt Master has cached the public key for this '
                        'node, this salt minion will wait for %s seconds '
                        'before attempting to re-authenticate',
                        self.opts['acceptance_wait_time']
                    )
                    return 'retry'
        if not self.verify_master(payload['pub_key'], payload['token']):
            m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)
            log.critical(
                'The Salt Master server\'s public key did not authenticate!\n'
                'If you are confident that you are connecting to a valid Salt '
                'Master, then remove the master public key and restart the '
                'Salt Minion.\nThe master public key can be found at:\n%s',
                m_pub_fn
            )
            sys.exit(42)
        auth['aes'] = self.decrypt_aes(payload['aes'])
        auth['publish_port'] = payload['publish_port']
        return auth


class Crypticle(object):
    '''
    Authenticated encryption class

    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    '''

    PICKLE_PAD = 'pickle::'
    AES_BLOCK_SIZE = 16
    SIG_SIZE = hashlib.sha256().digest_size

    def __init__(self, opts, key_string, key_size=192):
        self.keys = self.extract_keys(key_string, key_size)
        self.key_size = key_size
        self.serial = salt.payload.Serial(opts)

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
            log.warning('Failed to authenticate message')
            raise AuthenticationError('message authentication failed')
        iv_bytes = data[:self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE:]
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
        return data[:-ord(data[-1])]

    def dumps(self, obj):
        '''
        Serialize and encrypt a python object
        '''
        return self.encrypt(self.PICKLE_PAD + self.serial.dumps(obj))

    def loads(self, data):
        '''
        Decrypt and un-serialize a python object
        '''
        data = self.decrypt(data)
        # simple integrity check to verify that we got meaningful data
        if not data.startswith(self.PICKLE_PAD):
            return {}
        return self.serial.loads(data[len(self.PICKLE_PAD):])


class SAuth(Auth):
    '''
    Set up an object to maintain the standalone authentication session with
    the salt master
    '''
    def __init__(self, opts):
        super(SAuth, self).__init__(opts)
        self.crypticle = self.__authenticate()

    def __authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign in,
        signing in can occur as often as needed to keep up with the revolving
        master aes key.
        '''
        creds = self.sign_in()
        if creds == 'retry':
            print 'Failed to authenticate with the master, verify that this'\
                + ' minion\'s public key has been accepted on the salt master'
            sys.exit(2)
        return Crypticle(self.opts, creds['aes'])

    def gen_token(self, clear_tok):
        '''
        Encrypt a string with the minion private key to verify identity with
        the master.
        '''
        return self.get_priv_key().private_encrypt(clear_tok, 5)
