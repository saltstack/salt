# -*- coding: utf-8 -*-
'''
Management of Mongodb databases

Only deletion is supported, creation doesn't make sense
and can be done using mongodb_user.present
'''

from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.versions


def absent(name,
           user=None,
           password=None,
           host=None,
           port=None,
           authdb=None):
    '''
    .. deprecated:: Fluorine
        Use ``mongodb.database_absent`` instead

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

    authdb
        The database in which to authenticate
    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    salt.utils.versions.warn_until(
        'Fluorine',
        'The \'mongodb_database.absent\' function has been deprecated and will be removed in Salt '
        '{version}. Please use \'mongodb.database_absent\' instead.'
    )

    #check if database exists and remove it
    if __salt__['mongodb.db_exists'](name, user, password, host, port, authdb=authdb):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = ('Database {0} is present and needs to be removed'
                    ).format(name)
            return ret
        if __salt__['mongodb.db_remove'](name, user, password, host, port, authdb=authdb):
            ret['comment'] = 'Database {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = ('User {0} is not present, so it cannot be removed'
            ).format(name)
    return ret
