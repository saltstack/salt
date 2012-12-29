'''
Module to provide MongoDB functionality to Salt

:configuration: This module uses PyMongo, and accepts configuration details as
    parameters as well as configuration settings::

        mongodb.host: 'localhost'
        mongodb.port: '27017'
        mongodb.user: ''
        mongodb.password: ''

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.
'''

# Import python libs
import logging

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
        return False


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
        conn = pymongo.connection.Connection(host=host, port=port)
        mdb = pymongo.database.Database(conn, database)
        if user and password:
            mdb.authenticate(user, password)
    except pymongo.errors.PyMongoError:
        log.error('Error connecting to database {0}'.format(database.message))
        return False

    return conn


def db_list(user=None, password=None, host=None, port=None):
    '''
    List all Mongodb databases
    '''
    conn = _connect(user, password, host, port)

    try:
        log.info("Listing databases")
        return conn.database_names()
    except pymongo.errors.PyMongoError as err:
        log.error(err)
        return err.message


def db_exists(name, user=None, password=None, host=None, port=None,
              database='admin'):
    '''
    Checks if a database exists in Mongodb
    '''
    dbs = db_list(user, password, host, port)
    for mdb in dbs:
        if name == mdb:
            return True

    return False


def db_remove(name, user=None, password=None, host=None, port=None):
    '''
    Remove a Mongodb database
    '''
    conn = _connect(user, password, host, port)

    try:
        log.info('Removing database {0}'.format(name))
        conn.drop_database(name)
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Removing database {0} failed with error: {1}'.format(
                name, err.message
            )
        )
        return err.message

    return True


def user_list(user=None, password=None, host=None, port=None, database='admin'):
    '''
    List users of a Mongodb database
    '''
    conn = _connect(user, password, host, port)

    try:
        log.info('Listing users')
        mdb = pymongo.database.Database(conn, database)

        output = []

        for user in mdb.system.users.find():
            output.append([
                ('user', user['user']),
                ('readOnly', user['readOnly'])
            ])
        return output

    except pymongo.errors.PyMongoError as err:
        log.error(
            'Listing users failed with error: {0}'.format(
                err.message
            )
        )
        return err.message


def user_exists(name, user=None, password=None, host=None, port=None,
                database='admin'):
    '''
    Checks if a user exists in Mongodb
    '''
    users = user_list(user, password, host, port, database)
    for user in users:
        if name == dict(user).get('user'):
            return True

    return False


def user_create(name, passwd, user=None, password=None, host=None, port=None,
                database='admin'):
    '''
    Create a Mongodb user
    '''
    conn = _connect(user, password, host, port)

    try:
        log.info('Creating user {0}'.format(name))
        mdb = pymongo.database.Database(conn, database)
        mdb.add_user(name, passwd)
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Creating database {0} failed with error: {1}'.format(
                name, err.message
            )
        )
        return err.message
    return True


def user_remove(name, user=None, password=None, host=None, port=None,
                database='admin'):
    '''
    Remove a Mongodb user
    '''
    conn = _connect(user, password, host, port)

    try:
        log.info('Removing user {0}'.format(name))
        mdb = pymongo.database.Database(conn, database)
        mdb.remove_user(name)
    except pymongo.errors.PyMongoError as err:
        log.error(
            'Creating database {0} failed with error: {1}'.format(
                name, err.message
            )
        )
        return err.message

    return True
