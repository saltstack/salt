# -*- coding: utf-8 -*-
'''
Management of Open vSwitch ports.
'''


def __virtual__():
    '''
    Only make these states available if Open vSwitch module is available.
    '''
    return 'openvswitch.port_add' in __salt__


def present(name, bridge):
    '''
    Ensures that the named port exists on bridge, eventually creates it.

    Args:
        name: The name of the port.
        bridge: The name of the bridge.

    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    bridge_exists = __salt__['openvswitch.bridge_exists'](bridge)

    if bridge_exists:
        port_list = __salt__['openvswitch.port_list'](bridge)

    # Comment and change messages
    comment_bridge_notexists = 'Bridge {0} does not exist.'.format(bridge)
    comment_port_exists = 'Port {0} already exists.'.format(name)
    comment_port_created = 'Port {0} created on bridge {1}.'.format(name, bridge)
    comment_port_notcreated = 'Unable to create port {0} on bridge {1}.'.format(name, bridge)
    changes_port_created = {name: {'old': 'No port named {0} present.'.format(name),
                                   'new': 'Created port {1} on bridge {0}.'.format(bridge, name),
                                   }
                            }

    # Dry run, test=true mode
    if __opts__['test']:
        if bridge_exists:
            if name in port_list:
                ret['result'] = True
                ret['comment'] = comment_port_exists
            else:
                ret['result'] = None
                ret['comment'] = comment_port_created
                ret['changes'] = changes_port_created

        else:
            ret['result'] = None
            ret['comment'] = comment_bridge_notexists

        return ret

    if bridge_exists:
        if name in port_list:
            ret['result'] = True
            ret['comment'] = comment_port_exists
        else:
            port_add = __salt__['openvswitch.port_add'](bridge, name)
            if port_add:
                ret['result'] = True
                ret['comment'] = comment_port_created
                ret['changes'] = changes_port_created
            else:
                ret['result'] = False
                ret['comment'] = comment_port_notcreated
    else:
        ret['result'] = False
        ret['comment'] = comment_bridge_notexists

    return ret


def absent(name, bridge=None):
    '''
    Ensures that the named port exists on bridge, eventually deletes it.
    If bridge is not set, port is removed from  whatever bridge contains it.

    Args:
        name: The name of the port.
        bridge: The name of the bridge.

    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if bridge:
        bridge_exists = __salt__['openvswitch.bridge_exists'](bridge)
        if bridge_exists:
            port_list = __salt__['openvswitch.port_list'](bridge)
        else:
            port_list = ()
    else:
        port_list = [name]

    # Comment and change messages
    comment_bridge_notexists = 'Bridge {0} does not exist.'.format(bridge)
    comment_port_notexists = 'Port {0} does not exist on bridge {1}.'.format(name, bridge)
    comment_port_deleted = 'Port {0} deleted.'.format(name)
    comment_port_notdeleted = 'Unable to delete port {0}.'.format(name)
    changes_port_deleted = {name: {'old': 'Port named {0} may exist.'.format(name),
                                   'new': 'Deleted port {0}.'.format(name),
                                   }
                            }

    # Dry run, test=true mode
    if __opts__['test']:
        if bridge and not bridge_exists:
            ret['result'] = None
            ret['comment'] = comment_bridge_notexists
        elif name not in port_list:
            ret['result'] = True
            ret['comment'] = comment_port_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_port_deleted
            ret['changes'] = changes_port_deleted
        return ret

    if bridge and not bridge_exists:
        ret['result'] = False
        ret['comment'] = comment_bridge_notexists
    elif name not in port_list:
        ret['result'] = True
        ret['comment'] = comment_port_notexists
    else:
        if bridge:
            port_remove = __salt__['openvswitch.port_remove'](br=bridge, port=name)
        else:
            port_remove = __salt__['openvswitch.port_remove'](br=None, port=name)

        if port_remove:
            ret['result'] = True
            ret['comment'] = comment_port_deleted
            ret['changes'] = changes_port_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_port_notdeleted

    return ret
