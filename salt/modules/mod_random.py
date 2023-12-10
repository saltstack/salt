"""
Provides access to randomness generators.
=========================================

.. versionadded:: 2014.7.0

"""

import base64
import random

import salt.utils.data
import salt.utils.pycrypto
from salt.exceptions import SaltInvocationError

# Define the module's virtual name
__virtualname__ = "random"


def __virtual__():
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
    return salt.utils.data.hash(value, algorithm=algorithm)


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
    if isinstance(value, str):
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


def get_str(
    length=20,
    chars=None,
    lowercase=True,
    uppercase=True,
    digits=True,
    punctuation=True,
    whitespace=False,
    printable=False,
):
    """
    .. versionadded:: 2014.7.0
    .. versionchanged:: 3004

         Changed the default character set used to include symbols and implemented arguments to control the used character set.

    Returns a random string of the specified length.

    length : 20
        Any valid number of bytes.

    chars : None
        .. versionadded:: 3004

        String with any character that should be used to generate random string.

        This argument supersedes all other character controlling arguments.

    lowercase : True
        .. versionadded:: 3004

        Use lowercase letters in generated random string.
        (see :py:data:`string.ascii_lowercase`)

        This argument is superseded by chars.

    uppercase : True
        .. versionadded:: 3004

        Use uppercase letters in generated random string.
        (see :py:data:`string.ascii_uppercase`)

        This argument is superseded by chars.

    digits : True
        .. versionadded:: 3004

        Use digits in generated random string.
        (see :py:data:`string.digits`)

        This argument is superseded by chars.

    printable : False
        .. versionadded:: 3004

        Use printable characters in generated random string and includes lowercase, uppercase,
        digits, punctuation and whitespace.
        (see :py:data:`string.printable`)

        It is disabled by default as includes whitespace characters which some systems do not
        handle well in passwords.
        This argument also supersedes all other classes because it includes them.

        This argument is superseded by chars.

    punctuation : True
        .. versionadded:: 3004

        Use punctuation characters in generated random string.
        (see :py:data:`string.punctuation`)

        This argument is superseded by chars.

    whitespace : False
        .. versionadded:: 3004

        Use whitespace characters in generated random string.
        (see :py:data:`string.whitespace`)

        It is disabled by default as some systems do not handle whitespace characters in passwords
        well.

        This argument is superseded by chars.

    CLI Example:

    .. code-block:: bash

        salt '*' random.get_str 128
        salt '*' random.get_str 128 chars='abc123.!()'
        salt '*' random.get_str 128 lowercase=False whitespace=True
    """
    return salt.utils.pycrypto.secure_password(
        length=length,
        chars=chars,
        lowercase=lowercase,
        uppercase=uppercase,
        digits=digits,
        punctuation=punctuation,
        whitespace=whitespace,
        printable=printable,
    )


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

    .. versionadded:: 2015.5.3

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

    .. versionadded:: 2015.8.0

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


def sample(value, size, seed=None):
    """
    Return a given sample size from a list. By default, the random number
    generator uses the current system time unless given a seed value.

    .. versionadded:: 3005

    value
        A list to e used as input.

    size
        The sample size to return.

    seed
        Any value which will be hashed as a seed for random.

    CLI Example:

    .. code-block:: bash

        salt '*' random.sample '["one", "two"]' 1 seed="something"
    """
    return salt.utils.data.sample(value, size, seed=seed)


def shuffle(value, seed=None):
    """
    Return a shuffled copy of an input list. By default, the random number
    generator uses the current system time unless given a seed value.

    .. versionadded:: 3005

    value
        A list to be used as input.

    seed
        Any value which will be hashed as a seed for random.

    CLI Example:

    .. code-block:: bash

        salt '*' random.shuffle '["one", "two"]' seed="something"
    """
    return salt.utils.data.shuffle(value, seed=seed)
