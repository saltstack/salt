# -*- coding: utf-8 -*-
'''
Provides access to randomness generators.
=========================================

.. versionadded:: 2014.7.0

'''
from __future__ import absolute_import
# Import python libs
import hashlib
import random

# Import salt libs
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError

# Define the module's virtual name
__virtualname__ = 'random'


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    # Certain versions of hashlib do not contain
    # the necessary functions
    if not hasattr(hashlib, 'algorithms'):
        return False
    return __virtualname__


def hash(value, algorithm='sha512'):
    '''
    .. versionadded:: 2014.7.0

    Encodes a value with the specified encoder.

    value
        The value to be hashed.

    algorithm : sha512
        The algorithm to use. May be any valid algorithm supported by
        hashlib.

    CLI Example:

    .. code-block:: bash

        salt '*' random.hash 'I am a string' md5
    '''
    if algorithm in hashlib.algorithms:
        hasher = hashlib.new(algorithm)
        hasher.update(value)
        out = hasher.hexdigest()
    else:
        raise SaltInvocationError('You must specify a valid algorithm.')

    return out


def str_encode(value, encoder='base64'):
    '''
    .. versionadded:: 2014.7.0

    value
        The value to be encoded.

    encoder : base64
        The encoder to use on the subsequent string.

    CLI Example:

    .. code-block:: bash

        salt '*' random.str_encode 'I am a new string' base64
    '''
    try:
        out = value.encode(encoder)
    except LookupError:
        raise SaltInvocationError('You must specify a valid encoder')
    except AttributeError:
        raise SaltInvocationError('Value must be an encode-able string')

    return out


def get_str(length=20):
    '''
    .. versionadded:: 2014.7.0

    Returns a random string of the specified length.

    length : 20
        Any valid number of bytes.

    CLI Example:

    .. code-block:: bash

        salt '*' random.get_str 128
    '''
    return salt.utils.pycrypto.secure_password(length)


def shadow_hash(crypt_salt=None, password=None, algorithm='sha512'):
    '''
    Generates a salted hash suitable for /etc/shadow.

    crypt_salt : None
        Salt to be used in the generation of the hash. If one is not
        provided, a random salt will be generated.

    password : None
        Value to be salted and hashed. If one is not provided, a random
        password will be generated.

    algorithm : sha512
        Hash algorithm to use.

    CLI Example:

    .. code-block:: bash

        salt '*' random.shadow_hash 'My5alT' 'MyP@asswd' md5
    '''
    return salt.utils.pycrypto.gen_hash(crypt_salt, password, algorithm)


def rand_int(start=1, end=10):
    '''
    Returns a random integer number between the start and end number.

    .. versionadded: 2015.5.3

    start : 1
        Any valid integer number

    end : 10
        Any valid integer number

    CLI Example:

    .. code-block:: bash

        salt '*' random.rand_int 1 10
    '''
    return random.randint(start, end)


def seed(range=10, hash=None):
    '''
    Returns a random number within a range. Optional hash argument can
    be any hashable object. If hash is omitted or None, the id of the minion is used.

    .. versionadded: 2015.8.0

    hash: None
        Any hashable object.

    range: 10
        Any valid integer number

    CLI Example:

    .. code-block:: bash

        salt '*' random.seed 10 hash=None
    '''
    if hash is None:
        hash = __grains__['id']

    random.seed(hash)
    return random.randrange(range)
