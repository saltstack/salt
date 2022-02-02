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
from salt.utils.versions import LooseVersion as _LooseVersion

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
    user=None, password=None, host=None, port=None, database="admin", authdb=None
):
    """
    Returns a tuple of (user, host, port) with config, pillar, or default
    values assigned to missing values.
    """
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
        conn = pymongo.MongoClient(host=host, port=port)
        mdb = pymongo.database.Database(conn, database)
        if user and password:
            mdb.authenticate(user, password, source=authdb)
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


def db_list(user=None, password=None, host=None, port=None, authdb=None):
    """
    List all MongoDB databases

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_list <user> <password> <host> <port>
    """
    conn = _connect(user, password, host, port, authdb=authdb)
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Listing databases")
        return conn.database_names()
    except pymongo.errors.PyMongoError as err:
        log.error(err)
        return str(err)


def db_exists(name, user=None, password=None, host=None, port=None, authdb=None):
    """
    Checks if a database exists in MongoDB

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_exists <name> <user> <password> <host> <port>
    """
    dbs = db_list(user, password, host, port, authdb=authdb)

    if isinstance(dbs, str):
        return False

    return name in dbs


def db_remove(name, user=None, password=None, host=None, port=None, authdb=None):
    """
    Remove a MongoDB database

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.db_remove <name> <user> <password> <host> <port>
    """
    conn = _connect(user, password, host, port, authdb=authdb)
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
    user=None, password=None, host=None, port=None, database="admin", authdb=None
):
    """
    Get MongoDB instance version

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.version <user> <password> <host> <port> <database>
    """
    conn = _connect(user, password, host, port, authdb=authdb)
    if not conn:
        err_msg = "Failed to connect to MongoDB database {}:{}".format(host, port)
        log.error(err_msg)
        return (False, err_msg)

    try:
        mdb = pymongo.database.Database(conn, database)
        return _version(mdb)
    except pymongo.errors.PyMongoError as err:
        log.error("Listing users failed with error: %s", err)
        return str(err)


def user_find(
    name, user=None, password=None, host=None, port=None, database="admin", authdb=None
):
    """
    Get single user from MongoDB

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_find <name> <user> <password> <host> <port> <database> <authdb>
    """
    conn = _connect(user, password, host, port, authdb=authdb)
    if not conn:
        err_msg = "Failed to connect to MongoDB database {}:{}".format(host, port)
        log.error(err_msg)
        return (False, err_msg)

    mdb = pymongo.database.Database(conn, database)
    try:
        return mdb.command("usersInfo", name)["users"]
    except pymongo.errors.PyMongoError as err:
        log.error("Listing users failed with error: %s", err)
        return (False, str(err))


def user_list(
    user=None, password=None, host=None, port=None, database="admin", authdb=None
):
    """
    List users of a MongoDB database

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_list <user> <password> <host> <port> <database>
    """
    conn = _connect(user, password, host, port, authdb=authdb)
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Listing users")
        mdb = pymongo.database.Database(conn, database)

        output = []
        mongodb_version = _version(mdb)

        if _LooseVersion(mongodb_version) >= _LooseVersion("2.6"):
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
    name, user=None, password=None, host=None, port=None, database="admin", authdb=None
):
    """
    Checks if a user exists in MongoDB

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_exists <name> <user> <password> <host> <port> <database>
    """
    users = user_list(user, password, host, port, database, authdb)

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
):
    """
    Create a MongoDB user

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_create <user_name> <user_password> <roles> <user> <password> <host> <port> <database>
    """
    conn = _connect(user, password, host, port, authdb=authdb)
    if not conn:
        return "Failed to connect to mongo database"

    if not roles:
        roles = []

    try:
        log.info("Creating user %s", name)
        mdb = pymongo.database.Database(conn, database)
        mdb.add_user(name, passwd, roles=roles)
    except pymongo.errors.PyMongoError as err:
        log.error("Creating database %s failed with error: %s", name, err)
        return str(err)
    return True


def user_remove(
    name, user=None, password=None, host=None, port=None, database="admin", authdb=None
):
    """
    Remove a MongoDB user

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.user_remove <name> <user> <password> <host> <port> <database>
    """
    conn = _connect(user, password, host, port)
    if not conn:
        return "Failed to connect to mongo database"

    try:
        log.info("Removing user %s", name)
        mdb = pymongo.database.Database(conn, database)
        mdb.remove_user(name)
    except pymongo.errors.PyMongoError as err:
        log.error("Creating database %s failed with error: %s", name, err)
        return str(err)

    return True


def user_roles_exists(
    name, roles, database, user=None, password=None, host=None, port=None, authdb=None
):
    """
    Checks if a user of a MongoDB database has specified roles

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

    users = user_list(user, password, host, port, database, authdb)

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
    name, roles, database, user=None, password=None, host=None, port=None, authdb=None
):
    """
    Grant one or many roles to a MongoDB user

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_grant_roles johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_grant_roles janedoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    """
    conn = _connect(user, password, host, port, authdb=authdb)
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
    name, roles, database, user=None, password=None, host=None, port=None, authdb=None
):
    """
    Revoke one or many roles to a MongoDB user

    CLI Examples:

    .. code-block:: bash

        salt '*' mongodb.user_revoke_roles johndoe '["readWrite"]' dbname admin adminpwd localhost 27017

    .. code-block:: bash

        salt '*' mongodb.user_revoke_roles janedoe '[{"role": "readWrite", "db": "dbname" }, {"role": "read", "db": "otherdb"}]' dbname admin adminpwd localhost 27017
    """
    conn = _connect(user, password, host, port, authdb=authdb)
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


def insert(
    objects,
    collection,
    user=None,
    password=None,
    host=None,
    port=None,
    database="admin",
    authdb=None,
):
    """
    Insert an object or list of objects into a collection

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.insert '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]' mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database, authdb)
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
        ids = col.insert(objects)
        return ids
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
):
    """
    Update an object into a collection
    http://api.mongodb.com/python/current/api/pymongo/collection.html#pymongo.collection.Collection.update_one

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.update_one '{"_id": "my_minion"} {"bar": "BAR"}' mycollection <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database, authdb)
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
    test_f = find(collection, objs[0], user, password, host, port, database, authdb)
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
            return "{} objects updated".format(nb_mod)
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
):
    """
    Find an object or list of objects in a collection

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.find mycollection '[{"foo": "FOO", "bar": "BAR"}]' <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database, authdb)
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
        ret = col.find(query)
        return list(ret)
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
):
    """
    Remove an object or list of objects into a collection

    CLI Example:

    .. code-block:: bash

        salt '*' mongodb.remove mycollection '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]' <user> <password> <host> <port> <database>

    """
    conn = _connect(user, password, host, port, database, authdb)
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
        ret = col.remove(query, w=w)
        return "{} objects removed".format(ret["n"])
    except pymongo.errors.PyMongoError as err:
        log.error("Removing objects failed with error: %s", _get_error_message(err))
        return _get_error_message(err)
