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


def _changes(
        name,
        uid=None,
        gid=None,
        groups=None,
        home=True,
        password=None,
        enforce_password=True,
        shell=None,
        fullname=None,
        roomnumber=None,
        workphone=None,
        homephone=None,
        other=None,
        unique=True,
        ):
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
            if uid:
                if lusr['uid'] != uid:
                    change['uid'] = uid
            if gid:
                if lusr['gid'] != gid:
                    change['gid'] = gid
            if groups:
                if lusr['groups'] != sorted(groups):
                    change['groups'] = groups
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
            if fullname:
                if lusr['fullname'] != fullname:
                    change['fullname'] = fullname
            if roomnumber:
                if lusr['roomnumber'] != roomnumber:
                    change['roomnumber'] = roomnumber
            if workphone:
                if lusr['workphone'] != workphone:
                    change['workphone'] = workphone
            if homephone:
                if lusr['homephone'] != homephone:
                    change['homephone'] = homephone
            if other:
                if lusr['other'] != other:
                    change['other'] = other
    if not found:
        return False
    return change


def present(
        name,
        uid=None,
        gid=None,
        groups=None,
        home=True,
        password=None,
        enforce_password=True,
        shell=None,
        fullname=None,
        roomnumber=None,
        workphone=None,
        homephone=None,
        other=None,
        unique=True,
        system=False,
        ):
    '''
    Ensure that the named user is present with the specified properties

    name
        The name of the user to manage

    uid
        The user id to assign, if left empty then the next available user id
        will be assigned

    gid
        The default group id

    groups
        A list of groups to assign the user to, pass a list object

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


    User comment field (GECOS) support (currently Linux-only):

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

    other
        The user's "other" GECOS field

    unique
        Require a unique UID, True by default

    system
        Choose UID in the range of FIRST_SYSTEM_UID and LAST_SYSTEM_UID.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}

    changes = _changes(
            name,
            uid,
            gid,
            groups,
            home,
            password,
            enforce_password,
            shell,
            fullname,
            roomnumber,
            workphone,
            homephone,
            other,
            unique)
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
                                fullname=fullname,
                                roomnumber=roomnumber,
                                workphone=workphone,
                                homephone=homephone,
                                other=other,
                                unique=unique,
                                system=system):
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
