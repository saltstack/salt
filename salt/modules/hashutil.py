# encoding: utf-8
'''
A collection of hashing and encoding functions
'''
from __future__ import absolute_import
import base64
import hashlib
import hmac
import StringIO

import salt.exceptions


def digest(instr, checksum='md5'):
    '''
    Return a checksum digest for a string

    instr
        A string
    checksum : ``md5``
        The hashing algorithm to use to generate checksums. Valid options: md5,
        sha256, sha512.

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.digest 'get salted'
    '''
    hashing_funcs = {
        'md5': __salt__['hashutil.md5_digest'],
        'sha256': __salt__['hashutil.sha256_digest'],
        'sha512': __salt__['hashutil.sha512_digest'],
    }
    hash_func = hashing_funcs.get(checksum)

    if hash_func is None:
        raise salt.exceptions.CommandExecutionError(
                "Hash func '{0}' is not supported.".format(checksum))

    return hash_func(instr)


def digest_file(infile, checksum='md5'):
    '''
    Return a checksum digest for a file

    infile
        A file path
    checksum : ``md5``
        The hashing algorithm to use to generate checksums. Wraps the
        :py:func:`hashutil.digest <salt.modules.hashutil.digest>` execution
        function.

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.digest_file /path/to/file
    '''
    if not __salt__['file.file_exists'](infile):
        raise salt.exceptions.CommandExecutionError(
                "File path '{0}' not found.".format(infile))

    with open(infile, 'rb') as f:
        file_hash = __salt__['hashutil.digest'](f.read(), checksum)

    return file_hash


def base64_encodestring(instr):
    '''
    Encode a string as base64

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_encodestring 'get salted'
    '''
    return base64.encodestring(instr)


def base64_encodefile(fname):
    '''
    Read a file from the file system and return as a base64 encoded string

    .. versionadded:: 2015.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_encodefile /path/to/binary_file
    '''
    encoded_f = StringIO.StringIO()

    with open(fname, 'rb') as f:
        base64.encode(f, encoded_f)

    encoded_f.seek(0)
    return encoded_f.read()


def base64_decodestring(instr):
    '''
    Decode a base64-encoded string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_decodestring instr='Z2V0IHNhbHRlZAo='

    '''
    return base64.decodestring(instr)


def base64_decodefile(instr, outfile):
    r'''
    Decode a base64-encoded string and write the result to a file

    .. versionadded:: 2015.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_decodefile instr='Z2V0IHNhbHRlZAo=' outfile='/path/to/binary_file'
    '''
    encoded_f = StringIO.StringIO(instr)

    with open(outfile, 'wb') as f:
        base64.decode(encoded_f, f)

    return True


def md5_digest(instr):
    '''
    Generate an md5 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.md5_digest 'get salted'
    '''
    return hashlib.md5(instr).hexdigest()


def sha256_digest(instr):
    '''
    Generate an sha256 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.sha256_digest 'get salted'
    '''
    return hashlib.sha256(instr).hexdigest()


def sha512_digest(instr):
    '''
    Generate an sha512 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.sha512_digest 'get salted'
    '''
    return hashlib.sha512(instr).hexdigest()


def hmac_signature(string, shared_secret, challenge_hmac):
    '''
    Verify a challenging hmac signature against a string / shared-secret

    .. versionadded:: 2014.7.0

    Returns a boolean if the verification succeeded or failed.

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.hmac_signature 'get salted' 'shared secret' 'NS2BvKxFRk+rndAlFbCYIFNVkPtI/3KiIYQw4okNKU8='
    '''
    hmac_hash = hmac.new(string, shared_secret, hashlib.sha256)
    valid_hmac = base64.b64encode(hmac_hash.digest())
    return valid_hmac == challenge_hmac
