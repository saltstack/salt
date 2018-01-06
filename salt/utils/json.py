# -*- coding: utf-8 -*-
'''
Functions to work with JSON
'''

from __future__ import absolute_import

# Import Python libs
import json  # future lint: blacklisted-module
import logging

# Import Salt libs
import salt.utils.data
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def find_json(raw):
    '''
    Pass in a raw string and load the json when it starts. This allows for a
    string to start with garbage and end with json but be cleanly loaded
    '''
    ret = {}
    for ind, _ in enumerate(raw):
        working = '\n'.join(raw.splitlines()[ind:])
        try:
            ret = json.loads(working, object_hook=salt.utils.data.decode_dict)  # future lint: blacklisted-function
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
    .. versionadded:: Oxygen

    Wraps json.load

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    return kwargs.pop('_json_module', json).load(fp, **kwargs)


def loads(s, **kwargs):
    '''
    .. versionadded:: Oxygen

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
            raise exc


def dump(obj, fp, **kwargs):
    '''
    .. versionadded:: Oxygen

    Wraps json.dump and encodes the result to the system encoding. Also assumes
    that ensure_ascii is False (unless explicitly passed as True) for unicode
    compatibility. Note that setting it to True will mess up any unicode
    characters, as they will be dumped as the string literal version of the
    unicode code point.

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    json_module = kwargs.pop('_json_module', json)
    if 'ensure_ascii' not in kwargs:
        kwargs['ensure_ascii'] = False
    obj = salt.utils.data.encode(obj)
    return json.dump(obj, fp, **kwargs)  # future lint: blacklisted-function


def dumps(obj, **kwargs):
    '''
    .. versionadded:: Oxygen

    Wraps json.dumps and encodes the result to the system encoding. Also
    assumes that ensure_ascii is False (unless explicitly passed as True) for
    unicode compatibility. Note that setting it to True will mess up any
    unicode characters, as they will be dumped as the string literal version of
    the unicode code point.

    You can pass an alternate json module (loaded via import_json() above)
    using the _json_module argument)
    '''
    import sys
    json_module = kwargs.pop('_json_module', json)
    if 'ensure_ascii' not in kwargs:
        kwargs['ensure_ascii'] = False
    obj = salt.utils.data.encode(obj)
    return json_module.dumps(obj, **kwargs)  # future lint: blacklisted-function
