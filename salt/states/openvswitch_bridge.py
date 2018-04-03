# -*- coding: utf-8 -*-
'''
Management of Open vSwitch bridges.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    '''
    Only make these states available if Open vSwitch module is available.
    '''
    return 'openvswitch.bridge_create' in __salt__


def present(name):
    '''
    Ensures that the named bridge exists, eventually creates it.

    Args:
        name: The name of the bridge.

    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_bridge_created = 'Bridge {0} created.'.format(name)
    comment_bridge_notcreated = 'Unable to create bridge: {0}.'.format(name)
    comment_bridge_exists = 'Bridge {0} already exists.'.format(name)
    changes_bridge_created = {name: {'old': 'Bridge {0} does not exist.'.format(name),
                                     'new': 'Bridge {0} created'.format(name),
                                     }
                              }

    bridge_exists = __salt__['openvswitch.bridge_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if bridge_exists:
            ret['result'] = True
            ret['comment'] = comment_bridge_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_bridge_created

        return ret

    if bridge_exists:
        ret['result'] = True
        ret['comment'] = comment_bridge_exists
    else:
        bridge_create = __salt__['openvswitch.bridge_create'](name)
        if bridge_create:
            ret['result'] = True
            ret['comment'] = comment_bridge_created
            ret['changes'] = changes_bridge_created
        else:
            ret['result'] = False
            ret['comment'] = comment_bridge_notcreated

    return ret


def absent(name):
    '''
    Ensures that the named bridge does not exist, eventually deletes it.

    Args:
        name: The name of the bridge.

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_bridge_deleted = 'Bridge {0} deleted.'.format(name)
    comment_bridge_notdeleted = 'Unable to delete bridge: {0}.'.format(name)
    comment_bridge_notexists = 'Bridge {0} does not exist.'.format(name)
    changes_bridge_deleted = {name: {'old': 'Bridge {0} exists.'.format(name),
                                     'new': 'Bridge {0} deleted.'.format(name),
                                     }
                              }

    bridge_exists = __salt__['openvswitch.bridge_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if not bridge_exists:
            ret['result'] = True
            ret['comment'] = comment_bridge_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_bridge_deleted

        return ret

    if not bridge_exists:
        ret['result'] = True
        ret['comment'] = comment_bridge_notexists
    else:
        bridge_delete = __salt__['openvswitch.bridge_delete'](name)
        if bridge_delete:
            ret['result'] = True
            ret['comment'] = comment_bridge_deleted
            ret['changes'] = changes_bridge_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_bridge_notdeleted

    return ret
