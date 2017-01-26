# -*- coding: utf-8 -*-
'''
The key Thorium State is used to apply changes to the accepted/rejected/pending keys

.. versionadded:: 2016.11.0
'''
# Import python libs
from __future__ import absolute_import
import time

# Import salt libs
import salt.key


def _get_key_api():
    '''
    Return the key api hook
    '''
    if 'keyapi' not in __context__:
        __context__['keyapi'] = salt.key.Key(__opts__)
    return __context__['keyapi']


def timeout(name, delete=0, reject=0):
    '''
    If any minion's status is older than the timeout value then apply the
    given action to the timed out key. This example will remove keys to
    minions that have not checked in for 300 seconds (5 minutes)

    USAGE:

    .. code-block:: yaml

        statreg:
          status.reg

        clean_keys:
          key.timeout:
            - require:
              - status: statreg
            - delete: 300
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    now = time.time()
    ktr = 'key_start_tracker'
    if ktr not in __context__:
        __context__[ktr] = {}
    remove = set()
    reject_set = set()
    keyapi = _get_key_api()
    current = keyapi.list_status('acc')
    for id_ in current.get('minions', []):
        if id_ in __reg__['status']['val']:
            # minion is reporting, check timeout and mark for removal
            if delete and (now - __reg__['status']['val'][id_]['recv_time']) > delete:
                remove.add(id_)
            if reject and (now - __reg__['status']['val'][id_]['recv_time']) > reject:
                reject_set.add(id_)
        else:
            # No report from minion recorded, mark for change if thorium has
            # been running for longer than the timeout
            if id_ not in __context__[ktr]:
                __context__[ktr][id_] = now
            else:
                if delete and (now - __context__[ktr][id_]) > delete:
                    remove.add(id_)
                if reject and (now - __context__[ktr][id_]) > reject:
                    reject_set.add(id_)
    for id_ in remove:
        keyapi.delete_key(id_)
        __reg__['status']['val'].pop(id_, None)
        __context__[ktr].pop(id_, None)
    for id_ in reject_set:
        keyapi.reject(id_)
        __reg__['status']['val'].pop(id_, None)
        __context__[ktr].pop(id_, None)
    return ret
