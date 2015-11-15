# -*- coding: utf-8 -*-
'''
    salt.serializers.json
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Implements a configparser serializer.
'''

from __future__ import absolute_import

import StringIO
import ConfigParser as configparser

from salt.ext.six import string_types
from salt.serializers import DeserializationError, SerializationError

__all__ = ['deserialize', 'serialize', 'available']

available = True


def deserialize(stream_or_string, **options):
    """
    Deserialize any string or stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower configparser module.
    """

    cp = configparser.SafeConfigParser(**options)

    try:
        if not isinstance(stream_or_string, (bytes, string_types)):
            return cp.readfp(stream_or_string)

        if isinstance(stream_or_string, bytes):
            stream_or_string = stream_or_string.decode('utf-8')

        # python2's ConfigParser cannot parse a config from a string
        return cp.readfp(StringIO.StringIO(stream_or_string))
    except Exception as error:
        raise DeserializationError(error)


def serialize(obj, **options):
    """
    Serialize Python data to a configparser formatted string or file.

    :param obj: the data structure to serialize
    :param options: options given to lower configparser module.
    """

    try:
        if not isinstance(obj, dict):
            raise TypeError("configparser can only serialize dictionaries, not {}".format(type(obj)))
        fp = options.pop('fp', None)
        cp = configparser.SafeConfigParser(**options)
        _read_dict(cp, obj)

        if fp:
            return cp.write(fp)
        else:
            s = StringIO.StringIO()
            cp.write(s)
            return s.getvalue()
    except Exception as error:
        raise SerializationError(error)


def _read_dict(configparser, dictionary):
    """
    Cribbed from python3's ConfigParser.read_dict function.
    """
    for section, keys in dictionary.items():
        section = str(section)
        configparser.add_section(section)
        for key, value in keys.items():
            key = configparser.optionxform(str(key))
            if value is not None:
                value = str(value)
            configparser.set(section, key, value)
