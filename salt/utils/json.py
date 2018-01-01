# -*- coding: utf-8 -*-
'''
Functions to work with JSON
'''

from __future__ import absolute_import

# Import Python libs
import json
import logging

# Import Salt libs
import salt.utils.data

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
            ret = json.loads(working, object_hook=salt.utils.data.decode_dict)
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
