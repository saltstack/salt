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
import copy
import time
import hmac
import base64
import hashlib
import logging
import stat
import traceback
import binascii
import weakref
import getpass
import tornado.gen

# Import third party libs
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin
from salt.ext import six
try:
    from Cryptodome.Cipher import AES, PKCS1_OAEP
    from Cryptodome.Hash import SHA
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import PKCS1_v1_5
    import Cryptodome.Random  # pylint: disable=W0611
    CDOME = True
except ImportError:
    CDOME = False
if not CDOME:
    try:
        from Crypto.Cipher import AES, PKCS1_OAEP
        from Crypto.Hash import SHA
        from Crypto.PublicKey import RSA
        from Crypto.Signature import PKCS1_v1_5
        # let this be imported, if possible
        import Crypto.Random  # pylint: disable=W0611
    except ImportError:
        # No need for crypt in local mode
        pass

# Import salt libs
import salt.defaults.exitcodes
import salt.payload
import salt.transport.client
import salt.transport.frame
import salt.utils
import salt.utils.decorators
import salt.utils.event
import salt.utils.files
import salt.utils.rsax931
import salt.utils.sdb
import salt.utils.stringutils
import salt.utils.verify
import salt.version
from salt.exceptions import (
    AuthenticationError, SaltClientError, SaltReqTimeoutError, MasterExit
)

log = logging.getLogger(__name__)


def dropfile(cachedir, user=None):
    '''
    Set an AES dropfile to request the master update the publish session key
    '''
    dfn = os.path.join(cachedir, u'.dfn')
    # set a mask (to avoid a race condition on file creation) and store original.
    mask = os.umask(191)
    try:
        log.info(u'Rotating AES key')
        if os.path.isfile(dfn):
            log.info(u'AES key rotation already requested')
            return

        if os.path.isfile(dfn) and not os.access(dfn, os.W_OK):
            os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
        with salt.utils.files.fopen(dfn, u'wb+') as fp_:
            fp_.write(b'')  # future lint: disable=non-unicode-string
        os.chmod(dfn, stat.S_IRUSR)
        if user:
            try:
                import pwd
                uid = pwd.getpwnam(user).pw_uid
                os.chown(dfn, uid, -1)
            except (KeyError, ImportError, OSError, IOError):
                pass
    finally:
        os.umask(mask)  # restore original umask


def gen_keys(keydir, keyname, keysize, user=None, passphrase=None):
    '''
    Generate a RSA public keypair for use with salt

    :param str keydir: The directory to write the keypair to
    :param str keyname: The type of salt server for whom this key should be written. (i.e. 'master' or 'minion')
    :param int keysize: The number of bits in the key
    :param str user: The user on the system who should own this keypair
    :param str passphrase: The passphrase which should be used to encrypt the private key

    :rtype: str
    :return: Path on the filesystem to the RSA private key
    '''
    base = os.path.join(keydir, keyname)
    priv = u'{0}.pem'.format(base)
    pub = u'{0}.pub'.format(base)

    salt.utils.reinit_crypto()
    gen = RSA.generate(bits=keysize, e=65537)
    if os.path.isfile(priv):
        # Between first checking and the generation another process has made
        # a key! Use the winner's key
        return priv

    # Do not try writing anything, if directory has no permissions.
    if not os.access(keydir, os.W_OK):
        raise IOError(u'Write access denied to "{0}" for user "{1}".'.format(os.path.abspath(keydir), getpass.getuser()))

    cumask = os.umask(191)
    with salt.utils.files.fopen(priv, u'wb+') as f:
        f.write(gen.exportKey(u'PEM', passphrase))
    os.umask(cumask)
    with salt.utils.files.fopen(pub, u'wb+') as f:
        f.write(gen.publickey().exportKey(u'PEM'))
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


@salt.utils.decorators.memoize
def _get_key_with_evict(path, timestamp, passphrase):
    '''
    Load a key from disk.  `timestamp` above is intended to be the timestamp
    of the file's last modification. This fn is memoized so if it is called with the
    same path and timestamp (the file's last modified time) the second time
    the result is returned from the memoiziation.  If the file gets modified
    then the params are different and the key is loaded from disk.
    '''
    log.debug(u'salt.crypt._get_key_with_evict: Loading private key')
    with salt.utils.files.fopen(path) as f:
        key = RSA.importKey(f.read(), passphrase)
    return key


def _get_rsa_key(path, passphrase):
    '''
    Read a key off the disk.  Poor man's simple cache in effect here,
    we memoize the result of calling _get_rsa_with_evict.  This means
    the first time _get_key_with_evict is called with a path and a timestamp
    the result is cached.  If the file (the private key) does not change
    then its timestamp will not change and the next time the result is returned
    from the cache.  If the key DOES change the next time _get_rsa_with_evict
    is called it is called with different parameters and the fn is run fully to
    retrieve the key from disk.
    '''
    log.debug(u'salt.crypt._get_rsa_key: Loading private key')
    return _get_key_with_evict(path, str(os.path.getmtime(path)), passphrase)


def sign_message(privkey_path, message, passphrase=None):
    '''
    Use Crypto.Signature.PKCS1_v1_5 to sign a message. Returns the signature.
    '''
    key = _get_rsa_key(privkey_path, passphrase)
    log.debug(u'salt.crypt.sign_message: Signing message.')
    signer = PKCS1_v1_5.new(key)
    return signer.sign(SHA.new(message))


