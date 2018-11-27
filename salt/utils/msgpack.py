# -*- coding: utf-8 -*-
'''
Functions to work with MessagePack
'''

from __future__ import absolute_import

# Import Python libs
try:
    # Attempt to import msgpack
    import msgpack
except ImportError:
    # Fall back to msgpack_pure
    import msgpack_pure as msgpack  # pylint: disable=import-error


def pack(o, stream, **kwargs):
    '''
    .. versionadded:: 2018.3.4

    Wraps msgpack.pack and ensures that the passed object is unwrapped if it is
    a proxy.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available. You can pass an alternate
    msgpack module using the _msgpack_module argument.
    '''
    msgpack_module = kwargs.pop('_msgpack_module', msgpack)
    return msgpack_module.pack(o, stream, **kwargs)


def packb(o, **kwargs):
    '''
    .. versionadded:: 2018.3.4

    Wraps msgpack.packb and ensures that the passed object is unwrapped if it
    is a proxy.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available. You can pass an alternate
    msgpack module using the _msgpack_module argument.
    '''
    msgpack_module = kwargs.pop('_msgpack_module', msgpack)
    return msgpack_module.packb(o, **kwargs)


def unpack(stream, **kwargs):
    '''
    .. versionadded:: 2018.3.4

    Wraps msgpack.unpack.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available. You can pass an alternate
    msgpack module using the _msgpack_module argument.
    '''
    msgpack_module = kwargs.pop('_msgpack_module', msgpack)
    return msgpack_module.unpack(stream, **kwargs)


def unpackb(packed, **kwargs):
    '''
    .. versionadded:: 2018.3.4

    Wraps msgpack.unpack.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available. You can pass an alternate
    msgpack module using the _msgpack_module argument.
    '''
    msgpack_module = kwargs.pop('_msgpack_module', msgpack)
    return msgpack_module.unpackb(packed, **kwargs)


# alias for compatibility to simplejson/marshal/pickle.
load = unpack
loads = unpackb

dump = pack
dumps = packb
