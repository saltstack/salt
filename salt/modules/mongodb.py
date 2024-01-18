"""
Module to provide MongoDB functionality to Salt

:configuration: This module uses PyMongo, and accepts configuration details as
    parameters as well as configuration settings::

        mongodb.host: 'localhost'
        mongodb.port: 27017
        mongodb.user: ''
        mongodb.password: ''

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.
"""

import logging
import re

import salt.utils.json
from salt.exceptions import get_error_message as _get_error_message
from salt.utils.versions import Version

try:
    import pymongo

    HAS_MONGODB = True
except ImportError:
    HAS_MONGODB = False

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if pymongo is installed
    """
    if HAS_MONGODB:
        return "mongodb"
    else:
        return (
            False,
            "The mongodb execution module cannot be loaded: the pymongo library is not"
            " available.",
        )


def _connect(
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Connect to a mongodb database with pymongo.MongoClient. If user and
    password are provided, use those to authenticate with the database. If
    any of user, password, host, or port are not provided then fall back to
    config options:

    - mongodb.user
    - mongodb.password
    - mongodb.host
    - mongodb.port

    By default use the admin database for the database and authdb.

    If ``ssl`` is True, connect to mongodb over SSL.

    If connection fails for any reason, log error and return False.
    """

    verify_ssl = True if verify_ssl is None else verify_ssl

    if not user:
        user = __salt__["config.option"]("mongodb.user")
    if not password:
        password = __salt__["config.option"]("mongodb.password")
    if not host:
        host = __salt__["config.option"]("mongodb.host")
    if not port:
        port = __salt__["config.option"]("mongodb.port")
    if not authdb:
        authdb = database

    try:
        conn = pymongo.MongoClient(
            host=host,
            port=port,
            username=user,
            password=password,
            authSource=authdb,
            ssl=bool(ssl),
            tlsAllowInvalidCertificates=not verify_ssl,
        )
    except pymongo.errors.PyMongoError:
        log.error("Error connecting to database %s", database)
        return False

    return conn


def _to_dict(objects):
    """
    Potentially interprets a string as JSON for usage with mongo
    """
    try:
        if isinstance(objects, str):
            objects = salt.utils.json.loads(objects)
    except ValueError as err:
        log.error("Could not parse objects: %s", err)
        raise

    return objects


