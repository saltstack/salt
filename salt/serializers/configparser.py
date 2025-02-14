"""
    salt.serializers.configparser
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. versionadded:: 2016.3.0

    Implements a configparser serializer.
"""

import configparser
import io

from salt.serializers import DeserializationError, SerializationError

__all__ = ["deserialize", "serialize", "available"]

available = True


def deserialize(stream_or_string, **options):
    """
    Deserialize any string or stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to lower configparser module.
    """

    cp = configparser.ConfigParser(**options)

    try:
        if not isinstance(stream_or_string, (bytes, str)):
            cp.read_file(stream_or_string)
        else:
            cp.read_file(io.StringIO(stream_or_string))
        data = {}
        for section_name in cp.sections():
            section = {}
            for k, v in cp.items(section_name):
                section[k] = v
            data[section_name] = section
        return data
    except Exception as error:  # pylint: disable=broad-except
        raise DeserializationError(error)


def serialize(obj, **options):
    """
    Serialize Python data to a configparser formatted string or file.

    :param obj: the data structure to serialize
    :param options: options given to lower configparser module.
    """

    try:
        if not isinstance(obj, dict):
            raise TypeError(
                f"configparser can only serialize dictionaries, not {type(obj)}"
            )
        fp = options.pop("fp", None)
        cp = configparser.ConfigParser(**options)
        _read_dict(cp, obj)

        if fp:
            return cp.write(fp)
        else:
            s = io.StringIO()
            cp.write(s)
            return s.getvalue()
    except Exception as error:  # pylint: disable=broad-except
        raise SerializationError(error)


def _is_defaultsect(section_name):
    return section_name == configparser.DEFAULTSECT


def _read_dict(cp, dictionary):
    """
    Cribbed from python3's ConfigParser.read_dict function.
    """
    for section, keys in dictionary.items():
        section = str(section)
        if not _is_defaultsect(section):
            cp.add_section(section)

        for key, value in keys.items():
            key = cp.optionxform(str(key))
            if value is not None:
                value = str(value)
            cp.set(section, key, value)