def verify_signature(pubkey_path, message, signature):
    '''
    Use Crypto.Signature.PKCS1_v1_5 to verify the signature on a message.
    Returns True for valid signature.
    '''
    log.debug(u'salt.crypt.verify_signature: Loading public key')
    with salt.utils.files.fopen(pubkey_path) as f:
        pubkey = RSA.importKey(f.read())
    log.debug(u'salt.crypt.verify_signature: Verifying signature')
    verifier = PKCS1_v1_5.new(pubkey)
    return verifier.verify(SHA.new(message), signature)


def gen_signature(priv_path, pub_path, sign_path, passphrase=None):
    '''
    creates a signature for the given public-key with
    the given private key and writes it to sign_path
    '''

    with salt.utils.files.fopen(pub_path) as fp_:
        mpub_64 = fp_.read()

    mpub_sig = sign_message(priv_path, mpub_64, passphrase)
    mpub_sig_64 = binascii.b2a_base64(mpub_sig)
    if os.path.isfile(sign_path):
        return False
    log.trace(
        u'Calculating signature for %s with %s',
        os.path.basename(pub_path), os.path.basename(priv_path)
    )

    if os.path.isfile(sign_path):
        log.trace(
            u'Signature file %s already exists, please remove it first and '
            u'try again', sign_path
        )
    else:
        with salt.utils.files.fopen(sign_path, u'wb+') as sig_f:
            sig_f.write(salt.utils.stringutils.to_bytes(mpub_sig_64))
        log.trace(u'Wrote signature to %s', sign_path)
    return True


def private_encrypt(key, message):
    '''
    Generate an M2Crypto-compatible signature

    :param Crypto.PublicKey.RSA._RSAobj key: The RSA key object
    :param str message: The message to sign
    :rtype: str
    :return: The signature, or an empty string if the signature operation failed
    '''
    signer = salt.utils.rsax931.RSAX931Signer(key.exportKey(u'PEM'))
    return signer.sign(message)


def public_decrypt(pub, message):
    '''
    Verify an M2Crypto-compatible signature

    :param Crypto.PublicKey.RSA._RSAobj key: The RSA public key object
    :param str message: The signed message to verify
    :rtype: str
    :return: The message (or digest) recovered from the signature, or an
        empty string if the verification failed
    '''
    verifier = salt.utils.rsax931.RSAX931Verifier(pub.exportKey(u'PEM'))
    return verifier.verify(message)


class MasterKeys(dict):
    '''
    The Master Keys class is used to manage the RSA public key pair used for
    authentication by the master.

    It also generates a signing key-pair if enabled with master_sign_key_name.
    '''
    def __init__(self, opts):
        super(MasterKeys, self).__init__()
        self.opts = opts
        self.pub_path = os.path.join(self.opts[u'pki_dir'], u'master.pub')
        self.rsa_path = os.path.join(self.opts[u'pki_dir'], u'master.pem')

        key_pass = salt.utils.sdb.sdb_get(self.opts['key_pass'], self.opts)
        self.key = self.__get_keys(passphrase=key_pass)

        self.pub_signature = None

        # set names for the signing key-pairs
        if opts[u'master_sign_pubkey']:

            # if only the signature is available, use that
            if opts[u'master_use_pubkey_signature']:
                self.sig_path = os.path.join(self.opts[u'pki_dir'],
                                             opts[u'master_pubkey_signature'])
                if os.path.isfile(self.sig_path):
                    with salt.utils.files.fopen(self.sig_path) as fp_:
                        self.pub_signature = fp_.read()
                    log.info(
                        u'Read %s\'s signature from %s',
                        os.path.basename(self.pub_path),
                        self.opts[u'master_pubkey_signature']
                    )
                else:
                    log.error(
                        u'Signing the master.pub key with a signature is '
                        u'enabled but no signature file found at the defined '
                        u'location %s', self.sig_path
                    )
                    log.error(
                        u'The signature-file may be either named differently '
                        u'or has to be created with \'salt-key --gen-signature\''
                    )
                    sys.exit(1)

            # create a new signing key-pair to sign the masters
            # auth-replies when a minion tries to connect
            else:
                key_pass = salt.utils.sdb.sdb_get(self.opts[u'signing_key_pass'], self.opts)
                self.pub_sign_path = os.path.join(self.opts[u'pki_dir'],
                                                  opts[u'master_sign_key_name'] + u'.pub')
                self.rsa_sign_path = os.path.join(self.opts[u'pki_dir'],
                                                  opts[u'master_sign_key_name'] + u'.pem')
                self.sign_key = self.__get_keys(name=opts[u'master_sign_key_name'])

    # We need __setstate__ and __getstate__ to avoid pickling errors since
    # some of the member variables correspond to Cython objects which are
    # not picklable.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        self.__init__(state[u'opts'])

    def __getstate__(self):
        return {u'opts': self.opts}

    def __get_keys(self, name=u'master', passphrase=None):
        '''
        Returns a key object for a key in the pki-dir
        '''
        path = os.path.join(self.opts[u'pki_dir'],
                            name + u'.pem')
        if os.path.exists(path):
            with salt.utils.files.fopen(path) as f:
                try:
                    key = RSA.importKey(f.read(), passphrase)
                except ValueError as e:
                    message = u'Unable to read key: {0}; passphrase may be incorrect'.format(path)
                    log.error(message)
                    raise MasterExit(message)
            log.debug(u'Loaded %s key: %s', name, path)
        else:
            log.info(u'Generating %s keys: %s', name, self.opts[u'pki_dir'])
            gen_keys(self.opts[u'pki_dir'],
                     name,
                     self.opts[u'keysize'],
                     self.opts.get(u'user'),
                     passphrase)
            with salt.utils.files.fopen(self.rsa_path) as f:
                key = RSA.importKey(f.read(), passphrase)
        return key

    def get_pub_str(self, name=u'master'):
        '''
        Return the string representation of a public key
        in the pki-directory
        '''
        path = os.path.join(self.opts[u'pki_dir'],
                            name + u'.pub')
        if not os.path.isfile(path):
            key = self.__get_keys()
            with salt.utils.files.fopen(path, u'wb+') as wfh:
                wfh.write(key.publickey().exportKey(u'PEM'))
        with salt.utils.files.fopen(path) as rfh:
            return rfh.read()

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


