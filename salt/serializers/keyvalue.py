"""
    salt.serializers.keyvalue
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    .. versionadded:: 3006.0

    Implements keyvalue serializer which can be used for serializing or
    deserializing any file which defines keys and values separated by a common
    set of characters, such environment files, which are in "KEY=value" format.

    Options:

    :param line_ending:
        String representation of LF or CRLF to be used for serialization to a
        file. Defaults to ``\\r\\n`` on Windows and ``\\n`` on other operating
        systems.

    :param quoting:
        Boolean flag to determine if values should be quoted (``True``) during
        serialization or dequoted (``False``) during deserialization. Defaults
        to ``None`` (no action).

    :param separator:
        String representing the character(s) used when concatenating or reading
        key/value pairs. Defaults to ``=``.

    A dataset such as:

    .. code-block:: yaml

        foo: bar
        wang: chung

    or

    .. code-block:: yaml

        - [foo, bar]
        - [wang, chung]

    can be represented as:

    .. code-block:: text

        foo=bar
        wang=chung
"""

import salt.utils.platform
from salt.serializers import DeserializationError, SerializationError
from salt.utils.jinja import quote
from salt.utils.stringutils import dequote

__all__ = ["deserialize", "serialize", "available"]

available = True


def deserialize(stream_or_string, **options):
    """
    Deserialize any string or stream like object into a Python data structure.

    :param stream_or_string: stream or string to deserialize.
    :param options: options given to the function
    """
    try:
        if not isinstance(stream_or_string, (bytes, str)):
            stream_or_string = stream_or_string.read()

        separator = options.get("separator", "=")

        obj = {}

        if isinstance(stream_or_string, bytes):
            stream_or_string = stream_or_string.decode("utf-8")

        for line in stream_or_string.splitlines():
            key, val = line.split(separator, maxsplit=1)
            if options.get("quoting") is False:
                val = dequote(val)
            obj[key] = val
    except Exception as error:  # pylint: disable=broad-except
        raise DeserializationError(error)

    return obj


def serialize(obj, **options):
    """
    Serialize Python data to environment file.

    :param obj: the data structure to serialize
    :param options: options given to the function
    """
    if not isinstance(obj, (dict, list, tuple, set)):
        raise SerializationError("Input validation failed. Iterable required.")

    linend = options.get("line_ending", "\n")

    if not options.get("line_ending") and salt.utils.platform.is_windows():
        linend = "\r\n"

    separator = options.get("separator", "=")

    lines = []

    try:
        if isinstance(obj, dict):
            for key, val in obj.items():
                if options.get("quoting"):
                    val = quote(val)
                lines.append(f"{key}{separator}{val}")
        else:
            for item in obj:
                key, val = item
                if options.get("quoting"):
                    val = quote(val)
                lines.append(f"{key}{separator}{val}")
    except Exception as error:  # pylint: disable=broad-except
        raise SerializationError(error)

    return linend.join(lines)
