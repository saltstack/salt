'''
Manage users
'''

def present(
        name,
        uid=None,
        gid=None,
        groups=None,
        home=False,
        shell='/bin/bash'
        ):
    '''
    Ensure that the named user is present with the specified properties
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}
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
            post = __salt__['user.info'](name)
            # See if anything changed
            for key in post:
                if post[key] != pre[key]:
                    ret['changes'][key] = post[key]
            if ret['changes']:
                ret['comment'] = 'Updated user {0}'.format(name)
            return ret
    # The user is not present, make it!
    if __salt__['user.add'](name, uid, gid, groups, home, shell):
        ret['comment'] = 'New user {0} created'.format(name)
        ret['changes'] = __salt__['user.info'](name)
    else:
        ret['comment'] = 'Failed to create new user {0}'.format(name)
        ret['result'] = False
    return ret

def absent(name, purge=False, force=False):
    '''
    Ensure that the named user is absent
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

