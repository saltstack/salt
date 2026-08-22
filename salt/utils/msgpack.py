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


# Module-level cache for the ``msgpack_pack_buf_size`` opt.  Salt calls
# ``salt.utils.msgpack.dumps`` / ``packb`` from many places that do not have
# ``__opts__`` in scope (transport framing helpers, payload packagers, and
# various serializers).  Setting this once at daemon startup via
# :func:`set_pack_buf_size` lets those helpers pre-allocate the C ``Packer``
# buffer without threading opts through every call site.  The default of
# ``1048576`` (1 MiB) pre-allocates a workload-appropriate buffer that fits
# typical Salt payloads (state returns, grains, event payloads) without a
# realloc chain.  A value of ``0`` means "do not override" and restores the
# msgpack default (256 KiB progressive growth).
_PACK_BUF_SIZE = 1048576

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


def set_pack_buf_size(size):
    """
    Set the initial ``buf_size`` used when constructing an msgpack ``Packer``
    for pack/packb calls made through this module.

    Called from :func:`salt.config.apply_master_config`,
    :func:`salt.config.apply_minion_config`, and :func:`salt.config.api_config`
    at daemon startup so downstream helpers (transport framing, payload
    packaging, etc.) can honor the ``msgpack_pack_buf_size`` opt without
    receiving opts directly.

    The default (``1048576`` -- 1 MiB) pre-allocates a workload-appropriate
    buffer that fits typical Salt payloads without a realloc chain.  A value
    of ``0`` means "do not override" -- the underlying :class:`msgpack.Packer`
    then uses its own default (currently 256 KiB, grown progressively).  Any
    positive integer is passed through as ``buf_size=<value>`` so the C packer
    pre-allocates that many bytes on construction.

    Accepts either an integer byte count or a human-friendly size string like
    ``"1MB"`` / ``"512KiB"`` / ``"2G"`` -- string forms are parsed via
    :func:`salt.utils.stringutils.human_to_bytes`.

    Non-integer, unparseable, or negative values are ignored with a debug log
    so bad opts never crash a daemon.
    """
    global _PACK_BUF_SIZE
    if isinstance(size, str):
        # Import here to avoid a top-level circular dependency between
        # ``salt.utils.stringutils`` and modules it may transitively pull in
        # during interpreter startup before ``salt.utils.msgpack`` finishes
        # importing.
        import salt.utils.stringutils

        stripped = size.strip()
        # Preserve the explicit "0" escape hatch even when written as a
        # string; ``human_to_bytes("")`` and unparseable inputs both return
        # 0, so we special-case an empty string as "ignore" instead of
        # silently clobbering the previous setting to 0.
        if not stripped:
            log.debug("Ignoring empty msgpack_pack_buf_size value")
            return
        if stripped == "0":
            parsed = 0
        else:
            parsed = salt.utils.stringutils.human_to_bytes(stripped)
            if parsed == 0:
                log.debug("Ignoring unparseable msgpack_pack_buf_size value: %r", size)
                return
        size = parsed
    try:
        size = int(size)
    except (TypeError, ValueError):
        log.debug("Ignoring non-integer msgpack_pack_buf_size value: %r", size)
        return
    if size < 0:
        log.debug("Ignoring negative msgpack_pack_buf_size value: %s", size)
        return
    _PACK_BUF_SIZE = size


def get_pack_buf_size():
    """
    Return the configured initial ``buf_size`` for msgpack pack operations.
    A value of ``0`` means "unset" -- callers should not pass ``buf_size`` to
    the packer in that case, restoring the msgpack default (256 KiB
    progressive growth).
    """
    return _PACK_BUF_SIZE


def _apply_pack_buf_size(kwargs):
    """
    Populate ``buf_size`` in ``kwargs`` from the module-level cache when the
    caller has not already specified it and a positive value is configured.
    """
    if _PACK_BUF_SIZE and "buf_size" not in kwargs:
        kwargs["buf_size"] = _PACK_BUF_SIZE
    return kwargs


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
        if salt.utils.versions.reqs.msgpack > "0.5.2":
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
    msgpack.pack(o, stream, **_apply_pack_buf_size(_sanitize_msgpack_kwargs(kwargs)))


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
    return msgpack.packb(o, **_apply_pack_buf_size(_sanitize_msgpack_kwargs(kwargs)))


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
