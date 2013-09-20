# -*- coding: utf-8 -*-
'''
Management of Mongodb databases

Only deletion is supported, creation doesn't make sense
and can be done using mongodb_user.present
'''


def absent(name,
           user=None,
           password=None,
           host=None,
           port=None):
    '''
    Ensure that the named database is absent

    name
        The name of the database to remove

    user
        The user to connect as (must be able to create the user)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if database exists and remove it
    if __salt__['mongodb.db_exists'](name, user, password, host, port):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Database {0} is present and needs to be removed'
                    ).format(name)
            return ret
        if __salt__['mongodb.db_remove'](name, user, password, host, port):
            ret['comment'] = 'Database {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = ('User {0} is not present, so it cannot be removed'
            ).format(name)
    return ret
