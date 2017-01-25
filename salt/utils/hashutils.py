# encoding: utf-8
'''
A collection of hashing and encoding utils.
'''
from __future__ import absolute_import

# Import python libs
import base64
import hashlib
import hmac

# Import Salt libs
import salt.ext.six as six
import salt.utils


def base64_b64encode(instr):
    '''
    Encode a string as base64 using the "modern" Python interface.

    Among other possible differences, the "modern" encoder does not include
    newline ('\\n') characters in the encoded output.
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        b64 = base64.b64encode(b)
        return salt.utils.to_str(b64)
    return base64.b64encode(instr)


def base64_b64decode(instr):
    '''
    Decode a base64-encoded string using the "modern" Python interface.
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        data = base64.b64decode(b)
        try:
            return salt.utils.to_str(data)
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
        b = salt.utils.to_bytes(instr)
        b64 = base64.encodebytes(b)
        return salt.utils.to_str(b64)
    return base64.encodestring(instr)


def base64_decodestring(instr):
    '''
    Decode a base64-encoded string using the "legacy" Python interface.

    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        data = base64.decodebytes(b)
        try:
            return salt.utils.to_str(data)
        except UnicodeDecodeError:
            return data
    return base64.decodestring(instr)


def md5_digest(instr):
    '''
    Generate an md5 hash of a given string.
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        return hashlib.md5(b).hexdigest()
    return hashlib.md5(instr).hexdigest()


def sha256_digest(instr):
    '''
    Generate an sha256 hash of a given string.
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        return hashlib.sha256(b).hexdigest()
    return hashlib.sha256(instr).hexdigest()


def sha512_digest(instr):
    '''
    Generate an sha512 hash of a given string
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        return hashlib.sha512(b).hexdigest()
    return hashlib.sha512(instr).hexdigest()


def hmac_signature(string, shared_secret, challenge_hmac):
    '''
    Verify a challenging hmac signature against a string / shared-secret
    Returns a boolean if the verification succeeded or failed.
    '''
    if six.PY3:
        msg = salt.utils.to_bytes(string)
        key = salt.utils.to_bytes(shared_secret)
        challenge = salt.utils.to_bytes(challenge_hmac)
    else:
        msg = string
        key = shared_secret
        challenge = challenge_hmac
    hmac_hash = hmac.new(key, msg, hashlib.sha256)
    valid_hmac = base64.b64encode(hmac_hash.digest())
    return valid_hmac == challenge
