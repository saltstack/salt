# -*- coding: utf-8 -*-
'''
Alex Martelli's soulution for recursive dict update from
http://stackoverflow.com/a/3233356
'''

# Import python libs
from __future__ import absolute_import
import collections

# Import 3rd-party libs
import copy
import logging
import salt.ext.six as six
from salt.serializers.yamlex import merge_recursive as _yamlex_merge_recursive

log = logging.getLogger(__name__)


def update(dest, upd, recursive_update=True, merge_lists=False):
    '''
    Recursive version of the default dict.update

    Merges upd recursively into dest

    If recursive_update=False, will use the classic dict.update, or fall back
    on a manual merge (helpful for non-dict types like FunctionWrapper)

    If merge_lists=True, will aggregate list object types instead of replace.
    This behavior is only activated when recursive_update=True. By default
    merge_lists=False.
    '''
    if (not isinstance(dest, collections.Mapping)) \
            or (not isinstance(upd, collections.Mapping)):
        raise TypeError('Cannot update using non-dict types in dictupdate.update()')
    updkeys = list(upd.keys())
    if not set(list(dest.keys())) & set(updkeys):
        recursive_update = False
    if recursive_update:
        for key in updkeys:
            val = upd[key]
            try:
                dest_subkey = dest.get(key, None)
            except AttributeError:
                dest_subkey = None
            if isinstance(dest_subkey, collections.Mapping) \
                    and isinstance(val, collections.Mapping):
                ret = update(dest_subkey, val, merge_lists=merge_lists)
                dest[key] = ret
            elif isinstance(dest_subkey, list) \
                     and isinstance(val, list):
                if merge_lists:
                    dest[key] = dest.get(key, []) + val
                else:
                    dest[key] = upd[key]
            else:
                dest[key] = upd[key]
        return dest
    else:
        try:
            dest.update(upd)
        except AttributeError:
            # this mapping is not a dict
            for k in upd:
                dest[k] = upd[k]
        return dest


def merge_list(obj_a, obj_b):
    ret = {}
    for key, val in six.iteritems(obj_a):
        if key in obj_b:
            ret[key] = [val, obj_b[key]]
        else:
            ret[key] = val
    return ret


def merge_recurse(obj_a, obj_b, merge_lists=False):
    copied = copy.deepcopy(obj_a)
    return update(copied, obj_b, merge_lists=merge_lists)


def merge_aggregate(obj_a, obj_b):
    return _yamlex_merge_recursive(obj_a, obj_b, level=1)


def merge_overwrite(obj_a, obj_b, merge_lists=False):
    for obj in obj_b:
        if obj in obj_a:
            obj_a[obj] = obj_b[obj]
    return merge_recurse(obj_a, obj_b, merge_lists=merge_lists)


def merge(obj_a, obj_b, strategy='smart', renderer='yaml', merge_lists=False):
    if strategy == 'smart':
        if renderer == 'yamlex' or renderer.startswith('yamlex_'):
            strategy = 'aggregate'
        else:
            strategy = 'recurse'

    if strategy == 'list':
        merged = merge_list(obj_a, obj_b)
    elif strategy == 'recurse':
        merged = merge_recurse(obj_a, obj_b, merge_lists)
    elif strategy == 'aggregate':
        #: level = 1 merge at least root data
        merged = merge_aggregate(obj_a, obj_b)
    elif strategy == 'overwrite':
        merged = merge_overwrite(obj_a, obj_b, merge_lists)
    else:
        log.warning('Unknown merging strategy \'{0}\', '
                    'fallback to recurse'.format(strategy))
        merged = merge_recurse(obj_a, obj_b)

    return merged
