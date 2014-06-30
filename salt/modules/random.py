# -*- coding: utf-8 -*-
'''
.. versionadded:: Helium

Provides access to randomness generators.
'''

# Import python libs
import base64
import hashlib
import os

# Import salt libs
from salt.exceptions import SaltInvocationError

def encode(value, encoder='sha256'):
    '''
    .. versionadded:: Helium

    Encodes a value with the specified encoder.

    value
        The value to be encoded.

    encoder : sha256
        The encoder to use. May be any valid algorithm supported by hashlib or
        ``base64``.

    CLI Example:
    
    .. code-block:: bash

        salt '*' random.encode 'I am a string' md5
    '''
    if encoder == 'base64':
        out = base64.b64encode(value)
    elif encoder in hashlib.algorithms:
        hasher = hashlib.new(encoder)
        hasher.update(value)
        out = hasher.hexdigest()
    else:
        raise SaltInvocationError('You must specify a valid encoder.')

    return out


def urandom(length=256, encoder=None):
    '''
    .. versionadded:: Helium

    Returns a random string of the specified length, optionally encoded. The
    truncation takes place prior to encoding so final output may be larger or
    smaller according to the encoder output.

    length : 256
        Any valid number of bytes.

    encoder : None
        An optional encoder. May be any valid algorithm supported by haslib
        or ``base64``.

    CLI Example:

    .. code-block:: bash

        salt '*' random.get 128 sha512
    '''

    rand = os.urandom(length)

    if encoder is not None:
        rand = encode(rand, encoder)

    return rand
