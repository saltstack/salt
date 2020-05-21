# -*- coding: utf-8 -*-
"""
The crypt module manages all of the cryptography functions for minions and
masters, encrypting and decrypting payloads, preparing messages, and
authenticating peers
"""

# NOTE: We can't use unicode_literals because this module implicitly uses
# the Array class, which has incompatibilities with it.
from __future__ import absolute_import, print_function

import base64
import binascii
import copy
import getpass
import hashlib
import hmac
import logging

# Import python libs
import os
import random
import stat
import sys
import time
import traceback
import weakref

# Import salt libs
import salt.defaults.exitcodes
import salt.ext.tornado.gen
import salt.payload
import salt.transport.client
import salt.transport.frame
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
    MasterExit,
    SaltClientError,
    SaltReqTimeoutError,
)
from salt.ext import six

# Import third party libs
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin

try:
    from M2Crypto import RSA, EVP, BIO

    HAS_M2 = True
except ImportError:
    HAS_M2 = False

if not HAS_M2:
    try:
        from Cryptodome.Cipher import AES, PKCS1_OAEP
        from Cryptodome.Hash import SHA
        from Cryptodome.PublicKey import RSA
        from Cryptodome.Signature import PKCS1_v1_5
        import Cryptodome.Random  # pylint: disable=W0611

        HAS_CDOME = True
    except ImportError:
        HAS_CDOME = False

if not HAS_M2 and not HAS_CDOME:
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


log = logging.getLogger(__name__)


def dropfile(cachedir, user=None):
    """
    Set an AES dropfile to request the master update the publish session key
    """
    dfn = os.path.join(cachedir, ".dfn")
    # set a mask (to avoid a race condition on file creation) and store original.
    with salt.utils.files.set_umask(0o277):
        log.info("Rotating AES key")
        if os.path.isfile(dfn):
            log.info("AES key rotation already requested")
            return

        if os.path.isfile(dfn) and not os.access(dfn, os.W_OK):
            os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
        with salt.utils.files.fopen(dfn, "wb+") as fp_:
            fp_.write(b"")
        os.chmod(dfn, stat.S_IRUSR)
        if user:
            try:
                import pwd

                uid = pwd.getpwnam(user).pw_uid
                os.chown(dfn, uid, -1)
            except (KeyError, ImportError, OSError, IOError):
                pass


def gen_keys(keydir, keyname, keysize, user=None, passphrase=None):
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
    priv = "{0}.pem".format(base)
    pub = "{0}.pub".format(base)

    if HAS_M2:
        gen = RSA.gen_key(keysize, 65537, lambda: None)
    else:
        salt.utils.crypt.reinit_crypto()
        gen = RSA.generate(bits=keysize, e=65537)
    if os.path.isfile(priv):
        # Between first checking and the generation another process has made
        # a key! Use the winner's key
        return priv

    # Do not try writing anything, if directory has no permissions.
    if not os.access(keydir, os.W_OK):
        raise IOError(
            'Write access denied to "{0}" for user "{1}".'.format(
                os.path.abspath(keydir), getpass.getuser()
            )
        )

    with salt.utils.files.set_umask(0o277):
        if HAS_M2:
            # if passphrase is empty or None use no cipher
            if not passphrase:
                gen.save_pem(priv, cipher=None)
            else:
                gen.save_pem(
                    priv,
                    cipher="des_ede3_cbc",
                    callback=lambda x: salt.utils.stringutils.to_bytes(passphrase),
                )
        else:
            with salt.utils.files.fopen(priv, "wb+") as f:
                f.write(gen.exportKey("PEM", passphrase))
    if HAS_M2:
        gen.save_pub_key(pub)
    else:
        with salt.utils.files.fopen(pub, "wb+") as f:
            f.write(gen.publickey().exportKey("PEM"))
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


@salt.utils.decorators.memoize
def _get_key_with_evict(path, timestamp, passphrase):
    """
    Load a private key from disk.  `timestamp` above is intended to be the
    timestamp of the file's last modification. This fn is memoized so if it is
    called with the same path and timestamp (the file's last modified time) the
    second time the result is returned from the memoiziation.  If the file gets
    modified then the params are different and the key is loaded from disk.
    """
    log.debug("salt.crypt._get_key_with_evict: Loading private key")
    if HAS_M2:
        key = RSA.load_key(path, lambda x: six.b(passphrase))
    else:
        with salt.utils.files.fopen(path) as f:
            key = RSA.importKey(f.read(), passphrase)
    return key


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
    return _get_key_with_evict(path, six.text_type(os.path.getmtime(path)), passphrase)


