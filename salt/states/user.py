'''
User Management
===============
The user module is used to create and manage user settings, users can be set
as either absent or present

.. code-block:: yaml

    fred:
      user:
        - present
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
        home=False,
        password=None,
        shell='/bin/bash'
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

    shell
        The login shell, defaults to /bin/bash
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
                    if lshad['pwd'] != password:
                        # Set the new password
                        __salt__['shadow.set_password'](name, password)
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
    if __salt__['user.add'](name, uid, gid, groups, home, shell):
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
