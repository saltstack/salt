# -*- coding: utf-8 -*-
'''
Management of Mongodb users
===========================
'''


def present(name,
            passwd,
            database="admin",
            user=None,
            password=None,
            host=None,
            port=None):
    '''
    Ensure that the user is present with the specified properties

    name
        The name of the user to manage

    passwd
        The password of the user

    user
        The user to connect as (must be able to create the user)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    database
        The database to create the user in (if the db doesn't exist, it will be created)

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is already present'.format(name)}
    # check if user exists
    if __salt__['mongodb.user_exists'](name, user, password, host, port, database):
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('User {0} is not present and needs to be created'
                ).format(name)
        return ret
    # The user is not present, make it!
    if __salt__['mongodb.user_create'](name, passwd, user, password, host, port, database=database):
        ret['comment'] = 'User {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    else:
        ret['comment'] = 'Failed to create database {0}'.format(name)
        ret['result'] = False

    return ret


def absent(name,
           user=None,
           password=None,
           host=None,
           port=None,
           database="admin"):
    '''
    Ensure that the named user is absent

    name
        The name of the user to remove

    user
        The user to connect as (must be able to create the user)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    database
        The database to create the user in (if the db doesn't exist, it will be created)

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if user exists and remove it
    if __salt__['mongodb.user_exists'](name, user, password, host, port, database=database):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('User {0} is present and needs to be removed'
                    ).format(name)
            return ret
        if __salt__['mongodb.user_remove'](name, user, password, host, port, database=database):
            ret['comment'] = 'User {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = ('User {0} is not present, so it cannot be removed'
            ).format(name)
    return ret
