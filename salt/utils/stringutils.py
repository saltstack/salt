# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import string

# Import Salt libs
from salt.utils.decorators.jinja import jinja_filter

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin


@jinja_filter('to_bytes')
def to_bytes(s, encoding=None):
    '''
    Given bytes, bytearray, str, or unicode (python 2), return bytes (str for
    python 2)
    '''
    if six.PY3:
        if isinstance(s, bytes):
            return s
        if isinstance(s, bytearray):
            return bytes(s)
        if isinstance(s, six.string_types):
            return s.encode(encoding or __salt_system_encoding__)
        raise TypeError('expected bytes, bytearray, or str')
    else:
        return to_str(s, encoding)


def to_str(s, encoding=None):
    '''
    Given str, bytes, bytearray, or unicode (py2), return str
    '''
    # This shouldn't be six.string_types because if we're on PY2 and we already
    # have a string, we should just return it.
    if isinstance(s, str):
        return s
    if six.PY3:
        if isinstance(s, (bytes, bytearray)):
            # https://docs.python.org/3/howto/unicode.html#the-unicode-type
            # replace error with U+FFFD, REPLACEMENT CHARACTER
            return s.decode(encoding or __salt_system_encoding__, "replace")
        raise TypeError('expected str, bytes, or bytearray not {}'.format(type(s)))
    else:
        if isinstance(s, bytearray):
            return str(s)
        if isinstance(s, unicode):  # pylint: disable=incompatible-py3-code,undefined-variable
            return s.encode(encoding or __salt_system_encoding__)
        raise TypeError('expected str, bytearray, or unicode')


def to_unicode(s, encoding=None):
    '''
    Given str or unicode, return unicode (str for python 3)
    '''
    if not isinstance(s, (bytes, bytearray, six.string_types)):
        return s
    if six.PY3:
        if isinstance(s, (bytes, bytearray)):
            return to_str(s, encoding)
    else:
        # This needs to be str and not six.string_types, since if the string is
        # already a unicode type, it does not need to be decoded (and doing so
        # will raise an exception).
        if isinstance(s, str):
            return s.decode(encoding or __salt_system_encoding__)
    return s


@jinja_filter('str_to_num')  # Remove this for Neon
@jinja_filter('to_num')
def to_num(text):
    '''
    Convert a string to a number.
    Returns an integer if the string represents an integer, a floating
    point number if the string is a real number, or the string unchanged
    otherwise.
    '''
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def to_none(text):
    '''
    Convert a string to None if the string is empty or contains only spaces.
    '''
    if str(text).strip():
        return text
    return None


def is_quoted(value):
    '''
    Return a single or double quote, if a string is wrapped in extra quotes.
    Otherwise return an empty string.
    '''
    ret = ''
    if isinstance(value, six.string_types) \
            and value[0] == value[-1] \
            and value.startswith(('\'', '"')):
        ret = value[0]
    return ret


def dequote(value):
    '''
    Remove extra quotes around a string.
    '''
    if is_quoted(value):
        return value[1:-1]
    return value


@jinja_filter('is_hex')
def is_hex(value):
    '''
    Returns True if value is a hexidecimal string, otherwise returns False
    '''
    try:
        int(value, 16)
        return True
    except (TypeError, ValueError):
        return False


def is_binary(data):
    '''
    Detects if the passed string of data is binary or text
    '''
    if '\0' in data:
        return True
    if not data:
        return False

    text_characters = ''.join([chr(x) for x in range(32, 127)] + list('\n\r\t\b'))
    # Get the non-text characters (map each character to itself then use the
    # 'remove' option to get rid of the text characters.)
    if six.PY3:
        trans = ''.maketrans('', '', text_characters)
        nontext = data.translate(trans)
    else:
        trans = string.maketrans('', '')  # pylint: disable=no-member
        nontext = data.translate(trans, text_characters)

    # If more than 30% non-text characters, then
    # this is considered binary data
    if float(len(nontext)) / len(data) > 0.30:
        return True
    return False


@jinja_filter('random_str')
def random(size=32):
    key = os.urandom(size)
    return key.encode('base64').replace('\n', '')[:size]


@jinja_filter('contains_whitespace')
def contains_whitespace(text):
    '''
    Returns True if there are any whitespace characters in the string
    '''
    return any(x.isspace() for x in text)


def human_to_bytes(size):
    '''
    Given a human-readable byte string (e.g. 2G, 30M),
    return the number of bytes.  Will return 0 if the argument has
    unexpected form.

    .. versionadded:: Oxygen
    '''
    sbytes = size[:-1]
    unit = size[-1]
    if sbytes.isdigit():
        sbytes = int(sbytes)
        if unit == 'P':
            sbytes *= 1125899906842624
        elif unit == 'T':
            sbytes *= 1099511627776
        elif unit == 'G':
            sbytes *= 1073741824
        elif unit == 'M':
            sbytes *= 1048576
        else:
            sbytes = 0
    else:
        sbytes = 0
    return sbytes
