# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import sys

import salt.payload


def _trim_dict_in_dict(data, max_val_size, replace_with):
    """
    Takes a dictionary, max_val_size and replace_with
    and recursively loops through and replaces any values
    that are greater than max_val_size.
    """
    for key in data:
        if isinstance(data[key], dict):
            _trim_dict_in_dict(data[key], max_val_size, replace_with)
        else:
            if sys.getsizeof(data[key]) > max_val_size:
                data[key] = replace_with


def trim_dict(
    data,
    max_dict_bytes,
    percent=50.0,
    stepper_size=10,
    replace_with="VALUE_TRIMMED",
    is_msgpacked=False,
    use_bin_type=False,
):
    """
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
    >>> salt.utils.dicttrim.trim_dict({'a': 'b', 'c': 'x' * 10000}, 100)
    {'a': 'b', 'c': 'VALUE_TRIMMED'}

    To improve performance, it is adviseable to pass in msgpacked
    data structures instead of raw dictionaries. If a msgpack
    structure is passed in, it will not be unserialized unless
    necessary.

    If a msgpack is passed in, it will be repacked if necessary
    before being returned.

    :param use_bin_type: Set this to true if "is_msgpacked=True"
                         and the msgpack data has been encoded
                         with "use_bin_type=True". This also means
                         that the msgpack data should be decoded with
                         "encoding='utf-8'".
    """
    serializer = salt.payload.Serial({"serial": "msgpack"})
    if is_msgpacked:
        dict_size = sys.getsizeof(data)
    else:
        dict_size = sys.getsizeof(serializer.dumps(data))
    if dict_size > max_dict_bytes:
        if is_msgpacked:
            if use_bin_type:
                data = serializer.loads(data, encoding="utf-8")
            else:
                data = serializer.loads(data)
        while True:
            percent = float(percent)
            max_val_size = float(max_dict_bytes * (percent / 100))
            try:
                for key in data:
                    if isinstance(data[key], dict):
                        _trim_dict_in_dict(data[key], max_val_size, replace_with)
                    else:
                        if sys.getsizeof(data[key]) > max_val_size:
                            data[key] = replace_with
                percent = percent - stepper_size
                max_val_size = float(max_dict_bytes * (percent / 100))
                if use_bin_type:
                    dump_data = serializer.dumps(data, use_bin_type=True)
                else:
                    dump_data = serializer.dumps(data)
                cur_dict_size = sys.getsizeof(dump_data)
                if cur_dict_size < max_dict_bytes:
                    if is_msgpacked:  # Repack it
                        return dump_data
                    else:
                        return data
                elif max_val_size == 0:
                    if is_msgpacked:
                        return dump_data
                    else:
                        return data
            except ValueError:
                pass
        if is_msgpacked:
            if use_bin_type:
                return serializer.dumps(data, use_bin_type=True)
            else:
                return serializer.dumps(data)
        else:
            return data
    else:
        return data
