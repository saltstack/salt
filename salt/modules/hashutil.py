# encoding: utf-8
'''
A collection of hashing and encoding functions
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import base64
import hashlib
import hmac

# Import Salt libs
import salt.exceptions
from salt.ext import six
import salt.utils.files
import salt.utils.hashutils
import salt.utils.stringutils

if six.PY2:
    import StringIO
elif six.PY3:
    from io import StringIO


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

    with salt.utils.files.fopen(infile, 'rb') as f:
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
    return salt.utils.hashutils.base64_b64encode(instr)


def base64_b64decode(instr):
    '''
    Decode a base64-encoded string using the "modern" Python interface

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_b64decode 'Z2V0IHNhbHRlZA=='
    '''
    return salt.utils.hashutils.base64_b64decode(instr)


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
    return salt.utils.hashutils.base64_encodestring(instr)


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

    with salt.utils.files.fopen(fname, 'rb') as f:
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
    return salt.utils.hashutils.base64_decodestring(instr)


def base64_decodefile(instr, outfile):
    r'''
    Decode a base64-encoded string and write the result to a file

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.base64_decodefile instr='Z2V0IHNhbHRlZAo=' outfile='/path/to/binary_file'
    '''
    encoded_f = StringIO.StringIO(instr)

    with salt.utils.files.fopen(outfile, 'wb') as f:
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
    return salt.utils.hashutils.md5_digest(instr)


def sha256_digest(instr):
    '''
    Generate an sha256 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.sha256_digest 'get salted'
    '''
    return salt.utils.hashutils.sha256_digest(instr)


def sha512_digest(instr):
    '''
    Generate an sha512 hash of a given string

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.sha512_digest 'get salted'
    '''
    return salt.utils.hashutils.sha512_digest(instr)


def hmac_signature(string, shared_secret, challenge_hmac):
    '''
    Verify a challenging hmac signature against a string / shared-secret

    .. versionadded:: 2014.7.0

    Returns a boolean if the verification succeeded or failed.

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.hmac_signature 'get salted' 'shared secret' 'eBWf9bstXg+NiP5AOwppB5HMvZiYMPzEM9W5YMm/AmQ='
    '''
    return salt.utils.hashutils.hmac_signature(string, shared_secret, challenge_hmac)


def github_signature(string, shared_secret, challenge_hmac):
    '''
    Verify a challenging hmac signature against a string / shared-secret for
    github webhooks.

    .. versionadded:: 2017.7.0

    Returns a boolean if the verification succeeded or failed.

    CLI Example:

    .. code-block:: bash

        salt '*' hashutil.github_signature '{"ref":....} ' 'shared secret' 'sha1=bc6550fc290acf5b42283fa8deaf55cea0f8c206'
    '''
    msg = string
    key = shared_secret
    hashtype, challenge = challenge_hmac.split('=')
    if six.text_type:
        msg = salt.utils.stringutils.to_bytes(msg)
        key = salt.utils.stringutils.to_bytes(key)
    hmac_hash = hmac.new(key, msg, getattr(hashlib, hashtype))
    return hmac_hash.hexdigest() == challenge
