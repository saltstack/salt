'''
SSH Authorized Key Management
=============================

The information stored in a user's ssh authorized key file can be easily
controlled via the ssh_auth state:

.. code-block:: yaml

    AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==:
      ssh_auth:
        - present
        - user: root
        - enc: ssh-dss
'''


def present(
        name,
        user,
        enc='ssh-rsa',
        comment='',
        options=[],       # FIXME: mutable type; http://goo.gl/ToU2z
        config='.ssh/authorized_keys'):
    '''
    Verifies that the specified ssh key is present for the specified user

    name
        The ssh key to manage

    user
        The user who owns the ssh authorized keys file to modify

    enc
        Defines what type of key is being used, can be ssh-rsa or ssh-dss

    comment
        The comment to be placed with the ssh public key

    options
        The options passed to the key, pass a list object

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/authorized_keys"
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
        ret['comment'] = ('The authorized host key {0} for user {1} was '
                          'updated'.format(name, user))
        return ret
    elif data == 'no change':
        ret['comment'] = ('The authorized host key {0} is already present '
                          'for user {1}'.format(name, user))
    elif data == 'new':
        ret['changes'][name] = 'New'
        ret['comment'] = ('The authorized host key {0} for user {1} was added'
                          .format(name, user))
    elif data == 'fail':
        ret['result'] = False
        ret['comment'] = ('Failed to add the ssh key, is the home directory'
                          ' available?')

    return ret


def absent(name, user, config='.ssh/authorized_keys'):
    '''
    Verifies that the specified ssh key is absent

    name
        The ssh key to manage

    user
        The user who owns the ssh authorized keys file to modify

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/authorized_keys"
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
