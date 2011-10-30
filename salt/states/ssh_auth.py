'''
SSH Authorized Key Management
=============================

The information stored in a user's ssh authorized key file can be easily
controlled via the ssh_auth state:

.. code-block:: yaml

    AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyYvlRBsJdDOfhlWHWXQRqul6rwL4KIuPrhY7hBw0tV7UNC7J9IZRNO4iGod9C+OYutuWGJ2x5YNf7P4uGhH9AhBQGQ4LKOLxhDyT1OrDKXVFw3wgY3rHiJYAbd1PXNuclJHOKL27QZCRFjWSEaSrUOoczvAAAAFQD9d4jp2dCJSIseSkk4Lez3LqFcqQAAAIAmovHIVSrbLbXAXQE8eyPoL9x5C+x2GRpEcA7AeMH6bGx/xw6NtnQZVMcmZIre5Elrw3OKgxcDNomjYFNHuOYaQLBBMosyO++tJe1KTAr3A2zGj2xbWO9JhEzu8xvSdF8jRu0N5SRXPpzSyU4o1WGIPLVZSeSq1VFTHRT4lXB7PQAAAIBXUz6ZO0bregF5xtJRuxUN583HlfQkXvxLqHAGY8WSEVlTnuG/x75wolBDbVzeTlxWxgxhafj7P6Ncdv25Wz9wvc6ko/puww0b3rcLNqK+XCNJlsM/7lB8Q26iK5mRZzNsGeGwGTyzNIMBjhgjhYQ5MRdIcPv5t7IP/1M6fQDEsAXQ==:
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
        options=[],
        config='.ssh/authorized_keys'):
    '''
    Verifies that the specified ssh key is present for the specified user

    name
        The ssh key to manage

    user
        The user who owns the ssh authorixed keys file to modify

    enc
        Defines what type of key is being used, can be ssh-rsa or ssh-dss

    comment
        The comment to be placed with the ssh public key

    options
        The options passed to the key, pass a list object

    config
        The location of the authorized keys file relative to the user's home
        direcotory, defaults to ".ssh/authorized_keys"
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

    name
        The ssh key to manage

    user
        The user who owns the ssh authorixed keys file to modify

    config
        The location of the authorized keys file relative to the user's home
        direcotory, defaults to ".ssh/authorized_keys"
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
