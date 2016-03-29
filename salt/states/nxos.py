def __virtual__():
    return 'nxos.cmd' in __salt__


def user_present(name, password=None, roles=None, encrypted=False, crypt_salt=None, algorithm='sha256'):
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    change_password = False
    if password is not None:
        change_password = not __salt__['nxos.cmd']('check_password',
                                       username=name,
                                       password=password,
                                       encrypted=encrypted)

    change_roles = False
    if roles is not None:
        cur_roles = __salt__['nxos.cmd']('get_roles', username=name)
        change_roles = set(roles) != cur_roles

    old_user = __salt__['nxos.cmd']('get_user', username=name)

    if not any([change_password, change_roles, not old_user]):
        ret['result'] = True
        ret['comment'] = 'User already exists'
        return ret

    if change_roles is True:
        remove_roles = cur_roles - set(roles)
        add_roles = set(roles) - cur_roles

    if __opts__['test'] is True:
        ret['result'] = None
        if not old_user:
            ret['comment'] = 'User will be created'
            if password is not None:
                ret['changes']['password'] = True
            if roles is not None:
                ret['changes']['role'] = {'add': roles,
                                          'remove': [],}
            return ret
        if change_password is True:
            ret['comment'] = 'User will be updated'
            ret['changes']['password'] = True
        if change_roles is True:
            ret['comment'] = 'User will be updated'
            ret['changes']['roles'] = {'add': list(add_roles),
                                      'remove': list(remove_roles)}
        return ret

    if change_password is True:
        new_user = __salt__['nxos.cmd']('set_password',
                                         username=name,
                                         password=password,
                                         encrypted=encrypted,
                                         role=roles[0] if roles else None,
                                         crypt_salt=crypt_salt,
                                         algorithm=algorithm)
        ret['changes']['password'] = {
            'new': new_user,
            'old': old_user,
        }
    if change_roles is True:
        for role in add_roles:
            __salt__['nxos.cmd']('set_role', username=name, role=role)
        for role in remove_roles:
            __salt__['nxos.cmd']('unset_role', username=name, role=role)
        ret['changes']['roles'] = {
            'new': list(__salt__['nxos.cmd']('get_roles', username=name)),
            'old': list(cur_roles),
        }

    correct_password = True
    if password is not None:
        correct_password = __salt__['nxos.cmd']('check_password',
                                    username=name,
                                    password=password,
                                    encrypted=encrypted)

    correct_roles = True
    if roles is not None:
        cur_roles = __salt__['nxos.cmd']('get_roles', username=name)
        correct_roles = set(roles) != cur_roles

    if not correct_roles:
        ret['comment'] = 'Failed to set correct roles'
    elif not correct_password:
        ret['comment'] = 'Failed to set correct password'
    else:
        ret['comment'] = 'User set correctly'
        ret['result'] = True

    return ret


def user_absent(name):
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    old_user = __salt__['nxos.cmd']('get_user', username=name)

    if not old_user:
        ret['result'] = True
        ret['comment'] = 'User does not exist'
        return ret

    if __opts__['test'] is True and old_user:
        ret['result'] = None
        ret['comment'] = 'User will be removed'
        ret['changes']['old'] = old_user
        ret['changes']['new'] = ''
        return ret

    __salt__['nxos.cmd']('remove_user', username=name)

    if __salt__['nxos.cmd']('get_user', username=name):
        ret['comment'] = 'Failed to remove user'
    else:
        ret['result'] = True
        ret['comment'] = 'User removed'
        ret['changes']['old'] = old_user
        ret['changes']['new'] = ''
    return ret
