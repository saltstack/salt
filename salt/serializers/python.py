# -*- coding: utf-8 -*-
'''
    salt.serializers.python
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    .. versionadded:: 2016.3.0

    Implements a Python serializer (via pprint.format)
'''

from __future__ import absolute_import

try:
    import simplejson as json
except ImportError:
    import json

import pprint
import salt.utils

__all__ = ['serialize', 'available']

available = True


def serialize(obj, **options):
    '''
    Serialize Python data to a Python string representation (via pprint.format)

    :param obj: the data structure to serialize
    :param options: options given to pprint.format
    '''

    #round-trip this through JSON to avoid OrderedDict types
    # there's probably a more performant way to do this...
    # TODO remove json round-trip when all dataset will use
    # serializers
    return pprint.pformat(
        json.loads(
            json.dumps(obj),
            object_hook=salt.utils.decode_dict
        ),
        **options
    )
