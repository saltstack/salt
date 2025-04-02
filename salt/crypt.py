"""
The crypt module manages all of the cryptography functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
"""

import base64
import binascii
import copy
import getpass
import hashlib
import hmac
import logging
import os
import pathlib
import random
import stat
import sys
import tempfile
import time
import traceback
import uuid
import weakref

import tornado.gen

import salt.channel.client
import salt.defaults.exitcodes
import salt.payload
import salt.utils.crypt
import salt.utils.decorators
import salt.utils.event
import salt.utils.files
import salt.utils.rsax931
import salt.utils.sdb
import salt.utils.stringutils
import salt.utils.user
import salt.utils.verify
import salt.version
from salt.exceptions import (
    AuthenticationError,
    InvalidKeyError,
    MasterExit,
    SaltClientError,
    SaltReqTimeoutError,
    UnsupportedAlgorithm,
)

try:
    import cryptography.exceptions
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


log = logging.getLogger(__name__)

OAEP = "OAEP"
PKCS1v15 = "PKCS1v15"

SHA1 = "SHA1"
SHA224 = "SHA224"

OAEP_SHA1 = f"{OAEP}-{SHA1}"
OAEP_SHA224 = f"{OAEP}-{SHA224}"

PKCS1v15_SHA1 = f"{PKCS1v15}-{SHA1}"
PKCS1v15_SHA224 = f"{PKCS1v15}-{SHA224}"


VALID_HASHES = (
    SHA1,
    SHA224,
)

VALID_PADDING_FOR_SIGNING = (PKCS1v15,)
VALID_PADDING_FOR_ENCRYPTION = (OAEP,)
VALID_ENCRYPTION_ALGORITHMS = (
    OAEP_SHA1,
    OAEP_SHA224,
)
VALID_SIGNING_ALGORITHMS = (
    PKCS1v15_SHA1,
    PKCS1v15_SHA224,
)


def fips_enabled():
    if HAS_CRYPTOGRAPHY:
        import cryptography.hazmat.backends.openssl.backend

        return cryptography.hazmat.backends.openssl.backend._fips_enabled


def clean_key(key):
    """
    Clean the key so that it only has unix style line endings (\\n)
    """
    return "\n".join(key.strip().splitlines())


def read_dropfile(cachedir):
    dfn = os.path.join(cachedir, ".dfn")
    try:
        with salt.utils.files.fopen(dfn, "r") as fp:
            return fp.read()
    except FileNotFoundError:
        pass


def dropfile(cachedir, user=None, master_id=""):
    """
    Set an AES dropfile to request the master update the publish session key
    """
    dfn_next = os.path.join(cachedir, ".dfn-next")
    dfn = os.path.join(cachedir, ".dfn")
    # set a mask (to avoid a race condition on file creation) and store original.
    with salt.utils.files.set_umask(0o277):
        log.info("Rotating AES key")
        if os.path.isfile(dfn):
            log.info("AES key rotation already requested")
            return

        if os.path.isfile(dfn) and not os.access(dfn, os.W_OK):
            os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
        with salt.utils.files.fopen(dfn_next, "w+") as fp_:
            fp_.write(master_id)
        os.chmod(dfn_next, stat.S_IRUSR)
        if user:
            try:
                import pwd

                uid = pwd.getpwnam(user).pw_uid
                os.chown(dfn_next, uid, -1)
            except (KeyError, ImportError, OSError):
                pass
        os.rename(dfn_next, dfn)


def gen_keys(keydir, keyname, keysize, user=None, passphrase=None, e=65537):
    """
    Generate a RSA public keypair for use with salt

    :param str keydir: The directory to write the keypair to
    :param str keyname: The type of salt server for whom this key should be written. (i.e. 'master' or 'minion')
    :param int keysize: The number of bits in the key
    :param str user: The user on the system who should own this keypair
    :param str passphrase: The passphrase which should be used to encrypt the private key

    :rtype: str
    :return: Path on the filesystem to the RSA private key
    """
    base = os.path.join(keydir, keyname)
    priv = f"{base}.pem"
    pub = f"{base}.pub"

    gen = rsa.generate_private_key(e, keysize)

    if os.path.isfile(priv):
        # Between first checking and the generation another process has made
        # a key! Use the winner's key
        return priv

    # Do not try writing anything, if directory has no permissions.
    if not os.access(keydir, os.W_OK):
        raise OSError(
            'Write access denied to "{}" for user "{}".'.format(
                os.path.abspath(keydir), getpass.getuser()
            )
        )

    with salt.utils.files.set_umask(0o277):
        with salt.utils.files.fopen(priv, "wb+") as f:
            if passphrase:
                enc = serialization.BestAvailableEncryption(passphrase.encode())
                _format = serialization.PrivateFormat.TraditionalOpenSSL
                if fips_enabled():
                    _format = serialization.PrivateFormat.PKCS8
            else:
                enc = serialization.NoEncryption()
                _format = serialization.PrivateFormat.TraditionalOpenSSL
            pem = gen.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=_format,
                encryption_algorithm=enc,
            )
            f.write(pem)

    pubkey = gen.public_key()
    with salt.utils.files.fopen(pub, "wb+") as f:
        pem = pubkey.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        f.write(pem)

    os.chmod(priv, 0o400)
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


class BaseKey:

    @staticmethod
    def parse_padding_for_signing(algorithm):
        if algorithm not in VALID_SIGNING_ALGORITHMS:
            raise UnsupportedAlgorithm(f"Invalid signing algorithm: {algorithm}")
        _pad, _hash = algorithm.split("-", 1)
        if _pad not in VALID_PADDING_FOR_SIGNING:
            raise UnsupportedAlgorithm(f"Invalid padding algorithm: {_pad}")
        return getattr(padding, _pad)

    @staticmethod
    def parse_padding_for_encryption(algorithm):
        if algorithm not in VALID_ENCRYPTION_ALGORITHMS:
            raise UnsupportedAlgorithm(f"Invalid encryption algorithm: {algorithm}")
        _pad, _hash = algorithm.split("-", 1)
        if _pad not in VALID_PADDING_FOR_ENCRYPTION:
            raise UnsupportedAlgorithm(f"Invalid padding algorithm: {_pad}")
        return getattr(padding, _pad)

    @staticmethod
    def parse_hash(algorithm):
        if "-" not in algorithm:
            raise UnsupportedAlgorithm(f"Invalid encryption algorithm: {algorithm}")
        _pad, _hash = algorithm.split("-", 1)
        if _hash not in VALID_HASHES:
            raise Exception("Invalid hashing algorithm")
        return getattr(hashes, _hash)