def get_rsa_pub_key(path):
    """
    Read a public key off the disk.
    """
    log.debug("salt.crypt.get_rsa_pub_key: Loading public key")
    if HAS_M2:
        with salt.utils.files.fopen(path, "rb") as f:
            data = f.read().replace(b"RSA ", b"")
        bio = BIO.MemoryBuffer(data)
        key = RSA.load_pub_key_bio(bio)
    else:
        with salt.utils.files.fopen(path) as f:
            key = RSA.importKey(f.read())
    return key


def sign_message(privkey_path, message, passphrase=None):
    """
    Use Crypto.Signature.PKCS1_v1_5 to sign a message. Returns the signature.
    """
    key = get_rsa_key(privkey_path, passphrase)
    log.debug("salt.crypt.sign_message: Signing message.")
    if HAS_M2:
        md = EVP.MessageDigest("sha1")
        md.update(salt.utils.stringutils.to_bytes(message))
        digest = md.final()
        return key.sign(digest)
    else:
        signer = PKCS1_v1_5.new(key)
        return signer.sign(SHA.new(salt.utils.stringutils.to_bytes(message)))


def verify_signature(pubkey_path, message, signature):
    """
    Use Crypto.Signature.PKCS1_v1_5 to verify the signature on a message.
    Returns True for valid signature.
    """
    log.debug("salt.crypt.verify_signature: Loading public key")
    pubkey = get_rsa_pub_key(pubkey_path)
    log.debug("salt.crypt.verify_signature: Verifying signature")
    if HAS_M2:
        md = EVP.MessageDigest("sha1")
        md.update(salt.utils.stringutils.to_bytes(message))
        digest = md.final()
        return pubkey.verify(digest, signature)
    else:
        verifier = PKCS1_v1_5.new(pubkey)
        return verifier.verify(
            SHA.new(salt.utils.stringutils.to_bytes(message)), signature
        )


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
            "Signature file %s already exists, please remove it first and " "try again",
            sign_path,
        )
    else:
        with salt.utils.files.fopen(sign_path, "wb+") as sig_f:
            sig_f.write(salt.utils.stringutils.to_bytes(mpub_sig_64))
        log.trace("Wrote signature to %s", sign_path)
    return True


def private_encrypt(key, message):
    """
    Generate an M2Crypto-compatible signature

    :param Crypto.PublicKey.RSA._RSAobj key: The RSA key object
    :param str message: The message to sign
    :rtype: str
    :return: The signature, or an empty string if the signature operation failed
    """
    if HAS_M2:
        return key.private_encrypt(message, salt.utils.rsax931.RSA_X931_PADDING)
    else:
        signer = salt.utils.rsax931.RSAX931Signer(key.exportKey("PEM"))
        return signer.sign(message)


def public_decrypt(pub, message):
    """
    Verify an M2Crypto-compatible signature

    :param Crypto.PublicKey.RSA._RSAobj key: The RSA public key object
    :param str message: The signed message to verify
    :rtype: str
    :return: The message (or digest) recovered from the signature, or an
        empty string if the verification failed
    """
    if HAS_M2:
        return pub.public_decrypt(message, salt.utils.rsax931.RSA_X931_PADDING)
    else:
        verifier = salt.utils.rsax931.RSAX931Verifier(pub.exportKey("PEM"))
        return verifier.verify(message)


