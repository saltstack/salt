"""

    salt.serializers.tomlmod
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Implements TOML serializer.

    It's just a wrapper around the python toml module.
"""

import logging

from salt.serializers import DeserializationError, SerializationError

try:
    import toml

    HAS_TOML = True
except ImportError:
    HAS_TOML = False


__virtualname__ = "toml"

__all__ = ["deserialize", "serialize", "HAS_TOML"]

log = logging.getLogger(__name__)


def __virtual__():
    if HAS_TOML is False:
        return (False, "The 'toml' library is missing")
    return __virtualname__


def deserialize(stream_or_string, **options):
    """
    Deserialize from TOML into Python data structure.

    :param stream_or_string: toml stream or string to deserialize.
    :param options: options given to the python toml module.
    """

    try:
        if not isinstance(stream_or_string, (bytes, str)):
            return toml.load(stream_or_string, **options)

        if isinstance(stream_or_string, bytes):
            stream_or_string = stream_or_string.decode("utf-8")

        return toml.loads(stream_or_string)
    except Exception as error:  # pylint: disable=broad-except
        raise DeserializationError(error)


def serialize(obj, **options):
    """
    Serialize Python data to TOML.

    :param obj: the data structure to serialize.
    :param options: options given to the python toml module.
    """

    try:
        if "file_out" in options:
            return toml.dump(obj, options["file_out"], **options)
        else:
            return toml.dumps(obj, **options)
    except Exception as error:  # pylint: disable=broad-except
        raise SerializationError(error)