class PrivateKey(BaseKey):

    def __init__(self, path, passphrase=None):
        self.key = get_rsa_key(path, passphrase)

    def encrypt(self, data):
        pem = self.key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return salt.utils.rsax931.RSAX931Signer(pem).sign(data)

    def sign(self, data, algorithm=PKCS1v15_SHA1):
        _padding = self.parse_padding_for_signing(algorithm)
        _hash = self.parse_hash(algorithm)
        try:
            return self.key.sign(
                salt.utils.stringutils.to_bytes(data), _padding(), _hash()
            )
        except cryptography.exceptions.UnsupportedAlgorithm:
            raise UnsupportedAlgorithm(f"Unsupported algorithm: {algorithm}")

    def decrypt(self, data, algorithm=OAEP_SHA1):
        _padding = self.parse_padding_for_encryption(algorithm)
        _hash = self.parse_hash(algorithm)
        try:
            return self.key.decrypt(
                data,
                _padding(
                    mgf=padding.MGF1(algorithm=_hash()),
                    algorithm=_hash(),
                    label=None,
                ),
            )
        except cryptography.exceptions.UnsupportedAlgorithm:
            raise UnsupportedAlgorithm(f"Unsupported algorithm: {algorithm}")


class PublicKey(BaseKey):
    def __init__(self, path):
        with salt.utils.files.fopen(path, "rb") as fp:
            try:
                self.key = serialization.load_pem_public_key(fp.read())
            except ValueError as exc:
                raise InvalidKeyError("Invalid key")

    def encrypt(self, data, algorithm=OAEP_SHA1):
        _padding = self.parse_padding_for_encryption(algorithm)
        _hash = self.parse_hash(algorithm)
        bdata = salt.utils.stringutils.to_bytes(data)
        try:
            return self.key.encrypt(
                bdata,
                _padding(
                    mgf=padding.MGF1(algorithm=_hash()),
                    algorithm=_hash(),
                    label=None,
                ),
            )
        except cryptography.exceptions.UnsupportedAlgorithm:
            raise UnsupportedAlgorithm(f"Unsupported algorithm: {algorithm}")

    def verify(self, data, signature, algorithm=PKCS1v15_SHA1):
        _padding = self.parse_padding_for_signing(algorithm)
        _hash = self.parse_hash(algorithm)
        try:
            self.key.verify(
                salt.utils.stringutils.to_bytes(signature),
                salt.utils.stringutils.to_bytes(data),
                _padding(),
                _hash(),
            )
        except cryptography.exceptions.InvalidSignature:
            return False
        return True

    def decrypt(self, data):
        pem = self.key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        verifier = salt.utils.rsax931.RSAX931Verifier(pem)
        return verifier.verify(data)


@salt.utils.decorators.memoize
def _get_key_with_evict(path, timestamp, passphrase):
    """
    Load a private key from disk.  `timestamp` above is intended to be the
    timestamp of the file's last modification. This fn is memoized so if it is
    called with the same path and timestamp (the file's last modified time) the
    second time the result is returned from the memoization.  If the file gets
    modified then the params are different and the key is loaded from disk.
    """
    log.debug("salt.crypt._get_key_with_evict: Loading private key")
    if passphrase:
        password = passphrase.encode()
    else:
        password = None
    with salt.utils.files.fopen(path, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=password,
        )


def get_rsa_key(path, passphrase):
    """
    Read a private key off the disk.  Poor man's simple cache in effect here,
    we memoize the result of calling _get_rsa_with_evict.  This means the first
    time _get_key_with_evict is called with a path and a timestamp the result
    is cached.  If the file (the private key) does not change then its
    timestamp will not change and the next time the result is returned from the
    cache.  If the key DOES change the next time _get_rsa_with_evict is called
    it is called with different parameters and the fn is run fully to retrieve
    the key from disk.
    """
    log.debug("salt.crypt.get_rsa_key: Loading private key")
    return _get_key_with_evict(path, str(os.path.getmtime(path)), passphrase)


def get_rsa_pub_key(path):
    """
    Read a public key off the disk.
    """
    log.debug("salt.crypt.get_rsa_pub_key: Loading public key")
    try:
        with salt.utils.files.fopen(path, "rb") as fp:
            return serialization.load_pem_public_key(fp.read())
    except ValueError:
        raise InvalidKeyError("Encountered bad RSA public key")
    except cryptography.exceptions.UnsupportedAlgorithm:
        raise InvalidKeyError("Unsupported key algorithm")


def sign_message(privkey_path, message, passphrase=None, algorithm=PKCS1v15_SHA1):
    """
    Use Crypto.Signature.PKCS1_v1_5 to sign a message. Returns the signature.
    """
    return PrivateKey(privkey_path, passphrase).sign(message, algorithm)


def verify_signature(pubkey_path, message, signature, algorithm=PKCS1v15_SHA1):
    """
    Use Crypto.Signature.PKCS1_v1_5 to verify the signature on a message.
    Returns True for valid signature.
    """
    log.debug("salt.crypt.verify_signature: Loading public key")
    return PublicKey(pubkey_path).verify(message, signature, algorithm)


def gen_signature(priv_path, pub_path, sign_path, passphrase=None):
    """
    creates a signature for the given public-key with
    the given private key and writes it to sign_path
    """

    with salt.utils.files.fopen(pub_path) as fp_:
        mpub_64 = fp_.read()

    mpub_sig = sign_message(priv_path, mpub_64, passphrase)
    mpub_sig_64 = binascii.b2a_base64(mpub_sig)
    if os.path.isfile(sign_path):
        return False
    log.trace(
        "Calculating signature for %s with %s",
        os.path.basename(pub_path),
        os.path.basename(priv_path),
    )

    if os.path.isfile(sign_path):
        log.trace(
            "Signature file %s already exists, please remove it first and try again",
            sign_path,
        )
    else:
        with salt.utils.files.fopen(sign_path, "wb+") as sig_f:
            sig_f.write(salt.utils.stringutils.to_bytes(mpub_sig_64))
        log.trace("Wrote signature to %s", sign_path)
    return True


def pwdata_decrypt(rsa_key, pwdata):
    key = serialization.load_pem_private_key(rsa_key.encode(), password=None)
    password = key.decrypt(
        pwdata,
        padding.PKCS1v15(),
    )
    return salt.utils.stringutils.to_unicode(password)


