"""
Functions to work with MessagePack
"""

# Import Python libs

import logging

log = logging.getLogger(__name__)

# Import 3rd party libs
HAS_MSGPACK = False
try:
    import msgpack

    # There is a serialization issue on ARM and potentially other platforms for some msgpack bindings, check for it
    if (
        msgpack.version >= (0, 4, 0)
        and msgpack.loads(msgpack.dumps([1, 2, 3], use_bin_type=False), use_list=True)
        is None
    ):
        raise ImportError
    elif msgpack.loads(msgpack.dumps([1, 2, 3]), use_list=True) is None:
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
    if version < (0, 6, 0) and kwargs.pop("strict_map_key", None) is not None:
        log.info("removing unsupported `strict_map_key` argument from msgpack call")
    if version < (0, 5, 2) and kwargs.pop("raw", None) is not None:
        log.info("removing unsupported `raw` argument from msgpack call")
    if version < (0, 4, 0) and kwargs.pop("use_bin_type", None) is not None:
        log.info("removing unsupported `use_bin_type` argument from msgpack call")
    if version >= (1, 0, 0) and kwargs.pop("encoding", None) is not None:
        log.debug("removing unsupported `encoding` argument from msgpack call")

    return kwargs


def _sanitize_msgpack_unpack_kwargs(kwargs):
    """
    Clean up msgpack keyword arguments for unpack operations, based on
    the version
    https://github.com/msgpack/msgpack-python/blob/master/ChangeLog.rst
    """
    assert isinstance(kwargs, dict)
    if version >= (1, 0, 0):
        kwargs.setdefault("raw", True)
        kwargs.setdefault("strict_map_key", False)
    return _sanitize_msgpack_kwargs(kwargs)

def _add_msgpack_unpack_kwargs(kwargs):
    '''
    Add any msgpack unpack kwargs here.

    max_buffer_size: will make sure the buffer is set to a minimum 
    of 100MiB in versions >=6 and <1.0
    '''
    assert isinstance(kwargs, dict)
    if version >= (0, 6, 0) and version < (1, 0, 0):
        kwargs["max_buffer_size"] = 100 * 1024 * 1024
    return _sanitize_msgpack_unpack_kwargs(kwargs)

class Unpacker(msgpack.Unpacker):
    """
    Wraps the msgpack.Unpacker and removes non-relevant arguments
    """

    def __init__(self, *args, **kwargs):
        msgpack.Unpacker.__init__(
            self, *args, **_add_msgpack_unpack_kwargs(kwargs)
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
