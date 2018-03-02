# -*- coding: utf-8 -*-
'''
Used to manage the thorium register. The thorium register is where compound
values are stored and computed, such as averages etc.
'''

# import python libs
from __future__ import absolute_import, division, print_function, unicode_literals
import salt.utils.stringutils

__func_alias__ = {
    'set_': 'set',
    'list_': 'list',
}


def set_(name, add, match):
    '''
    Add a value to the named set

    USAGE:

    .. code-block:: yaml

        foo:
          reg.set:
            - add: bar
            - match: my/custom/event
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name not in __reg__:
        __reg__[name] = {}
        __reg__[name]['val'] = set()
    for event in __events__:
        if salt.utils.stringutils.expr_match(event['tag'], match):
            try:
                val = event['data']['data'].get(add)
            except KeyError:
                val = event['data'].get(add)
            if val is None:
                val = 'None'
            ret['changes'][add] = val
            __reg__[name]['val'].add(val)
    return ret


def list_(name, add, match, stamp=False, prune=0):
    '''
    Add the specified values to the named list

    If ``stamp`` is True, then the timestamp from the event will also be added
    if ``prune`` is set to an integer higher than ``0``, then only the last
        ``prune`` values will be kept in the list.

    USAGE:

    .. code-block:: yaml

        foo:
          reg.list:
            - add: bar
            - match: my/custom/event
            - stamp: True
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if not isinstance(add, list):
        add = add.split(',')
    if name not in __reg__:
        __reg__[name] = {}
        __reg__[name]['val'] = []
    for event in __events__:
        try:
            event_data = event['data']['data']
        except KeyError:
            event_data = event['data']
        if salt.utils.stringutils.expr_match(event['tag'], match):
            item = {}
            for key in add:
                if key in event_data:
                    item[key] = event_data[key]
                    if stamp is True:
                        item['time'] = event['data']['_stamp']
            __reg__[name]['val'].append(item)
    if prune > 0:
        __reg__[name]['val'] = __reg__[name]['val'][:prune]
    return ret


def mean(name, add, match):
    '''
    Accept a numeric value from the matched events and store a running average
    of the values in the given register. If the specified value is not numeric
    it will be skipped

    USAGE:

    .. code-block:: yaml

        foo:
          reg.mean:
            - add: data_field
            - match: my/custom/event
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name not in __reg__:
        __reg__[name] = {}
        __reg__[name]['val'] = 0
        __reg__[name]['total'] = 0
        __reg__[name]['count'] = 0
    for event in __events__:
        try:
            event_data = event['data']['data']
        except KeyError:
            event_data = event['data']
        if salt.utils.stringutils.expr_match(event['tag'], match):
            if add in event_data:
                try:
                    comp = int(event_data)
                except ValueError:
                    continue
            __reg__[name]['total'] += comp
            __reg__[name]['count'] += 1
            __reg__[name]['val'] = __reg__[name]['total'] / __reg__[name]['count']
    return ret


def clear(name):
    '''
    Clear the namespace from the register

    USAGE:

    .. code-block:: yaml

        clearns:
          reg.clear:
            - name: myregister
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name in __reg__:
        __reg__[name].clear()
    return ret


def delete(name):
    '''
    Delete the namespace from the register

    USAGE:

    .. code-block:: yaml

        deletens:
          reg.delete:
            - name: myregister
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name in __reg__:
        del __reg__[name]
    return ret
