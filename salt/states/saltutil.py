# -*- coding: utf-8 -*-
'''
Saltutil State
==============

This state wraps the saltutil execution modules to make them easier to run
from a states. Rather than needing to to use ``module.run`` this state allows for
improved change detection.

    .. versionadded: Neon
'''
from __future__ import absolute_import, unicode_literals, print_function

import logging

# Define the module's virtual name
__virtualname__ = 'saltutil'

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Named saltutil
    '''
    return __virtualname__


def sync_all(name, **kwargs):
    '''
    Performs the same task as saltutil.sync_all module
    See :mod:`saltutil module for full list of options <salt.modules.saltutil>`

    .. code-block:: yaml

        sync_everything:
          saltutil.sync_all:
            - refresh: True
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = "saltutil.sync_all would have been run"
        return ret

    try:
        sync_status = __salt__['saltutil.sync_all'](**kwargs)
        for key, value in sync_status.items():
            if value:
                ret['changes'][key] = value
                ret['comment'] += "Updated {0}. ".format(key)
    except Exception as e:
        log.error("Failed to run saltutil.sync_all: %s", e)
        ret['result'] = False
        ret['comment'] = "Failed to run sync_all: {0}".format(e)
        return ret

    if not ret['changes']:
        ret['comment'] = "No updates to sync"
    ret['comment'] = ret['comment'].strip()
    return ret
