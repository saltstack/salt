"""
Functions to work with MessagePack
"""

import logging

import salt.utils.versions

log = logging.getLogger(__name__)

msgpack = None
if salt.utils.versions.reqs.msgpack:
    msgpack = salt.utils.versions.reqs.msgpack.module
else:
    # TODO: Come up with a sane way to get a configured logfile
    #       and write to the logfile when this error is hit also
    log.fatal("Unable to import msgpack or msgpack_pure python modules")

if msgpack and not hasattr(msgpack, "exceptions"):

    class PackValueError(Exception):
        """
        older versions of msgpack do not have PackValueError
        """

    class _exceptions:
        """
        older versions of msgpack do not have an exceptions module
        """

        PackValueError = PackValueError()

    exceptions = _exceptions()
elif msgpack:
    exceptions = msgpack.exceptions

# One-to-one mappings
Packer = None
ExtType = None
version = (0, 0, 0)
if msgpack:
    Packer = msgpack.Packer
    ExtType = msgpack.ExtType
    version = msgpack.version


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
    if salt.utils.versions.reqs.msgpack:
        if salt.utils.versions.reqs.msgpack > (0, 5, 2):
            kwargs.setdefault("raw", True)
            kwargs.setdefault("strict_map_key", False)
    return _sanitize_msgpack_kwargs(kwargs)


if msgpack:

    class Unpacker(msgpack.Unpacker):
        """
        Wraps the msgpack.Unpacker and removes non-relevant arguments
        """

        def __init__(self, *args, **kwargs):
            msgpack.Unpacker.__init__(
                self, *args, **_sanitize_msgpack_unpack_kwargs(kwargs)
            )

else:

    class Unpacker:
        """
        Stub for msgpack.Unpacker
        """

        def __init__(self, *args, **kwargs):
            raise RuntimeError("msgpack is not available")


def pack(o, stream, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.pack and ensures that the passed object is unwrapped if it is
    a proxy.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available.
    """
    if not msgpack:
        raise RuntimeError("msgpack is not available")
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
    if not msgpack:
        raise RuntimeError("msgpack is not available")
    return msgpack.packb(o, **_sanitize_msgpack_kwargs(kwargs))


def unpack(stream, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.unpack.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure, if the msgpack is not available.
    """
    if not msgpack:
        raise RuntimeError("msgpack is not available")
    return msgpack.unpack(stream, **_sanitize_msgpack_unpack_kwargs(kwargs))


def unpackb(packed, **kwargs):
    """
    .. versionadded:: 2018.3.4

    Wraps msgpack.unpack.

    By default, this function uses the msgpack module and falls back to
    msgpack_pure.
    """
    if not msgpack:
        raise RuntimeError("msgpack is not available")
    return msgpack.unpackb(packed, **_sanitize_msgpack_unpack_kwargs(kwargs))


# alias for compatibility to simplejson/marshal/pickle.
load = unpack
loads = unpackb

dump = pack
dumps = packb