class AsyncAuth(object):
    '''
    Set up an Async object to maintain authentication with the salt master
    '''
    # This class is only a singleton per minion/master pair
    # mapping of io_loop -> {key -> auth}
    instance_map = weakref.WeakKeyDictionary()

    # mapping of key -> creds
    creds_map = {}

    def __new__(cls, opts, io_loop=None):
        '''
        Only create one instance of AsyncAuth per __key()
        '''
        # do we have any mapping for this io_loop
        io_loop = io_loop or tornado.ioloop.IOLoop.current()
        if io_loop not in AsyncAuth.instance_map:
            AsyncAuth.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = AsyncAuth.instance_map[io_loop]

        key = cls.__key(opts)
        auth = loop_instance_map.get(key)
        if auth is None:
            log.debug(u'Initializing new AsyncAuth for %s', key)
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            auth = object.__new__(cls)
            auth.__singleton_init__(opts, io_loop=io_loop)
            loop_instance_map[key] = auth
        else:
            log.debug(u'Re-using AsyncAuth for %s', key)
        return auth

    @classmethod
    def __key(cls, opts, io_loop=None):
        return (opts[u'pki_dir'],     # where the keys are stored
                opts[u'id'],          # minion ID
                opts[u'master_uri'],  # master ID
                )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, io_loop=None):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, io_loop=None):
        '''
        Init an Auth instance

        :param dict opts: Options for this server
        :return: Auth instance
        :rtype: Auth
        '''
        self.opts = opts
        if six.PY2:
            self.token = Crypticle.generate_key_string()
        else:
            self.token = salt.utils.stringutils.to_bytes(Crypticle.generate_key_string())
        self.serial = salt.payload.Serial(self.opts)
        self.pub_path = os.path.join(self.opts[u'pki_dir'], u'minion.pub')
        self.rsa_path = os.path.join(self.opts[u'pki_dir'], u'minion.pem')
        if self.opts[u'__role'] == u'syndic':
            self.mpub = u'syndic_master.pub'
        else:
            self.mpub = u'minion_master.pub'
        if not os.path.isfile(self.pub_path):
            self.get_keys()

        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()

        salt.utils.reinit_crypto()
        key = self.__key(self.opts)
        # TODO: if we already have creds for this key, lets just re-use
        if key in AsyncAuth.creds_map:
            creds = AsyncAuth.creds_map[key]
            self._creds = creds
            self._crypticle = Crypticle(self.opts, creds[u'aes'])
            self._authenticate_future = tornado.concurrent.Future()
            self._authenticate_future.set_result(True)
        else:
            self.authenticate()

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls, copy.deepcopy(self.opts, memo), io_loop=None)
        memo[id(self)] = result
        for key in self.__dict__:
            if key in (u'io_loop',):
                # The io_loop has a thread Lock which will fail to be deep
                # copied. Skip it because it will just be recreated on the
                # new copy.
                continue
            setattr(result, key, copy.deepcopy(self.__dict__[key], memo))
        return result

    @property
    def creds(self):
        return self._creds

    @property
    def crypticle(self):
        return self._crypticle

    @property
    def authenticated(self):
        return hasattr(self, u'_authenticate_future') and \
               self._authenticate_future.done() and \
               self._authenticate_future.exception() is None

    def invalidate(self):
        if self.authenticated:
            del self._authenticate_future
            key = self.__key(self.opts)
            if key in AsyncAuth.creds_map:
                del AsyncAuth.creds_map[key]

    def authenticate(self, callback=None):
        '''
        Ask for this client to reconnect to the origin

        This function will de-dupe all calls here and return a *single* future
        for the sign-in-- whis way callers can all assume there aren't others
        '''
        # if an auth is in flight-- and not done-- just pass that back as the future to wait on
        if hasattr(self, u'_authenticate_future') and not self._authenticate_future.done():
            future = self._authenticate_future
        else:
            future = tornado.concurrent.Future()
            self._authenticate_future = future
            self.io_loop.add_callback(self._authenticate)

        if callback is not None:
            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)
            future.add_done_callback(handle_future)

        return future

    @tornado.gen.coroutine
    def _authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master AES key.

        :rtype: Crypticle
        :returns: A crypticle used for encryption operations
        '''
        acceptance_wait_time = self.opts[u'acceptance_wait_time']
        acceptance_wait_time_max = self.opts[u'acceptance_wait_time_max']
        if not acceptance_wait_time_max:
            acceptance_wait_time_max = acceptance_wait_time
        creds = None
        channel = salt.transport.client.AsyncReqChannel.factory(self.opts,
                                                                crypt=u'clear',
                                                                io_loop=self.io_loop)
        error = None
        while True:
            try:
                creds = yield self.sign_in(channel=channel)
            except SaltClientError as exc:
                error = exc
                break
            if creds == u'retry':
                if self.opts.get(u'detect_mode') is True:
                    error = SaltClientError(u'Detect mode is on')
                    break
                if self.opts.get(u'caller'):
                    print(u'Minion failed to authenticate with the master, '
                          u'has the minion key been accepted?')
                    sys.exit(2)
                if acceptance_wait_time:
                    log.info(
                        u'Waiting %s seconds before retry.', acceptance_wait_time
                    )
                    yield tornado.gen.sleep(acceptance_wait_time)
                if acceptance_wait_time < acceptance_wait_time_max:
                    acceptance_wait_time += acceptance_wait_time
                    log.debug(
                        u'Authentication wait time is %s', acceptance_wait_time
                    )
                continue
            break
        if not isinstance(creds, dict) or u'aes' not in creds:
            if self.opts.get(u'detect_mode') is True:
                error = SaltClientError(u'-|RETRY|-')
            try:
                del AsyncAuth.creds_map[self.__key(self.opts)]
            except KeyError:
                pass
            if not error:
                error = SaltClientError(u'Attempt to authenticate with the salt master failed')
            self._authenticate_future.set_exception(error)
        else:
            key = self.__key(self.opts)
            AsyncAuth.creds_map[key] = creds
            self._creds = creds
            self._crypticle = Crypticle(self.opts, creds[u'aes'])
            self._authenticate_future.set_result(True)  # mark the sign-in as complete
            # Notify the bus about creds change
            event = salt.utils.event.get_event(self.opts.get(u'__role'), opts=self.opts, listen=False)
            event.fire_event({u'key': key, u'creds': creds}, salt.utils.event.tagify(prefix=u'auth', suffix=u'creds'))

    @tornado.gen.coroutine
    def sign_in(self, timeout=60, safe=True, tries=1, channel=None):
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

        auth_timeout = self.opts.get(u'auth_timeout', None)
        if auth_timeout is not None:
            timeout = auth_timeout
        auth_safemode = self.opts.get(u'auth_safemode', None)
        if auth_safemode is not None:
            safe = auth_safemode
        auth_tries = self.opts.get(u'auth_tries', None)
        if auth_tries is not None:
            tries = auth_tries

        m_pub_fn = os.path.join(self.opts[u'pki_dir'], self.mpub)

        auth[u'master_uri'] = self.opts[u'master_uri']

        if not channel:
            channel = salt.transport.client.AsyncReqChannel.factory(self.opts,
                                                                crypt=u'clear',
                                                                io_loop=self.io_loop)

        sign_in_payload = self.minion_sign_in_payload()
        try:
            payload = yield channel.send(
                sign_in_payload,
                tries=tries,
                timeout=timeout
            )
        except SaltReqTimeoutError as e:
            if safe:
                log.warning(u'SaltReqTimeoutError: %s', e)
                raise tornado.gen.Return(u'retry')
            if self.opts.get(u'detect_mode') is True:
                raise tornado.gen.Return(u'retry')
            else:
                raise SaltClientError(u'Attempt to authenticate with the salt master failed with timeout error')
        if u'load' in payload:
            if u'ret' in payload[u'load']:
                if not payload[u'load'][u'ret']:
                    if self.opts[u'rejected_retry']:
                        log.error(
                            u'The Salt Master has rejected this minion\'s public '
                            u'key.\nTo repair this issue, delete the public key '
                            u'for this minion on the Salt Master.\nThe Salt '
                            u'Minion will attempt to to re-authenicate.'
                        )
                        raise tornado.gen.Return(u'retry')
                    else:
                        log.critical(
                            u'The Salt Master has rejected this minion\'s public '
                            u'key!\nTo repair this issue, delete the public key '
                            u'for this minion on the Salt Master and restart this '
                            u'minion.\nOr restart the Salt Master in open mode to '
                            u'clean out the keys. The Salt Minion will now exit.'
                        )
                        sys.exit(salt.defaults.exitcodes.EX_NOPERM)
                # has the master returned that its maxed out with minions?
                elif payload[u'load'][u'ret'] == u'full':
                    raise tornado.gen.Return(u'full')
                else:
                    log.error(
                        u'The Salt Master has cached the public key for this '
                        u'node, this salt minion will wait for %s seconds '
                        u'before attempting to re-authenticate',
                        self.opts[u'acceptance_wait_time']
                    )
                    raise tornado.gen.Return(u'retry')
        auth[u'aes'] = self.verify_master(payload, master_pub=u'token' in sign_in_payload)
        if not auth[u'aes']:
            log.critical(
                u'The Salt Master server\'s public key did not authenticate!\n'
                u'The master may need to be updated if it is a version of Salt '
                u'lower than %s, or\n'
                u'If you are confident that you are connecting to a valid Salt '
                u'Master, then remove the master public key and restart the '
                u'Salt Minion.\nThe master public key can be found '
                u'at:\n%s', salt.version.__version__, m_pub_fn
            )
            raise SaltClientError(u'Invalid master key')
        if self.opts.get(u'syndic_master', False):  # Is syndic
            syndic_finger = self.opts.get(u'syndic_finger', self.opts.get(u'master_finger', False))
            if syndic_finger:
                if salt.utils.pem_finger(m_pub_fn, sum_type=self.opts[u'hash_type']) != syndic_finger:
                    self._finger_fail(syndic_finger, m_pub_fn)
        else:
            if self.opts.get(u'master_finger', False):
                if salt.utils.pem_finger(m_pub_fn, sum_type=self.opts[u'hash_type']) != self.opts[u'master_finger']:
                    self._finger_fail(self.opts[u'master_finger'], m_pub_fn)
        auth[u'publish_port'] = payload[u'publish_port']
        raise tornado.gen.Return(auth)

    def get_keys(self):
        '''
        Return keypair object for the minion.

        :rtype: Crypto.PublicKey.RSA._RSAobj
        :return: The RSA keypair
        '''
        # Make sure all key parent directories are accessible
        user = self.opts.get(u'user', u'root')
        salt.utils.verify.check_path_traversal(self.opts[u'pki_dir'], user)

        if os.path.exists(self.rsa_path):
            with salt.utils.files.fopen(self.rsa_path) as f:
                key = RSA.importKey(f.read())
            log.debug(u'Loaded minion key: %s', self.rsa_path)
        else:
            log.info(u'Generating keys: %s', self.opts[u'pki_dir'])
            gen_keys(self.opts[u'pki_dir'],
                     u'minion',
                     self.opts[u'keysize'],
                     self.opts.get(u'user'))
            with salt.utils.files.fopen(self.rsa_path) as f:
                key = RSA.importKey(f.read())
        return key

    def gen_token(self, clear_tok):
        '''
        Encrypt a string with the minion private key to verify identity
        with the master.

        :param str clear_tok: A plaintext token to encrypt
        :return: Encrypted token
        :rtype: str
        '''
        return private_encrypt(self.get_keys(), clear_tok)

    def minion_sign_in_payload(self):
        '''
        Generates the payload used to authenticate with the master
        server. This payload consists of the passed in id_ and the ssh
        public key to encrypt the AES key sent back from the master.

        :return: Payload dictionary
        :rtype: dict
        '''
        payload = {}
        payload[u'cmd'] = u'_auth'
        payload[u'id'] = self.opts[u'id']
        try:
            pubkey_path = os.path.join(self.opts[u'pki_dir'], self.mpub)
            with salt.utils.files.fopen(pubkey_path) as f:
                pub = RSA.importKey(f.read())
            cipher = PKCS1_OAEP.new(pub)
            payload[u'token'] = cipher.encrypt(self.token)
        except Exception:
            pass
        with salt.utils.files.fopen(self.pub_path) as f:
            payload[u'pub'] = f.read()
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
            'sig': The message signature
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The public key of the sender.

        :rtype: str
        :return: The decrypted token that was provided, with padding.

        :rtype: str
        :return: The decrypted AES seed key
        '''
        if self.opts.get(u'auth_trb', False):
            log.warning(u'Auth Called: %s', u''.join(traceback.format_stack()))
        else:
            log.debug(u'Decrypting the current master AES key')
        key = self.get_keys()
        cipher = PKCS1_OAEP.new(key)
        key_str = cipher.decrypt(payload[u'aes'])
        if u'sig' in payload:
            m_path = os.path.join(self.opts[u'pki_dir'], self.mpub)
            if os.path.exists(m_path):
                try:
                    with salt.utils.files.fopen(m_path) as f:
                        mkey = RSA.importKey(f.read())
                except Exception:
                    return u'', u''
                digest = hashlib.sha256(key_str).hexdigest()
                if six.PY3:
                    digest = salt.utils.stringutils.to_bytes(digest)
                m_digest = public_decrypt(mkey.publickey(), payload[u'sig'])
                if m_digest != digest:
                    return u'', u''
        else:
            return u'', u''

        if six.PY3:
            key_str = salt.utils.stringutils.to_str(key_str)

        if u'_|-' in key_str:
            return key_str.split(u'_|-')
        else:
            if u'token' in payload:
                token = cipher.decrypt(payload[u'token'])
                return key_str, token
            elif not master_pub:
                return key_str, u''
        return u'', u''

    def verify_pubkey_sig(self, message, sig):
        '''
        Wraps the verify_signature method so we have
        additional checks.

        :rtype: bool
        :return: Success or failure of public key verification
        '''
        if self.opts[u'master_sign_key_name']:
            path = os.path.join(self.opts[u'pki_dir'],
                                self.opts[u'master_sign_key_name'] + u'.pub')

            if os.path.isfile(path):
                res = verify_signature(path,
                                       message,
                                       binascii.a2b_base64(sig))
            else:
                log.error(
                    u'Verification public key %s does not exist. You need to '
                    u'copy it from the master to the minions pki directory',
                    os.path.basename(path)
                )
                return False
            if res:
                log.debug(
                    u'Successfully verified signature of master public key '
                    u'with verification public key %s',
                    self.opts[u'master_sign_key_name'] + u'.pub'
                )
                return True
            else:
                log.debug(u'Failed to verify signature of public key')
                return False
        else:
            log.error(
                u'Failed to verify the signature of the message because the '
                u'verification key-pairs name is not defined. Please make '
                u'sure that master_sign_key_name is defined.'
            )
            return False

    def verify_signing_master(self, payload):
        try:
            if self.verify_pubkey_sig(payload[u'pub_key'],
                                      payload[u'pub_sig']):
                log.info(
                    u'Received signed and verified master pubkey from master %s',
                    self.opts[u'master']
                )
                m_pub_fn = os.path.join(self.opts[u'pki_dir'], self.mpub)
                uid = salt.utils.get_uid(self.opts.get(u'user', None))
                with salt.utils.files.fpopen(m_pub_fn, u'wb+', uid=uid) as wfh:
                    wfh.write(salt.utils.stringutils.to_bytes(payload[u'pub_key']))
                return True
            else:
                log.error(
                    u'Received signed public-key from master %s but signature '
                    u'verification failed!', self.opts[u'master']
                )
                return False
        except Exception as sign_exc:
            log.error(
                u'There was an error while verifying the masters public-key '
                u'signature'
            )
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
        if u'pub_sig' in payload and self.opts[u'verify_master_pubkey_sign']:
            return True
        # master and minion do NOT sign and do NOT verify
        elif u'pub_sig' not in payload and not self.opts[u'verify_master_pubkey_sign']:
            return True

        # master signs, but minion does NOT verify
        elif u'pub_sig' in payload and not self.opts[u'verify_master_pubkey_sign']:
            log.error(u'The masters sent its public-key signature, but signature '
                      u'verification is not enabled on the minion. Either enable '
                      u'signature verification on the minion or disable signing '
                      u'the public key on the master!')
            return False
        # master does NOT sign but minion wants to verify
        elif u'pub_sig' not in payload and self.opts[u'verify_master_pubkey_sign']:
            log.error(u'The master did not send its public-key signature, but '
                      u'signature verification is enabled on the minion. Either '
                      u'disable signature verification on the minion or enable '
                      u'signing the public on the master!')
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
                        u'The master failed to decrypt the random minion token'
                    )
                    return u''
            except Exception:
                log.error(
                    u'The master failed to decrypt the random minion token'
                )
                return u''
            return aes
        else:
            aes, token = self.decrypt_aes(payload, master_pub)
            return aes

    def verify_master(self, payload, master_pub=True):
        '''
        Verify that the master is the same one that was previously accepted.

        :param dict payload: The incoming payload. This is a dictionary which may have the following keys:
            'aes': The shared AES key
            'enc': The format of the message. ('clear', 'pub', etc)
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The RSA public key of the sender.
        :param bool master_pub: Operate as if minion had no master pubkey when it sent auth request, i.e. don't verify
        the minion signature

        :rtype: str
        :return: An empty string on verification failure. On success, the decrypted AES message in the payload.
        '''
        m_pub_fn = os.path.join(self.opts[u'pki_dir'], self.mpub)
        m_pub_exists = os.path.isfile(m_pub_fn)
        if m_pub_exists and master_pub and not self.opts[u'open_mode']:
            with salt.utils.files.fopen(m_pub_fn) as fp_:
                local_master_pub = fp_.read()

            if payload[u'pub_key'].replace(u'\n', u'').replace(u'\r', u'') != \
                    local_master_pub.replace(u'\n', u'').replace(u'\r', u''):
                if not self.check_auth_deps(payload):
                    return u''

                if self.opts[u'verify_master_pubkey_sign']:
                    if self.verify_signing_master(payload):
                        return self.extract_aes(payload, master_pub=False)
                    else:
                        return u''
                else:
                    # This is not the last master we connected to
                    log.error(
                        u'The master key has changed, the salt master could '
                        u'have been subverted, verify salt master\'s public '
                        u'key'
                    )
                    return u''

            else:
                if not self.check_auth_deps(payload):
                    return u''
                # verify the signature of the pubkey even if it has
                # not changed compared with the one we already have
                if self.opts[u'always_verify_signature']:
                    if self.verify_signing_master(payload):
                        return self.extract_aes(payload)
                    else:
                        log.error(
                            u'The masters public could not be verified. Is the '
                            u'verification pubkey %s up to date?',
                            self.opts[u'master_sign_key_name'] + u'.pub'
                        )
                        return u''

                else:
                    return self.extract_aes(payload)
        else:
            if not self.check_auth_deps(payload):
                return u''

            # verify the masters pubkey signature if the minion
            # has not received any masters pubkey before
            if self.opts[u'verify_master_pubkey_sign']:
                if self.verify_signing_master(payload):
                    return self.extract_aes(payload, master_pub=False)
                else:
                    return u''
            else:
                if not m_pub_exists:
                    # the minion has not received any masters pubkey yet, write
                    # the newly received pubkey to minion_master.pub
                    with salt.utils.files.fopen(m_pub_fn, u'wb+') as fp_:
                        fp_.write(salt.utils.stringutils.to_bytes(payload[u'pub_key']))
                return self.extract_aes(payload, master_pub=False)

    def _finger_fail(self, finger, master_key):
        log.critical(
            u'The specified fingerprint in the master configuration '
            u'file:\n%s\nDoes not match the authenticating master\'s '
            u'key:\n%s\nVerify that the configured fingerprint '
            u'matches the fingerprint of the correct master and that '
            u'this minion is not subject to a man-in-the-middle attack.',
            finger,
            salt.utils.pem_finger(master_key, sum_type=self.opts[u'hash_type'])
        )
        sys.exit(42)