def db_list(
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    List all MongoDB databases.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_list <user> <password> <host> <port>
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Listing databases")
        return conn.list_database_names()
    except pymongo.errors.PyMongoError as err:
        print("Ooops")
        log.error(err)
        return str(err)


def db_exists(
    name,
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Checks if a database exists in MongoDB.

    name
        The name of the database to check for.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_exists <name> <user> <password> <host> <port>
    """
    dbs = db_list(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )

    if isinstance(dbs, str):
        return False

    return name in dbs


def db_remove(
    name,
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Remove a MongoDB database.

    name
        The name of the database to remove.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_remove <name> <user> <password> <host> <port>
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Removing database %s", name)
        conn.drop_database(name)
    except pymongo.errors.PyMongoError as err:
        log.error("Removing database %s failed with error: %s", name, err)
        return str(err)

    return True


def _version(mdb):
    return mdb.command("buildInfo")["version"]


def version(
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Get MongoDB instance version.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.version <user> <password> <host> <port> <database> <ssl>
    """
    # database is not passed into _connect here, which authdb typically falls
    # back on. Probably not a bug but still confusing -W. Werner, 2022-02-10
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        err_msg = f"Failed to connect to MongoDB database {host}:{port}"
        log.error(err_msg)
        return (False, err_msg)

    try:
        mdb = pymongo.database.Database(conn, database)
        return _version(mdb)
    except pymongo.errors.PyMongoError as err:
        log.error("Listing users failed with error: %s", err)
        return str(err)


def user_find(
    name,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Get single user from MongoDB.

    name
        The name of the user to find.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The MongoDB database to use when looking for the user. Default is ``admin``.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_find <name> <user> <password> <host> <port> <database> <authdb> <ssl>
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        err_msg = f"Failed to connect to MongoDB database {host}:{port}"
        log.error(err_msg)
        return (False, err_msg)

    mdb = pymongo.database.Database(conn, database)
    try:
        return mdb.command("usersInfo", name)["users"]
    except pymongo.errors.PyMongoError as err:
        log.error("Listing users failed with error: %s", err)
        return (False, str(err))


def user_list(
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    List users of a MongoDB database.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The MongoDB database to use when listing users. Default is ``admin``.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_list <user> <password> <host> <port> <database> <authdb> <ssl>
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Listing users")
        mdb = pymongo.database.Database(conn, database)

        output = []
        mongodb_version = _version(mdb)

        if Version(mongodb_version) >= Version("2.6"):
            for user in mdb.command("usersInfo")["users"]:
                output.append({"user": user["user"], "roles": user["roles"]})
        else:
            for user in mdb.system.users.find():
                output.append(
                    {"user": user["user"], "readOnly": user.get("readOnly", "None")}
                )
        return output

    except pymongo.errors.PyMongoError as err:
        log.error("Listing users failed with error: %s", err)
        return str(err)


def user_exists(
    name,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Checks if a user exists in MongoDB.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The MongoDB database to use when checking if the user exists. Default is ``admin``.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_exists <name> <user> <password> <host> <port> <database> <authdb> <ssl>
    """
    users = user_list(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )

    if isinstance(users, str):
        return "Failed to connect to mongo database"

    for user in users:
        if name == dict(user).get("user"):
            return True

    return False


def user_create(
    name,
    passwd,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    roles=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Create a MongoDB user.

    name
        The name of the user to create.

    passwd
        The password for the user that is being created.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The MongoDB database to use when checking if the user exists. Default is ``admin``.

    authdb
        The MongoDB database to use for authentication. Default is None.

    roles
        The roles that should be associated with the user. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_create <user_name> <user_password> <roles> <user> <password> <host> <port> <database> <authdb> <roles> <ssl>
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    if not roles:
        roles = []

    _roles = [{"role": _role, "db": database} for _role in roles]
    try:
        log.info("Creating user %s", name)
        mdb = pymongo.database.Database(conn, database)
        mdb.command("createUser", name, pwd=passwd, roles=_roles)

    except pymongo.errors.PyMongoError as err:
        log.error("Creating user %s failed with error: %s", name, err)
        return False
    return True


def user_remove(
    name,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Remove a MongoDB user.

    name
        The name of the user that should be removed.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_remove <name> <user> <password> <host> <port> <database> <authdb> <ssl>
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Removing user %s", name)
        mdb = pymongo.database.Database(conn, database)
        mdb.command("dropUser", name)
    except pymongo.errors.PyMongoError as err:
        log.error("Removing user %s failed with error: %s", name, err)
        return False
    return True


def user_roles_exists(
    name,
    roles,
    database,
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Checks if a user of a MongoDB database has specified roles.

    name
        The name of the user to check for roles.

    roles
        JSON list of roles to check either as strings, or JSON objects of
        rolename and dbname to check. Example: ``'["salt", "readWrite",
        "dinner"]'`` or ``[{"db": "some_database", "role": "dinner"}, {"db":
        "another_db", "role": "kaiser"}]``

    database
        The name of the database to check the user and roles against.

    user
        The user to authenticate with, if necessary.

    password
        The password to authenticate with, if necessary.

    host
        The host running MongoDB.

    port
        The port MongoDB is listening on.

    authdb
        The database to authenticate against, if not "admin".

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_roles_exists johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_roles_exists johndoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    """
    try:
        roles = _to_dict(roles)
    except Exception:  # pylint: disable=broad-except
        return "Roles provided in wrong format"

    # Here we pass in the database - does MongoDB return *all* of the roles
    # across databases for a particular user?
    users = user_list(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )

    if isinstance(users, str):
        return "Failed to connect to mongo database"

    for user in users:
        if name == dict(user).get("user"):
            for role in roles:
                # if the role was provided in the shortened form, we convert it to a long form
                if not isinstance(role, dict):
                    role = {"role": role, "db": database}
                if role not in dict(user).get("roles", []):
                    return False
            return True

    return False


def user_grant_roles(
    name,
    roles,
    database,
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Grant one or many roles to a MongoDB user.

    name
        The name of the user to grant roles to.

    roles
        JSON list of roles to check either as strings, or JSON objects of
        rolename and dbname to check. See ``user_roles_exists`` or examples
        below.

    database
        The database to grant roles on.

    user
        The user to authenticate with, if necessary.

    password
        The password to authenticate with, if necessary.

    host
        The host running MongoDB.

    port
        The port MongoDB is listening on.

    authdb
        The database to authenticate against, if not "admin".

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_grant_roles johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_grant_roles janedoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        roles = _to_dict(roles)
    except Exception:  # pylint: disable=broad-except
        return "Roles provided in wrong format"

    try:
        log.info("Granting roles %s to user %s", roles, name)
        mdb = pymongo.database.Database(conn, database)
        mdb.command("grantRolesToUser", name, roles=roles)
    except pymongo.errors.PyMongoError as err:
        log.error(
            "Granting roles %s to user %s failed with error: %s", roles, name, err
        )
        return str(err)

    return True


def user_revoke_roles(
    name,
    roles,
    database,
    user=None,
    password=None,
    host=None,
    port=None,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Revoke one or many roles from a MongoDB user.

    name
        The name of the user to revoke roles from.

    roles
        JSON list of roles to revoke either as strings, or JSON objects of
        rolename and dbname to check. See ``user_roles_exists`` or examples
        below.

    database
        The database to revoke roles on.

    user
        The user to authenticate with, if necessary.

    password
        The password to authenticate with, if necessary.

    host
        The host running MongoDB.

    port
        The port MongoDB is listening on.

    authdb
        The database to authenticate against, if not "admin".

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_revoke_roles johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_revoke_roles janedoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    """
    conn = _connect(
        user, password, host, port, authdb=authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        roles = _to_dict(roles)
    except Exception:  # pylint: disable=broad-except
        return "Roles provided in wrong format"

    try:
        log.info("Revoking roles %s from user %s", roles, name)
        mdb = pymongo.database.Database(conn, database)
        mdb.command("revokeRolesFromUser", name, roles=roles)
    except pymongo.errors.PyMongoError as err:
        log.error(
            "Revoking roles %s from user %s failed with error: %s", roles, name, err
        )
        return str(err)

    return True


def collection_create(
    collection,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    .. versionadded:: 3006.0

    Create a collection in the specified database.

    collection
        The name of the collection to create.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.collection_create mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Creating %s.%s", database, collection)
        mdb = pymongo.database.Database(conn, database)
        mdb.create_collection(collection)
    except pymongo.errors.PyMongoError as err:
        log.error(
            "Creating collection %r.%r failed with error %s", database, collection, err
        )
        return err
    return True


def collection_drop(
    collection,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    .. versionadded:: 3006.0

    Drop a collection in the specified database.

    collection
        The name of the collection to drop.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.collection_drop mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Dropping %s.%s", database, collection)
        mdb = pymongo.database.Database(conn, database)
        mdb.drop_collection(collection)
    except pymongo.errors.PyMongoError as err:
        log.error(
            "Creating collection %r.%r failed with error %s", database, collection, err
        )
        return err
    return True


def collections_list(
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    .. versionadded:: 3006.0

    List the collections available in the specified database.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.collections_list mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        mdb = pymongo.database.Database(conn, database)
        ret = mdb.list_collection_names()
    except pymongo.errors.PyMongoError as err:
        log.error("Listing collections failed with error %s", err)
        return err
    return ret


# TODO: Add SSL arg + docs -W. Werner, 2022-02-08
def insert(
    objects,
    collection,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Insert an object or list of objects into a collection.

    objects
        The documents to store in the collection.

    collection
        The MongoDB collection to store the documents in.

    user
        The user to authenticate with, if necessary.

    password
        The password to authenticate with, if necessary.

    host
        The host running MongoDB.

    port
        The port MongoDB is listening on.

    database
        The database containing the collection, if not "admin".

    authdb
        The database to authenticate against, if not "admin".

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.insert '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]' mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        objects = _to_dict(objects)
    except Exception as err:  # pylint: disable=broad-except
        return err

    try:
        log.info("Inserting %r into %s.%s", objects, database, collection)
        mdb = pymongo.database.Database(conn, database)
        col = getattr(mdb, collection)
        ids = col.insert_many(objects)
        return ids.acknowledged
    except pymongo.errors.PyMongoError as err:
        log.error("Inserting objects %r failed with error %s", objects, err)
        return err


def update_one(
    objects,
    collection,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Update a MongoDB document that matches the provided filter.
    http://api.mongodb.com/python/current/api/pymongo/collection.html#pymongo.collection.Collection.update_one

    If the document is not found or too many documents match, then an error
    will be returned.

    .. versionadded:: 2016.11.0

    objects
        The objects to update in the collection, should be provided as a list.

    collection
        The collection to insert the objects into.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The database containing the collection, if not "admin".

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.update_one '{"_id": "my_minion"} {"bar": "BAR"}' mycollection <user> <password> <host> <port> <database> <ssl>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    objects = str(objects)
    objs = re.split(r"}\s+{", objects)

    if len(objs) != 2:
        return (
            "Your request does not contain a valid "
            + '\'{_"id": "my_id"} {"my_doc": "my_val"}\''
        )

    objs[0] = objs[0] + "}"
    objs[1] = "{" + objs[1]

    document = []

    for obj in objs:
        try:
            obj = _to_dict(obj)
            document.append(obj)
        except Exception as err:  # pylint: disable=broad-except
            return err

    _id_field = document[0]
    _update_doc = document[1]

    # need a string to perform the test, so using objs[0]
    test_f = find(
        collection, objs[0], user, password, host, port, database, authdb, ssl
    )
    if not isinstance(test_f, list):
        return "The find result is not well formatted. An error appears; cannot update."
    elif not test_f:
        return "Did not find any result. You should try an insert before."
    elif len(test_f) > 1:
        return "Too many results. Please try to be more specific."
    else:
        try:
            log.info("Updating %r into %s.%s", _id_field, database, collection)
            mdb = pymongo.database.Database(conn, database)
            col = getattr(mdb, collection)
            ids = col.update_one(_id_field, {"$set": _update_doc})
            nb_mod = ids.modified_count
            return f"{nb_mod} objects updated"
        except pymongo.errors.PyMongoError as err:
            log.error("Updating object %s failed with error %s", objects, err)
            return err


def find(
    collection,
    query=None,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Find an object or list of objects in a collection

    collection
        The collection to find the objects in.

    query
        The query to use when locating objects in the collection.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The database containing the collection, if not "admin".

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.find mycollection '[{"foo": "FOO", "bar": "BAR"}]' <user> <password> <host> <port> <database> <authdb> <ssl>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        query = _to_dict(query)
    except Exception as err:  # pylint: disable=broad-except
        return err

    try:
        log.info("Searching for %r in %s", query, collection)
        mdb = pymongo.database.Database(conn, database)
        col = getattr(mdb, collection)
        if isinstance(query, list):
            ret = []
            for _query in query:
                res = col.find(_query)
                _ret = [_res for _res in res]
                ret.extend(_ret)
        else:
            res = col.find(query)
            ret = [_res for _res in res]
        return ret
    except pymongo.errors.PyMongoError as err:
        log.error("Searching objects failed with error: %s", err)
        return err


def remove(
    collection,
    query=None,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    w=1,
    authdb=None,
    ssl=False,
    verify_ssl=None,
):
    """
    Remove an object or list of objects from a collection

    collection
        The collection to remove objects from based on the query.

    query
        Query to determine which objects to remove.

    user
        The user to connect to MongoDB as. Default is None.

    password
        The password to use to connect to MongoDB as.  Default is None.

    host
        The host where MongoDB is running. Default is None.

    port
        The host where MongoDB is running. Default is None.

    database
        The database where the collection is.

    w
        The number of matches to remove from the collection.

    authdb
        The MongoDB database to use for authentication. Default is None.

    ssl
        Whether or not to connect to MongoDB over SSL. Default ``False``.

        .. versionadded:: 3008.0

    verify_ssl
        Whether or not to verify the server cert when connecting. Default True.

        .. versionadded:: 3008.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.remove mycollection '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]' <user> <password> <host> <port> <database> <w> <authdb> <ssl>

    """
    conn = _connect(
        user, password, host, port, database, authdb, ssl=ssl, verify_ssl=verify_ssl
    )
    if not conn:
        return "Failed to connect to mongo database"

    try:
        query = _to_dict(query)
    except Exception as err:  # pylint: disable=broad-except
        return _get_error_message(err)

    try:
        log.info("Removing %r from %s", query, collection)
        mdb = pymongo.database.Database(conn, database)
        col = getattr(mdb, collection)
        deleted_count = 0
        if isinstance(query, list):
            for _query in query:
                for count in range(0, w):
                    res = col.delete_one(_query)
                    deleted_count += res.deleted_count
        else:
            for count in range(0, w):
                res = col.delete_one(query)
                deleted_count += res.deleted_count
        return f"{deleted_count} objects removed"
    except pymongo.errors.PyMongoError as err:
        log.error("Removing objects failed with error: %s", _get_error_message(err))
        return _get_error_message(err)
