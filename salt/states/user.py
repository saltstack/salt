'''
Management of user accounts.
============================

The user module is used to create and manage user settings, users can be set
as either absent or present

.. code-block:: yaml

    fred:
      user.present:
        - fullname: Fred Jones
        - shell: /bin/zsh
        - home: /home/fred
        - uid: 4000
        - gid: 4000
        - groups:
          - wheel
          - storage
          - games

    testuser:
      user.absent
'''

# Import python libs
import logging
import sys

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def _shadow_supported():
    if salt.utils.is_windows():
        return False
    return 'shadow.info' in __salt__


def _changes(name,
             uid=None,
             gid=None,
             groups=None,
             optional_groups=None,
             remove_groups=True,
             home=None,
             password=None,
             enforce_password=True,
             shell=None,
             fullname='',
             roomnumber='',
             workphone='',
             homephone=''):
    '''
    Return a dict of the changes required for a user if the user is present,
    otherwise return False.
    '''

    if _shadow_supported():
        lshad = __salt__['shadow.info'](name)

    lusr = __salt__['user.info'](name)
    if not lusr:
        return False

    change = {}
    wanted_groups = sorted(set((groups or []) + (optional_groups or [])))
    if uid:
        if lusr['uid'] != uid:
            change['uid'] = uid
    if gid is not None:
        if lusr['gid'] not in (gid, __salt__['file.group_to_gid'](gid)):
            change['gid'] = gid
    # remove the default group from the list for comparison purposes
    if gid and __salt__['file.gid_to_group'](gid or lusr['gid']) in \
            lusr['groups']:
        lusr['groups'].remove(
            __salt__['file.gid_to_group'](gid or lusr['gid'])
        )
    if name in lusr['groups'] and name not in wanted_groups:
        lusr['groups'].remove(name)
    # remove default group from wanted_groups, as this requirement is
    # already met
    if gid and __salt__['file.gid_to_group'](gid or lusr['gid']) in \
            wanted_groups:
        wanted_groups.remove(
            __salt__['file.gid_to_group'](gid or lusr['gid']))
    if groups is not None or wanted_groups:
        if remove_groups:
            if lusr['groups'] != wanted_groups:
                change['groups'] = wanted_groups
        else:
            for wanted_group in wanted_groups:
                if wanted_group not in lusr['groups']:
                    if 'groups' not in change:
                        change['groups'] = []
                    change['groups'].append(wanted_group)
    if home:
        if lusr['home'] != home:
            change['home'] = home
    if shell:
        if lusr['shell'] != shell:
            change['shell'] = shell
    if password:
        if _shadow_supported():
            default_hash = __salt__['shadow.default_hash']()
            if lshad['passwd'] == default_hash \
                    or lshad['passwd'] != default_hash and enforce_password:
                if lshad['passwd'] != password:
                    change['passwd'] = password
    # GECOS fields
    if fullname is not None and lusr['fullname'] != fullname:
        change['fullname'] = fullname
    if roomnumber is not None and lusr['roomnumber'] != roomnumber:
        change['roomnumber'] = roomnumber
    if workphone is not None and lusr['workphone'] != workphone:
        change['workphone'] = workphone
    if homephone is not None and lusr['homephone'] != homephone:
        change['homephone'] = homephone

    return change


