# -*- coding: utf-8 -*-
'''
Display return data in JSON format
==================================

Example output::

    {
        "myminion": {
            "list": [
                "Hello",
                "World"
            ],
            "bar": "baz",
            "dictionary": {
                "abc": 123,
                "def": 456
            }
        }
    }
'''

# Import python libs
import json
import logging

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'json'


def __virtual__():
    '''
    Rename to json
    '''
    return __virtualname__


def output(data):
    '''
    Print the output data in JSON
    '''
    try:
        if 'output_indent' in __opts__:
            if __opts__['output_indent'] >= 0:
                return json.dumps(data, default=repr, indent=__opts__['output_indent'])
            return json.dumps(data, default=repr)
        return json.dumps(data, default=repr, indent=4)
    except TypeError:
        log.debug('An error occurred while outputting JSON', exc_info=True)
    # Return valid JSON for unserializable objects
    return json.dumps({})
