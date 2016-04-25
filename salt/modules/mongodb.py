# -*- coding: utf-8 -*-
'''
Module to provide MongoDB functionality to Salt

:configuration: This module uses PyMongo, and accepts configuration details as
    parameters as well as configuration settings::

        mongodb.host: 'localhost'
        mongodb.port: 27017
        mongodb.user: ''
        mongodb.password: ''

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.
'''
from __future__ import absolute_import

# Import python libs
import logging
from distutils.version import LooseVersion  # pylint: disable=import-error,no-name-in-module
import json

# Import salt libs
from salt.ext.six import string_types
from salt.exceptions import get_error_message as _get_error_message


# Import third party libs
try:
    import pymongo
    HAS_MONGODB = True
except ImportError:
    HAS_MONGODB = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if pymongo is installed
    '''
    if HAS_MONGODB:
        return 'mongodb'
    else:
        return (False, 'The mongodb execution module cannot be loaded: the pymongo library is not available.')


def _connect(user=None, password=None, host=None, port=None, database='admin'):
    '''
    Returns a tuple of (user, host, port) with config, pillar, or default
    values assigned to missing values.
    '''
    if not user:
        user = __salt__['config.option']('mongodb.user')
    if not password:
        password = __salt__['config.option']('mongodb.password')
    if not host:
        host = __salt__['config.option']('mongodb.host')
    if not port:
        port = __salt__['config.option']('mongodb.port')

    try:
        conn = pymongo.MongoClient(host=host, port=port)
        mdb = pymongo.database.Database(conn, database)
        if user and password:
            mdb.authenticate(user, password)
    except pymongo.errors.PyMongoError:
        log.error('Error connecting to database {0}'.format(database))
        return False

    return conn


def _to_dict(objects):
    """
    Potentially interprets a string as JSON for usage with mongo
    """
    try:
        if isinstance(objects, string_types):
            objects = json.loads(objects)
    except ValueError as err:
        log.error("Could not parse objects: %s", err)
        raise err

    return objects


def db_list(user=None, password=None, host=None, port=None):
    '''
    List all Mongodb databases

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_list <user> <password> <host> <port>
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        log.info('Listing databases')
        return conn.database_names()
    except pymongo.errors.PyMongoError as err:
        log.error(err)
        return str(err)


def db_exists(name, user=None, password=None, host=None, port=None):
    '''
    Checks if a database exists in Mongodb

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_exists <name> <user> <password> <host> <port>
    '''
    dbs = db_list(user, password, host, port)

    if isinstance(dbs, string_types):
        return False

    return name in dbs


def db_remove(name, user=None, password=None, host=None, port=None):
    '''
    Remove a Mongodb database

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_remove <name> <user> <password> <host> <port>
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        log.info('Removing database {0}'.format(name))
        conn.drop_database(name)
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Removing database {0} failed with error: {1}'.format(
                name, str(err)
            )
        )
        return str(err)

    return True


def user_list(user=None, password=None, host=None, port=None, database='admin'):
    '''
    List users of a Mongodb database

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_list <user> <password> <host> <port> <database>
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        log.info('Listing users')
        mdb = pymongo.database.Database(conn, database)

        output = []
        mongodb_version = mdb.eval('db.version()')

        if LooseVersion(mongodb_version) >= LooseVersion('2.6'):
            for user in mdb.eval('db.getUsers()'):
                output.append([
                    ('user', user['user']),
                    ('roles', user['roles'])
                ])
        else:
            for user in mdb.system.users.find():
                output.append([
                    ('user', user['user']),
                    ('readOnly', user.get('readOnly', 'None'))
                ])
        return output

    except pymongo.errors.PyMongoError as err:
        log.error(
            'Listing users failed with error: {0}'.format(
                str(err)
            )
        )
        return str(err)


def user_exists(name, user=None, password=None, host=None, port=None,
                database='admin'):
    '''
    Checks if a user exists in Mongodb

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_exists <name> <user> <password> <host> <port> <database>
    '''
    users = user_list(user, password, host, port, database)

    if isinstance(users, string_types):
        return 'Failed to connect to mongo database'

    for user in users:
        if name == dict(user).get('user'):
            return True

    return False


