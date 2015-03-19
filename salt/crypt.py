# -*- coding: utf-8 -*-
'''
The crypt module manages all of the cryptography functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
'''
# Import python libs
from __future__ import absolute_import, print_function
import os
import sys
import time
import hmac
import hashlib
import logging
import traceback
import binascii
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin

# Import third party libs
try:
    from M2Crypto import RSA, EVP
    from Crypto.Cipher import AES
except ImportError:
    # No need for crypt in local mode
    pass

# Import salt libs
import salt.defaults.exitcodes
import salt.utils
import salt.payload
import salt.utils.verify
import salt.version
from salt.exceptions import (
    AuthenticationError, SaltClientError, SaltReqTimeoutError
)

log = logging.getLogger(__name__)


def dropfile(cachedir, user=None):
    '''
    Set an AES dropfile to request the master update the publish session key
    '''
    dfn = os.path.join(cachedir, '.dfn')
    # set a mask (to avoid a race condition on file creation) and store original.
    mask = os.umask(191)
    try:
        log.info('Rotating AES key')

        with salt.utils.fopen(dfn, 'w+') as fp_:
            fp_.write('')
        if user:
            try:
                import pwd
                uid = pwd.getpwnam(user).pw_uid
                os.chown(dfn, uid, -1)
            except (KeyError, ImportError, OSError, IOError):
                pass
    finally:
        os.umask(mask)  # restore original umask


def gen_keys(keydir, keyname, keysize, user=None):
    '''
    Generate a RSA public keypair for use with salt

    :param str keydir: The directory to write the keypair to
    :param str keyname: The type of salt server for whom this key should be written. (i.e. 'master' or 'minion')
    :param int keysize: The number of bits in the key
    :param str user: The user on the system who should own this keypair

    :rtype: str
    :return: Path on the filesystem to the RSA private key
    '''
    base = os.path.join(keydir, keyname)
    priv = '{0}.pem'.format(base)
    pub = '{0}.pub'.format(base)

    gen = RSA.gen_key(keysize, 65537, callback=lambda x, y, z: None)
    if os.path.isfile(priv):
        # Between first checking and the generation another process has made
        # a key! Use the winner's key
        return priv
    cumask = os.umask(191)
    gen.save_key(priv, None)
    os.umask(cumask)
    gen.save_pub_key(pub)
    os.chmod(priv, 256)
    if user:
        try:
            import pwd
            uid = pwd.getpwnam(user).pw_uid
            os.chown(priv, uid, -1)
            os.chown(pub, uid, -1)
        except (KeyError, ImportError, OSError):
            # The specified user was not found, allow the backup systems to
            # report the error
            pass
    return priv


def sign_message(privkey_path, message):
    '''
    Use M2Crypto's EVP ("Envelope") functions to sign a message.  Returns the signature.
    '''
    log.debug('salt.crypt.sign_message: Loading private key')
    evp_rsa = EVP.load_key(privkey_path)
    evp_rsa.sign_init()
    evp_rsa.sign_update(message)
    log.debug('salt.crypt.sign_message: Signing message.')
    return evp_rsa.sign_final()


def verify_signature(pubkey_path, message, signature):
    '''
    Use M2Crypto's EVP ("Envelope") functions to verify the signature on a message.
    Returns True for valid signature.
    '''
    # Verify that the signature is valid
    log.debug('salt.crypt.verify_signature: Loading public key')
    pubkey = RSA.load_pub_key(pubkey_path)
    verify_evp = EVP.PKey()
    verify_evp.assign_rsa(pubkey)
    verify_evp.verify_init()
    verify_evp.verify_update(message)
    log.debug('salt.crypt.verify_signature: Verifying signature')
    result = verify_evp.verify_final(signature)
    return result


