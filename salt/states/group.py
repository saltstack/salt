# -*- coding: utf-8 -*-
'''
Management of user groups
=========================

The group module is used to create and manage unix group settings, groups
can be either present or absent:

.. code-block:: yaml

    cheese:
      group.present:
        - gid: 7648
        - system: True
        - addusers:
          - user1
          - users2
        - delusers:
          - foo

    cheese:
      group.present:
        - gid: 7648
        - system: True
        - members:
          - foo
          - bar
          - user1
          - user2
'''

# Import python libs
import grp
import sys


def _changes(name,
             gid=None,
             addusers=None,
             delusers=None,
             members=None):
    '''
    Return a dict of the changes required for a group if the group is present,
    otherwise return False.
    '''
    lgrp = __salt__['group.info'](name)
    if not lgrp:
        return False

    change = {}
    if gid:
        if lgrp['gid'] != gid:
            change['gid'] = gid

    if members:
        #-- if new memeber list if different than the current
        if set(lgrp['members']) ^ set(members):
            change['members'] = members

    if addusers:
        users_2add = [user for user in addusers if user not in lgrp['members']]
        if users_2add:
            change['addusers'] = users_2add

    if delusers:
        users_2del = [user for user in delusers if user in lgrp['members']]
        if users_2del:
            change['delusers'] = users_2del

    return change


def present(name,
            gid=None,
            system=False,
            addusers=None,
            delusers=None,
            members=None):
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

    addusers
        List of additional users to be added as a group members.

    delusers
        Ensure these user are removed from the group membership.

    members
        Replace existing group members with a list of new members.

    Note: Options 'members' and 'addusers/delusers' are mutually exclusive and
          can not be used together.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    grp_info = __salt__['group.info'](name)
    if grp_info:
        # Group already exists
        if gid is not None:
            # is the GID correct?
            if grp_info['gid'] == gid:
                ret['comment'] = 'No change'
                return ret
            else:
                # Gid is not correct.
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
    else:
        # Group is not present, test if gid is free
        if gid is not None:
            try:
                gid_ent = grp.getgrgid(gid)
                # If we do NOT get a KeyError here, GID is already taken
                ret['result'] = False
                ret['comment'] = ('Group {0} is not present but gid {1}'
                                  ' is already taken by group {2}'
                                  .format(name, gid, gid_ent.gr_name))
                return ret
            except KeyError:
                # Group ID is not taken. Ok to make the group.
                pass
    # Now actually make the group
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('Group {0} is not present and should '
                          'be created'
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
    grp_info = __salt__['group.info'](name)
    if grp_info:
        # Group already exists. Remove the group.
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
    else:
        ret['comment'] = 'Group not present'
        return ret
