# -*- coding: utf-8 -*-
'''
    salt.serializers.json
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements JSON serializer.

    It's just a wrapper around json (or simplejson if available).
'''

from __future__ import absolute_import

try:
    import simplejson as json
except ImportError:
    import json

from salt.ext.six import string_types
from salt.serializers import DeserializationError, SerializationError

__all__ = ['deserialize', 'serialize', 'available']

available = True


def deserialize(stream_or_string, **options):
    """
    Deserialize any string of stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower json/simplejson module.
    """

    try:
        if not isinstance(stream_or_string, (bytes, string_types)):
            return json.load(stream_or_string, **options)

        if isinstance(stream_or_string, bytes):
            stream_or_string = stream_or_string.decode('utf-8')

        return json.loads(stream_or_string)
    except Exception as error:
        raise DeserializationError(error)


def serialize(obj, **options):
    """
    Serialize Python data to JSON.

    :param obj: the data structure to serialize
    :param options: options given to lower json/simplejson module.
    """

    try:
        if 'fp' in options:
            return json.dump(obj, **options)
        else:
            return json.dumps(obj, **options)
    except Exception as error:
        raise SerializationError(error)
