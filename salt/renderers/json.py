# -*- coding: utf-8 -*-
from __future__ import absolute_import

# Import python libs
import json

# Import salt libs
from salt._compat import string_types


def render(json_data, saltenv='base', sls='', **kws):
    '''
    Accepts JSON as a string or as a file object and runs it through the JSON
    parser.

    :rtype: A Python data structure
    '''
    if not isinstance(json_data, string_types):
        json_data = json_data.read()

    if json_data.startswith('#!'):
        json_data = json_data[(json_data.find('\n') + 1):]
    if not json_data.strip():
        return {}
    return json.loads(json_data)
