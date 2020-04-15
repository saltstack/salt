# -*- coding: utf-8 -*-
"""
Functions for manipulating or otherwise processing strings
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import base64
import difflib
import errno
import fnmatch
import logging
import os
import re
import shlex
import time
import unicodedata

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

# Import Salt libs
from salt.utils.decorators.jinja import jinja_filter

log = logging.getLogger(__name__)


@jinja_filter("to_bytes")
def to_bytes(s, encoding=None, errors="strict"):
    """
    Given bytes, bytearray, str, or unicode (python 2), return bytes (str for
    python 2)
    """
    if encoding is None:
        # Try utf-8 first, and fall back to detected encoding
        encoding = ("utf-8", __salt_system_encoding__)
    if not isinstance(encoding, (tuple, list)):
        encoding = (encoding,)

    if not encoding:
        raise ValueError("encoding cannot be empty")

    exc = None
    if six.PY3:
        if isinstance(s, bytes):
            return s
        if isinstance(s, bytearray):
            return bytes(s)
        if isinstance(s, six.string_types):
            for enc in encoding:
                try:
                    return s.encode(enc, errors)
                except UnicodeEncodeError as err:
                    exc = err
                    continue
            # The only way we get this far is if a UnicodeEncodeError was
            # raised, otherwise we would have already returned (or raised some
            # other exception).
            raise exc  # pylint: disable=raising-bad-type
        raise TypeError("expected str, bytes, or bytearray not {}".format(type(s)))
    else:
        return to_str(s, encoding, errors)


def to_str(s, encoding=None, errors="strict", normalize=False):
    """
    Given str, bytes, bytearray, or unicode (py2), return str
    """

    def _normalize(s):
        try:
            return unicodedata.normalize("NFC", s) if normalize else s
        except TypeError:
            return s

    if encoding is None:
        # Try utf-8 first, and fall back to detected encoding
        encoding = ("utf-8", __salt_system_encoding__)
    if not isinstance(encoding, (tuple, list)):
        encoding = (encoding,)

    if not encoding:
        raise ValueError("encoding cannot be empty")

    # This shouldn't be six.string_types because if we're on PY2 and we already
    # have a string, we should just return it.
    if isinstance(s, str):
        return _normalize(s)

    exc = None
    if six.PY3:
        if isinstance(s, (bytes, bytearray)):
            for enc in encoding:
                try:
                    return _normalize(s.decode(enc, errors))
                except UnicodeDecodeError as err:
                    exc = err
                    continue
            # The only way we get this far is if a UnicodeDecodeError was
            # raised, otherwise we would have already returned (or raised some
            # other exception).
            raise exc  # pylint: disable=raising-bad-type
        raise TypeError("expected str, bytes, or bytearray not {}".format(type(s)))
    else:
        if isinstance(s, bytearray):
            return str(s)  # future lint: disable=blacklisted-function
        # pylint: disable=incompatible-py3-code,undefined-variable
        if isinstance(s, unicode):
            for enc in encoding:
                try:
                    return _normalize(s).encode(enc, errors)
                except UnicodeEncodeError as err:
                    exc = err
                    continue
            # The only way we get this far is if a UnicodeDecodeError was
            # raised, otherwise we would have already returned (or raised some
            # other exception).
            raise exc  # pylint: disable=raising-bad-type
        # pylint: enable=incompatible-py3-code,undefined-variable
        raise TypeError("expected str, bytes, or bytearray not {}".format(type(s)))


def to_unicode(s, encoding=None, errors="strict", normalize=False):
    """
    Given str or unicode, return unicode (str for python 3)
    """

    def _normalize(s):
        return unicodedata.normalize("NFC", s) if normalize else s

    if encoding is None:
        # Try utf-8 first, and fall back to detected encoding
        encoding = ("utf-8", __salt_system_encoding__)
    if not isinstance(encoding, (tuple, list)):
        encoding = (encoding,)

    if not encoding:
        raise ValueError("encoding cannot be empty")

    exc = None
    if six.PY3:
        if isinstance(s, str):
            return _normalize(s)
        elif isinstance(s, (bytes, bytearray)):
            return _normalize(to_str(s, encoding, errors))
        raise TypeError("expected str, bytes, or bytearray not {}".format(type(s)))
    else:
        # This needs to be str and not six.string_types, since if the string is
        # already a unicode type, it does not need to be decoded (and doing so
        # will raise an exception).
        # pylint: disable=incompatible-py3-code
        if isinstance(s, unicode):  # pylint: disable=E0602
            return _normalize(s)
        elif isinstance(s, (str, bytearray)):
            for enc in encoding:
                try:
                    return _normalize(s.decode(enc, errors))
                except UnicodeDecodeError as err:
                    exc = err
                    continue
            # The only way we get this far is if a UnicodeDecodeError was
            # raised, otherwise we would have already returned (or raised some
            # other exception).
            raise exc  # pylint: disable=raising-bad-type
        # pylint: enable=incompatible-py3-code
        raise TypeError("expected str, bytes, or bytearray not {}".format(type(s)))


@jinja_filter("str_to_num")
@jinja_filter("to_num")
def to_num(text):
    """
    Convert a string to a number.
    Returns an integer if the string represents an integer, a floating
    point number if the string is a real number, or the string unchanged
    otherwise.
    """
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def to_none(text):
    """
    Convert a string to None if the string is empty or contains only spaces.
    """
    if six.text_type(text).strip():
        return text
    return None


def is_quoted(value):
    """
    Return a single or double quote, if a string is wrapped in extra quotes.
    Otherwise return an empty string.
    """
    ret = ""
    if (
        isinstance(value, six.string_types)
        and value[0] == value[-1]
        and value.startswith(("'", '"'))
    ):
        ret = value[0]
    return ret


def dequote(value):
    """
    Remove extra quotes around a string.
    """
    if is_quoted(value):
        return value[1:-1]
    return value


@jinja_filter("is_hex")
def is_hex(value):
    """
    Returns True if value is a hexidecimal string, otherwise returns False
    """
    try:
        int(value, 16)
        return True
    except (TypeError, ValueError):
        return False


def is_binary(data):
    """
    Detects if the passed string of data is binary or text
    """
    if not data or not isinstance(data, (six.string_types, six.binary_type)):
        return False

    if isinstance(data, six.binary_type):
        if b"\0" in data:
            return True
    elif str("\0") in data:
        return True

    text_characters = "".join([chr(x) for x in range(32, 127)] + list("\n\r\t\b"))
    # Get the non-text characters (map each character to itself then use the
    # 'remove' option to get rid of the text characters.)
    if six.PY3:
        if isinstance(data, six.binary_type):
            import salt.utils.data

            nontext = data.translate(None, salt.utils.data.encode(text_characters))
        else:
            trans = "".maketrans("", "", text_characters)
            nontext = data.translate(trans)
    else:
        if isinstance(data, six.text_type):
            trans_args = ({ord(x): None for x in text_characters},)
        else:
            trans_args = (
                None,
                str(text_characters),
            )  # future lint: blacklisted-function
        nontext = data.translate(*trans_args)

    # If more than 30% non-text characters, then
    # this is considered binary data
    if float(len(nontext)) / len(data) > 0.30:
        return True
    return False


@jinja_filter("random_str")
def random(size=32):
    key = os.urandom(size)
    return to_unicode(base64.b64encode(key).replace(b"\n", b"")[:size])


@jinja_filter("contains_whitespace")
def contains_whitespace(text):
    """
    Returns True if there are any whitespace characters in the string
    """
    return any(x.isspace() for x in text)


def human_to_bytes(size):
    """
    Given a human-readable byte string (e.g. 2G, 30M),
    return the number of bytes.  Will return 0 if the argument has
    unexpected form.

    .. versionadded:: 2018.3.0
    """
    sbytes = size[:-1]
    unit = size[-1]
    if sbytes.isdigit():
        sbytes = int(sbytes)
        if unit == "P":
            sbytes *= 1125899906842624
        elif unit == "T":
            sbytes *= 1099511627776
        elif unit == "G":
            sbytes *= 1073741824
        elif unit == "M":
            sbytes *= 1048576
        else:
            sbytes = 0
    else:
        sbytes = 0
    return sbytes


def build_whitespace_split_regex(text):
    '''
    Create a regular expression at runtime which should match ignoring the
    addition or deletion of white space or line breaks, unless between commas

    Example:

    .. code-block:: python

        >>> import re
        >>> import salt.utils.stringutils
        >>> regex = salt.utils.stringutils.build_whitespace_split_regex(
        ...     """if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then"""
        ... )

        >>> regex
        '(?:[\\s]+)?if(?:[\\s]+)?\\[(?:[\\s]+)?\\-z(?:[\\s]+)?\\"\\$debian'
        '\\_chroot\\"(?:[\\s]+)?\\](?:[\\s]+)?\\&\\&(?:[\\s]+)?\\[(?:[\\s]+)?'
        '\\-r(?:[\\s]+)?\\/etc\\/debian\\_chroot(?:[\\s]+)?\\]\\;(?:[\\s]+)?'
        'then(?:[\\s]+)?'
        >>> re.search(
        ...     regex,
        ...     """if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then"""
        ... )

        <_sre.SRE_Match object at 0xb70639c0>
        >>>

    '''

    def __build_parts(text):
        lexer = shlex.shlex(text)
        lexer.whitespace_split = True
        lexer.commenters = ""
        if r"'\"" in text:
            lexer.quotes = ""
        elif "'" in text:
            lexer.quotes = '"'
        elif '"' in text:
            lexer.quotes = "'"
        return list(lexer)

    regex = r""
    for line in text.splitlines():
        parts = [re.escape(s) for s in __build_parts(line)]
        regex += r"(?:[\s]+)?{0}(?:[\s]+)?".format(r"(?:[\s]+)?".join(parts))
    return r"(?m)^{0}$".format(regex)


def expr_match(line, expr):
    """
    Checks whether or not the passed value matches the specified expression.
    Tries to match expr first as a glob using fnmatch.fnmatch(), and then tries
    to match expr as a regular expression. Originally designed to match minion
    IDs for whitelists/blacklists.

    Note that this also does exact matches, as fnmatch.fnmatch() will return
    ``True`` when no glob characters are used and the string is an exact match:

    .. code-block:: python

        >>> fnmatch.fnmatch('foo', 'foo')
        True
    """
    try:
        if fnmatch.fnmatch(line, expr):
            return True
        try:
            if re.match(r"\A{0}\Z".format(expr), line):
                return True
        except re.error:
            pass
    except TypeError:
        log.exception("Value %r or expression %r is not a string", line, expr)
    return False


@jinja_filter("check_whitelist_blacklist")
def check_whitelist_blacklist(value, whitelist=None, blacklist=None):
    """
    Check a whitelist and/or blacklist to see if the value matches it.

    value
        The item to check the whitelist and/or blacklist against.

    whitelist
        The list of items that are white-listed. If ``value`` is found
        in the whitelist, then the function returns ``True``. Otherwise,
        it returns ``False``.

    blacklist
        The list of items that are black-listed. If ``value`` is found
        in the blacklist, then the function returns ``False``. Otherwise,
        it returns ``True``.

    If both a whitelist and a blacklist are provided, value membership
    in the blacklist will be examined first. If the value is not found
    in the blacklist, then the whitelist is checked. If the value isn't
    found in the whitelist, the function returns ``False``.
    """
    # Normalize the input so that we have a list
    if blacklist:
        if isinstance(blacklist, six.string_types):
            blacklist = [blacklist]
        if not hasattr(blacklist, "__iter__"):
            raise TypeError(
                "Expecting iterable blacklist, but got {0} ({1})".format(
                    type(blacklist).__name__, blacklist
                )
            )
    else:
        blacklist = []

    if whitelist:
        if isinstance(whitelist, six.string_types):
            whitelist = [whitelist]
        if not hasattr(whitelist, "__iter__"):
            raise TypeError(
                "Expecting iterable whitelist, but got {0} ({1})".format(
                    type(whitelist).__name__, whitelist
                )
            )
    else:
        whitelist = []

    _blacklist_match = any(expr_match(value, expr) for expr in blacklist)
    _whitelist_match = any(expr_match(value, expr) for expr in whitelist)

    if blacklist and not whitelist:
        # Blacklist but no whitelist
        return not _blacklist_match
    elif whitelist and not blacklist:
        # Whitelist but no blacklist
        return _whitelist_match
    elif blacklist and whitelist:
        # Both whitelist and blacklist
        return not _blacklist_match and _whitelist_match
    else:
        # No blacklist or whitelist passed
        return True


def check_include_exclude(path_str, include_pat=None, exclude_pat=None):
    """
    Check for glob or regexp patterns for include_pat and exclude_pat in the
    'path_str' string and return True/False conditions as follows.
      - Default: return 'True' if no include_pat or exclude_pat patterns are
        supplied
      - If only include_pat or exclude_pat is supplied: return 'True' if string
        passes the include_pat test or fails exclude_pat test respectively
      - If both include_pat and exclude_pat are supplied: return 'True' if
        include_pat matches AND exclude_pat does not match
    """
    ret = True  # -- default true
    # Before pattern match, check if it is regexp (E@'') or glob(default)
    if include_pat:
        if re.match("E@", include_pat):
            retchk_include = True if re.search(include_pat[2:], path_str) else False
        else:
            retchk_include = True if fnmatch.fnmatch(path_str, include_pat) else False

    if exclude_pat:
        if re.match("E@", exclude_pat):
            retchk_exclude = False if re.search(exclude_pat[2:], path_str) else True
        else:
            retchk_exclude = False if fnmatch.fnmatch(path_str, exclude_pat) else True

    # Now apply include/exclude conditions
    if include_pat and not exclude_pat:
        ret = retchk_include
    elif exclude_pat and not include_pat:
        ret = retchk_exclude
    elif include_pat and exclude_pat:
        ret = retchk_include and retchk_exclude
    else:
        ret = True

    return ret


def print_cli(msg, retries=10, step=0.01):
    """
    Wrapper around print() that suppresses tracebacks on broken pipes (i.e.
    when salt output is piped to less and less is stopped prematurely).
    """
    while retries:
        try:
            try:
                print(msg)
            except UnicodeEncodeError:
                print(msg.encode("utf-8"))
        except IOError as exc:
            err = "{0}".format(exc)
            if exc.errno != errno.EPIPE:
                if (
                    "temporarily unavailable" in err or exc.errno in (errno.EAGAIN,)
                ) and retries:
                    time.sleep(step)
                    retries -= 1
                    continue
                else:
                    raise
        break


def get_context(template, line, num_lines=5, marker=None):
    """
    Returns debugging context around a line in a given string

    Returns:: string
    """
    template_lines = template.splitlines()
    num_template_lines = len(template_lines)

    # In test mode, a single line template would return a crazy line number like,
    # 357. Do this sanity check and if the given line is obviously wrong, just
    # return the entire template
    if line > num_template_lines:
        return template

    context_start = max(0, line - num_lines - 1)  # subt 1 for 0-based indexing
    context_end = min(num_template_lines, line + num_lines)
    error_line_in_context = line - context_start - 1  # subtr 1 for 0-based idx

    buf = []
    if context_start > 0:
        buf.append("[...]")
        error_line_in_context += 1

    buf.extend(template_lines[context_start:context_end])

    if context_end < num_template_lines:
        buf.append("[...]")

    if marker:
        buf[error_line_in_context] += marker

    return "---\n{0}\n---".format("\n".join(buf))


def get_diff(a, b, *args, **kwargs):
    """
    Perform diff on two iterables containing lines from two files, and return
    the diff as as string. Lines are normalized to str types to avoid issues
    with unicode on PY2.
    """
    encoding = ("utf-8", "latin-1", __salt_system_encoding__)
    # Late import to avoid circular import
    import salt.utils.data

    return "".join(
        difflib.unified_diff(
            salt.utils.data.decode_list(a, encoding=encoding),
            salt.utils.data.decode_list(b, encoding=encoding),
            *args,
            **kwargs
        )
    )


@jinja_filter("to_snake_case")
def camel_to_snake_case(camel_input):
    """
    Converts camelCase (or CamelCase) to snake_case.
    From https://codereview.stackexchange.com/questions/185966/functions-to-convert-camelcase-strings-to-snake-case

    :param str camel_input: The camelcase or CamelCase string to convert to snake_case

    :return str
    """
    res = camel_input[0].lower()
    for i, letter in enumerate(camel_input[1:], 1):
        if letter.isupper():
            if camel_input[i - 1].islower() or (
                i != len(camel_input) - 1 and camel_input[i + 1].islower()
            ):
                res += "_"
        res += letter.lower()
    return res


@jinja_filter("to_camelcase")
def snake_to_camel_case(snake_input, uppercamel=False):
    """
    Converts snake_case to camelCase (or CamelCase if uppercamel is ``True``).
    Inspired by https://codereview.stackexchange.com/questions/85311/transform-snake-case-to-camelcase

    :param str snake_input: The input snake_case string to convert to camelCase
    :param bool uppercamel: Whether or not to convert to CamelCase instead

    :return str
    """
    words = snake_input.split("_")
    if uppercamel:
        words[0] = words[0].capitalize()
    return words[0] + "".join(word.capitalize() for word in words[1:])
