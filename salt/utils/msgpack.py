"""
Functions to work with MessagePack
"""
import logging

import msgpack

log = logging.getLogger(__name__)

# One-to-one mappings
Packer = msgpack.Packer
ExtType = msgpack.ExtType
exceptions = msgpack.exceptions


def _sanitize_msgpack_kwargs(kwargs):
    """
    Clean up msgpack keyword arguments based on the version
    https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst
    """
    assert isinstance(kwargs, dict)
    if kwargs.pop("encoding", None) is not None:
        log.debug("removing unsupported `encoding` argument from msgpack call")

    return kwargs


def _sanitize_msgpack_unpack_kwargs(kwargs):
    """
    Clean up msgpack keyword arguments for unpack operations, based on
    the version
    https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst
    """
    assert isinstance(kwargs, dict)
    kwargs.setdefault("raw", True)
    kwargs.setdefault("strict_map_key", False)
    return _sanitize_msgpack_kwargs(kwargs)


def _add_msgpack_unpack_kwargs(kwargs):
    """
    Add any msgpack unpack kwargs here.
    """
    assert isinstance(kwargs, dict)
    return _sanitize_msgpack_unpack_kwargs(kwargs)


class Unpacker(msgpack.Unpacker):
    """
    Wraps the msgpack.Unpacker and removes non-relevant arguments
    """

    def __init__(self, *args, **kwargs):
        msgpack.Unpacker.__init__(self, *args, **_add_msgpack_unpack_kwargs(kwargs))


def pack(o, stream, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.pack and ensures that the passed object is unwrapped if it is
    a proxy.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available.
    """
    # Writes to a stream, there is no return
    msgpack.pack(o, stream, **_sanitize_msgpack_kwargs(kwargs))


def packb(o, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.packb and ensures that the passed object is unwrapped if it
    is a proxy.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available.
    """
    return msgpack.packb(o, **_sanitize_msgpack_kwargs(kwargs))


def unpack(stream, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.unpack.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available.
    """
    return msgpack.unpack(stream, **_sanitize_msgpack_unpack_kwargs(kwargs))


def unpackb(packed, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.unpack.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure.
    """
    return msgpack.unpackb(packed, **_sanitize_msgpack_unpack_kwargs(kwargs))


# alias for compatibility to simplejson/marshal/pickle.
load = unpack
loads = unpackb

dump = pack
dumps = packb
