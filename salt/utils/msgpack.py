"""
Functions to work with MessagePack
"""

import logging

log = logging.getLogger(__name__)

HAS_MSGPACK = False
try:
    import msgpack

    # There is a serialization issue on ARM and potentially other platforms for some msgpack bindings, check for it
    if (
        msgpack.loads(msgpack.dumps([1, 2, 3], use_bin_type=False), use_list=True)
        is None
    ):
        raise ImportError
    HAS_MSGPACK = True
except ImportError:
    try:
        import msgpack_pure as msgpack  # pylint: disable=import-error

        HAS_MSGPACK = True
    except ImportError:
        pass
        # Don't exit if msgpack is not available, this is to make local mode work without msgpack
        # sys.exit(salt.defaults.exitcodes.EX_GENERIC)

if HAS_MSGPACK and hasattr(msgpack, "exceptions"):
    exceptions = msgpack.exceptions
else:

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

# One-to-one mappings
Packer = msgpack.Packer
ExtType = msgpack.ExtType
version = (0, 0, 0) if not HAS_MSGPACK else msgpack.version


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


class Unpacker(msgpack.Unpacker):
    """
    Wraps the msgpack.Unpacker and removes non-relevant arguments
    """

    def __init__(self, *args, **kwargs):
        msgpack.Unpacker.__init__(
            self, *args, **_sanitize_msgpack_unpack_kwargs(kwargs)
        )


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
