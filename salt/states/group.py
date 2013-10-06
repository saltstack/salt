# -*- coding: utf-8 -*-
'''
Management of user groups.
==========================

The group module is used to create and manage unix group settings, groups
can be either present or absent:

.. code-block:: yaml

    cheese:
      group.present:
        - gid: 7648
        - system: True
'''

# Import python libs
import sys


def present(name, gid=None, system=False):
    '''
    Ensure that a group is present

    name
        The name of the group to manage

    gid
        The group id to assign to the named group; if left empty, then the next
        available group id will be assigned

    system
        Whether or not the named group is a system group.  This is essentially
        the '-r' option of 'groupadd'.

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    grps = __salt__['group.getent']()
    for lgrp in grps:
        # Scan over the groups
        if lgrp['name'] == name:
            # The group is present, is the gid right?
            if gid:
                if lgrp['gid'] == gid:
                    # All good, return likewise
                    ret['comment'] = 'No change'
                    return ret
                else:
                    if __opts__['test']:
                        ret['result'] = None
                        ret['comment'] = (
                            'Group {0} exists but the gid will '
                            'be changed to {1}').format(name, gid)
                        return ret
                    ret['result'] = __salt__['group.chgid'](name, gid)
                    # Clear cached group data
                    sys.modules[
                        __salt__['test.ping'].__module__
                    ].__context__.pop('group.getent', None)
                    if ret['result']:
                        ret['comment'] = ('Changed gid to {0} for group {1}'
                                          .format(gid, name))
                        ret['changes'] = {name: gid}
                        return ret
                    else:
                        ret['comment'] = ('Failed to change gid to {0} for '
                                          'group {1}'.format(gid, name))
                        return ret
            else:
                ret['comment'] = 'Group {0} is already present'.format(name)
                return ret

    # Group is not present, test if gid is free
    if gid is not None:
        gid_group = None
        for lgrp in grps:
            if lgrp['gid'] == gid:
                gid_group = lgrp['name']
                break

        if gid_group is not None:
            ret['result'] = False
            ret['comment'] = ('Group {0} is not present but gid {1}'
                              ' is already taken by group {2}'
                              .format(name, gid, gid_group))
            return ret

    # Group is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Group {0} is not present and should be created'
                ).format(name)
        return ret

    ret['result'] = __salt__['group.add'](name, gid, system=system)
    # Clear cached group data
    sys.modules[
        __salt__['test.ping'].__module__
    ].__context__.pop('group.getent', None)

    if ret['result']:
        ret['changes'] = __salt__['group.info'](name)
        ret['comment'] = 'Added group {0}'.format(name)
        return ret
    else:
        ret['comment'] = 'Failed to apply group {0}'.format(name)
        return ret


def absent(name):
    '''
    Ensure that the named group is absent

    name
        The name of the group to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    for lgrp in __salt__['group.getent']():
        # Scan over the groups
        if lgrp['name'] == name:
            # The group is present, DESTROY!!
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'Group {0} is set for removal'.format(name)
                return ret
            ret['result'] = __salt__['group.delete'](name)
            if ret['result']:
                ret['changes'] = {name: ''}
                ret['comment'] = 'Removed group {0}'.format(name)
                return ret
            else:
                ret['comment'] = 'Failed to remove group {0}'.format(name)
                return ret
    ret['comment'] = 'Group not present'
    return ret
