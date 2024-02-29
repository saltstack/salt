"""
    salt.serializers.msgpack
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements MsgPack serializer.
"""

import logging

import salt.utils.msgpack
from salt.serializers import DeserializationError, SerializationError

log = logging.getLogger(__name__)


__all__ = ["deserialize", "serialize", "available"]

available = salt.utils.msgpack.HAS_MSGPACK


def serialize(obj, **options):
    """
    Serialize Python data to MsgPack.

    :param obj: the data structure to serialize
    :param options: options given to lower msgpack module.
    """
    try:
        return salt.utils.msgpack.dumps(obj, **options)
    except Exception as error:  # pylint: disable=broad-except
        raise SerializationError(error)


def deserialize(stream_or_string, **options):
    """
    Deserialize any string of stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower msgpack module.
    """
    try:
        options.setdefault("use_list", True)
        options.setdefault("raw", False)
        return salt.utils.msgpack.loads(stream_or_string, **options)
    except Exception as error:  # pylint: disable=broad-except
        raise DeserializationError(error)
