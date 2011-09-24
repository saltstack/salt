'''
Allows for state management of ssh authorized keys
'''

def present(
        name,
        user,
        enc='ssh-rsa',
        comment='',
        options=[],
        config='.ssh/authorized_keys'):
    '''
    Verifies that the specified ssh key is present for the specified user
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    data = __salt__['ssh.set_auth_key'](
            user,
            name,
            enc,
            comment,
            options,
            config)
    if data == 'replace':
        ret['changes'][name] = 'Updated'
        ret['comment'] = 'The authorized host key {0} for user {1} was updated'.format(name, user)
        return ret
    elif data == 'no change':
        ret['comment'] = 'The authorized host key {0} is already present for user {1}'.format(name, user)
    elif data == 'new':
        ret['changes'][name] = 'New'
        ret['comment'] = 'The authorized host key {0} for user {1} was added'.format(name, user)
    return ret

def absent(name, user, config='.ssh/authorized_keys'):
    '''
    Verifies that the specified ssh key is absent
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    ret['comment'] = __salt__['ssh.rm_auth_key'](user, name, config)
    if ret['comment'] == 'User authorized keys file not present':
        ret['result'] = False
        return ret
    elif ret['comment'] == 'Key removed':
        ret['changes'][name] = 'Removed'
    return ret
