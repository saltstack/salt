def __virtual__():
    return 'nxos.cmd' in __salt__


def user_present(name, password, encrypted=False, crypt_salt=None, algorithm='sha256', role=None):
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    change_password = not __salt__['nxos.cmd']('check_password',
                                   username=name,
                                   password=password,
                                   encrypted=encrypted)

    change_role = not True

    old_user = __salt__['nxos.cmd']('get_user', username=name)

    if not any([change_password, change_role, not old_user]):
        ret['result'] = True
        ret['comment'] = 'User already exists'
        return ret

    if __opts__['test'] is True:
        ret['result'] = None
        if not old_user:
            ret['comment'] = 'User will be created'
            ret['changes']['password'] = True
            ret['changes']['role'] = True
            return ret
        if change_password is True:
            ret['comment'] = 'User will be updated'
            ret['changes']['password'] = True
        if change_role is True:
            ret['comment'] = 'User will be updated'
            ret['changes']['role'] = True
        return ret

    ret['changes']['old'] = old_user
    if change_role is True:
        ret['changes']['new'] = __salt__['nxos.cmd']('set_role',
                                         username=name,
                                         role=role)
    if change_password is True:
        ret['changes']['new'] = __salt__['nxos.cmd']('set_password',
                                         username=name,
                                         password=password,
                                         encrypted=encrypted,
                                         crypt_salt=crypt_salt,
                                         algorithm=algorithm,
                                         role=role)
    ret['result'] = True
    return ret