class MasterKeys(dict):
    """
    The Master Keys class is used to manage the RSA public key pair used for
    authentication by the master.

    It also generates a signing key-pair if enabled with master_sign_key_name.
    """

    def __init__(self, opts):
        super().__init__()
        self.opts = opts
        self.master_pub_path = os.path.join(self.opts["pki_dir"], "master.pub")
        self.master_rsa_path = os.path.join(self.opts["pki_dir"], "master.pem")
        key_pass = salt.utils.sdb.sdb_get(self.opts["key_pass"], self.opts)
        self.master_key = self.__get_keys(passphrase=key_pass)

        self.cluster_pub_path = None
        self.cluster_rsa_path = None
        self.cluster_key = None
        if self.opts["cluster_id"]:
            self.cluster_pub_path = os.path.join(
                self.opts["cluster_pki_dir"], "cluster.pub"
            )
            self.cluster_rsa_path = os.path.join(
                self.opts["cluster_pki_dir"], "cluster.pem"
            )
            self.cluster_shared_path = os.path.join(
                self.opts["cluster_pki_dir"],
                "peers",
                f"{self.opts['id']}.pub",
            )
            self.check_master_shared_pub()
            key_pass = salt.utils.sdb.sdb_get(self.opts["cluster_key_pass"], self.opts)
            self.cluster_key = self.__get_keys(
                name="cluster",
                passphrase=key_pass,
                pki_dir=self.opts["cluster_pki_dir"],
            )
        self.pub_signature = None

        # set names for the signing key-pairs
        if opts["master_sign_pubkey"]:

            # if only the signature is available, use that
            if opts["master_use_pubkey_signature"]:
                self.sig_path = os.path.join(
                    self.opts["pki_dir"], opts["master_pubkey_signature"]
                )
                if os.path.isfile(self.sig_path):
                    with salt.utils.files.fopen(self.sig_path) as fp_:
                        self.pub_signature = clean_key(fp_.read())
                    log.info(
                        "Read %s's signature from %s",
                        os.path.basename(self.pub_path),
                        self.opts["master_pubkey_signature"],
                    )
                else:
                    log.error(
                        "Signing the master.pub key with a signature is "
                        "enabled but no signature file found at the defined "
                        "location %s",
                        self.sig_path,
                    )
                    log.error(
                        "The signature-file may be either named differently "
                        "or has to be created with 'salt-key --gen-signature'"
                    )
                    sys.exit(1)

            # create a new signing key-pair to sign the masters
            # auth-replies when a minion tries to connect
            else:
                key_pass = salt.utils.sdb.sdb_get(
                    self.opts["signing_key_pass"], self.opts
                )
                self.pub_sign_path = os.path.join(
                    self.opts["pki_dir"], opts["master_sign_key_name"] + ".pub"
                )
                self.rsa_sign_path = os.path.join(
                    self.opts["pki_dir"], opts["master_sign_key_name"] + ".pem"
                )
                self.sign_key = self.__get_keys(name=opts["master_sign_key_name"])

    # We need __setstate__ and __getstate__ to avoid pickling errors since
    # some of the member variables correspond to Cython objects which are
    # not picklable.
    # These methods are only used when pickling so will not be used on
    # non-Windows platforms.
    def __setstate__(self, state):
        self.__init__(state["opts"])

    def __getstate__(self):
        return {"opts": self.opts}

    @property
    def key(self):
        if self.cluster_key:
            return self.cluster_key
        return self.master_key

    @property
    def pub_path(self):
        if self.cluster_pub_path:
            return self.cluster_pub_path
        return self.master_pub_path

    @property
    def rsa_path(self):
        if self.cluster_rsa_path:
            return self.cluster_rsa_path
        return self.master_rsa_path

    def __key_exists(self, name="master", passphrase=None, pki_dir=None):
        if pki_dir is None:
            pki_dir = self.opts["pki_dir"]
        path = os.path.join(pki_dir, name + ".pem")
        return os.path.exists(path)

    def __get_keys(self, name="master", passphrase=None, pki_dir=None):
        """
        Returns a key object for a key in the pki-dir
        """
        if pki_dir is None:
            pki_dir = self.opts["pki_dir"]
        path = os.path.join(pki_dir, name + ".pem")
        if not self.__key_exists(name, passphrase, pki_dir):
            log.info("Generating %s keys: %s", name, pki_dir)
            gen_keys(
                pki_dir,
                name,
                self.opts["keysize"],
                self.opts.get("user"),
                passphrase,
            )
        try:
            key = PrivateKey(path, passphrase)
        except ValueError as e:
            message = f"Unable to read key: {path}; file may be corrupt"
        except TypeError as e:
            message = f"Unable to read key: {path}; passphrase may be incorrect"
        except InvalidKeyError as e:
            message = f"Unable to read key: {path}; key contains unsupported algorithm"
        except cryptography.exceptions.UnsupportedAlgorithm as e:
            message = f"Unable to read key: {path}; key contains unsupported algorithm"
        else:
            log.debug("Loaded %s key: %s", name, path)
            return key
        log.error(message)
        raise MasterExit(message)

    def get_pub_str(self, name="master"):
        """
        Return the string representation of a public key
        in the pki-directory
        """
        if self.cluster_pub_path:
            path = self.cluster_pub_path
        else:
            path = self.master_pub_path
        # XXX We should always have a key present when this is called, if not
        # it's an error.
        # if not os.path.isfile(path):
        #     raise RuntimeError(f"The key {path} does not exist.")
        if not os.path.isfile(path):
            pubkey = self.key.public_key()
            with salt.utils.files.fopen(path, "wb+") as f:
                f.write(
                    pubkey.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                )
        with salt.utils.files.fopen(path) as rfh:
            return clean_key(rfh.read())

    def get_ckey_paths(self):
        return self.cluster_pub_path, self.cluster_rsa_path

    def get_mkey_paths(self):
        return self.pub_path, self.rsa_path

    def get_sign_paths(self):
        return self.pub_sign_path, self.rsa_sign_path

    def pubkey_signature(self):
        """
        returns the base64 encoded signature from the signature file
        or None if the master has its own signing keys
        """
        return self.pub_signature

    def check_master_shared_pub(self):
        """
        Check the status of the master's shared public key.

        If the shared master key does not exist, write this master's public key
        to the shared location. Otherwise validate the shared key matches our
        key. Failed validation raises MasterExit
        """
        shared_pub = pathlib.Path(self.cluster_shared_path)
        master_pub = pathlib.Path(self.master_pub_path)
        if shared_pub.exists():
            if shared_pub.read_bytes() != master_pub.read_bytes():
                message = (
                    f"Shared key does not match, remove it to continue: {shared_pub}"
                )
                log.error(message)
                raise MasterExit(message)
        else:
            # permissions
            log.debug("Writing shared key %s", shared_pub)
            shared_pub.write_bytes(master_pub.read_bytes())


