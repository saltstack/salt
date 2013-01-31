'''
The crypt module manages all of the cryptography functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
'''

# Import python libs
import os
import sys
import hmac
import hashlib
import logging

# Import third party libs
from M2Crypto import RSA
from Crypto.Cipher import AES

# Import salt libs
import salt.utils
import salt.payload
import salt.utils.verify
import salt.version
from salt.exceptions import (
    AuthenticationError, SaltClientError, SaltReqTimeoutError
)

log = logging.getLogger(__name__)


try:
    import win32api
    import win32con
except ImportError:
    pass


def gen_keys(keydir, keyname, keysize):
    '''
    Generate a keypair for use with salt
    '''
    base = os.path.join(keydir, keyname)
    priv = '{0}.pem'.format(base)
    pub = '{0}.pub'.format(base)

    gen = RSA.gen_key(keysize, 1, callback=lambda x,y,z:None)
    cumask = os.umask(191)
    gen.save_key(priv, None)
    os.umask(cumask)
    gen.save_pub_key(pub)
    os.chmod(priv, 256)
    return priv


class MasterKeys(dict):
    '''
    The Master Keys class is used to manage the public key pair used for
    authentication by the master.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.pub_path = os.path.join(self.opts['pki_dir'], 'master.pub')
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'master.pem')
        self.key = self.__get_keys()
        self.token = self.__gen_token()

    def __get_keys(self):
        '''
        Returns a key objects for the master
        '''
        if os.path.exists(self.rsa_path):
            key = RSA.load_key(self.rsa_path)
            log.debug('Loaded master key: {0}'.format(self.rsa_path))
        else:
            log.info('Generating keys: {0}'.format(self.opts['pki_dir']))
            gen_keys(self.opts['pki_dir'], 'master', 4096)
            key = RSA.load_key(self.rsa_path)
        return key

    def __gen_token(self):
        '''
        Generate the authentication token
        '''
        return self.key.private_encrypt('salty bacon', 5)

    def get_pub_str(self):
        '''
        Return the string representation of the public key
        '''
        if not os.path.isfile(self.pub_path):
            key = self.__get_keys()
            key.save_pub_key(self.pub_path)
        return salt.utils.fopen(self.pub_path, 'r').read()


class Auth(object):
    '''
    The Auth class provides the sequence for setting up communication with
    the master server from a minion.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.token = Crypticle.generate_key_string()
        self.serial = salt.payload.Serial(self.opts)
        self.pub_path = os.path.join(self.opts['pki_dir'], 'minion.pub')
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'minion.pem')
        if 'syndic_master' in self.opts:
            self.mpub = 'syndic_master.pub'
        elif 'alert_master' in self.opts:
            self.mpub = 'monitor_master.pub'
        else:
            self.mpub = 'minion_master.pub'

    def get_keys(self):
        '''
        Returns a key objects for the minion
        '''
        # Make sure all key parent directories are accessible
        user = self.opts.get('user', 'root')
        salt.utils.verify.check_path_traversal(self.opts['pki_dir'], user)

        if os.path.exists(self.rsa_path):
            key = RSA.load_key(self.rsa_path)
            log.debug('Loaded minion key: {0}'.format(self.rsa_path))
        else:
            log.info('Generating keys: {0}'.format(self.opts['pki_dir']))
            gen_keys(self.opts['pki_dir'], 'minion', 4096)
            key = RSA.load_key(self.rsa_path)
        return key

    def minion_sign_in_payload(self):
        '''
        Generates the payload used to authenticate with the master
        server. This payload consists of the passed in id_ and the ssh
        public key to encrypt the AES key sent back form the master.
        '''
        payload = {}
        key = self.get_keys()
        tmp_pub = salt.utils.mkstemp()
        key.save_pub_key(tmp_pub)
        payload['enc'] = 'clear'
        payload['load'] = {}
        payload['load']['cmd'] = '_auth'
        payload['load']['id'] = self.opts['id']
        try:
            pub = RSA.load_pub_key(os.path.join(self.opts['pki_dir'], self.mpub))
            payload['load']['token'] = pub.public_encrypt(self.token, 4)
        except Exception:
            pass
        with salt.utils.fopen(tmp_pub, 'r') as fp_:
            payload['load']['pub'] = fp_.read()
        os.remove(tmp_pub)
        return payload

    def decrypt_aes(self, payload, master_pub=True):
        '''
        This function is used to decrypt the aes seed phrase returned from
        the master server, the seed phrase is decrypted with the ssh rsa
        host key.

        Pass in the encrypted aes key.
        Returns the decrypted aes seed key, a string
        '''
        log.debug('Decrypting the current master AES key')
        key = self.get_keys()
        key_str = key.private_decrypt(payload['aes'], 4)
        if 'sig' in payload:
            m_path = os.path.join(self.opts['pki_dir'], self.mpub)
            if os.path.exists(m_path):
                try:
                    mkey = RSA.load_pub_key(m_path)
                except Exception:
                    return '', ''
                digest = hashlib.sha256(key_str).hexdigest()
                m_digest = mkey.public_decrypt(payload['sig'], 5)
                if not m_digest == digest:
                    return '', ''
        else:
            return '', ''
        if '_|-' in key_str:
            return key_str.split('_|-')
        else:
            if 'token' in payload:
                token = key.private_decrypt(payload['token'], 4)
                return key_str, token
            elif not master_pub:
                return key_str, ''
        return '', ''

    def verify_master(self, payload):
        '''
        '''
        m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)
        if os.path.isfile(m_pub_fn) and not self.opts['open_mode']:
            local_master_pub = salt.utils.fopen(m_pub_fn).read()
            if not payload['pub_key'] == local_master_pub:
                # This is not the last master we connected to
                log.error('The master key has changed, the salt master could '
                          'have been subverted, verify salt master\'s public '
                          'key')
                return ''
            try:
                aes, token = self.decrypt_aes(payload)
                if not token == self.token:
                    log.error('The master failed to decrypt the random minion token')
                    return ''
            except Exception:
                log.error('The master failed to decrypt the random minion token')
                return ''
            return aes
        else:
            salt.utils.fopen(m_pub_fn, 'w+').write(payload['pub_key'])
            aes, token = self.decrypt_aes(payload, False)
            return aes

    def sign_in(self):
        '''
        Send a sign in request to the master, sets the key information and
        returns a dict containing the master publish interface to bind to
        and the decrypted aes key for transport decryption.
        '''
        auth = {}
        m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)
        try:
            self.opts['master_ip'] = salt.utils.dns_check(
                    self.opts['master'],
                    True
                    )
        except SaltClientError:
            return 'retry'
        sreq = salt.payload.SREQ(
                self.opts['master_uri'],
                self.opts.get('id', '')
                )
        try:
            payload = sreq.send_auto(self.minion_sign_in_payload())
        except SaltReqTimeoutError:
            return 'retry'
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
                        'node, this salt minion will wait for {0} seconds '
                        'before attempting to re-authenticate'.format(
                            self.opts['acceptance_wait_time']
                        )
                    )
                    return 'retry'
        auth['aes'] = self.verify_master(payload)
        if not auth['aes']:
            log.critical(
                'The Salt Master server\'s public key did not authenticate!\n'
                'The master may need to be updated if it is a version of Salt '
                'lower than {0}, or\n'
                'If you are confident that you are connecting to a valid Salt '
                'Master, then remove the master public key and restart the '
                'Salt Minion.\nThe master public key can be found '
                'at:\n{1}'.format(salt.version.__version__, m_pub_fn)
            )
            sys.exit(42)
        if self.opts.get('master_finger', False):
            if salt.utils.pem_finger(m_pub_fn) != self.opts['master_finger']:
                log.critical((
                    'The specified fingerprint in the master configuration '
                    'file:\n{0}\nDoes not match the authenticating master\'s '
                    'key:\n{1}\nVerify that the configured fingerprint '
                    'matches the fingerprint of the correct master and that '
                    'this minion is not subject to a man in the middle attack'
                    ).format(
                        self.opts['master_finger'],
                        salt.utils.pem_finger(m_pub_fn)
                        )
                    )
                sys.exit(42)
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
        key = os.urandom(key_size // 8 + cls.SIG_SIZE)
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
        mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
        if len(mac_bytes) != len(sig):
            log.debug('Failed to authenticate message')
            raise AuthenticationError('message authentication failed')
        result = 0
        for zipped_x, zipped_y in zip(mac_bytes, sig):
            result |= ord(zipped_x) ^ ord(zipped_y)
        if result != 0:
            log.debug('Failed to authenticate message')
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
    Set up an object to maintain the standalone authentication session
    with the salt master
    '''
    def __init__(self, opts):
        super(SAuth, self).__init__(opts)
        self.crypticle = self.__authenticate()

    def __authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master aes key.
        '''
        creds = self.sign_in()
        if creds == 'retry':
            log.error('Failed to authenticate with the master, verify this'\
                + ' minion\'s public key has been accepted on the salt master')
            sys.exit(2)
        return Crypticle(self.opts, creds['aes'])

    def gen_token(self, clear_tok):
        '''
        Encrypt a string with the minion private key to verify identity
        with the master.
        '''
        return self.get_keys().private_encrypt(clear_tok, 5)
