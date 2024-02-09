"""
Create and verify ANSI X9.31 RSA signatures using OpenSSL libcrypto
"""

import ctypes.util
import glob
import os
import platform
import sys
from ctypes import c_char_p, c_int, c_void_p, cdll, create_string_buffer, pointer

import salt.utils.platform
import salt.utils.stringutils

# Constants taken from openssl-1.1.0c/include/openssl/crypto.h
OPENSSL_INIT_ADD_ALL_CIPHERS = 0x00000004
OPENSSL_INIT_ADD_ALL_DIGESTS = 0x00000008
OPENSSL_INIT_NO_LOAD_CONFIG = 0x00000080


def _find_libcrypto():
    """
    Find the path (or return the short name) of libcrypto.
    """
    if sys.platform.startswith("win"):
        lib = None
        for path in sys.path:
            lib = glob.glob(os.path.join(path, "libcrypto*.dll"))
            lib = lib[0] if lib else None
            if lib:
                break

    elif salt.utils.platform.is_darwin():
        # will look for several different location on the system,
        # Search in the following order:
        # - salt's pkg install location
        # - relative to the running python (sys.executable)
        # - homebrew
        # - macports
        # - system libraries

        # look in salts pkg install location.
        lib = glob.glob("/opt/salt/lib/libcrypto.dylib")

        # look in location salt is running from
        # this accounts for running from an unpacked onedir file
        lib = lib or glob.glob("lib/libcrypto.dylib")

        # Look in the location relative to the python binary
        # Try to account for this being a venv by resolving the path if it is a
        # symlink
        py_bin = sys.executable
        if os.path.islink(py_bin):
            py_bin = os.path.realpath(py_bin)
        target = os.path.dirname(py_bin)
        if os.path.basename(target) == "bin":
            target = os.path.dirname(target)
        lib = lib or glob.glob(f"{target}/lib/libcrypto.dylib")

        # Find library symlinks in Homebrew locations.
        brew_prefix = os.getenv("HOMEBREW_PREFIX", "/usr/local")
        lib = lib or glob.glob(
            os.path.join(brew_prefix, "opt/openssl/lib/libcrypto.dylib")
        )
        lib = lib or glob.glob(
            os.path.join(brew_prefix, "opt/openssl@*/lib/libcrypto.dylib")
        )
        # look in macports.
        lib = lib or glob.glob("/opt/local/lib/libcrypto.dylib")
        # check if 10.15, regular libcrypto.dylib is just a false pointer.
        if platform.mac_ver()[0].split(".")[:2] == ["10", "15"]:
            lib = lib or glob.glob("/usr/lib/libcrypto.*.dylib")
            lib = list(reversed(sorted(lib)))
        elif int(platform.mac_ver()[0].split(".")[0]) < 11:
            # Fall back on system libcrypto (only works before Big Sur)
            lib = lib or ["/usr/lib/libcrypto.dylib"]
        lib = lib[0] if lib else None
    elif getattr(sys, "frozen", False) and salt.utils.platform.is_smartos():
        lib = glob.glob(os.path.join(os.path.dirname(sys.executable), "libcrypto.so*"))
        lib = lib[0] if lib else None
    else:
        lib = ctypes.util.find_library("crypto")
        if not lib:
            if salt.utils.platform.is_sunos():
                # Solaris-like distribution that use pkgsrc have libraries
                # in a non standard location.
                # (SmartOS, OmniOS, OpenIndiana, ...)
                # This could be /opt/tools/lib (Global Zone) or
                # /opt/local/lib (non-Global Zone), thus the two checks
                # below
                lib = glob.glob("/opt/saltstack/salt/run/libcrypto.so*")
                lib = lib or glob.glob("/opt/local/lib/libcrypto.so*")
                lib = lib or glob.glob("/opt/tools/lib/libcrypto.so*")
                lib = lib[0] if lib else None
            elif salt.utils.platform.is_aix():
                if os.path.isdir("/opt/saltstack/salt/run") or os.path.isdir(
                    "/opt/salt/lib"
                ):
                    # preference for Salt installed fileset
                    lib = glob.glob("/opt/saltstack/salt/run/libcrypto.so*")
                    lib = lib or glob.glob("/opt/salt/lib/libcrypto.so*")
                else:
                    lib = glob.glob("/opt/freeware/lib/libcrypto.so*")
                lib = lib[0] if lib else None
    if not lib:
        raise OSError("Cannot locate OpenSSL libcrypto")
    return lib


def _load_libcrypto():
    """
    Attempt to load libcrypto.
    """
    return cdll.LoadLibrary(_find_libcrypto())