def gen_signature(priv_path, pub_path, sign_path):
    '''
    creates a signature for the given public-key with
    the given private key and writes it to sign_path
    '''

    with salt.utils.fopen(pub_path) as fp_:
        mpub_64 = fp_.read()

    mpub_sig = sign_message(priv_path, mpub_64)
    mpub_sig_64 = binascii.b2a_base64(mpub_sig)
    if os.path.isfile(sign_path):
        return False
    log.trace('Calculating signature for {0} with {1}'
              .format(os.path.basename(pub_path),
                      os.path.basename(priv_path)))

    if os.path.isfile(sign_path):
        log.trace('Signature file {0} already exists, please '
                  'remove it first and try again'.format(sign_path))
    else:
        with salt.utils.fopen(sign_path, 'w+') as sig_f:
            sig_f.write(mpub_sig_64)
        log.trace('Wrote signature to {0}'.format(sign_path))
    return True


class MasterKeys(dict):
    '''
    The Master Keys class is used to manage the RSA public key pair used for
    authentication by the master.

    It also generates a signing key-pair if enabled with master_sign_key_name.
    '''
    def __init__(self, opts):
        super(MasterKeys, self).__init__()
        self.opts = opts
        self.pub_path = os.path.join(self.opts['pki_dir'], 'master.pub')
        self.rsa_path = os.path.join(self.opts['pki_dir'], 'master.pem')

        self.key = self.__get_keys()
        self.token = self.__gen_token()
        self.pub_signature = None

        # set names for the signing key-pairs
        if opts['master_sign_pubkey']:

            # if only the signature is available, use that
            if opts['master_use_pubkey_signature']:
                self.sig_path = os.path.join(self.opts['pki_dir'],
                                             opts['master_pubkey_signature'])
                if os.path.isfile(self.sig_path):
                    self.pub_signature = salt.utils.fopen(self.sig_path).read()
                    log.info('Read {0}\'s signature from {1}'
                             ''.format(os.path.basename(self.pub_path),
                                       self.opts['master_pubkey_signature']))
                else:
                    log.error('Signing the master.pub key with a signature is enabled '
                              'but no signature file found at the defined location '
                              '{0}'.format(self.sig_path))
                    log.error('The signature-file may be either named differently '
                               'or has to be created with \'salt-key --gen-signature\'')
                    sys.exit(1)

            # create a new signing key-pair to sign the masters
            # auth-replies when a minion tries to connect
            else:
                self.pub_sign_path = os.path.join(self.opts['pki_dir'],
                                                  opts['master_sign_key_name'] + '.pub')
                self.rsa_sign_path = os.path.join(self.opts['pki_dir'],
                                                  opts['master_sign_key_name'] + '.pem')
                self.sign_key = self.__get_keys(name=opts['master_sign_key_name'])

    def __get_keys(self, name='master'):
        '''
        Returns a key object for a key in the pki-dir
        '''
        path = os.path.join(self.opts['pki_dir'],
                            name + '.pem')
        if os.path.exists(path):
            key = RSA.load_key(path)
            log.debug('Loaded {0} key: {1}'.format(name, path))
        else:
            log.info('Generating {0} keys: {1}'.format(name, self.opts['pki_dir']))
            gen_keys(self.opts['pki_dir'],
                     name,
                     self.opts['keysize'],
                     self.opts.get('user'))
            key = RSA.load_key(self.rsa_path)
        return key

    def __gen_token(self):
        '''
        Generate the authentication token
        '''
        return self.key.private_encrypt('salty bacon', 5)

    def get_pub_str(self, name='master'):
        '''
        Return the string representation of a public key
        in the pki-directory
        '''
        path = os.path.join(self.opts['pki_dir'],
                            name + '.pub')
        if not os.path.isfile(path):
            key = self.__get_keys()
            key.save_pub_key(path)
        return salt.utils.fopen(path, 'r').read()

    def get_mkey_paths(self):
        return self.pub_path, self.rsa_path

    def get_sign_paths(self):
        return self.pub_sign_path, self.rsa_sign_path

    def pubkey_signature(self):
        '''
        returns the base64 encoded signature from the signature file
        or None if the master has its own signing keys
        '''
        return self.pub_signature