class AsyncAuth:
    """
    Set up an Async object to maintain authentication with the salt master
    """

    # This class is only a singleton per minion/master pair
    # mapping of io_loop -> {key -> auth}
    instance_map = weakref.WeakKeyDictionary()

    # mapping of key -> creds
    creds_map = {}

    def __new__(cls, opts, io_loop=None):
        """
        Only create one instance of AsyncAuth per __key()
        """
        # do we have any mapping for this io_loop
        io_loop = io_loop or tornado.ioloop.IOLoop.current()
        if io_loop not in AsyncAuth.instance_map:
            AsyncAuth.instance_map[io_loop] = weakref.WeakValueDictionary()
        loop_instance_map = AsyncAuth.instance_map[io_loop]

        key = cls.__key(opts)
        auth = loop_instance_map.get(key)
        if auth is None:
            log.debug("Initializing new AsyncAuth for %s", key)
            # we need to make a local variable for this, as we are going to store
            # it in a WeakValueDictionary-- which will remove the item if no one
            # references it-- this forces a reference while we return to the caller
            auth = object.__new__(cls)
            auth.__singleton_init__(opts, io_loop=io_loop)
            loop_instance_map[key] = auth
        else:
            log.debug("Re-using AsyncAuth for %s", key)
        return auth

    @classmethod
    def __key(cls, opts, io_loop=None):
        return (
            opts["pki_dir"],  # where the keys are stored
            opts["id"],  # minion ID
            opts["master_uri"],  # master ID
        )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, io_loop=None):
        pass

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, io_loop=None):
        """
        Init an Auth instance

        :param dict opts: Options for this server
        :return: Auth instance
        :rtype: Auth
        """
        self.opts = opts
        self.token = salt.utils.stringutils.to_bytes(Crypticle.generate_key_string())
        self.pub_path = os.path.join(self.opts["pki_dir"], "minion.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "minion.pem")
        if self.opts["__role"] == "syndic":
            self.mpub = "syndic_master.pub"
        else:
            self.mpub = "minion_master.pub"
        if not os.path.isfile(self.pub_path):
            self.get_keys()
        self.io_loop = io_loop or tornado.ioloop.IOLoop.current()
        key = self.__key(self.opts)
        # TODO: if we already have creds for this key, lets just re-use
        if key in AsyncAuth.creds_map:
            creds = AsyncAuth.creds_map[key]
            self._creds = creds
            self._crypticle = Crypticle(self.opts, creds["aes"])
            self._authenticate_future = tornado.concurrent.Future()
            self._authenticate_future.set_result(True)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls, copy.deepcopy(self.opts, memo))
        memo[id(self)] = result
        for key in self.__dict__:
            if key in ("io_loop",):
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
        return (
            hasattr(self, "_authenticate_future")
            and self._authenticate_future.done()
            and self._authenticate_future.exception() is None
        )

    def invalidate(self):
        if self.authenticated:
            del self._authenticate_future
            key = self.__key(self.opts)
            if key in AsyncAuth.creds_map:
                del AsyncAuth.creds_map[key]

    def authenticate(self, callback=None):
        """
        Ask for this client to reconnect to the origin

        This function will de-dupe all calls here and return a *single* future
        for the sign-in-- whis way callers can all assume there aren't others
        """
        # if an auth is in flight-- and not done-- just pass that back as the future to wait on
        if (
            hasattr(self, "_authenticate_future")
            and not self._authenticate_future.done()
        ):
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
        """
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master AES key.

        :rtype: Crypticle
        :returns: A crypticle used for encryption operations
        """
        acceptance_wait_time = self.opts["acceptance_wait_time"]
        acceptance_wait_time_max = self.opts["acceptance_wait_time_max"]
        if not acceptance_wait_time_max:
            acceptance_wait_time_max = acceptance_wait_time
        creds = None

        with salt.channel.client.AsyncReqChannel.factory(
            self.opts, crypt="clear", io_loop=self.io_loop
        ) as channel:
            error = None
            while True:
                try:
                    creds = yield self.sign_in(channel=channel)
                except SaltClientError as exc:
                    error = exc
                    break
                if creds == "retry":
                    if self.opts.get("detect_mode") is True:
                        error = SaltClientError("Detect mode is on")
                        break
                    if self.opts.get("caller"):
                        # We have a list of masters, so we should break
                        # and try the next one in the list.
                        if self.opts.get("local_masters", None):
                            error = SaltClientError(
                                "Minion failed to authenticate"
                                " with the master, has the "
                                "minion key been accepted?"
                            )
                            break
                        else:
                            print(
                                "Minion failed to authenticate with the master, "
                                "has the minion key been accepted?"
                            )
                            sys.exit(2)
                    if acceptance_wait_time:
                        log.info(
                            "Waiting %s seconds before retry.", acceptance_wait_time
                        )
                        yield tornado.gen.sleep(acceptance_wait_time)
                    if acceptance_wait_time < acceptance_wait_time_max:
                        acceptance_wait_time += acceptance_wait_time
                        log.debug(
                            "Authentication wait time is %s", acceptance_wait_time
                        )
                    continue
                elif creds == "bad enc algo":
                    log.error(
                        "This minion is using a encryption algorithm that is "
                        "not supported by it's Master. Please check your minion configutation."
                    )
                    break
                elif creds == "bad sig algo":
                    log.error(
                        "This minion is using a signing algorithm that is "
                        "not supported by it's Master. Please check your minion configutation."
                    )
                    break
                break
            if not isinstance(creds, dict) or "aes" not in creds:
                if self.opts.get("detect_mode") is True:
                    error = SaltClientError("-|RETRY|-")
                try:
                    del AsyncAuth.creds_map[self.__key(self.opts)]
                except KeyError:
                    pass
                if not error:
                    error = SaltClientError(
                        "Attempt to authenticate with the salt master failed"
                    )
                self._authenticate_future.set_exception(error)
            else:
                key = self.__key(self.opts)
                if key not in AsyncAuth.creds_map:
                    log.debug("%s Got new master aes key.", self)
                    AsyncAuth.creds_map[key] = creds
                    self._creds = creds
                    self._crypticle = Crypticle(self.opts, creds["aes"])
                elif self._creds["aes"] != creds["aes"]:
                    log.debug("%s The master's aes key has changed.", self)
                    AsyncAuth.creds_map[key] = creds
                    self._creds = creds
                    self._crypticle = Crypticle(self.opts, creds["aes"])

                self._authenticate_future.set_result(
                    True
                )  # mark the sign-in as complete
                # Notify the bus about creds change
                if self.opts.get("auth_events") is True:
                    with salt.utils.event.get_event(
                        self.opts.get("__role"), opts=self.opts, listen=False
                    ) as event:
                        event.fire_event(
                            {"key": key, "creds": creds},
                            salt.utils.event.tagify(prefix="auth", suffix="creds"),
                        )

    @tornado.gen.coroutine
    def sign_in(self, timeout=60, safe=True, tries=1, channel=None):
        """
        Send a sign in request to the master, sets the key information and
        returns a dict containing the master publish interface to bind to
        and the decrypted aes key for transport decryption.

        :param int timeout: Number of seconds to wait before timing out the sign-in request
        :param bool safe: If True, do not raise an exception on timeout. Retry instead.
        :param int tries: The number of times to try to authenticate before giving up.

        :raises SaltReqTimeoutError: If the sign-in request has timed out and :param safe: is not set

        :return: Return a string on failure indicating the reason for failure. On success, return a dictionary
        with the publication port and the shared AES key.

        """

        auth_timeout = self.opts.get("auth_timeout", None)
        if auth_timeout is not None:
            timeout = auth_timeout
        auth_safemode = self.opts.get("auth_safemode", None)
        if auth_safemode is not None:
            safe = auth_safemode
        auth_tries = self.opts.get("auth_tries", None)
        if auth_tries is not None:
            tries = auth_tries

        close_channel = False
        if not channel:
            close_channel = True
            channel = salt.channel.client.AsyncReqChannel.factory(
                self.opts, crypt="clear", io_loop=self.io_loop
            )

        sign_in_payload = self.minion_sign_in_payload()
        try:
            payload = yield channel.send(sign_in_payload, tries=tries, timeout=timeout)
        except SaltReqTimeoutError as e:
            if safe:
                log.warning("SaltReqTimeoutError: %s", e)
                raise tornado.gen.Return("retry")
            if self.opts.get("detect_mode") is True:
                raise tornado.gen.Return("retry")
            else:
                raise SaltClientError(
                    "Attempt to authenticate with the salt master failed with timeout"
                    " error"
                )
        finally:
            if close_channel:
                channel.close()
        ret = self.handle_signin_response(sign_in_payload, payload)
        raise tornado.gen.Return(ret)

    def handle_signin_response(self, sign_in_payload, payload):
        auth = {}
        m_pub_fn = os.path.join(self.opts["pki_dir"], self.mpub)
        auth["master_uri"] = self.opts["master_uri"]
        if not isinstance(payload, dict) or "load" not in payload:
            log.error("Sign-in attempt failed: %s", payload)
            return False
        elif isinstance(payload["load"], dict) and "ret" in payload["load"]:
            if payload["load"]["ret"] == "bad enc algo":
                log.error("Sign-in attempt failed: %s", payload)
                return "bad enc algo"
            elif payload["load"]["ret"] == "bad sig algo":
                log.error("Sign-in attempt failed: %s", payload)
                return "bad sig algo"

        clear_signed_data = payload["load"]
        clear_signature = payload["sig"]
        payload = salt.payload.loads(clear_signed_data)

        if "pub_key" in payload:
            auth["aes"] = self.verify_master(
                payload, master_pub="token" in sign_in_payload
            )
            if not auth["aes"]:
                log.critical(
                    "The Salt Master server's public key did not authenticate!\n"
                    "The master may need to be updated if it is a version of Salt "
                    "lower than %s, or\n"
                    "If you are confident that you are connecting to a valid Salt "
                    "Master, then remove the master public key and restart the "
                    "Salt Minion.\nThe master public key can be found "
                    "at:\n%s",
                    salt.version.__version__,
                    m_pub_fn,
                )
                raise SaltClientError("Invalid master key")

        master_pubkey_path = os.path.join(self.opts["pki_dir"], self.mpub)
        if os.path.exists(master_pubkey_path) and not PublicKey(
            master_pubkey_path
        ).verify(
            clear_signed_data,
            clear_signature,
            algorithm=self.opts["signing_algorithm"],
        ):
            log.critical("The payload signature did not validate.")
            raise SaltClientError("Invalid signature")

        if payload["nonce"] != sign_in_payload["nonce"]:
            log.critical("The payload nonce did not validate.")
            raise SaltClientError("Invalid nonce")

        if "ret" in payload:
            if not payload["ret"]:
                if self.opts["rejected_retry"]:
                    log.error(
                        "The Salt Master has rejected this minion's public "
                        "key.\nTo repair this issue, delete the public key "
                        "for this minion on the Salt Master.\nThe Salt "
                        "Minion will attempt to re-authenicate."
                    )
                    return "retry"
                else:
                    log.critical(
                        "The Salt Master has rejected this minion's public "
                        "key!\nTo repair this issue, delete the public key "
                        "for this minion on the Salt Master and restart this "
                        "minion.\nOr restart the Salt Master in open mode to "
                        "clean out the keys. The Salt Minion will now exit."
                    )
                    # Add a random sleep here for systems that are using a
                    # service manager to immediately restart the service to
                    # avoid overloading the system
                    time.sleep(random.randint(10, 20))
                    sys.exit(salt.defaults.exitcodes.EX_NOPERM)
            # Has the master returned that it's maxed out with minions?
            elif payload["ret"] == "full":
                return "full"
            else:
                log.error(
                    "The Salt Master has cached the public key for this "
                    "node, this salt minion will wait for %s seconds "
                    "before attempting to re-authenticate",
                    self.opts["acceptance_wait_time"],
                )
                return "retry"

        if self.opts.get("syndic_master", False):  # Is syndic
            syndic_finger = self.opts.get(
                "syndic_finger", self.opts.get("master_finger", False)
            )
            if syndic_finger:
                if (
                    salt.utils.crypt.pem_finger(
                        m_pub_fn, sum_type=self.opts["hash_type"]
                    )
                    != syndic_finger
                ):
                    self._finger_fail(syndic_finger, m_pub_fn)
        else:
            if self.opts.get("master_finger", False):
                if (
                    salt.utils.crypt.pem_finger(
                        m_pub_fn, sum_type=self.opts["hash_type"]
                    )
                    != self.opts["master_finger"]
                ):
                    self._finger_fail(self.opts["master_finger"], m_pub_fn)

        auth["publish_port"] = payload["publish_port"]
        return auth

    def get_keys(self):
        """
        Return keypair object for the minion.

        :rtype: Crypto.PublicKey.RSA._RSAobj
        :return: The RSA keypair
        """
        # Make sure all key parent directories are accessible
        user = self.opts.get("user", "root")
        salt.utils.verify.check_path_traversal(self.opts["pki_dir"], user)

        if not os.path.exists(self.rsa_path):
            log.info("Generating keys: %s", self.opts["pki_dir"])
            gen_keys(
                self.opts["pki_dir"],
                "minion",
                self.opts["keysize"],
                self.opts.get("user"),
            )
        key = PrivateKey(self.rsa_path, None)
        log.debug("Loaded minion key: %s", self.rsa_path)
        return key

    def gen_token(self, clear_tok):
        """
        Encrypt a string with the minion private key to verify identity
        with the master.

        :param str clear_tok: A plaintext token to encrypt
        :return: Encrypted token
        :rtype: str
        """
        return self.get_keys().encrypt(clear_tok)

    def minion_sign_in_payload(self):
        """
        Generates the payload used to authenticate with the master
        server. This payload consists of the passed in id_ and the ssh
        public key to encrypt the AES key sent back from the master.

        :return: Payload dictionary
        :rtype: dict
        """
        payload = {}
        payload["cmd"] = "_auth"
        payload["id"] = self.opts["id"]
        payload["nonce"] = uuid.uuid4().hex
        payload["enc_algo"] = self.opts["encryption_algorithm"]
        payload["sig_algo"] = self.opts["signing_algorithm"]
        if "autosign_grains" in self.opts:
            autosign_grains = {}
            for grain in self.opts["autosign_grains"]:
                autosign_grains[grain] = self.opts["grains"].get(grain, None)
            payload["autosign_grains"] = autosign_grains
        try:
            pubkey_path = os.path.join(self.opts["pki_dir"], self.mpub)
            pub = PublicKey(pubkey_path)
            payload["token"] = pub.encrypt(
                self.token, self.opts["encryption_algorithm"]
            )
        except FileNotFoundError:
            log.debug("Master public key not found")
        except Exception as exc:  # pylint: disable=broad-except
            log.debug("Exception while encrypting token %s", exc)
        with salt.utils.files.fopen(self.pub_path) as f:
            payload["pub"] = clean_key(f.read())
        return payload

    def decrypt_aes(self, payload, master_pub=True):
        """
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
        """
        if self.opts.get("auth_trb", False):
            log.warning("Auth Called: %s", "".join(traceback.format_stack()))
        else:
            log.debug("Decrypting the current master AES key")

        key = self.get_keys()
        key_str = key.decrypt(payload["aes"], self.opts["encryption_algorithm"])
        if "sig" in payload:
            m_path = os.path.join(self.opts["pki_dir"], self.mpub)
            if os.path.exists(m_path):
                try:
                    mkey = PublicKey(m_path)
                except Exception:  # pylint: disable=broad-except
                    return "", ""
                digest = hashlib.sha256(key_str).hexdigest()
                digest = salt.utils.stringutils.to_bytes(digest)
                m_digest = mkey.decrypt(payload["sig"])
                if m_digest != digest:
                    return "", ""
        else:
            return "", ""

        key_str = salt.utils.stringutils.to_str(key_str)

        if "_|-" in key_str:
            return key_str.split("_|-")
        else:
            if "token" in payload:
                token = key.decrypt(payload["token"], self.opts["encryption_algorithm"])
                return key_str, token
            elif not master_pub:
                return key_str, ""
        return "", ""

    def verify_pubkey_sig(self, message, sig):
        """
        Wraps the verify_signature method so we have
        additional checks.

        :rtype: bool
        :return: Success or failure of public key verification
        """
        if self.opts["master_sign_key_name"]:
            path = os.path.join(
                self.opts["pki_dir"], self.opts["master_sign_key_name"] + ".pub"
            )

            if os.path.isfile(path):
                res = verify_signature(
                    path,
                    message,
                    binascii.a2b_base64(sig),
                    algorithm=self.opts["signing_algorithm"],
                )
            else:
                log.error(
                    "Verification public key %s does not exist. You need to "
                    "copy it from the master to the minions pki directory",
                    os.path.basename(path),
                )
                return False
            if res:
                log.debug(
                    "Successfully verified signature of master public key "
                    "with verification public key %s",
                    self.opts["master_sign_key_name"] + ".pub",
                )
                return True
            else:
                log.debug("Failed to verify signature of public key")
                return False
        else:
            log.error(
                "Failed to verify the signature of the message because the "
                "verification key-pairs name is not defined. Please make "
                "sure that master_sign_key_name is defined."
            )
            return False

    def verify_signing_master(self, payload):
        try:
            if self.verify_pubkey_sig(payload["pub_key"], payload["pub_sig"]):
                log.info(
                    "Received signed and verified master pubkey from master %s",
                    self.opts["master"],
                )
                m_pub_fn = os.path.join(self.opts["pki_dir"], self.mpub)
                uid = salt.utils.user.get_uid(self.opts.get("user", None))
                with salt.utils.files.fpopen(m_pub_fn, "wb+", uid=uid) as wfh:
                    wfh.write(salt.utils.stringutils.to_bytes(payload["pub_key"]))
                return True
            else:
                log.error(
                    "Received signed public-key from master %s but signature "
                    "verification failed!",
                    self.opts["master"],
                )
                return False
        except Exception as sign_exc:  # pylint: disable=broad-except
            log.error(
                "There was an error while verifying the masters public-key signature"
            )
            raise Exception(sign_exc)

    def check_auth_deps(self, payload):
        """
        Checks if both master and minion either sign (master) and
        verify (minion). If one side does not, it should fail.

        :param dict payload: The incoming payload. This is a dictionary which may have the following keys:
            'aes': The shared AES key
            'enc': The format of the message. ('clear', 'pub', 'aes')
            'publish_port': The TCP port which published the message
            'token': The encrypted token used to verify the message.
            'pub_key': The RSA public key of the sender.
        """
        # master and minion sign and verify
        if "pub_sig" in payload and self.opts["verify_master_pubkey_sign"]:
            return True
        # master and minion do NOT sign and do NOT verify
        elif "pub_sig" not in payload and not self.opts["verify_master_pubkey_sign"]:
            return True

        # master signs, but minion does NOT verify
        elif "pub_sig" in payload and not self.opts["verify_master_pubkey_sign"]:
            log.error(
                "The masters sent its public-key signature, but signature "
                "verification is not enabled on the minion. Either enable "
                "signature verification on the minion or disable signing "
                "the public key on the master!"
            )
            return False
        # master does NOT sign but minion wants to verify
        elif "pub_sig" not in payload and self.opts["verify_master_pubkey_sign"]:
            log.error(
                "The master did not send its public-key signature, but "
                "signature verification is enabled on the minion. Either "
                "disable signature verification on the minion or enable "
                "signing the public on the master!"
            )
            return False

    def extract_aes(self, payload, master_pub=True):
        """
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
        """
        if master_pub:
            try:
                aes, token = self.decrypt_aes(payload, master_pub)
                if token != self.token:
                    log.error("The master failed to decrypt the random minion token")
                    return ""
            except Exception:  # pylint: disable=broad-except
                log.error("The master failed to decrypt the random minion token")
                return ""
            return aes
        else:
            aes, token = self.decrypt_aes(payload, master_pub)
            return aes

    def verify_master(self, payload, master_pub=True):
        """
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
        """
        m_pub_fn = os.path.join(self.opts["pki_dir"], self.mpub)
        m_pub_exists = os.path.isfile(m_pub_fn)
        if m_pub_exists and master_pub and not self.opts["open_mode"]:
            with salt.utils.files.fopen(m_pub_fn) as fp_:
                local_master_pub = clean_key(fp_.read())

            if payload["pub_key"] != local_master_pub:
                if not self.check_auth_deps(payload):
                    return ""

                if self.opts["verify_master_pubkey_sign"]:
                    if self.verify_signing_master(payload):
                        return self.extract_aes(payload, master_pub=False)
                    else:
                        return ""
                else:
                    # This is not the last master we connected to
                    log.error(
                        "The master key has changed, the salt master could "
                        "have been subverted, verify salt master's public "
                        "key"
                    )
                    return ""

            else:
                if not self.check_auth_deps(payload):
                    return ""
                # verify the signature of the pubkey even if it has
                # not changed compared with the one we already have
                if self.opts["always_verify_signature"]:
                    if self.verify_signing_master(payload):
                        return self.extract_aes(payload)
                    else:
                        log.error(
                            "The masters public could not be verified. Is the "
                            "verification pubkey %s up to date?",
                            self.opts["master_sign_key_name"] + ".pub",
                        )
                        return ""

                else:
                    return self.extract_aes(payload)
        else:
            if not self.check_auth_deps(payload):
                return ""

            # verify the masters pubkey signature if the minion
            # has not received any masters pubkey before
            if self.opts["verify_master_pubkey_sign"]:
                if self.verify_signing_master(payload):
                    return self.extract_aes(payload, master_pub=False)
                else:
                    return ""
            else:
                if not m_pub_exists:
                    # the minion has not received any masters pubkey yet, write
                    # the newly received pubkey to minion_master.pub
                    with salt.utils.files.fopen(m_pub_fn, "wb+") as fp_:
                        fp_.write(salt.utils.stringutils.to_bytes(payload["pub_key"]))
                return self.extract_aes(payload, master_pub=False)

    def _finger_fail(self, finger, master_key):
        log.critical(
            "The specified fingerprint in the master configuration "
            "file:\n%s\nDoes not match the authenticating master's "
            "key:\n%s\nVerify that the configured fingerprint "
            "matches the fingerprint of the correct master and that "
            "this minion is not subject to a man-in-the-middle attack.",
            finger,
            salt.utils.crypt.pem_finger(master_key, sum_type=self.opts["hash_type"]),
        )
        sys.exit(42)


