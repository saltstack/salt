# -*- coding: utf-8 -*-
'''
Management of Mongodb users
===========================
'''

# Define the module's virtual name
__virtualname__ = 'mongodb_user'


def __virtual__():
    if 'mongodb.user_exists' in __salt__:
        return __virtualname__
    return False


def present(name,
            passwd,
            database="admin",
            user=None,
            password=None,
            host="localhost",
            port=27017):
    '''
    Ensure that the user is present with the specified properties

    name
        The name of the user to manage

    passwd
        The password of the user to manage

    user
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified with the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database in which to create the user

        .. note::
            If the database doesn't exist, it will be created.

    Example:

    .. code-block:: yaml

        mongouser-myapp:
          mongodb_user.present:
          - name: myapp
          - passwd: password-of-myapp
          # Connect as admin:sekrit
          - user: admin
          - password: sekrit

    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is already present'.format(name)}

    # Check for valid port
    try:
        port = int(port)
    except TypeError:
        ret['result'] = False
        ret['comment'] = 'Port ({0}) is not an integer.'.format(port)
        return ret

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
        MongoDB user with sufficient privilege to create the user

    password
        Password for the admin user specified by the ``user`` parameter

    host
        The hostname/IP address of the MongoDB server

    port
        The port on which MongoDB is listening

    database
        The database from which to remove the user specified by the ``name``
        parameter
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