def present(name,
            uid=None,
            gid=None,
            gid_from_name=False,
            groups=None,
            optional_groups=None,
            remove_groups=True,
            home=None,
            createhome=True,
            password=None,
            enforce_password=True,
            shell=None,
            unique=True,
            system=False,
            fullname=None,
            roomnumber=None,
            workphone=None,
            homephone=None):
    '''
    Ensure that the named user is present with the specified properties

    name
        The name of the user to manage

    uid
        The user id to assign, if left empty then the next available user id
        will be assigned

    gid
        The default group id

    gid_from_name
        If True, the default group id will be set to the id of the group with
        the same name as the user.

    groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will fail.
        If set to the empty list, the user will be removed from all groups
        except the default group.

    optional_groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will silently
        ignore it.

    NOTE: If the same group is specified in both "groups" and
    "optional_groups", then it will be assumed to be required and not optional.

    remove_groups
        Remove groups that the user is a member of that weren't specified in
        the state, True by default

    home
        The location of the home directory to manage

    createhome
        If True, the home directory will be created if it doesn't exist.
        Please note that directories leading up to the home directory
        will NOT be created.

    password
        A password hash to set for the user. This field is only supported on
        Linux, FreeBSD, NetBSD, OpenBSD, and Solaris.

    .. versionchanged:: 0.16.0
       BSD support added.

    enforce_password
        Set to False to keep the password from being changed if it has already
        been set and the password hash differs from what is specified in the
        "password" field. This option will be ignored if "password" is not
        specified.

    shell
        The login shell, defaults to the system default shell

    unique
        Require a unique UID, True by default

    system
        Choose UID in the range of FIRST_SYSTEM_UID and LAST_SYSTEM_UID.


    User comment field (GECOS) support (currently Linux and FreeBSD only):

    The below values should be specified as strings to avoid ambiguities when
    the values are loaded. (Especially the phone and room number fields which
    are likely to contain numeric data)

    fullname
        The user's full name.

    roomnumber
        The user's room number

    workphone
        The user's work phone number

    homephone
        The user's home phone number
    '''
    roomnumber = str(roomnumber) if roomnumber is not None else roomnumber
    workphone = str(workphone) if workphone is not None else workphone
    homephone = str(homephone) if homephone is not None else homephone

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}

    if groups:
        missing_groups = [x for x in groups if not __salt__['group.info'](x)]
        if missing_groups:
            ret['comment'] = 'The following group(s) are not present: ' \
                             '{0}'.format(','.join(missing_groups))
            ret['result'] = False
            return ret

    if optional_groups:
        present_optgroups = [x for x in optional_groups
                             if __salt__['group.info'](x)]
        for missing_optgroup in [x for x in optional_groups
                                 if x not in present_optgroups]:
            log.debug('Optional group "{0}" for user "{1}" is not '
                      'present'.format(missing_optgroup, name))
    else:
        present_optgroups = None

    # Log a warning for all groups specified in both "groups" and
    # "optional_groups" lists.
    if groups and optional_groups:
        for isected in set(groups).intersection(optional_groups):
            log.warning('Group "{0}" specified in both groups and '
                        'optional_groups for user {1}'.format(isected, name))

    if gid_from_name:
        gid = __salt__['file.group_to_gid'](name)

    changes = _changes(name,
                       uid,
                       gid,
                       groups,
                       present_optgroups,
                       remove_groups,
                       home,
                       password,
                       enforce_password,
                       shell,
                       fullname,
                       roomnumber,
                       workphone,
                       homephone)

    if changes:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('The following user attributes are set to be '
                              'changed:\n')
            for key, val in changes.items():
                ret['comment'] += '{0}: {1}\n'.format(key, val)
            return ret
        # The user is present
        if _shadow_supported():
            lshad = __salt__['shadow.info'](name)
        pre = __salt__['user.info'](name)
        for key, val in changes.items():
            if key == 'passwd':
                __salt__['shadow.set_password'](name, password)
                continue
            if key == 'groups':
                __salt__['user.ch{0}'.format(key)](name,
                                                   val,
                                                   not remove_groups)
            else:
                __salt__['user.ch{0}'.format(key)](name, val)

        # Clear cached groups
        sys.modules[
            __salt__['user.info'].__module__
        ].__context__.pop('user.getgrall', None)

        post = __salt__['user.info'](name)
        spost = {}
        if _shadow_supported():
            if lshad['passwd'] != password:
                spost = __salt__['shadow.info'](name)
        # See if anything changed
        for key in post:
            if post[key] != pre[key]:
                ret['changes'][key] = post[key]
        if _shadow_supported():
            for key in spost:
                if lshad[key] != spost[key]:
                    ret['changes'][key] = spost[key]
        if ret['changes']:
            ret['comment'] = 'Updated user {0}'.format(name)
        changes = _changes(name,
                           uid,
                           gid,
                           groups,
                           present_optgroups,
                           remove_groups,
                           home,
                           password,
                           enforce_password,
                           shell,
                           fullname,
                           roomnumber,
                           workphone,
                           homephone)

        if changes:
            ret['comment'] = 'These values could not be changed: {0}'.format(
                changes
            )
            ret['result'] = False
        return ret

    if changes is False:
        # The user is not present, make it!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} set to be added'.format(name)
            return ret
        if groups and present_optgroups:
            groups.extend(present_optgroups)
        elif present_optgroups:
            groups = present_optgroups[:]
        if __salt__['user.add'](name,
                                uid=uid,
                                gid=gid,
                                groups=groups,
                                home=home,
                                shell=shell,
                                unique=unique,
                                system=system,
                                fullname=fullname,
                                roomnumber=roomnumber,
                                workphone=workphone,
                                homephone=homephone,
                                createhome=createhome):
            ret['comment'] = 'New user {0} created'.format(name)
            ret['changes'] = __salt__['user.info'](name)
            if password:
                __salt__['shadow.set_password'](name, password)
                spost = __salt__['shadow.info'](name)
                if spost['passwd'] != password:
                    ret['comment'] = 'User {0} created but failed to set' \
                                     ' password to {1}'.format(name, password)
                    ret['result'] = False
                ret['changes']['password'] = password
        else:
            ret['comment'] = 'Failed to create new user {0}'.format(name)
            ret['result'] = False

    return ret


def absent(name, purge=False, force=False):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove

    purge
        Set purge to delete all of the user's files as well as the user

    force
        If the user is logged in the absent state will fail, set the force
        option to True to remove the user even if they are logged in. Not
        supported in FreeBSD and Solaris.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    lusr = __salt__['user.info'](name)
    if lusr:
        # The user is present, make it not present
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} set for removal'.format(name)
            return ret
        beforegroups = set(
                [g['name'] for g in __salt__['group.getent'](refresh=True)])
        ret['result'] = __salt__['user.delete'](name, purge, force)
        aftergroups = set(
                [g['name'] for g in __salt__['group.getent'](refresh=True)])
        if ret['result']:
            ret['changes'] = {}
            for g in (beforegroups - aftergroups):
                ret['changes']['{0} group'.format(g)] = 'removed'
            ret['changes'][name] = 'removed'
            ret['comment'] = 'Removed user {0}'.format(name)
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to remove user {0}'.format(name)
        return ret

    ret['comment'] = 'User {0} is not present'.format(name)

    return ret
