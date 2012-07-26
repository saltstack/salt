'''
Management of PostgreSQL databases (schemas).
=============================================

The postgres_database module is used to create and manage Postgres databases.
Databases can be set as either absent or present

.. code-block:: yaml

    frank:
      postgres_database.present
'''


def present(name,
            tablespace=None,
            encoding=None,
            locale=None,
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

    locale
        The locale to be used in this database

    lc_collate
        The LC_COLLATE setting to be used in this database

    lc_ctype
        The LC_CTYPE setting to be used in this database

    owner
        The username of the database owner

    template
        The template database from which to build this database

    runas
        System user all operation should be preformed on behalf of
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Database {0} is already present'.format(name)}

    # check if database exists
    if __salt__['postgres.db_exists'](name, runas=runas):
        return ret

    # The database is not present, make it!
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Database {0} is set to be created'.format(name)
        return ret
    if __salt__['postgres.db_create'](name,
                                    tablespace=tablespace,
                                    encoding=encoding,
                                    locale=locale,
                                    lc_collate=lc_collate,
                                    lc_ctype=lc_ctype,
                                    owner=owner,
                                    template=template,
                                    runas=runas):
        ret['comment'] = 'The database {0} has been created'.format(name)
        ret['changes'][name] = 'Present'
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
        System user all operation should be preformed on behalf of
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
    ret['comment'] = (
            'Database {0} is not present, so it cannot be removed'
            ).format(name)
    return ret
