'''
Management of PostgreSQL users (roles).
=======================================

The postgres_users module is used to create and manage Postgres users.

.. code-block:: yaml

    frank:
      postgres_user.present
'''

def present(name,
            createdb=False,
            createuser=False,
            encrypted=False,
            superuser=False,
            password=None,
            runas=None):
    '''
    Ensure that the named user is present with the specified privileges

    name
        The name of the user to manage

    createdb
        Is the user allowed to create databases?

    createuser
        Is the user allowed to create other users?

    encrypted
        Shold the password be encrypted in the system catalog?

    superuser
        Shold the new user be a "superuser"

    password
        The user's pasword

    runas
        System user all operation should be preformed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is already present'.format(name)}

    # check if user exists
    if __salt__['postgres.user_exists'](name, runas=runas):
        return ret

    # The user is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'User {0} is set to be created'.format(name)
        return ret
    if __salt__['postgres.user_create'](username=name,
                                        createdb=createdb,
                                        createuser=createuser,
                                        encrypted=encrypted,
                                        superuser=superuser,
                                        password=password,
                                        runas=runas):
        ret['comment'] = 'The user {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create user {0}'.format(name)
        ret['result'] = False

    return ret


def absent(name, runas=None):
    '''
    Ensure that the named user is absent

    name
        The username of the user to remove

    runas
        System user all operation should be preformed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # check if user exists and remove it
    if __salt__['postgres.user_exists'](name, runas=runas):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} is set to be removed'.format(name)
            return ret
        if __salt__['postgres.user_remove'](name, runas=runas):
            ret['comment'] = 'User {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret
    else:
        ret['comment'] = 'User {0} is not present, so it cannot be removed'.format(name)

    return ret
