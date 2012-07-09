'''
Control of entries in SSH authorized_key files.
===============================================

The information stored in a user's ssh authorized key file can be easily
controlled via the ssh_auth state. Defaults can be set by the enc, options,
and comment keys. These defaults can be overridden by including them in the
name.

.. code-block:: yaml

    AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==:
      ssh_auth:
        - present
        - user: root
        - enc: ssh-dss

    thatch:
      ssh_auth:
        - present
        - user: root
        - source: salt://ssh_keys/thatch.id_rsa.pub

    sshkeys:
      ssh_auth:
        - present
        - user: root
        - enc: ssh-rsa
        - options:
          - option1="value1"
          - option2="value2 flag2"
        - comment: myuser
        - names:
          - AAAAB3NzaC1kc3MAAACBAL0sQ9fJ5bYTEyY==
          - ssh-dss AAAAB3NzaCL0sQ9fJ5bYTEyY== user@domain
          - option3="value3" ssh-dss AAAAB3NzaC1kcQ9J5bYTEyY== other@testdomain
          - AAAAB3NzaC1kcQ9fJFF435bYTEyY== newcomment
'''

# Import python libs
import re


def _present_test(user, name, enc, comment, options, source, config, env):
    '''
    Run checks for "present"
    '''
    result = None
    if source:
        keys = __salt__['ssh.check_key_file'](
                user,
                source,
                config,
                env)
        if keys:
            comment = ('A number of keys are going to be updated from the '
                       'keyfile: {0}').format(source)
        else:
            result = True
            comment = (
                    'All host keys in file {0} are already present'
                    ).format(source)
    check = __salt__['ssh.check_key'](
            user,
            name,
            enc,
            comment,
            options,
            config)
    if check == 'update':
        comment = (
                'Key {0} for user {1} is set to be updated'
                ).format(name, user)
    elif check == 'add':
        comment = (
                'Key {0} for user {1} is set to be added'
                ).format(name, user)
    elif check == 'exists':
        result = True
        comment = ('The authorized host key {0} is already present '
                          'for user {1}'.format(name, user))

    return result, comment


def present(
        name,
        user,
        enc='ssh-rsa',
        comment='',
        source='',
        options=[],
        config='.ssh/authorized_keys',
        **kwargs):
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

    source
        The source file for the key(s). Can contain any number of public keys,
        in standard "authorized_keys" format. If this is set, comment, enc,
        and options will be ignored.

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

    if __opts__['test']:
        ret['result'], ret['comment'] = _present_test(
                user,
                name,
                enc,
                comment,
                options,
                source,
                config,
                kwargs.get('__env__', 'base')
                )
        return ret

    if source != '':
        data = __salt__['ssh.set_auth_key_from_file'](
                user,
                source,
                config,
                kwargs.get('__env__', 'base'))
    else:
        # check if this is of form {options} {enc} {key} {comment}
        sshre = re.compile(r'^(.*?)\s?((?:ssh\-|ecds).+)$')
        fullkey = sshre.search(name)
        # if it is {key} [comment]
        if not fullkey:
            key_and_comment = name.split()
            name = key_and_comment[0]
            if len(key_and_comment) == 2:
                comment = key_and_comment[1]
        else:
            # if there are options, set them
            if fullkey.group(1):
                options = fullkey.group(1).split(',')
            # key is of format: {enc} {key} [comment]
            comps = fullkey.group(2).split()
            enc = comps[0]
            name = comps[1]
            if len(comps) == 3:
                comment = comps[2]

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
                          ' available and/or does the key file exist?')
    elif data == 'invalid':
        ret['result'] = False
        ret['comment'] = ('Invalid public ssh key, most likely has spaces')

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

    if __opts__['test']:
        check = __salt__['ssh.check_key'](
                user,
                name,
                '',
                '',
                [],
                config)
        if check == 'update' or check == 'exists':
            ret['return'] = None
            ret['comment'] = 'Key {0} is set for removal'.format(name)
            return ret
        else:
            ret['comment'] = 'Key is already absent'
            return ret

    ret['comment'] = __salt__['ssh.rm_auth_key'](user, name, config)

    if ret['comment'] == 'User authorized keys file not present':
        ret['result'] = False
        return ret
    elif ret['comment'] == 'Key removed':
        ret['changes'][name] = 'Removed'

    return ret