def _init_libcrypto():
    """
    Set up libcrypto argtypes and initialize the library
    """
    libcrypto = _load_libcrypto()

    try:
        # If we're greater than OpenSSL 1.1.0, no need to to the init
        openssl_version_num = libcrypto.OpenSSL_version_num
        if callable(openssl_version_num):
            openssl_version_num = openssl_version_num()
        if openssl_version_num < 0x10100000:
            libcrypto.OPENSSL_init_crypto()
    except AttributeError:
        # Support for OpenSSL < 1.1 (OPENSSL_API_COMPAT < 0x10100000L)
        libcrypto.OPENSSL_no_config()
        libcrypto.OPENSSL_add_all_algorithms_noconf()

    libcrypto.RSA_new.argtypes = ()
    libcrypto.RSA_new.restype = c_void_p
    libcrypto.RSA_free.argtypes = (c_void_p,)
    libcrypto.RSA_size.argtype = c_void_p
    libcrypto.BIO_new_mem_buf.argtypes = (c_char_p, c_int)
    libcrypto.BIO_new_mem_buf.restype = c_void_p
    libcrypto.BIO_free.argtypes = (c_void_p,)
    libcrypto.PEM_read_bio_RSAPrivateKey.argtypes = (
        c_void_p,
        c_void_p,
        c_void_p,
        c_void_p,
    )
    libcrypto.PEM_read_bio_RSAPrivateKey.restype = c_void_p
    libcrypto.PEM_read_bio_RSA_PUBKEY.argtypes = (
        c_void_p,
        c_void_p,
        c_void_p,
        c_void_p,
    )
    libcrypto.PEM_read_bio_RSA_PUBKEY.restype = c_void_p
    libcrypto.RSA_private_encrypt.argtypes = (
        c_int,
        c_char_p,
        c_char_p,
        c_void_p,
        c_int,
    )
    libcrypto.RSA_public_decrypt.argtypes = (c_int, c_char_p, c_char_p, c_void_p, c_int)

    return libcrypto


libcrypto = _init_libcrypto()

# openssl/rsa.h:#define RSA_X931_PADDING 5
RSA_X931_PADDING = 5


class RSAX931Signer:
    """
    Create ANSI X9.31 RSA signatures using OpenSSL libcrypto
    """

    def __init__(self, keydata):
        """
        Init an RSAX931Signer instance

        :param str keydata: The RSA private key in PEM format
        """
        keydata = salt.utils.stringutils.to_bytes(keydata, "ascii")
        self._bio = libcrypto.BIO_new_mem_buf(keydata, len(keydata))
        self._rsa = c_void_p(libcrypto.RSA_new())
        if not libcrypto.PEM_read_bio_RSAPrivateKey(
            self._bio, pointer(self._rsa), None, None
        ):
            raise ValueError("invalid RSA private key")

    # pylint: disable=W1701
    def __del__(self):
        libcrypto.BIO_free(self._bio)
        libcrypto.RSA_free(self._rsa)

    # pylint: enable=W1701

    def sign(self, msg):
        """
        Sign a message (digest) using the private key

        :param str msg: The message (digest) to sign
        :rtype: str
        :return: The signature, or an empty string if the encryption failed
        """
        # Allocate a buffer large enough for the signature. Freed by ctypes.
        buf = create_string_buffer(libcrypto.RSA_size(self._rsa))
        msg = salt.utils.stringutils.to_bytes(msg)
        size = libcrypto.RSA_private_encrypt(
            len(msg), msg, buf, self._rsa, RSA_X931_PADDING
        )
        if size < 0:
            raise ValueError("Unable to encrypt message")
        return buf[0:size]


class RSAX931Verifier:
    """
    Verify ANSI X9.31 RSA signatures using OpenSSL libcrypto
    """

    def __init__(self, pubdata):
        """
        Init an RSAX931Verifier instance

        :param str pubdata: The RSA public key in PEM format
        """
        pubdata = salt.utils.stringutils.to_bytes(pubdata, "ascii")
        pubdata = pubdata.replace(b"RSA ", b"")
        self._bio = libcrypto.BIO_new_mem_buf(pubdata, len(pubdata))
        self._rsa = c_void_p(libcrypto.RSA_new())
        if not libcrypto.PEM_read_bio_RSA_PUBKEY(
            self._bio, pointer(self._rsa), None, None
        ):
            raise ValueError("invalid RSA public key")

    # pylint: disable=W1701
    def __del__(self):
        libcrypto.BIO_free(self._bio)
        libcrypto.RSA_free(self._rsa)

    # pylint: enable=W1701

    def verify(self, signed):
        """
        Recover the message (digest) from the signature using the public key

        :param str signed: The signature created with the private key
        :rtype: str
        :return: The message (digest) recovered from the signature, or an empty
            string if the decryption failed
        """
        # Allocate a buffer large enough for the signature. Freed by ctypes.
        buf = create_string_buffer(libcrypto.RSA_size(self._rsa))
        signed = salt.utils.stringutils.to_bytes(signed)
        size = libcrypto.RSA_public_decrypt(
            len(signed), signed, buf, self._rsa, RSA_X931_PADDING
        )
        if size < 0:
            raise ValueError("Unable to decrypt message")
        return buf[0:size]
