# -*- coding: utf-8 -*-
'''
Alex Martelli's soulution for recursive dict update from
http://stackoverflow.com/a/3233356
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping

# Import 3rd-party libs
import copy
import logging
import salt.ext.six as six

log = logging.getLogger(__name__)


def update(dest, upd, recursive_update=True, merge_lists=False):
    '''
    Recursive version of the default dict.update

    Merges upd recursively into dest

    If recursive_update=False, will use the classic dict.update, or fall back
    on a manual merge (helpful for non-dict types like FunctionWrapper)

    If merge_lists=True, will aggregate list object types instead of replace.
    The list in ``upd`` is added to the list in ``dest``, so the resulting list
    is ``dest[key] + upd[key]``. This behavior is only activated when
    recursive_update=True. By default merge_lists=False.

    .. versionchanged: 2016.11.6
        When merging lists, duplicate values are removed. Values already
        present in the ``dest`` list are not added from the ``upd`` list.
    '''
    if (not isinstance(dest, Mapping)) \
            or (not isinstance(upd, Mapping)):
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
            if isinstance(dest_subkey, Mapping) \
                    and isinstance(val, Mapping):
                ret = update(dest_subkey, val, merge_lists=merge_lists)
                dest[key] = ret
            elif isinstance(dest_subkey, list) \
                     and isinstance(val, list):
                if merge_lists:
                    merged = copy.deepcopy(dest_subkey)
                    merged.extend([x for x in val if x not in merged])
                    dest[key] = merged
                else:
                    dest[key] = upd[key]
            else:
                dest[key] = upd[key]
        return dest
    else:
        try:
            for k in upd:
                dest[k] = upd[k]
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
    from salt.serializers.yamlex import merge_recursive as _yamlex_merge_recursive
    return _yamlex_merge_recursive(obj_a, obj_b, level=1)


def merge_overwrite(obj_a, obj_b, merge_lists=False):
    for obj in obj_b:
        if obj in obj_a:
            obj_a[obj] = obj_b[obj]
    return merge_recurse(obj_a, obj_b, merge_lists=merge_lists)


def merge(obj_a, obj_b, strategy='smart', renderer='yaml', merge_lists=False):
    if strategy == 'smart':
        if renderer.split('|')[-1] == 'yamlex' or renderer.startswith('yamlex_'):
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
    elif strategy == 'none':
        # If we do not want to merge, there is only one pillar passed, so we can safely use the default recurse,
        # we just do not want to log an error
        merged = merge_recurse(obj_a, obj_b)
    else:
        log.warning(
            'Unknown merging strategy \'%s\', fallback to recurse',
            strategy
        )
        merged = merge_recurse(obj_a, obj_b)

    return merged
