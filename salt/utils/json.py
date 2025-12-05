"""
Functions to work with JSON
"""

import contextlib
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


def find_json(s: str):
    """Pass in a string and load JSON within it.

    The string may contain non-JSON text before and after the JSON document.

    Raises ValueError if no valid JSON was found.
    """
    decoder = json.JSONDecoder()

    # We look for the beginning of JSON objects / arrays and let raw_decode() handle
    # extraneous data at the end.
    for idx, char in enumerate(s):
        if char == "{" or char == "[":
            # JSONDecodeErrors are expected on stray '{'/'[' in the non-JSON part
            with contextlib.suppress(json.JSONDecodeError):
                data, _ = decoder.raw_decode(s[idx:])
                return data

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