class MasterKeys(dict):
    """
    The Master Keys class is used to manage the RSA public key pair used for
    authentication by the master.

    It also generates a signing key-pair if enabled with master_sign_key_name.
    """

    def __init__(self, opts):
        super(MasterKeys, self).__init__()
        self.opts = opts
        self.pub_path = os.path.join(self.opts["pki_dir"], "master.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "master.pem")

        key_pass = salt.utils.sdb.sdb_get(self.opts["key_pass"], self.opts)
        self.key = self.__get_keys(passphrase=key_pass)

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
                        self.pub_signature = fp_.read()
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

    def __get_keys(self, name="master", passphrase=None):
        """
        Returns a key object for a key in the pki-dir
        """
        path = os.path.join(self.opts["pki_dir"], name + ".pem")
        if not os.path.exists(path):
            log.info("Generating %s keys: %s", name, self.opts["pki_dir"])
            gen_keys(
                self.opts["pki_dir"],
                name,
                self.opts["keysize"],
                self.opts.get("user"),
                passphrase,
            )
        if HAS_M2:
            key_error = RSA.RSAError
        else:
            key_error = ValueError
        try:
            key = get_rsa_key(path, passphrase)
        except key_error as e:
            message = "Unable to read key: {0}; passphrase may be incorrect".format(
                path
            )
            log.error(message)
            raise MasterExit(message)
        log.debug("Loaded %s key: %s", name, path)
        return key

    def get_pub_str(self, name="master"):
        """
        Return the string representation of a public key
        in the pki-directory
        """
        path = os.path.join(self.opts["pki_dir"], name + ".pub")
        if not os.path.isfile(path):
            key = self.__get_keys()
            if HAS_M2:
                key.save_pub_key(path)
            else:
                with salt.utils.files.fopen(path, "wb+") as wfh:
                    wfh.write(key.publickey().exportKey("PEM"))
        with salt.utils.files.fopen(path) as rfh:
            return rfh.read()

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


class AsyncAuth(object):
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
        io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()
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
        if six.PY2:
            self.token = Crypticle.generate_key_string()
        else:
            self.token = salt.utils.stringutils.to_bytes(
                Crypticle.generate_key_string()
            )
        self.serial = salt.payload.Serial(self.opts)
        self.pub_path = os.path.join(self.opts["pki_dir"], "minion.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "minion.pem")
        if self.opts["__role"] == "syndic":
            self.mpub = "syndic_master.pub"
        else:
            self.mpub = "minion_master.pub"
        if not os.path.isfile(self.pub_path):
            self.get_keys()

        self.io_loop = io_loop or salt.ext.tornado.ioloop.IOLoop.current()

        salt.utils.crypt.reinit_crypto()
        key = self.__key(self.opts)
        # TODO: if we already have creds for this key, lets just re-use
        if key in AsyncAuth.creds_map:
            creds = AsyncAuth.creds_map[key]
            self._creds = creds
            self._crypticle = Crypticle(self.opts, creds["aes"])
            self._authenticate_future = salt.ext.tornado.concurrent.Future()
            self._authenticate_future.set_result(True)
        else:
            self.authenticate()

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
            future = salt.ext.tornado.concurrent.Future()
            self._authenticate_future = future
            self.io_loop.add_callback(self._authenticate)

        if callback is not None:

            def handle_future(future):
                response = future.result()
                self.io_loop.add_callback(callback, response)

            future.add_done_callback(handle_future)

        return future

    @salt.ext.tornado.gen.coroutine
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

        with salt.transport.client.AsyncReqChannel.factory(
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
                        yield salt.ext.tornado.gen.sleep(acceptance_wait_time)
                    if acceptance_wait_time < acceptance_wait_time_max:
                        acceptance_wait_time += acceptance_wait_time
                        log.debug(
                            "Authentication wait time is %s", acceptance_wait_time
                        )
                    continue
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

    @salt.ext.tornado.gen.coroutine
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
            channel = salt.transport.client.AsyncReqChannel.factory(
                self.opts, crypt="clear", io_loop=self.io_loop
            )

        sign_in_payload = self.minion_sign_in_payload()
        try:
            payload = yield channel.send(sign_in_payload, tries=tries, timeout=timeout)
        except SaltReqTimeoutError as e:
            if safe:
                log.warning("SaltReqTimeoutError: %s", e)
                raise salt.ext.tornado.gen.Return("retry")
            if self.opts.get("detect_mode") is True:
                raise salt.ext.tornado.gen.Return("retry")
            else:
                raise SaltClientError(
                    "Attempt to authenticate with the salt master failed with timeout error"
                )
        finally:
            if close_channel:
                channel.close()

        if not isinstance(payload, dict):
            log.error("Sign-in attempt failed: %s", payload)
            raise salt.ext.tornado.gen.Return(False)
        if "load" in payload:
            if "ret" in payload["load"]:
                if not payload["load"]["ret"]:
                    if self.opts["rejected_retry"]:
                        log.error(
                            "The Salt Master has rejected this minion's public "
                            "key.\nTo repair this issue, delete the public key "
                            "for this minion on the Salt Master.\nThe Salt "
                            "Minion will attempt to to re-authenicate."
                        )
                        raise salt.ext.tornado.gen.Return("retry")
                    else:
                        log.critical(
                            "The Salt Master has rejected this minion's public "
                            "key!\nTo repair this issue, delete the public key "
                            "for this minion on the Salt Master and restart this "
                            "minion.\nOr restart the Salt Master in open mode to "
                            "clean out the keys. The Salt Minion will now exit."
                        )
                        # Add a random sleep here for systems that are using a
                        # a service manager to immediately restart the service
                        # to avoid overloading the system
                        time.sleep(random.randint(10, 20))
                        sys.exit(salt.defaults.exitcodes.EX_NOPERM)
                # has the master returned that its maxed out with minions?
                elif payload["load"]["ret"] == "full":
                    raise salt.ext.tornado.gen.Return("full")
                else:
                    log.error(
                        "The Salt Master has cached the public key for this "
                        "node, this salt minion will wait for %s seconds "
                        "before attempting to re-authenticate",
                        self.opts["acceptance_wait_time"],
                    )
                    raise salt.ext.tornado.gen.Return("retry")
        auth["aes"] = self.verify_master(payload, master_pub="token" in sign_in_payload)
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
        raise salt.ext.tornado.gen.Return(auth)

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
        key = get_rsa_key(self.rsa_path, None)
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
        return private_encrypt(self.get_keys(), clear_tok)

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
        if "autosign_grains" in self.opts:
            autosign_grains = {}
            for grain in self.opts["autosign_grains"]:
                autosign_grains[grain] = self.opts["grains"].get(grain, None)
            payload["autosign_grains"] = autosign_grains
        try:
            pubkey_path = os.path.join(self.opts["pki_dir"], self.mpub)
            pub = get_rsa_pub_key(pubkey_path)
            if HAS_M2:
                payload["token"] = pub.public_encrypt(
                    self.token, RSA.pkcs1_oaep_padding
                )
            else:
                cipher = PKCS1_OAEP.new(pub)
                payload["token"] = cipher.encrypt(self.token)
        except Exception:  # pylint: disable=broad-except
            pass
        with salt.utils.files.fopen(self.pub_path) as f:
            payload["pub"] = f.read()
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
        if HAS_M2:
            key_str = key.private_decrypt(payload["aes"], RSA.pkcs1_oaep_padding)
        else:
            cipher = PKCS1_OAEP.new(key)
            key_str = cipher.decrypt(payload["aes"])
        if "sig" in payload:
            m_path = os.path.join(self.opts["pki_dir"], self.mpub)
            if os.path.exists(m_path):
                try:
                    mkey = get_rsa_pub_key(m_path)
                except Exception:  # pylint: disable=broad-except
                    return "", ""
                digest = hashlib.sha256(key_str).hexdigest()
                if six.PY3:
                    digest = salt.utils.stringutils.to_bytes(digest)
                if HAS_M2:
                    m_digest = public_decrypt(mkey, payload["sig"])
                else:
                    m_digest = public_decrypt(mkey.publickey(), payload["sig"])
                if m_digest != digest:
                    return "", ""
        else:
            return "", ""

        if six.PY3:
            key_str = salt.utils.stringutils.to_str(key_str)

        if "_|-" in key_str:
            return key_str.split("_|-")
        else:
            if "token" in payload:
                if HAS_M2:
                    token = key.private_decrypt(
                        payload["token"], RSA.pkcs1_oaep_padding
                    )
                else:
                    token = cipher.decrypt(payload["token"])
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
                res = verify_signature(path, message, binascii.a2b_base64(sig))
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
                "There was an error while verifying the masters public-key " "signature"
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
                local_master_pub = fp_.read()

            if payload["pub_key"].replace("\n", "").replace(
                "\r", ""
            ) != local_master_pub.replace("\n", "").replace("\r", ""):
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
        super(SAuth, self).__init__(opts, io_loop=io_loop)

    # an init for the singleton instance to call
    def __singleton_init__(self, opts, io_loop=None):
        """
        Init an Auth instance

        :param dict opts: Options for this server
        :return: Auth instance
        :rtype: Auth
        """
        self.opts = opts
        if six.PY2:
            self.token = Crypticle.generate_key_string()
        else:
            self.token = salt.utils.stringutils.to_bytes(
                Crypticle.generate_key_string()
            )
        self.serial = salt.payload.Serial(self.opts)
        self.pub_path = os.path.join(self.opts["pki_dir"], "minion.pub")
        self.rsa_path = os.path.join(self.opts["pki_dir"], "minion.pem")
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
        with salt.transport.client.ReqChannel.factory(
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
            channel = salt.transport.client.ReqChannel.factory(self.opts, crypt="clear")

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

        if "load" in payload:
            if "ret" in payload["load"]:
                if not payload["load"]["ret"]:
                    if self.opts["rejected_retry"]:
                        log.error(
                            "The Salt Master has rejected this minion's public "
                            "key.\nTo repair this issue, delete the public key "
                            "for this minion on the Salt Master.\nThe Salt "
                            "Minion will attempt to to re-authenicate."
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
                        sys.exit(salt.defaults.exitcodes.EX_NOPERM)
                # has the master returned that its maxed out with minions?
                elif payload["load"]["ret"] == "full":
                    return "full"
                else:
                    log.error(
                        "The Salt Master has cached the public key for this "
                        "node. If this is the first time connecting to this "
                        "master then this key may need to be accepted using "
                        "'salt-key -a %s' on the salt master. This salt "
                        "minion will wait for %s seconds before attempting "
                        "to re-authenticate.",
                        self.opts["id"],
                        self.opts["acceptance_wait_time"],
                    )
                    return "retry"
        auth["aes"] = self.verify_master(payload, master_pub="token" in sign_in_payload)
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
            sys.exit(42)
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


class Crypticle(object):
    """
    Authenticated encryption class

    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    """

    PICKLE_PAD = b"pickle::"
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
            b64key = b64key.decode("utf-8")
        # Return data must be a base64-encoded string, not a unicode type
        return b64key.replace("\n", "")

    @classmethod
    def extract_keys(cls, key_string, key_size):
        if six.PY2:
            key = key_string.decode("base64")
        else:
            key = salt.utils.stringutils.to_bytes(base64.b64decode(key_string))
        assert len(key) == key_size / 8 + cls.SIG_SIZE, "invalid key"
        return key[: -cls.SIG_SIZE], key[-cls.SIG_SIZE :]

    def encrypt(self, data):
        """
        encrypt data with AES-CBC and sign it with HMAC-SHA256
        """
        aes_key, hmac_key = self.keys
        pad = self.AES_BLOCK_SIZE - len(data) % self.AES_BLOCK_SIZE
        if six.PY2:
            data = data + pad * chr(pad)
        else:
            data = data + salt.utils.stringutils.to_bytes(pad * chr(pad))
        iv_bytes = os.urandom(self.AES_BLOCK_SIZE)
        if HAS_M2:
            cypher = EVP.Cipher(
                alg="aes_192_cbc", key=aes_key, iv=iv_bytes, op=1, padding=False
            )
            encr = cypher.update(data)
            encr += cypher.final()
        else:
            cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
            encr = cypher.encrypt(data)
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
        if six.PY3 and not isinstance(data, bytes):
            data = salt.utils.stringutils.to_bytes(data)
        mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
        if len(mac_bytes) != len(sig):
            log.debug("Failed to authenticate message")
            raise AuthenticationError("message authentication failed")
        result = 0

        if six.PY2:
            for zipped_x, zipped_y in zip(mac_bytes, sig):
                result |= ord(zipped_x) ^ ord(zipped_y)
        else:
            for zipped_x, zipped_y in zip(mac_bytes, sig):
                result |= zipped_x ^ zipped_y
        if result != 0:
            log.debug("Failed to authenticate message")
            raise AuthenticationError("message authentication failed")
        iv_bytes = data[: self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE :]
        if HAS_M2:
            cypher = EVP.Cipher(
                alg="aes_192_cbc", key=aes_key, iv=iv_bytes, op=0, padding=False
            )
            encr = cypher.update(data)
            data = encr + cypher.final()
        else:
            cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
            data = cypher.decrypt(data)
        if six.PY2:
            return data[: -ord(data[-1])]
        else:
            return data[: -data[-1]]

    def dumps(self, obj):
        """
        Serialize and encrypt a python object
        """
        return self.encrypt(self.PICKLE_PAD + self.serial.dumps(obj))

    def loads(self, data, raw=False):
        """
        Decrypt and un-serialize a python object
        """
        data = self.decrypt(data)
        # simple integrity check to verify that we got meaningful data
        if not data.startswith(self.PICKLE_PAD):
            return {}
        load = self.serial.loads(data[len(self.PICKLE_PAD) :], raw=raw)
        return load
