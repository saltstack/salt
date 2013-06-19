'''
Management of PostgreSQL databases.
=============================================

The postgres_database module is used to create and manage Postgres databases.
Databases can be set as either absent or present

.. code-block:: yaml

    frank:
      postgres_database.present
'''


def __virtual__():
    '''
    Only load if the postgres module is present
    '''
    return 'postgres_database' if 'postgres.user_exists' in __salt__ else False


def present(name,
            tablespace=None,
            encoding=None,
            lc_collate=None,
            lc_ctype=None,
            owner=None,
            template=None,
            runas=None):
    '''
    Ensure that the named database is present with the specified properties.
    For more information about all of these options see man createdb(1)

    name
        The name of the database to manage

    tablespace
        Default tablespace for the database

    encoding
        The character encoding scheme to be used in this database

    lc_collate
        The LC_COLLATE setting to be used in this database

    lc_ctype
        The LC_CTYPE setting to be used in this database

    owner
        The username of the database owner

    template
        The template database from which to build this database

    runas
        System user all operations should be performed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Database {0} is already present'.format(name)}

    dbs = __salt__['postgres.db_list'](runas=runas)
    db_params = dbs.get(name, {})

    if name in dbs and all((
        db_params.get('Tablespace') == tablespace if tablespace else True,
        db_params.get('Encoding') == encoding if encoding else True,
        db_params.get('Collate') == lc_collate if lc_collate else True,
        db_params.get('Ctype') == lc_ctype if lc_ctype else True,
        db_params.get('Owner') == owner if owner else True
    )):
        return ret
    elif name in dbs and any((
        db_params.get('Encoding') != encoding if encoding else False,
        db_params.get('Collate') != lc_collate if lc_collate else False,
        db_params.get('Ctype') != lc_ctype if lc_ctype else False
    )):
        ret['comment'] = 'Database {0} has wrong parameters ' \
                         'which couldn\'t be changed on fly.'.format(name)
        ret['result'] = False
        return ret

    # The database is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        if name not in dbs:
            ret['comment'] = 'Database {0} is set to be created'.format(name)
        else:
            ret['comment'] = 'Database {0} exists, but parameters ' \
                             'need to be changed'.format(name)
        return ret
    if name not in dbs and __salt__['postgres.db_create'](
       name,
       tablespace=tablespace,
       encoding=encoding,
       lc_collate=lc_collate,
       lc_ctype=lc_ctype,
       owner=owner,
       template=template,
       runas=runas):
        ret['comment'] = 'The database {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
    elif name in dbs and __salt__['postgres.db_alter'](name,
                                                       tablespace=tablespace,
                                                       owner=owner):
        ret['comment'] = ('Parameters for database {0} have been changed'
                          ).format(name)
        ret['changes'][name] = 'Parameters changed'
    elif name in dbs:
        ret['comment'] = ('Failed to change parameters for database {0}'
                          ).format(name)
        ret['result'] = False
    else:
        ret['comment'] = 'Failed to create database {0}'.format(name)
        ret['result'] = False

    return ret


def absent(name, runas=None):
    '''
    Ensure that the named database is absent

    name
        The name of the database to remove

    runas
        System user all operations should be performed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    #check if db exists and remove it
    if __salt__['postgres.db_exists'](name, runas=runas):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Database {0} is set to be removed'.format(name)
            return ret
        if __salt__['postgres.db_remove'](name, runas=runas):
            ret['comment'] = 'Database {0} has been removed'.format(name)
            ret['changes'][name] = 'Absent'
            return ret

    # fallback
    ret['comment'] = 'Database {0} is not present, so it cannot ' \
                     'be removed'.format(name)
    return ret
