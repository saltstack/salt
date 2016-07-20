# -*- coding: utf-8 -*-
'''
State module to manage Elasticsearch indices

.. versionadded:: 2015.8.0
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs

log = logging.getLogger(__name__)


def absent(name):
    '''
    Ensure that the named index is absent
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    index_exists = __salt__['elasticsearch.index_exists'](index=name)
    if index_exists:
        if __opts__['test']:
            ret['comment'] = 'Index {0} will be removed'.format(name)
            ret['result'] = None
        else:
            ret['result'] = __salt__['elasticsearch.index_delete'](index=name)

            if ret['result']:
                ret['comment'] = 'Removed index {0} successfully'.format(name)
                # TODO show pending changes (body)
            else:
                ret['comment'] = 'Failed to remove index {0}'.format(name)  # TODO error handling
    elif not index_exists:
        ret['comment'] = 'Index {0} is already absent'.format(name)
    else:
        ret['comment'] = 'Failed to determine whether index {0} is absent, see Minion log for more information'.format(name)
        ret['result'] = False

    return ret


def present(name, definition):
    '''
    Ensure that the named index is present
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    index_exists = __salt__['elasticsearch.index_exists'](name=name)
    if not index_exists:
        if __opts__['test']:
            ret['comment'] = 'Index {0} will be created'.format(name)
            ret['result'] = None
        else:
            ret['result'] = __salt__['elasticsearch.index_create'](index=name, body=definition)
            # TODO show pending changes (body)

            if ret['result']:
                ret['comment'] = 'Created index {0} successfully'.format(name)
    elif index_exists:
        ret['comment'] = 'Index {0} is already present'.format(name)
    else:
        ret['comment'] = 'Failed to determine whether index {0} is present, see Minion log for more information'.format(name)
        ret['result'] = False

    return ret
