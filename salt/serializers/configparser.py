# -*- coding: utf-8 -*-
'''
    salt.serializers.configparser
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. versionadded:: 2016.3.0

    Implements a configparser serializer.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.ext import six
import salt.ext.six.moves.configparser as configparser  # pylint: disable=E0611
from salt.serializers import DeserializationError, SerializationError

__all__ = ['deserialize', 'serialize', 'available']

available = True


def deserialize(stream_or_string, **options):
    '''
    Deserialize any string or stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower configparser module.
    '''

    if six.PY3:
        cp = configparser.ConfigParser(**options)
    else:
        cp = configparser.SafeConfigParser(**options)

    try:
        if not isinstance(stream_or_string, (bytes, six.string_types)):
            if six.PY3:
                cp.read_file(stream_or_string)
            else:
                cp.readfp(stream_or_string)
        else:
            if six.PY3:
                cp.read_file(six.moves.StringIO(stream_or_string))
            else:
                # python2's ConfigParser cannot parse a config from a string
                cp.readfp(six.moves.StringIO(stream_or_string))
        data = {}
        for section_name in cp.sections():
            section = {}
            for k, v in cp.items(section_name):
                section[k] = v
            data[section_name] = section
        return data
    except Exception as error:
        raise DeserializationError(error)


def serialize(obj, **options):
    '''
    Serialize Python data to a configparser formatted string or file.

    :param obj: the data structure to serialize
    :param options: options given to lower configparser module.
    '''

    try:
        if not isinstance(obj, dict):
            raise TypeError("configparser can only serialize dictionaries, not {0}".format(type(obj)))
        fp = options.pop('fp', None)
        if six.PY3:
            cp = configparser.ConfigParser(**options)
        else:
            cp = configparser.SafeConfigParser(**options)
        _read_dict(cp, obj)

        if fp:
            return cp.write(fp)
        else:
            s = six.moves.StringIO()
            cp.write(s)
            return s.getvalue()
    except Exception as error:
        raise SerializationError(error)


def _read_dict(configparser, dictionary):
    '''
    Cribbed from python3's ConfigParser.read_dict function.
    '''
    for section, keys in dictionary.items():
        section = six.text_type(section)
        configparser.add_section(section)
        for key, value in keys.items():
            key = configparser.optionxform(six.text_type(key))
            if value is not None:
                value = six.text_type(value)
            configparser.set(section, key, value)
