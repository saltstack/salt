# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import sys

import salt.payload


def trim_dict(
        data,
        max_dict_bytes,
        percent=50.0,
        stepper_size=10,
        replace_with='VALUE_TRIMMED',
        is_msgpacked=False):
    '''
    Takes a dictionary and iterates over its keys, looking for
    large values and replacing them with a trimmed string.

    If after the first pass over dictionary keys, the dictionary
    is not sufficiently small, the stepper_size will be increased
    and the dictionary will be rescanned. This allows for progressive
    scanning, removing large items first and only making additional
    passes for smaller items if necessary.

    This function uses msgpack to calculate the size of the dictionary
    in question. While this might seem like unnecessary overhead, a
    data structure in python must be serialized in order for sys.getsizeof()
    to accurately return the items referenced in the structure.

    Ex:
    >>> salt.utils.trim_dict({'a': 'b', 'c': 'x' * 10000}, 100)
    {'a': 'b', 'c': 'VALUE_TRIMMED'}

    To improve performance, it is adviseable to pass in msgpacked
    data structures instead of raw dictionaries. If a msgpack
    structure is passed in, it will not be unserialized unless
    necessary.

    If a msgpack is passed in, it will be repacked if necessary
    before being returned.
    '''
    serializer = salt.payload.Serial({'serial': 'msgpack'})
    if is_msgpacked:
        dict_size = sys.getsizeof(data)
    else:
        dict_size = sys.getsizeof(serializer.dumps(data))
    if dict_size > max_dict_bytes:
        if is_msgpacked:
            data = serializer.loads(data)
        while True:
            percent = float(percent)
            max_val_size = float(max_dict_bytes * (percent / 100))
            try:
                for key in data:
                    if sys.getsizeof(data[key]) > max_val_size:
                        data[key] = replace_with
                percent = percent - stepper_size
                max_val_size = float(max_dict_bytes * (percent / 100))
                cur_dict_size = sys.getsizeof(serializer.dumps(data))
                if cur_dict_size < max_dict_bytes:
                    if is_msgpacked:  # Repack it
                        return serializer.dumps(data)
                    else:
                        return data
                elif max_val_size == 0:
                    if is_msgpacked:
                        return serializer.dumps(data)
                    else:
                        return data
            except ValueError:
                pass
        if is_msgpacked:
            return serializer.dumps(data)
        else:
            return data
    else:
        return data