def user_create(name, passwd, user=None, password=None, host=None, port=None,
                database='admin'):
    '''
    Create a Mongodb user

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_create <name> <user> <password> <host> <port> <database>
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        log.info('Creating user {0}'.format(name))
        mdb = pymongo.database.Database(conn, database)
        mdb.add_user(name, passwd)
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Creating database {0} failed with error: {1}'.format(
                name, str(err)
            )
        )
        return str(err)
    return True


def user_remove(name, user=None, password=None, host=None, port=None,
                database='admin'):
    '''
    Remove a Mongodb user

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_remove <name> <user> <password> <host> <port> <database>
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        log.info('Removing user {0}'.format(name))
        mdb = pymongo.database.Database(conn, database)
        mdb.remove_user(name)
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Creating database {0} failed with error: {1}'.format(
                name, str(err)
            )
        )
        return str(err)

    return True


def user_roles_exists(name, roles, database, user=None, password=None, host=None,
                      port=None):
    '''
    Checks if a user of a Mongodb database has specified roles

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_roles_exists johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_roles_exists johndoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    '''
    try:
        roles = _to_dict(roles)
    except Exception:
        return 'Roles provided in wrong format'

    users = user_list(user, password, host, port, database)

    if isinstance(users, string_types):
        return 'Failed to connect to mongo database'

    for user in users:
        if name == dict(user).get('user'):
            for role in roles:
                # if the role was provided in the shortened form, we convert it to a long form
                if not isinstance(role, dict):
                    role = {'role': role, 'db': database}
                if role not in dict(user).get('roles', []):
                    return False
            return True

    return False


def user_grant_roles(name, roles, database, user=None, password=None, host=None,
                     port=None):
    '''
    Grant one or many roles to a Mongodb user

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_grant_roles johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_grant_roles janedoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        roles = _to_dict(roles)
    except Exception:
        return 'Roles provided in wrong format'

    try:
        log.info('Granting roles {0} to user {1}'.format(roles, name))
        mdb = pymongo.database.Database(conn, database)
        mdb.eval("db.grantRolesToUser('{0}', {1})".format(name, roles))
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Granting roles {0} to user {1} failed with error: {2}'.format(
                roles, name, str(err)
            )
        )
        return str(err)

    return True


def user_revoke_roles(name, roles, database, user=None, password=None, host=None,
                      port=None):
    '''
    Revoke one or many roles to a Mongodb user

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_revoke_roles johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_revoke_roles janedoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    '''
    conn = _connect(user, password, host, port)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        roles = _to_dict(roles)
    except Exception:
        return 'Roles provided in wrong format'

    try:
        log.info('Revoking roles {0} from user {1}'.format(roles, name))
        mdb = pymongo.database.Database(conn, database)
        mdb.eval("db.revokeRolesFromUser('{0}', {1})".format(name, roles))
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Revoking roles {0} from user {1} failed with error: {2}'.format(
                roles, name, str(err)
            )
        )
        return str(err)

    return True


def insert(objects, collection, user=None, password=None,
           host=None, port=None, database='admin'):
    """
    Insert an object or list of objects into a collection

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.insert '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]' mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database)
    if not conn:
        return "Failed to connect to mongo database"

    try:
        objects = _to_dict(objects)
    except Exception as err:
        return err

    try:
        log.info("Inserting %r into %s.%s", objects, database, collection)
        mdb = pymongo.database.Database(conn, database)
        col = getattr(mdb, collection)
        ids = col.insert(objects)
        return ids
    except pymongo.errors.PyMongoError as err:
        log.error("Inserting objects %r failed with error %s", objects, err)
        return err


def find(collection, query=None, user=None, password=None,
         host=None, port=None, database='admin'):
    """
    Find an object or list of objects in a collection

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.find mycollection '[{"foo": "FOO", "bar": "BAR"}]' <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        query = _to_dict(query)
    except Exception as err:
        return err

    try:
        log.info("Searching for %r in %s", query, collection)
        mdb = pymongo.database.Database(conn, database)
        col = getattr(mdb, collection)
        ret = col.find(query)
        return list(ret)
    except pymongo.errors.PyMongoError as err:
        log.error("Searching objects failed with error: %s", err)
        return err


def remove(collection, query=None, user=None, password=None,
           host=None, port=None, database='admin', w=1):
    """
    Remove an object or list of objects into a collection

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.remove mycollection '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]' <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database)
    if not conn:
        return 'Failed to connect to mongo database'

    try:
        query = _to_dict(query)
    except Exception as err:
        return _get_error_message(err)

    try:
        log.info("Removing %r from %s", query, collection)
        mdb = pymongo.database.Database(conn, database)
        col = getattr(mdb, collection)
        ret = col.remove(query, w=w)
        return "{0} objects removed".format(ret['n'])
    except pymongo.errors.PyMongoError as err:
        log.error("Removing objects failed with error: %s", _get_error_message(err))
        return _get_error_message(err)
