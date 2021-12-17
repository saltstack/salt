"""
    salt.serializers.plist
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    .. versionadded:: 3001

    Implements plist serializer.

    Wrapper around plistlib.
"""
import logging
import plistlib

from salt.serializers import DeserializationError, SerializationError

log = logging.getLogger(__name__)

__all__ = ["deserialize", "serialize", "available"]

available = True


def deserialize(stream_or_string, **options):
    """
    Deserialize any string or stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower plist module.

    :returns: Deserialized data structure.
    """
    try:
        if not isinstance(stream_or_string, (bytes, str)):
            log.trace("Using plistlib.load to deserialize.")
            return plistlib.load(stream_or_string, **options)

        if isinstance(stream_or_string, str):
            log.trace("Need to encode plist string.")
            stream_or_string = stream_or_string.encode("utf-8")

        log.trace("Using plistlib.loads to deserialize.")
        return plistlib.loads(stream_or_string, **options)
    except Exception as error:  # pylint: disable=broad-except
        raise DeserializationError(error)


def serialize(value, **options):
    """
    Serialize Python data to plist. To create a binary plist pass
    ``fmt: FMT_BINARY`` as an option.

    :param obj: the data structure to serialize
    :param options: options given to lower plist module.

    :returns: bytes of serialized plist.
    """
    fmt = options.pop("fmt", None)
    # add support for serializing to binary.
    if fmt == "FMT_BINARY":
        log.trace("Adding plistlib.FMT_BINARY to options.")
        options["fmt"] = plistlib.FMT_BINARY

    try:
        if "fp" in options:
            log.trace("Using plistlib.dump to serialize.")
            return plistlib.dump(value, **options)

        log.trace("Using plistlib.dumps to serialize.")
        return plistlib.dumps(value, **options)
    except Exception as error:  # pylint: disable=broad-except
        raise SerializationError(error)
