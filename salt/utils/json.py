"""
Functions to work with JSON
"""

import json
import logging

import salt.utils.data
import salt.utils.stringutils

log = logging.getLogger(__name__)


# One to one mappings
JSONEncoder = json.JSONEncoder


def __split(raw):
    """
    Performs a splitlines on the string. This function exists to make mocking
    possible in unit tests, since the member functions of the str/unicode
    builtins cannot be mocked.
    """
    return raw.splitlines()


def find_json(raw):
    """
    Pass in a raw string and load the json when it starts. This allows for a
    string to start or end with garbage but the JSON be cleanly loaded
    """
    ret = {}
    lines = __split(raw)
    lengths = list(map(len, lines))
    starts = []
    ends = []

    # Search for possible starts and ends of the json fragments
    for ind, line in enumerate(lines):
        line = line.lstrip()
        line = line[0] if line else line
        if line == "{" or line == "[":
            starts.append((ind, line))
        if line == "}" or line == "]":
            ends.append((ind, line))

    # List all the possible pairs of starts and ends,
    # and fill the length of each block to sort by size after
    starts_ends = []
    for start, start_char in starts:
        for end, end_br in reversed(ends):
            if end > start and (
                (start_char == "{" and end_br == "}")
                or (start_char == "[" and end_br == "]")
            ):
                starts_ends.append((start, end, sum(lengths[start : end + 1])))

    # Iterate through all the possible pairs starting from the largest
    starts_ends.sort(key=lambda x: (x[2], x[1] - x[0], x[0]), reverse=True)
    for start, end, _ in starts_ends:
        # Try filtering non-JSON text right after the last closing character
        end_str = lines[end].lstrip()[0]
        working = "\n".join(lines[start:end]) + end_str
        try:
            ret = json.loads(working)
            return ret
        except ValueError:
            continue

    # Fall back to old implementation for backward compatibility
    # expecting json after the text
    for ind, _ in enumerate(lines):
        try:
            working = "\n".join(lines[ind:])
        except UnicodeDecodeError:
            working = "\n".join(salt.utils.data.decode(lines[ind:]))

        try:
            ret = json.loads(working)
        except ValueError:
            continue
        if ret:
            return ret
    if not ret:
        # Not json, raise an error
        raise ValueError


def import_json():
    """
    Import a json module, starting with the quick ones and going down the list)
    """
    for fast_json in ("ujson", "yajl", "json"):
        try:
            mod = __import__(fast_json)
            log.trace("loaded %s json lib", fast_json)
            return mod
        except ImportError:
            continue


def load(fp, **kwargs):
    """
    .. versionadded:: 2018.3.0

    Wraps json.load

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    """
    return kwargs.pop("_json_module", json).load(fp, **kwargs)


def loads(s, **kwargs):
    """
    .. versionadded:: 2018.3.0

    Wraps json.loads and prevents a traceback in the event that a bytestring is
    passed to the function. (Python < 3.6 cannot load bytestrings)

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    """
    json_module = kwargs.pop("_json_module", json)
    try:
        return json_module.loads(s, **kwargs)
    except TypeError as exc:
        # json.loads cannot load bytestrings in Python < 3.6
        if isinstance(s, bytes):
            return json_module.loads(salt.utils.stringutils.to_unicode(s), **kwargs)
        else:
            raise


def dump(obj, fp, **kwargs):
    """
    .. versionadded:: 2018.3.0

    Wraps json.dump, and assumes that ensure_ascii is False (unless explicitly
    passed as True) for unicode compatibility. Note that setting it to True
    will mess up any unicode characters, as they will be dumped as the string
    literal version of the unicode code point.

    On Python 2, encodes the result to a str since json.dump does not want
    unicode types.

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    """
    json_module = kwargs.pop("_json_module", json)
    if "ensure_ascii" not in kwargs:
        kwargs["ensure_ascii"] = False
    return json_module.dump(obj, fp, **kwargs)


def dumps(obj, **kwargs):
    """
    .. versionadded:: 2018.3.0

    Wraps json.dumps, and assumes that ensure_ascii is False (unless explicitly
    passed as True) for unicode compatibility. Note that setting it to True
    will mess up any unicode characters, as they will be dumped as the string
    literal version of the unicode code point.

    On Python 2, encodes the result to a str since json.dumps does not want
    unicode types.

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    """
    json_module = kwargs.pop("_json_module", json)
    if "ensure_ascii" not in kwargs:
        kwargs["ensure_ascii"] = False
    return json_module.dumps(obj, **kwargs)