# TODO: remove, we should just return a sync wrapper of AsyncAuth
class SAuth(AsyncAuth):
    '''
    Set up an object to maintain authentication with the salt master
    '''
    # This class is only a singleton per minion/master pair
    instances = weakref.WeakValueDictionary()

    def __new__(cls, opts, io_loop=None):
        '''
        Only create one instance of SAuth per __key()
        '''
        key = cls.__key(opts)
        auth = SAuth.instances.get(key)
        if auth is None:
            log.debug(u'Initializing new SAuth for %s', key)
            auth = object.__new__(cls)
            auth.__singleton_init__(opts)
            SAuth.instances[key] = auth
        else:
            log.debug(u'Re-using SAuth for %s', key)
        return auth

    @classmethod
    def __key(cls, opts, io_loop=None):
        return (opts[u'pki_dir'],     # where the keys are stored
                opts[u'id'],          # minion ID
                opts[u'master_uri'],  # master ID
                )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, io_loop=None):
        super(SAuth, self).__init__(opts, io_loop=io_loop)

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, io_loop=None):
        '''
        Init an Auth instance

        :param dict opts: Options for this server
        :return: Auth instance
        :rtype: Auth
        '''
        self.opts = opts
        if six.PY2:
            self.token = Crypticle.generate_key_string()
        else:
            self.token = salt.utils.stringutils.to_bytes(Crypticle.generate_key_string())
        self.serial = salt.payload.Serial(self.opts)
        self.pub_path = os.path.join(self.opts[u'pki_dir'], u'minion.pub')
        self.rsa_path = os.path.join(self.opts[u'pki_dir'], u'minion.pem')
        if u'syndic_master' in self.opts:
            self.mpub = u'syndic_master.pub'
        elif u'alert_master' in self.opts:
            self.mpub = u'monitor_master.pub'
        else:
            self.mpub = u'minion_master.pub'
        if not os.path.isfile(self.pub_path):
            self.get_keys()

    @property
    def creds(self):
        if not hasattr(self, u'_creds'):
            self.authenticate()
        return self._creds

    @property
    def crypticle(self):
        if not hasattr(self, u'_crypticle'):
            self.authenticate()
        return self._crypticle

    def authenticate(self, _=None):  # TODO: remove unused var
        '''
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master AES key.

        :rtype: Crypticle
        :returns: A crypticle used for encryption operations
        '''
        acceptance_wait_time = self.opts[u'acceptance_wait_time']
        acceptance_wait_time_max = self.opts[u'acceptance_wait_time_max']
        channel = salt.transport.client.ReqChannel.factory(self.opts, crypt=u'clear')
        if not acceptance_wait_time_max:
            acceptance_wait_time_max = acceptance_wait_time
        while True:
            creds = self.sign_in(channel=channel)
            if creds == u'retry':
                if self.opts.get(u'caller'):
                    print(u'Minion failed to authenticate with the master, '
                          u'has the minion key been accepted?')
                    sys.exit(2)
                if acceptance_wait_time:
                    log.info(u'Waiting %s seconds before retry.', acceptance_wait_time)
                    time.sleep(acceptance_wait_time)
                if acceptance_wait_time < acceptance_wait_time_max:
                    acceptance_wait_time += acceptance_wait_time
                    log.debug(u'Authentication wait time is %s', acceptance_wait_time)
                continue
            break
        self._creds = creds
        self._crypticle = Crypticle(self.opts, creds[u'aes'])

    def sign_in(self, timeout=60, safe=True, tries=1, channel=None):
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

        auth_timeout = self.opts.get(u'auth_timeout', None)
        if auth_timeout is not None:
            timeout = auth_timeout
        auth_safemode = self.opts.get(u'auth_safemode', None)
        if auth_safemode is not None:
            safe = auth_safemode
        auth_tries = self.opts.get(u'auth_tries', None)
        if auth_tries is not None:
            tries = auth_tries

        m_pub_fn = os.path.join(self.opts[u'pki_dir'], self.mpub)

        auth[u'master_uri'] = self.opts[u'master_uri']

        if not channel:
            channel = salt.transport.client.ReqChannel.factory(self.opts, crypt=u'clear')

        sign_in_payload = self.minion_sign_in_payload()
        try:
            payload = channel.send(
                sign_in_payload,
                tries=tries,
                timeout=timeout
            )
        except SaltReqTimeoutError as e:
            if safe:
                log.warning(u'SaltReqTimeoutError: %s', e)
                return u'retry'
            raise SaltClientError(u'Attempt to authenticate with the salt master failed with timeout error')

        if u'load' in payload:
            if u'ret' in payload[u'load']:
                if not payload[u'load'][u'ret']:
                    if self.opts[u'rejected_retry']:
                        log.error(
                            u'The Salt Master has rejected this minion\'s public '
                            u'key.\nTo repair this issue, delete the public key '
                            u'for this minion on the Salt Master.\nThe Salt '
                            u'Minion will attempt to to re-authenicate.'
                        )
                        return u'retry'
                    else:
                        log.critical(
                            u'The Salt Master has rejected this minion\'s public '
                            u'key!\nTo repair this issue, delete the public key '
                            u'for this minion on the Salt Master and restart this '
                            u'minion.\nOr restart the Salt Master in open mode to '
                            u'clean out the keys. The Salt Minion will now exit.'
                        )
                        sys.exit(salt.defaults.exitcodes.EX_NOPERM)
                # has the master returned that its maxed out with minions?
                elif payload[u'load'][u'ret'] == u'full':
                    return u'full'
                else:
                    log.error(
                        u'The Salt Master has cached the public key for this '
                        u'node. If this is the first time connecting to this '
                        u'master then this key may need to be accepted using '
                        u'\'salt-key -a %s\' on the salt master. This salt '
                        u'minion will wait for %s seconds before attempting '
                        u'to re-authenticate.',
                        self.opts[u'id'], self.opts[u'acceptance_wait_time']
                    )
                    return u'retry'
        auth[u'aes'] = self.verify_master(payload, master_pub=u'token' in sign_in_payload)
        if not auth[u'aes']:
            log.critical(
                u'The Salt Master server\'s public key did not authenticate!\n'
                u'The master may need to be updated if it is a version of Salt '
                u'lower than %s, or\n'
                u'If you are confident that you are connecting to a valid Salt '
                u'Master, then remove the master public key and restart the '
                u'Salt Minion.\nThe master public key can be found '
                u'at:\n%s', salt.version.__version__, m_pub_fn
            )
            sys.exit(42)
        if self.opts.get(u'syndic_master', False):  # Is syndic
            syndic_finger = self.opts.get(u'syndic_finger', self.opts.get(u'master_finger', False))
            if syndic_finger:
                if salt.utils.pem_finger(m_pub_fn, sum_type=self.opts[u'hash_type']) != syndic_finger:
                    self._finger_fail(syndic_finger, m_pub_fn)
        else:
            if self.opts.get(u'master_finger', False):
                if salt.utils.pem_finger(m_pub_fn, sum_type=self.opts[u'hash_type']) != self.opts[u'master_finger']:
                    self._finger_fail(self.opts[u'master_finger'], m_pub_fn)
        auth[u'publish_port'] = payload[u'publish_port']
        return auth


