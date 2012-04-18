'''
User Management
===============
The user module is used to create and manage user settings, users can be set
as either absent or present

.. code-block:: yaml

    fred:
      user:
        - present
        - fullname: Fred Jones
        - shell: /bin/zsh
        - home: /home/fred
        - uid: 4000
        - gid: 4000
        - groups:
          - wheel
          - storage
          - games
'''


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
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}

    if __grains__['os'] != 'FreeBSD':
        lshad = __salt__['shadow.info'](name)

    for lusr in __salt__['user.getent']():
        # Scan over the users
        if lusr['name'] == name:
            # The user is present, verify the params
            pre = __salt__['user.info'](name)
            if uid:
                if lusr['uid'] != uid:
                    # Fix the uid
                    __salt__['user.chuid'](name, uid)
            if gid:
                if lusr['gid'] != gid:
                    # Fix the gid
                    __salt__['user.chgid'](name, gid)
            if groups:
                if lusr['groups'] != sorted(groups):
                    # Fix the groups
                    __salt__['user.chgroups'](name, groups)
            if home:
                if lusr['home'] != home:
                    # Fix the home dir
                    __salt__['user.chhome'](name, home, True)
            if shell:
                if lusr['shell'] != shell:
                    # Fix the shell
                    __salt__['user.chshell'](name, shell)
            if password:
                if __grains__['os'] != 'FreeBSD':
                    if lshad['pwd'] == '!' or \
                            lshad['pwd'] != '!' and enforce_password:
                        if lshad['pwd'] != password:
                            # Set the new password
                            __salt__['shadow.set_password'](name, password)
            if fullname:
                if lusr['fullname'] != fullname:
                    # Fix the fullname
                    __salt__['user.chfullname'](name, fullname)
            if roomnumber:
                if lusr['roomnumber'] != roomnumber:
                    # Fix the roomnumber
                    __salt__['user.chroomnumber'](name, roomnumber)
            if workphone:
                if lusr['workphone'] != workphone:
                    # Fix the workphone
                    __salt__['user.chworkphone'](name, workphone)
            if homephone:
                if lusr['homephone'] != homephone:
                    # Fix the homephone
                    __salt__['user.chhomephone'](name, homephone)
            if other:
                if lusr['other'] != other:
                    # Fix the other
                    __salt__['user.chother'](name, other)
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

    # The user is not present, make it!
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
                            unique=unique):
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
