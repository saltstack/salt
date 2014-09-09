# -*- coding: utf-8 -*-
'''
Display return data in JSON format
==================================

:configuration: The output format can be configured with the ``output_indent``
    setting in the Master or Minion configuration file with the following
    values:

    * ``Null``: put each minion return on a single line.
    * ``pretty``: use four-space indents and sort the keys.
    * An integer: specify the indentation level.

Salt's outputters operate on a per-minion basis. Each minion return will be
output as a single JSON object once it comes in to the master.

Some JSON parsers can guess when an object ends and a new one begins but many
can not. A good way to differentiate between each minion return is to use the
single-line output format and to parse each line individually. Example output
(truncated)::

    {"dave": {"en0": {"hwaddr": "02:b0:26:32:4c:69", ...}}}
    {"jerry": {"en0": {"hwaddr": "02:26:ab:0d:b9:0d", ...}}}
    {"kevin": {"en0": {"hwaddr": "02:6d:7f:ce:9f:ee", ...}}}
    {"mike": {"en0": {"hwaddr": "02:48:a2:4b:70:a0", ...}}}
    {"phill": {"en0": {"hwaddr": "02:1d:cc:a2:33:55", ...}}}
    {"stuart": {"en0": {"hwaddr": "02:9a:e0:ea:9e:3c", ...}}}
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
        if 'output_indent' not in __opts__:
            return json.dumps(data, default=repr, indent=4)

        indent = __opts__.get('output_indent')
        sort_keys = False

        if indent is None:
            indent = None

        elif indent == 'pretty':
            indent = 4
            sort_keys = True

        elif isinstance(indent, int) and indent >= 0:
            indent = indent

        return json.dumps(data, default=repr, indent=indent, sort_keys=sort_keys)

    except TypeError:
        log.debug('An error occurred while outputting JSON', exc_info=True)
    # Return valid JSON for unserializable objects
    return json.dumps({})
