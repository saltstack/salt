'''
Management of MySQL users.
==========================

NOTE: This module requires the MySQLdb python module and the proper
settings in the minion config file.
See salt.modules.mysql for more information.

The mysql_user module is used to manage MySQL users.

.. code-block:: yaml

    frank:
      mysql_user.present:
        - host: localhost
        - password: bobcat
'''


def __virtual__():
    '''
    Only load if the mysql module is in __salt__
    '''
    return 'mysql_user' if 'mysql.user_create' in __salt__ else False


def present(name,
            host='localhost',
            password=None,
            password_hash=None,
            **connection_args):
    '''
    Ensure that the named user is present with the specified properties

    name
        The name of the user to manage

    password
        The password

    password_hash
        The password in hashed form. Be sure to quote the password because
        YAML doesn't like the ``*``::

            SELECT PASSWORD('mypass') ==> *6C8989366EAF75BB670AD8EA7A7FC1176A95CEF4
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0}@{1} is already present'.format(name, host)}

    # check if user exists with the same password
    if __salt__['mysql.user_exists'](name, host, password, password_hash, **connection_args):
        return ret

    # check if user exists with a different password
    if __salt__['mysql.user_exists'](name, host, **connection_args):

        # The user is present, change the password
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Password for user {0}@{1} is set '
                              'to be changed'.format(name, host))
            return ret

        if __salt__['mysql.user_chpass'](
                name, host, password, password_hash, **connection_args):
            ret['comment'] = ('Password for user {0}@{1} has '
                              'been changed'.format(name, host))
            ret['changes'][name] = 'Updated'
        else:
            ret['comment'] = ('Failed to change password for '
                              'user {0}@{1}'.format(name, host))
            ret['result'] = False
    else:

        # The user is not present, make it!
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0}@{1} is set to be added'.format(name, host)
            return ret

        if __salt__['mysql.user_create'](
                name, host, password, password_hash, **connection_args):
            ret['comment'] = 'The user {0}@{1} has been added'.format(name, host)
            ret['changes'][name] = 'Present'
        else:
            ret['comment'] = 'Failed to create user {0}@{1}'.format(name, host)
            ret['result'] = False

    return ret


def absent(name,
           host='localhost',
           **connection_args):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if db exists and remove it
    if __salt__['mysql.user_exists'](name, host, **connection_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0}@{1} is set to be removed'.format(
                    name,
                    host)
            return ret
        if __salt__['mysql.user_remove'](name, host, **connection_args):
            ret['comment'] = 'User {0}@{1} has been removed'.format(name, host)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = (
            'User {0}@{1} is not present, so it cannot be removed'
            ).format(name, host)
    return ret
