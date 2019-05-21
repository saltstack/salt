# -*- coding: utf-8 -*-
'''
Functions to work with JSON
'''

from __future__ import absolute_import, unicode_literals

# Import Python libs
import json  # future lint: blacklisted-module
import logging
import sys

# Import Salt libs
import salt.utils.data
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __split(raw):
    '''
    Performs a splitlines on the string. This function exists to make mocking
    possible in unit tests, since the member functions of the str/unicode
    builtins cannot be mocked.
    '''
    return raw.splitlines()


def find_json(raw):
    '''
    Pass in a raw string and load the json when it starts. This allows for a
    string to start with garbage and end with json but be cleanly loaded
    '''
    ret = {}
    lines = __split(raw)
    for ind, _ in enumerate(lines):
        try:
            working = '\n'.join(lines[ind:])
        except UnicodeDecodeError:
            working = '\n'.join(salt.utils.data.decode(lines[ind:]))

        try:
            ret = json.loads(working)  # future lint: blacklisted-function
        except ValueError:
            continue
        if ret:
            return ret
    if not ret:
        # Not json, raise an error
        raise ValueError


def import_json():
    '''
    Import a json module, starting with the quick ones and going down the list)
    '''
    for fast_json in ('ujson', 'yajl', 'json'):
        try:
            mod = __import__(fast_json)
            log.trace('loaded %s json lib', fast_json)
            return mod
        except ImportError:
            continue


def load(fp, **kwargs):
    '''
    .. versionadded:: 2018.3.0

    Wraps json.load

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    return kwargs.pop('_json_module', json).load(fp, **kwargs)


def loads(s, **kwargs):
    '''
    .. versionadded:: 2018.3.0

    Wraps json.loads and prevents a traceback in the event that a bytestring is
    passed to the function. (Python < 3.6 cannot load bytestrings)

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    json_module = kwargs.pop('_json_module', json)
    try:
        return json_module.loads(s, **kwargs)
    except TypeError as exc:
        # json.loads cannot load bytestrings in Python < 3.6
        if six.PY3 and isinstance(s, bytes):
            return json_module.loads(s.decode(__salt_system_encoding__), **kwargs)
        else:
            six.reraise(*sys.exc_info())


def dump(obj, fp, **kwargs):
    '''
    .. versionadded:: 2018.3.0

    Wraps json.dump, and assumes that ensure_ascii is False (unless explicitly
    passed as True) for unicode compatibility. Note that setting it to True
    will mess up any unicode characters, as they will be dumped as the string
    literal version of the unicode code point.

    On Python 2, encodes the result to a str since json.dump does not want
    unicode types.

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    json_module = kwargs.pop('_json_module', json)
    if 'ensure_ascii' not in kwargs:
        kwargs['ensure_ascii'] = False
    if six.PY2:
        obj = salt.utils.data.encode(obj)
    return json_module.dump(obj, fp, **kwargs)  # future lint: blacklisted-function


def dumps(obj, **kwargs):
    '''
    .. versionadded:: 2018.3.0

    Wraps json.dumps, and assumes that ensure_ascii is False (unless explicitly
    passed as True) for unicode compatibility. Note that setting it to True
    will mess up any unicode characters, as they will be dumped as the string
    literal version of the unicode code point.

    On Python 2, encodes the result to a str since json.dumps does not want
    unicode types.

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    import sys
    json_module = kwargs.pop('_json_module', json)
    if 'ensure_ascii' not in kwargs:
        kwargs['ensure_ascii'] = False
    if six.PY2:
        obj = salt.utils.data.encode(obj)
    return json_module.dumps(obj, **kwargs)  # future lint: blacklisted-function
