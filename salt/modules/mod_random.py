# -*- coding: utf-8 -*-
"""
Provides access to randomness generators.
=========================================

.. versionadded:: 2014.7.0

"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import base64
import hashlib
import random

# Import salt libs
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six

if six.PY2:
    ALGORITHMS_ATTR_NAME = "algorithms"
else:
    ALGORITHMS_ATTR_NAME = "algorithms_guaranteed"

# Define the module's virtual name
__virtualname__ = "random"


def __virtual__(algorithm="sha512"):
    """
    Sanity check for compatibility with Python 2.6 / 2.7
    """
    # The hashlib function on Python <= 2.6 does not provide the attribute 'algorithms'
    # This attribute was introduced on Python >= 2.7
    if six.PY2:
        if not hasattr(hashlib, "algorithms") and not hasattr(hashlib, algorithm):
            return (
                False,
                "The random execution module cannot be loaded: only available in Python >= 2.7.",
            )

    # Under python >= 3.2, the attribute name changed to 'algorithms_guaranteed'
    # Since we support python 3.4+, we're good
    return __virtualname__


def hash(value, algorithm="sha512"):
    """
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
    """
    if six.PY3 and isinstance(value, six.string_types):
        # Under Python 3 we must work with bytes
        value = value.encode(__salt_system_encoding__)

    if hasattr(hashlib, ALGORITHMS_ATTR_NAME) and algorithm in getattr(
        hashlib, ALGORITHMS_ATTR_NAME
    ):
        hasher = hashlib.new(algorithm)
        hasher.update(value)
        out = hasher.hexdigest()
    elif hasattr(hashlib, algorithm):
        hasher = hashlib.new(algorithm)
        hasher.update(value)
        out = hasher.hexdigest()
    else:
        raise SaltInvocationError("You must specify a valid algorithm.")

    return out


def str_encode(value, encoder="base64"):
    """
    .. versionadded:: 2014.7.0

    value
        The value to be encoded.

    encoder : base64
        The encoder to use on the subsequent string.

    CLI Example:

    .. code-block:: bash

        salt '*' random.str_encode 'I am a new string' base64
    """
    if six.PY2:
        try:
            out = value.encode(encoder)
        except LookupError:
            raise SaltInvocationError("You must specify a valid encoder")
        except AttributeError:
            raise SaltInvocationError("Value must be an encode-able string")
    else:
        if isinstance(value, six.string_types):
            value = value.encode(__salt_system_encoding__)
        if encoder == "base64":
            try:
                out = base64.b64encode(value)
                out = out.decode(__salt_system_encoding__)
            except TypeError:
                raise SaltInvocationError("Value must be an encode-able string")
        else:
            try:
                out = value.encode(encoder)
            except LookupError:
                raise SaltInvocationError("You must specify a valid encoder")
            except AttributeError:
                raise SaltInvocationError("Value must be an encode-able string")
    return out


def get_str(length=20):
    """
    .. versionadded:: 2014.7.0

    Returns a random string of the specified length.

    length : 20
        Any valid number of bytes.

    CLI Example:

    .. code-block:: bash

        salt '*' random.get_str 128
    """
    return salt.utils.pycrypto.secure_password(length)


def shadow_hash(crypt_salt=None, password=None, algorithm="sha512"):
    """
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
    """
    return salt.utils.pycrypto.gen_hash(crypt_salt, password, algorithm)


def rand_int(start=1, end=10, seed=None):
    """
    Returns a random integer number between the start and end number.

    .. versionadded: 2015.5.3

    start : 1
        Any valid integer number

    end : 10
        Any valid integer number

    seed :
        Optional hashable object

    .. versionchanged:: 2019.2.0
        Added seed argument. Will return the same result when run with the same seed.


    CLI Example:

    .. code-block:: bash

        salt '*' random.rand_int 1 10
    """
    if seed is not None:
        random.seed(seed)
    return random.randint(start, end)


def seed(range=10, hash=None):
    """
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
    """
    if hash is None:
        hash = __grains__["id"]

    random.seed(hash)
    return random.randrange(range)