class Crypticle(object):
    '''
    Authenticated encryption class

    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    '''

    PICKLE_PAD = b'pickle::'  # future lint: disable=non-unicode-string
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
        b64key = base64.b64encode(key)
        if six.PY3:
            b64key = b64key.decode(u'utf-8')
        # Return data must be a base64-encoded string, not a unicode type
        return b64key.replace('\n', '')  # future lint: disable=non-unicode-string

    @classmethod
    def extract_keys(cls, key_string, key_size):
        if six.PY2:
            key = key_string.decode(u'base64')
        else:
            key = salt.utils.stringutils.to_bytes(base64.b64decode(key_string))
        assert len(key) == key_size / 8 + cls.SIG_SIZE, u'invalid key'
        return key[:-cls.SIG_SIZE], key[-cls.SIG_SIZE:]

    def encrypt(self, data):
        '''
        encrypt data with AES-CBC and sign it with HMAC-SHA256
        '''
        aes_key, hmac_key = self.keys
        pad = self.AES_BLOCK_SIZE - len(data) % self.AES_BLOCK_SIZE
        if six.PY2:
            data = data + pad * chr(pad)
        else:
            data = data + salt.utils.stringutils.to_bytes(pad * chr(pad))
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
        if six.PY3 and not isinstance(data, bytes):
            data = salt.utils.stringutils.to_bytes(data)
        mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
        if len(mac_bytes) != len(sig):
            log.debug(u'Failed to authenticate message')
            raise AuthenticationError(u'message authentication failed')
        result = 0

        if six.PY2:
            for zipped_x, zipped_y in zip(mac_bytes, sig):
                result |= ord(zipped_x) ^ ord(zipped_y)
        else:
            for zipped_x, zipped_y in zip(mac_bytes, sig):
                result |= zipped_x ^ zipped_y
        if result != 0:
            log.debug(u'Failed to authenticate message')
            raise AuthenticationError(u'message authentication failed')
        iv_bytes = data[:self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE:]
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
        if six.PY2:
            return data[:-ord(data[-1])]
        else:
            return data[:-data[-1]]

    def dumps(self, obj):
        '''
        Serialize and encrypt a python object
        '''
        return self.encrypt(self.PICKLE_PAD + self.serial.dumps(obj))

    def loads(self, data, raw=False):
        '''
        Decrypt and un-serialize a python object
        '''
        data = self.decrypt(data)
        # simple integrity check to verify that we got meaningful data
        if not data.startswith(self.PICKLE_PAD):
            return {}
        load = self.serial.loads(data[len(self.PICKLE_PAD):], raw=raw)
        return load
