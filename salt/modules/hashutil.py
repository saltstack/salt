# encoding: utf-8
'''
A collection of hashing and encoding functions
'''
from __future__ import absolute_import

# Import python libs
import base64
import hashlib
import hmac
import StringIO

# Import Salt libs
import salt.exceptions
import salt.ext.six as six
import salt.utils


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


def base64_b64encode(instr):
    '''
    Encode a string as base64 using the "modern" Python interface.

    Among other possible differences, the "modern" encoder does not include
    newline ('\\n') characters in the encoded output.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_b64encode 'get salted'
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        b64 = base64.b64encode(b)
        return salt.utils.to_str(b64)
    return base64.b64encode(instr)


def base64_b64decode(instr):
    '''
    Decode a base64-encoded string using the "modern" Python interface

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_b64decode 'Z2V0IHNhbHRlZA=='
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

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_encodestring 'get salted'
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        b64 = base64.encodebytes(b)
        return salt.utils.to_str(b64)
    return base64.encodestring(instr)


def base64_encodefile(fname):
    '''
    Read a file from the file system and return as a base64 encoded string

    .. versionadded:: 2016.3.0

    Pillar example:

    .. code-block:: yaml

        path:
          to:
            data: |
              {{ salt.hashutil.base64_encodefile('/path/to/binary_file') | indent(6) }}

    The :py:func:`file.decode <salt.states.file.decode>` state function can be
    used to decode this data and write it to disk.

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
    Decode a base64-encoded string using the "legacy" Python interface

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_decodestring instr='Z2V0IHNhbHRlZAo='

    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        data = base64.decodebytes(b)
        try:
            return salt.utils.to_str(data)
        except UnicodeDecodeError:
            return data
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
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        return hashlib.md5(b).hexdigest()
    return hashlib.md5(instr).hexdigest()


def sha256_digest(instr):
    '''
    Generate an sha256 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.sha256_digest 'get salted'
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        return hashlib.sha256(b).hexdigest()
    return hashlib.sha256(instr).hexdigest()


def sha512_digest(instr):
    '''
    Generate an sha512 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.sha512_digest 'get salted'
    '''
    if six.PY3:
        b = salt.utils.to_bytes(instr)
        return hashlib.sha512(b).hexdigest()
    return hashlib.sha512(instr).hexdigest()


def hmac_signature(string, shared_secret, challenge_hmac):
    '''
    Verify a challenging hmac signature against a string / shared-secret

    .. versionadded:: 2014.7.0

    Returns a boolean if the verification succeeded or failed.

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.hmac_signature 'get salted' 'shared secret' 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ='
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
