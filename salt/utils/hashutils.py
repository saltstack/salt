"""
A collection of hashing and encoding utils.
"""

import base64
import hashlib
import hmac
import os
import random

import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.utils.decorators.jinja import jinja_filter


@jinja_filter("base64_encode")
def base64_b64encode(instr):
    """
    Encode a string as base64 using the "modern" Python interface.

    Among other possible differences, the "modern" encoder does not include
    newline ('\\n') characters in the encoded output.
    """
    return salt.utils.stringutils.to_unicode(
        base64.b64encode(salt.utils.stringutils.to_bytes(instr)),
        encoding="utf8" if salt.utils.platform.is_windows() else None,
    )


@jinja_filter("base64_decode")
def base64_b64decode(instr):
    """
    Decode a base64-encoded string using the "modern" Python interface.
    """
    decoded = base64.b64decode(salt.utils.stringutils.to_bytes(instr))
    try:
        return salt.utils.stringutils.to_unicode(
            decoded, encoding="utf8" if salt.utils.platform.is_windows() else None
        )
    except UnicodeDecodeError:
        return decoded


def base64_encodestring(instr):
    """
    Encode a byte-like object as base64 using the "modern" Python interface.

    Among other possible differences, the "modern" encoder includes
    a newline ('\\n') character after every 76 characters and always
    at the end of the encoded string.
    """
    return salt.utils.stringutils.to_unicode(
        base64.encodebytes(salt.utils.stringutils.to_bytes(instr)),
        encoding="utf8" if salt.utils.platform.is_windows() else None,
    )


def base64_decodestring(instr):
    """
    Decode a base64-encoded byte-like object using the "modern" Python interface.
    """
    bvalue = salt.utils.stringutils.to_bytes(instr)
    decoded = base64.decodebytes(bvalue)
    try:
        return salt.utils.stringutils.to_unicode(
            decoded, encoding="utf8" if salt.utils.platform.is_windows() else None
        )
    except UnicodeDecodeError:
        return decoded


@jinja_filter("md5")
def md5_digest(instr):
    """
    Generate an md5 hash of a given string.
    """
    return salt.utils.stringutils.to_unicode(
        hashlib.md5(salt.utils.stringutils.to_bytes(instr)).hexdigest()
    )


@jinja_filter("sha1")
def sha1_digest(instr):
    """
    Generate an sha1 hash of a given string.
    """
    return hashlib.sha1(salt.utils.stringutils.to_bytes(instr)).hexdigest()


@jinja_filter("sha256")
def sha256_digest(instr):
    """
    Generate a sha256 hash of a given string.
    """
    return salt.utils.stringutils.to_unicode(
        hashlib.sha256(salt.utils.stringutils.to_bytes(instr)).hexdigest()
    )


@jinja_filter("sha512")
def sha512_digest(instr):
    """
    Generate a sha512 hash of a given string
    """
    return salt.utils.stringutils.to_unicode(
        hashlib.sha512(salt.utils.stringutils.to_bytes(instr)).hexdigest()
    )


@jinja_filter("hmac")
def hmac_signature(string, shared_secret, challenge_hmac):
    """
    Verify a challenging hmac signature against a string / shared-secret
    Returns a boolean if the verification succeeded or failed.
    """
    msg = salt.utils.stringutils.to_bytes(string)
    key = salt.utils.stringutils.to_bytes(shared_secret)
    challenge = salt.utils.stringutils.to_bytes(challenge_hmac)
    hmac_hash = hmac.new(key, msg, hashlib.sha256)
    valid_hmac = base64.b64encode(hmac_hash.digest())
    return valid_hmac == challenge


@jinja_filter("hmac_compute")
def hmac_compute(string, shared_secret):
    """
    Create an hmac digest.
    """
    msg = salt.utils.stringutils.to_bytes(string)
    key = salt.utils.stringutils.to_bytes(shared_secret)
    hmac_hash = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return hmac_hash


@jinja_filter("rand_str")
@jinja_filter("random_hash")
def random_hash(size=9999999999, hash_type=None):
    """
    Return a hash of a randomized data from random.SystemRandom()
    """
    if not hash_type:
        hash_type = "md5"
    hasher = getattr(hashlib, hash_type)
    return hasher(
        salt.utils.stringutils.to_bytes(str(random.SystemRandom().randint(0, size)))
    ).hexdigest()


@jinja_filter("file_hashsum")
def get_hash(path, form="sha256", chunk_size=65536):
    """
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``
    """
    hash_type = hasattr(hashlib, form) and getattr(hashlib, form) or None
    if hash_type is None:
        raise ValueError(f"Invalid hash type: {form}")

    with salt.utils.files.fopen(path, "rb") as ifile:
        hash_obj = hash_type()
        # read the file in in chunks, not the entire file
        for chunk in iter(lambda: ifile.read(chunk_size), b""):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()


class DigestCollector:
    """
    Class to collect digest of the file tree.
    """

    def __init__(self, form="sha256", buff=0x10000):
        """
        Constructor of the class.
        :param form:
        """
        self.__digest = hasattr(hashlib, form) and getattr(hashlib, form)() or None
        if self.__digest is None:
            raise ValueError(f"Invalid hash type: {form}")
        self.__buff = buff

    def add(self, path):
        """
        Update digest with the file content by path.

        :param path:
        :return:
        """
        with salt.utils.files.fopen(path, "rb") as ifile:
            for chunk in iter(lambda: ifile.read(self.__buff), b""):
                self.__digest.update(chunk)

    def digest(self):
        """
        Get digest.

        :return:
        """

        return salt.utils.stringutils.to_str(self.__digest.hexdigest() + os.linesep)