# TODO: remove, we should just return a sync wrapper of AsyncAuth
class SAuth(AsyncAuth):
    """
    Set up an object to maintain authentication with the salt master
    """

    # This class is only a singleton per minion/master pair
    instances = weakref.WeakValueDictionary()

    def __new__(cls, opts, io_loop=None):
        """
        Only create one instance of SAuth per __key()
        """
        key = cls.__key(opts)
        auth = SAuth.instances.get(key)
        if auth is None:
            log.debug("Initializing new SAuth for %s", key)
            auth = object.__new__(cls)
            auth.__singleton_init__(opts)
            SAuth.instances[key] = auth
        else:
            log.debug("Re-using SAuth for %s", key)
        return auth

    @classmethod
    def __key(cls, opts, io_loop=None):
        return (
            opts["pki_dir"],  # where the keys are stored
            opts["id"],  # minion ID
            opts["master_uri"],  # master ID
        )

    # has to remain empty for singletons, since __init__ will *always* be called
    def __init__(self, opts, io_loop=None):
        super().__init__(opts, io_loop=io_loop)

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, io_loop=None):
        """
        Init an Auth instance

        :param dict opts: Options for this server
        :return: Auth instance
        :rtype: Auth
        """
        self.opts = opts
        self.token = salt.utils.stringutils.to_bytes(Crypticle.generate_key_string())
        self.pub_path = os.path.join(self.opts["pki_dir"], "minion.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "minion.pem")
        self._creds = None
        if "syndic_master" in self.opts:
            self.mpub = "syndic_master.pub"
        elif "alert_master" in self.opts:
            self.mpub = "monitor_master.pub"
        else:
            self.mpub = "minion_master.pub"
        if not os.path.isfile(self.pub_path):
            self.get_keys()

    @property
    def creds(self):
        if not hasattr(self, "_creds"):
            self.authenticate()
        return self._creds

    @property
    def crypticle(self):
        if not hasattr(self, "_crypticle"):
            self.authenticate()
        return self._crypticle

    def authenticate(self, _=None):  # TODO: remove unused var
        """
        Authenticate with the master, this method breaks the functional
        paradigm, it will update the master information from a fresh sign
        in, signing in can occur as often as needed to keep up with the
        revolving master AES key.

        :rtype: Crypticle
        :returns: A crypticle used for encryption operations
        """
        acceptance_wait_time = self.opts["acceptance_wait_time"]
        acceptance_wait_time_max = self.opts["acceptance_wait_time_max"]
        if not acceptance_wait_time_max:
            acceptance_wait_time_max = acceptance_wait_time
        with salt.channel.client.ReqChannel.factory(
            self.opts, crypt="clear"
        ) as channel:
            while True:
                creds = self.sign_in(channel=channel)
                if creds == "retry":
                    if self.opts.get("caller"):
                        # We have a list of masters, so we should break
                        # and try the next one in the list.
                        if self.opts.get("local_masters", None):
                            error = SaltClientError(
                                "Minion failed to authenticate"
                                " with the master, has the "
                                "minion key been accepted?"
                            )
                            break
                        else:
                            print(
                                "Minion failed to authenticate with the master, "
                                "has the minion key been accepted?"
                            )
                            sys.exit(2)
                    if acceptance_wait_time:
                        log.info(
                            "Waiting %s seconds before retry.", acceptance_wait_time
                        )
                        time.sleep(acceptance_wait_time)
                    if acceptance_wait_time < acceptance_wait_time_max:
                        acceptance_wait_time += acceptance_wait_time
                        log.debug(
                            "Authentication wait time is %s", acceptance_wait_time
                        )
                    continue
                break
            if self._creds is None:
                log.error("%s Got new master aes key.", self)
                self._creds = creds
                self._crypticle = Crypticle(self.opts, creds["aes"])
            elif self._creds["aes"] != creds["aes"]:
                log.error("%s The master's aes key has changed.", self)
                self._creds = creds
                self._crypticle = Crypticle(self.opts, creds["aes"])

    def sign_in(self, timeout=60, safe=True, tries=1, channel=None):
        """
        Send a sign in request to the master, sets the key information and
        returns a dict containing the master publish interface to bind to
        and the decrypted aes key for transport decryption.

        :param int timeout: Number of seconds to wait before timing out the sign-in request
        :param bool safe: If True, do not raise an exception on timeout. Retry instead.
        :param int tries: The number of times to try to authenticate before giving up.

        :raises SaltReqTimeoutError: If the sign-in request has timed out and :param safe: is not set

        :return: Return a string on failure indicating the reason for failure. On success, return a dictionary
        with the publication port and the shared AES key.

        """
        auth = {}

        auth_timeout = self.opts.get("auth_timeout", None)
        if auth_timeout is not None:
            timeout = auth_timeout
        auth_safemode = self.opts.get("auth_safemode", None)
        if auth_safemode is not None:
            safe = auth_safemode
        auth_tries = self.opts.get("auth_tries", None)
        if auth_tries is not None:
            tries = auth_tries

        m_pub_fn = os.path.join(self.opts["pki_dir"], self.mpub)

        auth["master_uri"] = self.opts["master_uri"]

        close_channel = False
        if not channel:
            close_channel = True
            channel = salt.channel.client.ReqChannel.factory(self.opts, crypt="clear")

        sign_in_payload = self.minion_sign_in_payload()
        try:
            payload = channel.send(sign_in_payload, tries=tries, timeout=timeout)
        except SaltReqTimeoutError as e:
            if safe:
                log.warning("SaltReqTimeoutError: %s", e)
                return "retry"
            raise SaltClientError(
                "Attempt to authenticate with the salt master failed with timeout error"
            )
        finally:
            if close_channel:
                channel.close()

        return self.handle_signin_response(sign_in_payload, payload)


class Crypticle:
    """
    Authenticated encryption class

    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    """

    PICKLE_PAD = b"pickle::"
    AES_BLOCK_SIZE = 16
    SIG_SIZE = hashlib.sha256().digest_size

    def __init__(self, opts, key_string, key_size=192, serial=0):
        self.key_string = key_string
        self.keys = self.extract_keys(self.key_string, key_size)
        self.key_size = key_size
        self.serial = serial

    @classmethod
    def generate_key_string(cls, key_size=192, **kwargs):
        key = os.urandom(key_size // 8 + cls.SIG_SIZE)
        b64key = base64.b64encode(key)
        b64key = b64key.decode("utf-8")
        # Return data must be a base64-encoded string, not a unicode type
        return b64key.replace("\n", "")

    @classmethod
    def write_key(cls, path, key_size=192):
        directory = pathlib.Path(path).parent
        with salt.utils.files.set_umask(0o177):
            fd, tmp = tempfile.mkstemp(dir=directory, prefix="aes")
            os.close(fd)
            with salt.utils.files.fopen(tmp, "w") as fp:
                fp.write(cls.generate_key_string(key_size))
            os.rename(tmp, path)

    @classmethod
    def read_key(cls, path):
        try:
            with salt.utils.files.fopen(path, "r") as fp:
                return fp.read()
        except FileNotFoundError:
            pass

    @classmethod
    def extract_keys(cls, key_string, key_size):
        key = salt.utils.stringutils.to_bytes(base64.b64decode(key_string))
        assert len(key) == key_size / 8 + cls.SIG_SIZE, "invalid key"
        return key[: -cls.SIG_SIZE], key[-cls.SIG_SIZE :]

    def encrypt(self, data):
        """
        encrypt data with AES-CBC and sign it with HMAC-SHA256
        """
        aes_key, hmac_key = self.keys
        pad = self.AES_BLOCK_SIZE - len(data) % self.AES_BLOCK_SIZE
        data = data + salt.utils.stringutils.to_bytes(pad * chr(pad))
        iv_bytes = os.urandom(self.AES_BLOCK_SIZE)
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv_bytes))
        encryptor = cipher.encryptor()
        encr = encryptor.update(data)
        encr += encryptor.finalize()
        data = iv_bytes + encr
        sig = hmac.new(hmac_key, data, hashlib.sha256).digest()
        return data + sig

    def decrypt(self, data):
        """
        verify HMAC-SHA256 signature and decrypt data with AES-CBC
        """
        aes_key, hmac_key = self.keys
        sig = data[-self.SIG_SIZE :]
        data = data[: -self.SIG_SIZE]
        if not isinstance(data, bytes):
            data = salt.utils.stringutils.to_bytes(data)
        mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
        if len(mac_bytes) != len(sig):
            log.debug("Failed to authenticate message")
            raise AuthenticationError("message authentication failed")
        result = 0
        for zipped_x, zipped_y in zip(mac_bytes, sig):
            result |= zipped_x ^ zipped_y
        if result != 0:
            log.debug("Failed to authenticate message")
            raise AuthenticationError("message authentication failed")
        iv_bytes = data[: self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE :]
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv_bytes))
        decryptor = cipher.decryptor()
        data = decryptor.update(data) + decryptor.finalize()
        return data[: -data[-1]]

    def dumps(self, obj, nonce=None):
        """
        Serialize and encrypt a python object
        """
        if nonce:
            toencrypt = self.PICKLE_PAD + nonce.encode() + salt.payload.dumps(obj)
        else:
            toencrypt = self.PICKLE_PAD + salt.payload.dumps(obj)
        return self.encrypt(toencrypt)

    def loads(self, data, raw=False, nonce=None):
        """
        Decrypt and un-serialize a python object
        """
        data = self.decrypt(data)
        # simple integrity check to verify that we got meaningful data
        if not data.startswith(self.PICKLE_PAD):
            return {}
        data = data[len(self.PICKLE_PAD) :]
        if nonce:
            ret_nonce = data[:32].decode()
            data = data[32:]
            if ret_nonce != nonce:
                raise SaltClientError(f"Nonce verification error {ret_nonce} {nonce}")
        payload = salt.payload.loads(data, raw=raw)
        if isinstance(payload, dict):
            if "serial" in payload:
                serial = payload.pop("serial")
                if serial <= self.serial:
                    log.critical(
                        "A message with an invalid serial was received.\n"
                        "this serial: %d\n"
                        "last serial: %d\n"
                        "The minion will not honor this request.",
                        serial,
                        self.serial,
                    )
                    return {}
                self.serial = serial
        return payload
