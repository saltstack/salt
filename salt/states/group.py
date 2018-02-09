# -*- coding: utf-8 -*-
'''
Management of user groups
=========================

The group module is used to create and manage group settings, groups can be
either present or absent. User/Group names can be passed to the ``adduser``,
``deluser``, and ``members`` parameters. ``adduser`` and ``deluser`` can be used
together but not with ``members``.

In Windows, if no domain is specified in the user or group name (i.e.
``DOMAIN\\username``) the module will assume a local user or group.

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
from __future__ import absolute_import, print_function, unicode_literals
import sys

# Import 3rd-party libs
from salt.ext import six

# Import Salt libs
import salt.utils.platform
import salt.utils.win_functions


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

    # User and Domain names are not case sensitive in Windows. Let's make them
    # all lower case so we can compare properly
    if salt.utils.platform.is_windows():
        if lgrp['members']:
            lgrp['members'] = [user.lower() for user in lgrp['members']]
        if members:
            members = [salt.utils.win_functions.get_sam_name(user).lower() for user in members]
        if addusers:
            addusers = [salt.utils.win_functions.get_sam_name(user).lower() for user in addusers]
        if delusers:
            delusers = [salt.utils.win_functions.get_sam_name(user).lower() for user in delusers]

    change = {}
    if gid:
        if lgrp['gid'] != gid:
            change['gid'] = gid

    if members:
        # -- if new member list if different than the current
        if set(lgrp['members']).symmetric_difference(members):
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
    r'''
    Ensure that a group is present

    Args:

        name (str):
            The name of the group to manage

        gid (str):
            The group id to assign to the named group; if left empty, then the
            next available group id will be assigned. Ignored on Windows

        system (bool):
            Whether or not the named group is a system group.  This is essentially
            the '-r' option of 'groupadd'. Ignored on Windows

        addusers (list):
            List of additional users to be added as a group members. Cannot
            conflict with names in delusers. Cannot be used in conjunction with
            members.

        delusers (list):
            Ensure these user are removed from the group membership. Cannot
            conflict with names in addusers. Cannot be used in conjunction with
            members.

        members (list):
            Replace existing group members with a list of new members. Cannot be
            used in conjunction with addusers or delusers.

    Example:

    .. code-block:: yaml

        # Adds DOMAIN\db_admins and Administrators to the local db_admin group
        # Removes Users
        db_admin:
          group.present:
            - addusers:
              - DOMAIN\db_admins
              - Administrators
            - delusers:
              - Users

        # Ensures only DOMAIN\domain_admins and the local Administrator are
        # members of the local Administrators group. All other users are
        # removed
        Administrators:
          group.present:
            - members:
              - DOMAIN\domain_admins
              - Administrator
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Group {0} is present and up to date'.format(name)}

    if members and (addusers or delusers):
        ret['result'] = None
        ret['comment'] = (
            'Error: Conflicting options "members" with "addusers" and/or'
            ' "delusers" can not be used together. ')
        return ret

    if addusers and delusers:
        # -- if trying to add and delete the same user(s) at the same time.
        if not set(addusers).isdisjoint(set(delusers)):
            ret['result'] = None
            ret['comment'] = (
                'Error. Same user(s) can not be added and deleted'
                ' simultaneously')
            return ret

    changes = _changes(name,
                       gid,
                       addusers,
                       delusers,
                       members)
    if changes:
        ret['comment'] = (
            'The following group attributes are set to be changed:\n')
        for key, val in six.iteritems(changes):
            ret['comment'] += '{0}: {1}\n'.format(key, val)

        if __opts__['test']:
            ret['result'] = None
            return ret

        for key, val in six.iteritems(changes):
            if key == 'gid':
                __salt__['group.chgid'](name, gid)
                continue
            if key == 'addusers':
                for user in val:
                    __salt__['group.adduser'](name, user)
                continue
            if key == 'delusers':
                for user in val:
                    __salt__['group.deluser'](name, user)
                continue
            if key == 'members':
                __salt__['group.members'](name, ','.join(members))
                continue
        # Clear cached group data
        sys.modules[
            __salt__['test.ping'].__module__
            ].__context__.pop('group.getent', None)
        changes = _changes(name,
                           gid,
                           addusers,
                           delusers,
                           members)
        if changes:
            ret['result'] = False
            ret['comment'] += 'Some changes could not be applied'
            ret['changes'] = {'Failed': changes}
        else:
            ret['changes'] = {'Final': 'All changes applied successfully'}

    if changes is False:
        # The group is not present, make it!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Group {0} set to be added'.format(name)
            return ret

        grps = __salt__['group.getent']()
        # Test if gid is free
        if gid is not None:
            gid_group = None
            for lgrp in grps:
                if lgrp['gid'] == gid:
                    gid_group = lgrp['name']
                    break

            if gid_group is not None:
                ret['result'] = False
                ret['comment'] = (
                    'Group {0} is not present but gid {1} is already taken by'
                    ' group {2}'.format(name, gid, gid_group))
                return ret

        # Group is not present, make it.
        if __salt__['group.add'](name, gid=gid, system=system):
            # if members to be added
            grp_members = None
            if members:
                grp_members = ','.join(members)
            if addusers:
                grp_members = ','.join(addusers)
            if grp_members:
                __salt__['group.members'](name, grp_members)
            # Clear cached group data
            sys.modules[__salt__['test.ping'].__module__].__context__.pop(
                'group.getent', None)
            ret['comment'] = 'New group {0} created'.format(name)
            ret['changes'] = __salt__['group.info'](name)
            changes = _changes(name,
                               gid,
                               addusers,
                               delusers,
                               members)
            if changes:
                ret['result'] = False
                ret['comment'] = (
                    'Group {0} has been created but, some changes could not'
                    ' be applied'.format(name))
                ret['changes'] = {'Failed': changes}
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to create new group {0}'.format(name)
    return ret


def absent(name):
    '''
    Ensure that the named group is absent

    Args:
        name (str):
            The name of the group to remove

    Example:

    .. code-block:: yaml

        # Removes the local group `db_admin`
        db_admin:
          group.absent
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
