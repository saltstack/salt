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

import logging

log = logging.getLogger(__name__)

def _changes(
        name,
        uid=None,
        gid=None,
        groups=None,
        optional_groups=None,
        home=True,
        password=None,
        enforce_password=True,
        shell=None,
        unique=True,
        fullname='',
        roomnumber='',
        workphone='',
        homephone=''):
    '''
    Return a dict of the changes required for a user if the user is present,
    otherwise return False.
    '''

    change = {}
    found = False

    if __grains__['os'] != 'FreeBSD':
        lshad = __salt__['shadow.info'](name)

    for lusr in __salt__['user.getent']():
        # Scan over the users
        if lusr['name'] == name:
            found = True
            wanted_groups = sorted(
                    list(set((groups or []) + (optional_groups or []))))
            if uid:
                if lusr['uid'] != uid:
                    change['uid'] = uid
            if gid:
                if lusr['gid'] != gid:
                    change['gid'] = gid
            if wanted_groups:
                if lusr['groups'] != wanted_groups:
                    change['groups'] = wanted_groups
            if home:
                if lusr['home'] != home:
                    if not home is True:
                        change['home'] = home
            if shell:
                if lusr['shell'] != shell:
                    change['shell'] = shell
            if password:
                if __grains__['os'] != 'FreeBSD':
                    if lshad['pwd'] == '!' or \
                            lshad['pwd'] != '!' and enforce_password:
                        if lshad['pwd'] != password:
                            change['passwd'] = password
            # GECOS fields
            if lusr['fullname'] != fullname:
                change['fullname'] = fullname
            if lusr['roomnumber'] != roomnumber:
                change['roomnumber'] = roomnumber
            if lusr['workphone'] != workphone:
                change['workphone'] = workphone
            if lusr['homephone'] != homephone:
                change['homephone'] = homephone

    if not found:
        return False
    return change


def present(
        name,
        uid=None,
        gid=None,
        gid_from_name=False,
        groups=None,
        optional_groups=None,
        home=True,
        password=None,
        enforce_password=True,
        shell=None,
        unique=True,
        system=False,
        fullname='',
        roomnumber='',
        workphone='',
        homephone=''):
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

    optional_groups
        A list of groups to assign the user to, pass a list object. If a group
        specified here does not exist on the minion, the state will silently
        ignore it.

    NOTE: If the same group is specified in both "groups" and
    "optional_groups", then it will be assumed to be required and not optional.

    home
        The location of the home directory to manage

    password
        A password hash to set for the user

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
                      'present'.format(missing_optgroup,name))
    else:
        present_optgroups = None


    # Log a warning for all groups specified in both "groups" and
    # "optional_groups" lists.
    if groups and optional_groups:
        for x in set(groups).intersection(optional_groups):
            log.warning('Group "{0}" specified in both groups and '
                        'optional_groups for user {1}'.format(x,name))

    if fullname is None: fullname = ''
    if roomnumber is None: roomnumber = ''
    if workphone is None: workphone = ''
    if homephone is None: homephone = ''

    if gid_from_name:
        gid = __salt__['file.group_to_gid'](name)
    changes = _changes(
            name,
            uid,
            gid,
            groups,
            present_optgroups,
            home,
            password,
            enforce_password,
            shell,
            unique,
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
        if __grains__['os'] != 'FreeBSD':
            lshad = __salt__['shadow.info'](name)
        pre = __salt__['user.info'](name)
        for key, val in changes.items():
            if key == 'passwd':
                __salt__['shadow.set_password'](name, password)
                continue
            __salt__['user.ch{0}'.format(key)](name, val)

        post = __salt__['user.info'](name)
        spost = {}
        if __grains__['os'] != 'FreeBSD':
            if lshad['pwd'] != password:
                spost = __salt__['shadow.info'](name)
        # See if anything changed
        for key in post:
            if post[key] != pre[key]:
                ret['changes'][key] = post[key]
        if __grains__['os'] != 'FreeBSD':
            for key in spost:
                if lshad[key] != spost[key]:
                    ret['changes'][key] = spost[key]
        if ret['changes']:
            ret['comment'] = 'Updated user {0}'.format(name)
        return ret

    if changes is False:
        # The user is not present, make it!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} set to be added'.format(name)
            return ret
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
                                homephone=homephone):
            ret['comment'] = 'New user {0} created'.format(name)
            ret['changes'] = __salt__['user.info'](name)
            if password:
                __salt__['shadow.set_password'](name, password)
                spost = __salt__['shadow.info'](name)
                if spost['pwd'] != password:
                    ret['comment'] = ('User {0} created but failed to set'
                    ' password to {1}').format(name, password)
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
        Set purge to delete all of the user's file as well as the user

    force
        If the user is logged in the absent state will fail, set the force
        option to True to remove the user even if they are logged in
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    for lusr in __salt__['user.getent']():
        # Scan over the users
        if lusr['name'] == name:
            # The user is present, make it not present
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'User {0} set for removal'.format(name)
                return ret
            ret['result'] = __salt__['user.delete'](name, purge, force)
            if ret['result']:
                ret['changes'] = {name: 'removed'}
                ret['comment'] = 'Removed user {0}'.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'Failed to remove user {0}'.format(name)
            return ret

    ret['comment'] = 'User {0} is not present'.format(name)

    return ret
