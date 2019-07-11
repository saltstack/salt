# -*- coding: utf-8 -*-
'''
Provides a way to see number of objects made and their types
Warning! This module is not thread safe but will not crash due to threads
the result may be off
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import Python
import os
import logging
import gc

log = logging.getLogger(__name__)


def get_type_count_str(type_dict, depth_count):
    '''
    formats a type_dict to a string
    :param type_dict: dict: key most be a type and the item most be a int
    :param depth_count: int
    :return: str
    '''

    log.debug('Calling: "get_type_count_str"')

    output = '###Type Count Start\nPID: {}\nMax depth: {}\n'.format(os.getpid(), depth_count)
    item_count_list = list({type_dict[key] for key in type_dict})
    item_count_list.sort(reverse=True)

    count_type_dict = {key: [] for key in item_count_list}
    for key in type_dict:
        count_type_dict[type_dict[key]].append(key)

    for count in item_count_list:
        for this_type in count_type_dict[count]:
            output = output + '{} {}\n'.format(count, this_type.__name__)

    output = output + '###Type Count End\n'
    return output


def get_type_count(max_depth=1000):
    '''
    info will find the number of objects that come from a type
    :param max_depth: int: max_depth for referents
    :return: (dict, int)
    '''

    log.debug('Calling: "get_type_count"')

    objects = gc.get_objects()
    type_dict = {}
    object_referrers = []
    found_ids = set()
    depth_count = 0
    while len(objects) != 0 and depth_count != max_depth:
        for this_object in objects:
            if id(this_object) not in found_ids:
                type_dict[type(this_object)] = type_dict.setdefault(type(this_object), 0) + 1
                found_ids.add(id(this_object))
                object_referrers.extend(gc.get_referents(this_object))

        objects = object_referrers
        object_referrers = []
        depth_count += 1

    return type_dict, depth_count


def get_type_count_snap_shoot(max_depth=1000, logtf=False):
    '''
    info will find the number of objects that come from a type
    :param max_depth: int: max_depth for referents
    :param logtf: bool: log return at debug level
    :return: str
    '''

    log.debug('Calling: "get_type_count_snap_shoot"')

    ret = get_type_count_str(*get_type_count(max_depth))
    if logtf:
        log.debug(ret)

    return ret