class SAuth(object):
    '''
    Set up an object to maintain authentication with the salt master
    '''
    # This class is only a singleton per minion/master pair
    instances = {}

    def __new__(cls, opts):
        '''
        Only create one instance of SAuth per __key()
        '''
        key = cls.__key(opts)
        if key not in SAuth.instances:
            log.debug('Initializing new SAuth for {0}'.format(key))
            SAuth.instances[key] = object.__new__(cls)
            SAuth.instances[key].__singleton_init__(opts)
        else:
            log.debug('Re-using SAuth for {0}'.format(key))
        return SAuth.instances[key]

    @classmethod
    def __key(cls, opts):
        return (opts['pki_dir'],     # where the keys are stored
                opts['id'],          # minion ID
                opts['master_uri'],  # master ID
                )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts):
        '''
        Init an Auth instance

        :param dict opts: Options for this server
        :return: Auth instance
        :rtype: Auth
        '''
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
        if not os.path.isfile(self.pub_path):
            self.get_keys()

        self.authenticate()

    def authenticate(self, timeout=None, safe=None):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master AES key.

        :rtype: Crypticle
        :returns: A crypticle used for encryption operations
        '''
        acceptance_wait_time = self.opts['acceptance_wait_time']
        acceptance_wait_time_max = self.opts['acceptance_wait_time_max']
        if not acceptance_wait_time_max:
            acceptance_wait_time_max = acceptance_wait_time

        while True:
            creds = self.sign_in(timeout, safe)
            if creds == 'retry':
                if self.opts.get('caller'):
                    print('Minion failed to authenticate with the master, '
                          'has the minion key been accepted?')
                    sys.exit(2)
                if acceptance_wait_time:
                    log.info('Waiting {0} seconds before retry.'.format(acceptance_wait_time))
                    time.sleep(acceptance_wait_time)
                if acceptance_wait_time < acceptance_wait_time_max:
                    acceptance_wait_time += acceptance_wait_time
                    log.debug('Authentication wait time is {0}'.format(acceptance_wait_time))
                continue
            break
        self.creds = creds
        self.crypticle = Crypticle(self.opts, creds['aes'])

    def get_keys(self):
        '''
        Return keypair object for the minion.

        :rtype: M2Crypto.RSA.RSA
        :return: The RSA keypair
        '''
        # Make sure all key parent directories are accessible
        user = self.opts.get('user', 'root')
        salt.utils.verify.check_path_traversal(self.opts['pki_dir'], user)

        if os.path.exists(self.rsa_path):
            key = RSA.load_key(self.rsa_path)
            log.debug('Loaded minion key: {0}'.format(self.rsa_path))
        else:
            log.info('Generating keys: {0}'.format(self.opts['pki_dir']))
            gen_keys(self.opts['pki_dir'],
                     'minion',
                     self.opts['keysize'],
                     self.opts.get('user'))
            key = RSA.load_key(self.rsa_path)
        return key

    def gen_token(self, clear_tok):
        '''
        Encrypt a string with the minion private key to verify identity
        with the master.

        :param str clear_tok: A plaintext token to encrypt
        :return: Encrypted token
        :rtype: str
        '''
        return self.get_keys().private_encrypt(clear_tok, 5)

    def minion_sign_in_payload(self):
        '''
        Generates the payload used to authenticate with the master
        server. This payload consists of the passed in id_ and the ssh
        public key to encrypt the AES key sent back form the master.

        :return: Payload dictionary
        :rtype: dict
        '''
        payload = {}
        payload['enc'] = 'clear'
        payload['load'] = {}
        payload['load']['cmd'] = '_auth'
        payload['load']['id'] = self.opts['id']
        try:
            pub = RSA.load_pub_key(
                os.path.join(self.opts['pki_dir'], self.mpub)
            )
            payload['load']['token'] = pub.public_encrypt(self.token, RSA.pkcs1_oaep_padding)
        except Exception:
            pass
        with salt.utils.fopen(self.pub_path, 'r') as fp_:
            payload['load']['pub'] = fp_.read()
        return payload

    def decrypt_aes(self, payload, master_pub=True):
        '''
        This function is used to decrypt the AES seed phrase returned from
        the master server. The seed phrase is decrypted with the SSH RSA
        host key.

        Pass in the encrypted AES key.
        Returns the decrypted AES seed key, a string

        :param dict payload: The incoming payload. This is a dictionary which may have the following keys:
            'aes': The shared AES key
            'enc': The format of the message. ('clear', 'pub', etc)
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The public key of the sender.

        :rtype: str
        :return: The decrypted token that was provided, with padding.

        :rtype: str
        :return: The decrypted AES seed key
        '''
        if self.opts.get('auth_trb', False):
            log.warning(
                    'Auth Called: {0}'.format(
                        ''.join(traceback.format_stack())
                        )
                    )
        else:
            log.debug('Decrypting the current master AES key')
        key = self.get_keys()
        key_str = key.private_decrypt(payload['aes'], RSA.pkcs1_oaep_padding)
        if 'sig' in payload:
            m_path = os.path.join(self.opts['pki_dir'], self.mpub)
            if os.path.exists(m_path):
                try:
                    mkey = RSA.load_pub_key(m_path)
                except Exception:
                    return '', ''
                digest = hashlib.sha256(key_str).hexdigest()
                m_digest = mkey.public_decrypt(payload['sig'], 5)
                if m_digest != digest:
                    return '', ''
        else:
            return '', ''
        if '_|-' in key_str:
            return key_str.split('_|-')
        else:
            if 'token' in payload:
                token = key.private_decrypt(payload['token'], RSA.pkcs1_oaep_padding)
                return key_str, token
            elif not master_pub:
                return key_str, ''
        return '', ''

    def verify_pubkey_sig(self, message, sig):
        '''
        Wraps the verify_signature method so we have
        additional checks.

        :rtype: bool
        :return: Success or failure of public key verification
        '''
        if self.opts['master_sign_key_name']:
            path = os.path.join(self.opts['pki_dir'],
                                self.opts['master_sign_key_name'] + '.pub')

            if os.path.isfile(path):
                res = verify_signature(path,
                                       message,
                                       binascii.a2b_base64(sig))
            else:
                log.error('Verification public key {0} does not exist. You '
                          'need to copy it from the master to the minions '
                          'pki directory'.format(os.path.basename(path)))
                return False
            if res:
                log.debug('Successfully verified signature of master '
                          'public key with verification public key '
                          '{0}'.format(self.opts['master_sign_key_name'] + '.pub'))
                return True
            else:
                log.debug('Failed to verify signature of public key')
                return False
        else:
            log.error('Failed to verify the signature of the message because '
                      'the verification key-pairs name is not defined. Please '
                      'make sure that master_sign_key_name is defined.')
            return False

    def verify_signing_master(self, payload):
        try:
            if self.verify_pubkey_sig(payload['pub_key'],
                                      payload['pub_sig']):
                log.info('Received signed and verified master pubkey '
                         'from master {0}'.format(self.opts['master']))
                m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)
                uid = salt.utils.get_uid(self.opts.get('user', None))
                with salt.utils.fpopen(m_pub_fn, 'w+', uid=uid) as wfh:
                    wfh.write(payload['pub_key'])
                return True
            else:
                log.error('Received signed public-key from master {0} '
                          'but signature verification failed!'.format(self.opts['master']))
                return False
        except Exception as sign_exc:
            log.error('There was an error while verifying the masters public-key signature')
            raise Exception(sign_exc)

    def check_auth_deps(self, payload):
        '''
        Checks if both master and minion either sign (master) and
        verify (minion). If one side does not, it should fail.

        :param dict payload: The incoming payload. This is a dictionary which may have the following keys:
            'aes': The shared AES key
            'enc': The format of the message. ('clear', 'pub', 'aes')
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The RSA public key of the sender.
        '''
        # master and minion sign and verify
        if 'pub_sig' in payload and self.opts['verify_master_pubkey_sign']:
            return True
        # master and minion do NOT sign and do NOT verify
        elif 'pub_sig' not in payload and not self.opts['verify_master_pubkey_sign']:
            return True

        # master signs, but minion does NOT verify
        elif 'pub_sig' in payload and not self.opts['verify_master_pubkey_sign']:
            log.error('The masters sent its public-key signature, but signature '
                      'verification is not enabled on the minion. Either enable '
                      'signature verification on the minion or disable signing '
                      'the public key on the master!')
            return False
        # master does NOT sign but minion wants to verify
        elif 'pub_sig' not in payload and self.opts['verify_master_pubkey_sign']:
            log.error('The master did not send its public-key signature, but '
                      'signature verification is enabled on the minion. Either '
                      'disable signature verification on the minion or enable '
                      'signing the public on the master!')
            return False

    def extract_aes(self, payload, master_pub=True):
        '''
        Return the AES key received from the master after the minion has been
        successfully authenticated.

        :param dict payload: The incoming payload. This is a dictionary which may have the following keys:
            'aes': The shared AES key
            'enc': The format of the message. ('clear', 'pub', etc)
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The RSA public key of the sender.

        :rtype: str
        :return: The shared AES key received from the master.
        '''
        if master_pub:
            try:
                aes, token = self.decrypt_aes(payload, master_pub)
                if token != self.token:
                    log.error(
                        'The master failed to decrypt the random minion token'
                    )
                    return ''
            except Exception:
                log.error(
                    'The master failed to decrypt the random minion token'
                )
                return ''
            return aes
        else:
            aes, token = self.decrypt_aes(payload, master_pub)
            return aes

    def verify_master(self, payload):
        '''
        Verify that the master is the same one that was previously accepted.

        :param dict payload: The incoming payload. This is a dictionary which may have the following keys:
            'aes': The shared AES key
            'enc': The format of the message. ('clear', 'pub', etc)
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The RSA public key of the sender.

        :rtype: str
        :return: An empty string on verification failure. On success, the decrypted AES message in the payload.
        '''
        m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)
        if os.path.isfile(m_pub_fn) and not self.opts['open_mode']:
            local_master_pub = salt.utils.fopen(m_pub_fn).read()

            if payload['pub_key'] != local_master_pub:
                if not self.check_auth_deps(payload):
                    return ''

                if self.opts['verify_master_pubkey_sign']:
                    if self.verify_signing_master(payload):
                        return self.extract_aes(payload, master_pub=False)
                    else:
                        return ''
                else:
                    # This is not the last master we connected to
                    log.error('The master key has changed, the salt master could '
                              'have been subverted, verify salt master\'s public '
                              'key')
                    return ''

            else:
                if not self.check_auth_deps(payload):
                    return ''
                # verify the signature of the pubkey even if it has
                # not changed compared with the one we already have
                if self.opts['always_verify_signature']:
                    if self.verify_signing_master(payload):
                        return self.extract_aes(payload)
                    else:
                        log.error('The masters public could not be verified. Is the '
                                  'verification pubkey {0} up to date?'
                                  ''.format(self.opts['master_sign_key_name'] + '.pub'))
                        return ''

                else:
                    return self.extract_aes(payload)
        else:
            if not self.check_auth_deps(payload):
                return ''

            # verify the masters pubkey signature if the minion
            # has not received any masters pubkey before
            if self.opts['verify_master_pubkey_sign']:
                if self.verify_signing_master(payload):
                    return self.extract_aes(payload, master_pub=False)
                else:
                    return ''
            # the minion has not received any masters pubkey yet, write
            # the newly received pubkey to minion_master.pub
            else:
                salt.utils.fopen(m_pub_fn, 'w+').write(payload['pub_key'])
                return self.extract_aes(payload, master_pub=False)

    def sign_in(self, timeout=60, safe=True, tries=1):
        '''
        Send a sign in request to the master, sets the key information and
        returns a dict containing the master publish interface to bind to
        and the decrypted aes key for transport decryption.

        :param int timeout: Number of seconds to wait before timing out the sign-in request
        :param bool safe: If True, do not raise an exception on timeout. Retry instead.
        :param int tries: The number of times to try to authenticate before giving up.

        :raises SaltReqTimeoutError: If the sign-in request has timed out and :param safe: is not set

        :return: Return a string on failure indicating the reason for failure. On success, return a dictionary
        with the publication port and the shared AES key.

        '''
        auth = {}

        auth_timeout = self.opts.get('auth_timeout', None)
        if auth_timeout is not None:
            timeout = auth_timeout
        auth_safemode = self.opts.get('auth_safemode', None)
        if auth_safemode is not None:
            safe = auth_safemode
        auth_tries = self.opts.get('auth_tries', None)
        if auth_tries is not None:
            tries = auth_tries

        m_pub_fn = os.path.join(self.opts['pki_dir'], self.mpub)

        auth['master_uri'] = self.opts['master_uri']

        sreq = salt.payload.SREQ(
            self.opts['master_uri'],
            opts=self.opts
        )

        try:
            payload = sreq.send_auto(
                self.minion_sign_in_payload(),
                tries=tries,
                timeout=timeout
            )
        except SaltReqTimeoutError as e:
            if safe:
                log.warning('SaltReqTimeoutError: {0}'.format(e))
                return 'retry'
            raise SaltClientError('Attempt to authenticate with the salt master failed')

        if 'load' in payload:
            if 'ret' in payload['load']:
                if not payload['load']['ret']:
                    if self.opts['rejected_retry']:
                        log.error(
                            'The Salt Master has rejected this minion\'s public '
                            'key.\nTo repair this issue, delete the public key '
                            'for this minion on the Salt Master.\nThe Salt '
                            'Minion will attempt to to re-authenicate.'
                        )
                        return 'retry'
                    else:
                        log.critical(
                            'The Salt Master has rejected this minion\'s public '
                            'key!\nTo repair this issue, delete the public key '
                            'for this minion on the Salt Master and restart this '
                            'minion.\nOr restart the Salt Master in open mode to '
                            'clean out the keys. The Salt Minion will now exit.'
                        )
                        sys.exit(salt.defaults.exitcodes.EX_OK)
                # has the master returned that its maxed out with minions?
                elif payload['load']['ret'] == 'full':
                    return 'full'
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
        if self.opts.get('syndic_master', False):  # Is syndic
            syndic_finger = self.opts.get('syndic_finger', self.opts.get('master_finger', False))
            if syndic_finger:
                if salt.utils.pem_finger(m_pub_fn) != syndic_finger:
                    self._finger_fail(syndic_finger, m_pub_fn)
        else:
            if self.opts.get('master_finger', False):
                if salt.utils.pem_finger(m_pub_fn) != self.opts['master_finger']:
                    self._finger_fail(self.opts['master_finger'], m_pub_fn)
        auth['publish_port'] = payload['publish_port']
        return auth

    def _finger_fail(self, finger, master_key):
        log.critical(
            'The specified fingerprint in the master configuration '
            'file:\n{0}\nDoes not match the authenticating master\'s '
            'key:\n{1}\nVerify that the configured fingerprint '
            'matches the fingerprint of the correct master and that '
            'this minion is not subject to a man-in-the-middle attack.'
            .format(
                finger,
                salt.utils.pem_finger(master_key)
            )
        )
        sys.exit(42)


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
        self.key_string = key_string
        self.keys = self.extract_keys(self.key_string, key_size)
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
