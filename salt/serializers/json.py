# -*- coding: utf-8 -*-
"""
    salt.serializers.json
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements JSON serializer.

    It's just a wrapper around json (or simplejson if available).
"""

from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.utils.json

# Import 3rd-party libs
from salt.ext import six
from salt.serializers import DeserializationError, SerializationError

try:
    import simplejson as _json
except ImportError:
    import json as _json  # pylint: disable=blacklisted-import


__all__ = ["deserialize", "serialize", "available"]

available = True


def deserialize(stream_or_string, **options):
    """
    Deserialize any string or stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower json/simplejson module.
    """

    try:
        if not isinstance(stream_or_string, (bytes, six.string_types)):
            return salt.utils.json.load(stream_or_string, _json_module=_json, **options)

        if isinstance(stream_or_string, bytes):
            stream_or_string = stream_or_string.decode("utf-8")

        return salt.utils.json.loads(stream_or_string, _json_module=_json)
    except Exception as error:  # pylint: disable=broad-except
        raise DeserializationError(error)


def serialize(obj, **options):
    """
    Serialize Python data to JSON.

    :param obj: the data structure to serialize
    :param options: options given to lower json/simplejson module.
    """

    try:
        if "fp" in options:
            return salt.utils.json.dump(obj, _json_module=_json, **options)
        else:
            return salt.utils.json.dumps(obj, _json_module=_json, **options)
    except Exception as error:  # pylint: disable=broad-except
        raise SerializationError(error)
