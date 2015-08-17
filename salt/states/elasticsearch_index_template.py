# -*- coding: utf-8 -*-
'''
State module to manage Elasticsearch index templates

.. versionadded:: 2015.8.0
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs

log = logging.getLogger(__name__)


def absent(name):
    '''
    Ensure that the named index template is absent
    '''

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    index_template_exists = __salt__['elasticsearch.index_template_exists'](name=name)
    if index_template_exists:
        if __opts__['test']:
            ret['comment'] = 'Index template {0} will be removed'.format(name)
            ret['result'] = None
        else:
            ret['result'] = __salt__['elasticsearch.index_template_delete'](name=name)

            if ret['result']:
                ret['comment'] = 'Removed index template {0} successfully'.format(name)
                # TODO show pending changes (body)
            else:
                ret['comment'] = 'Failed to remove index template {0}'.format(name)  # TODO error handling
    elif not index_template_exists:
        ret['comment'] = 'Index template {0} is already absent'.format(name)
    else:
        ret['comment'] = 'Failed to determine whether index template {0} is absent, see Minion log for more information'.format(name)
        ret['result'] = False

    return ret


def present(name, definition=None):
    '''
    Ensure that the named index template is present
    '''

    if definition is None:
        definition = {}

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    index_template_exists = __salt__['elasticsearch.index_template_exists'](name=name)
    if not index_template_exists:
        if __opts__['test']:
            ret['comment'] = 'Index template {0} will be created'.format(name)
            ret['result'] = None
        else:
            ret['result'] = __salt__['elasticsearch.index_template_create'](name=name, body=definition)
            # TODO show pending changes (body)

            if ret['result']:
                ret['comment'] = 'Created index template {0} successfully'.format(name)
    elif index_template_exists:
        ret['comment'] = 'Index template {0} is already present'.format(name)
    else:
        ret['comment'] = 'Failed to determine whether index template {0} is present, see Minion log for more information'.format(name)
        ret['result'] = False

    return ret
