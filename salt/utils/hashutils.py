# encoding: utf-8
'''
A collection of hashing and encoding utils.
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import base64
import hashlib
import hmac
import random

# Import Salt libs
from salt.ext import six
import salt.utils.files
import salt.utils.stringutils

from salt.utils.decorators.jinja import jinja_filter


@jinja_filter('base64_encode')
def base64_b64encode(instr):
    '''
    Encode a string as base64 using the "modern" Python interface.

    Among other possible differences, the "modern" encoder does not include
    newline ('\\n') characters in the encoded output.
    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        b64 = base64.b64encode(b)
        return salt.utils.stringutils.to_str(b64)
    return base64.b64encode(instr)


@jinja_filter('base64_decode')
def base64_b64decode(instr):
    '''
    Decode a base64-encoded string using the "modern" Python interface.
    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        data = base64.b64decode(b)
        try:
            return salt.utils.stringutils.to_str(data)
        except UnicodeDecodeError:
            return data
    return base64.b64decode(instr)


def base64_encodestring(instr):
    '''
    Encode a string as base64 using the "legacy" Python interface.

    Among other possible differences, the "legacy" encoder includes
    a newline ('\\n') character after every 76 characters and always
    at the end of the encoded string.
    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        b64 = base64.encodebytes(b)
        return salt.utils.stringutils.to_str(b64)
    return base64.encodestring(instr)


def base64_decodestring(instr):
    '''
    Decode a base64-encoded string using the "legacy" Python interface.

    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        data = base64.decodebytes(b)
        try:
            return salt.utils.stringutils.to_str(data)
        except UnicodeDecodeError:
            return data
    return base64.decodestring(instr)


@jinja_filter('md5')
def md5_digest(instr):
    '''
    Generate an md5 hash of a given string.
    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        return hashlib.md5(b).hexdigest()
    return hashlib.md5(instr).hexdigest()


@jinja_filter('sha256')
def sha256_digest(instr):
    '''
    Generate an sha256 hash of a given string.
    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        return hashlib.sha256(b).hexdigest()
    return hashlib.sha256(instr).hexdigest()


@jinja_filter('sha512')
def sha512_digest(instr):
    '''
    Generate an sha512 hash of a given string
    '''
    if six.PY3:
        b = salt.utils.stringutils.to_bytes(instr)
        return hashlib.sha512(b).hexdigest()
    return hashlib.sha512(instr).hexdigest()


@jinja_filter('hmac')
def hmac_signature(string, shared_secret, challenge_hmac):
    '''
    Verify a challenging hmac signature against a string / shared-secret
    Returns a boolean if the verification succeeded or failed.
    '''
    if six.text_type:
        msg = salt.utils.stringutils.to_bytes(string)
        key = salt.utils.stringutils.to_bytes(shared_secret)
        challenge = salt.utils.stringutils.to_bytes(challenge_hmac)
    else:
        msg = string
        key = shared_secret
        challenge = challenge_hmac
    hmac_hash = hmac.new(key, msg, hashlib.sha256)
    valid_hmac = base64.b64encode(hmac_hash.digest())
    return valid_hmac == challenge


@jinja_filter('rand_str')  # Remove this for Neon
@jinja_filter('random_hash')
def random_hash(size=9999999999, hash_type=None):
    '''
    Return a hash of a randomized data from random.SystemRandom()
    '''
    if not hash_type:
        hash_type = 'md5'
    hasher = getattr(hashlib, hash_type)
    return hasher(salt.utils.stringutils.to_bytes(six.text_type(random.SystemRandom().randint(0, size)))).hexdigest()


@jinja_filter('file_hashsum')
def get_hash(path, form='sha256', chunk_size=65536):
    '''
    Get the hash sum of a file

    This is better than ``get_sum`` for the following reasons:
        - It does not read the entire file into memory.
        - It does not return a string on error. The returned value of
            ``get_sum`` cannot really be trusted since it is vulnerable to
            collisions: ``get_sum(..., 'xyz') == 'Hash xyz not supported'``
    '''
    hash_type = hasattr(hashlib, form) and getattr(hashlib, form) or None
    if hash_type is None:
        raise ValueError('Invalid hash type: {0}'.format(form))

    with salt.utils.files.fopen(path, 'rb') as ifile:
        hash_obj = hash_type()
        # read the file in in chunks, not the entire file
        for chunk in iter(lambda: ifile.read(chunk_size), b''):
            hash_obj.update(chunk)
        return hash_obj.hexdigest()
