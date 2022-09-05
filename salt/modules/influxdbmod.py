"""
InfluxDB - A distributed time series database

Module to provide InfluxDB compatibility to Salt (compatible with InfluxDB
version 0.9+)

:depends:    - influxdb Python module (>= 3.0.0)

:configuration: This module accepts connection configuration details either as
    parameters or as configuration settings in /etc/salt/minion on the relevant
    minions::

        influxdb.host: 'localhost'
        influxdb.port: 8086
        influxdb.user: 'root'
        influxdb.password: 'root'

    This data can also be passed into pillar. Options passed into opts will
    overwrite options passed into pillar.

    Most functions in this module allow you to override or provide some or all
    of these settings via keyword arguments::

        salt '*' influxdb.foo_function influxdb_user='influxadmin' influxdb_password='s3cr1t'

    would override ``user`` and ``password`` while still using the defaults for
    ``host`` and ``port``.
"""

import collections
import logging
from collections.abc import Sequence

import salt.utils.json
from salt.state import STATE_INTERNAL_KEYWORDS as _STATE_INTERNAL_KEYWORDS

try:
    import influxdb

    HAS_INFLUXDB = True
except ImportError:
    HAS_INFLUXDB = False


log = logging.getLogger(__name__)

# name used to refer to this module in __salt__
__virtualname__ = "influxdb"


def __virtual__():
    """
    Only load if influxdb lib is present
    """
    if HAS_INFLUXDB:
        return __virtualname__
    return (
        False,
        "The influxdb execution module could not be loaded:"
        "influxdb library not available.",
    )


def _client(
    influxdb_user=None,
    influxdb_password=None,
    influxdb_host=None,
    influxdb_port=None,
    **client_args
):
    if not influxdb_user:
        influxdb_user = __salt__["config.option"]("influxdb.user", "root")
    if not influxdb_password:
        influxdb_password = __salt__["config.option"]("influxdb.password", "root")
    if not influxdb_host:
        influxdb_host = __salt__["config.option"]("influxdb.host", "localhost")
    if not influxdb_port:
        influxdb_port = __salt__["config.option"]("influxdb.port", 8086)
    for ignore in _STATE_INTERNAL_KEYWORDS:
        if ignore in client_args:
            del client_args[ignore]
    return influxdb.InfluxDBClient(
        host=influxdb_host,
        port=influxdb_port,
        username=influxdb_user,
        password=influxdb_password,
        **client_args
    )


def list_dbs(**client_args):
    """
    List all InfluxDB databases.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.list_dbs
    """
    client = _client(**client_args)

    return client.get_list_database()


def db_exists(name, **client_args):
    """
    Checks if a database exists in InfluxDB.

    name
        Name of the database to check.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.db_exists <name>
    """
    if name in [db["name"] for db in list_dbs(**client_args)]:
        return True

    return False


def create_db(name, **client_args):
    """
    Create a database.

    name
        Name of the database to create.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.create_db <name>
    """
    if db_exists(name, **client_args):
        log.info("DB '%s' already exists", name)
        return False

    client = _client(**client_args)
    client.create_database(name)

    return True


def drop_db(name, **client_args):
    """
    Drop a database.

    name
        Name of the database to drop.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.drop_db <name>
    """
    if not db_exists(name, **client_args):
        log.info("DB '%s' does not exist", name)
        return False

    client = _client(**client_args)
    client.drop_database(name)

    return True


def list_users(**client_args):
    """
    List all users.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.list_users
    """
    client = _client(**client_args)

    return client.get_list_users()


def user_exists(name, **client_args):
    """
    Check if a user exists.

    name
        Name of the user to check.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.user_exists <name>
    """
    if user_info(name, **client_args):
        return True

    return False


def user_info(name, **client_args):
    """
    Get information about given user.

    name
        Name of the user for which to get information.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.user_info <name>
    """
    matching_users = (
        user for user in list_users(**client_args) if user.get("user") == name
    )

    try:
        return next(matching_users)
    except StopIteration:
        pass


def create_user(name, passwd, admin=False, **client_args):
    """
    Create a user.

    name
        Name of the user to create.

    passwd
        Password of the new user.

    admin : False
        Whether the user should have cluster administration
        privileges or not.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.create_user <name> <password>
        salt '*' influxdb.create_user <name> <password> admin=True
    """
    if user_exists(name, **client_args):
        log.info("User '%s' already exists", name)
        return False

    client = _client(**client_args)
    client.create_user(name, passwd, admin)

    return True


def set_user_password(name, passwd, **client_args):
    """
    Change password of a user.

    name
        Name of the user for whom to set the password.

    passwd
        New password of the user.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.set_user_password <name> <password>
    """
    if not user_exists(name, **client_args):
        log.info("User '%s' does not exist", name)
        return False

    client = _client(**client_args)
    client.set_user_password(name, passwd)

    return True


def grant_admin_privileges(name, **client_args):
    """
    Grant cluster administration privileges to a user.

    name
        Name of the user to whom admin privileges will be granted.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.grant_admin_privileges <name>
    """
    client = _client(**client_args)
    client.grant_admin_privileges(name)

    return True


def revoke_admin_privileges(name, **client_args):
    """
    Revoke cluster administration privileges from a user.

    name
        Name of the user from whom admin privileges will be revoked.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.revoke_admin_privileges <name>
    """
    client = _client(**client_args)
    client.revoke_admin_privileges(name)

    return True


def remove_user(name, **client_args):
    """
    Remove a user.

    name
        Name of the user to remove

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.remove_user <name>
    """
    if not user_exists(name, **client_args):
        log.info("User '%s' does not exist", name)
        return False

    client = _client(**client_args)
    client.drop_user(name)

    return True


def get_retention_policy(database, name, **client_args):
    """
    Get an existing retention policy.

    database
        Name of the database for which the retention policy was
        defined.

    name
        Name of the retention policy.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.get_retention_policy metrics default
    """
    client = _client(**client_args)

    try:
        return next(
            p
            for p in client.get_list_retention_policies(database)
            if p.get("name") == name
        )
    except StopIteration:
        return {}


def retention_policy_exists(database, name, **client_args):
    """
    Check if retention policy with given name exists.

    database
        Name of the database for which the retention policy was
        defined.

    name
        Name of the retention policy to check.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.retention_policy_exists metrics default
    """
    if get_retention_policy(database, name, **client_args):
        return True

    return False


def drop_retention_policy(database, name, **client_args):
    """
    Drop a retention policy.

    database
        Name of the database for which the retention policy will be dropped.

    name
        Name of the retention policy to drop.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.drop_retention_policy mydb mypr
    """
    client = _client(**client_args)
    client.drop_retention_policy(name, database)

    return True


def create_retention_policy(
    database, name, duration, replication, default=False, **client_args
):
    """
    Create a retention policy.

    database
        Name of the database for which the retention policy will be created.

    name
        Name of the new retention policy.

    duration
        Duration of the new retention policy.

        Durations such as 1h, 90m, 12h, 7d, and 4w, are all supported and mean
        1 hour, 90 minutes, 12 hours, 7 day, and 4 weeks, respectively. For
        infinite retention – meaning the data will never be deleted – use 'INF'
        for duration. The minimum retention period is 1 hour.

    replication
        Replication factor of the retention policy.

        This determines how many independent copies of each data point are
        stored in a cluster.

    default : False
        Whether or not the policy as default will be set as default.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.create_retention_policy metrics default 1d 1
    """
    client = _client(**client_args)
    client.create_retention_policy(name, duration, replication, database, default)

    return True


def alter_retention_policy(
    database, name, duration, replication, default=False, **client_args
):
    """
    Modify an existing retention policy.

    name
        Name of the retention policy to modify.

    database
        Name of the database for which the retention policy was defined.

    duration
        New duration of given retention policy.

        Durations such as 1h, 90m, 12h, 7d, and 4w, are all supported
        and mean 1 hour, 90 minutes, 12 hours, 7 day, and 4 weeks,
        respectively. For infinite retention – meaning the data will
        never be deleted – use 'INF' for duration.
        The minimum retention period is 1 hour.

    replication
        New replication of given retention policy.

        This determines how many independent copies of each data point are
        stored in a cluster.

    default : False
        Whether or not to set the modified policy as default.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.alter_retention_policy metrics default 1d 1
    """
    client = _client(**client_args)
    client.alter_retention_policy(name, database, duration, replication, default)
    return True


def list_privileges(name, **client_args):
    """
    List privileges from a user.

    name
        Name of the user from whom privileges will be listed.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.list_privileges <name>
    """
    client = _client(**client_args)

    res = {}
    for item in client.get_list_privileges(name):
        res[item["database"]] = item["privilege"].split()[0].lower()
    return res


def grant_privilege(database, privilege, username, **client_args):
    """
    Grant a privilege on a database to a user.

    database
        Name of the database to grant the privilege on.

    privilege
        Privilege to grant. Can be one of 'read', 'write' or 'all'.

    username
        Name of the user to grant the privilege to.
    """
    client = _client(**client_args)
    client.grant_privilege(privilege, database, username)

    return True


def revoke_privilege(database, privilege, username, **client_args):
    """
    Revoke a privilege on a database from a user.

    database
        Name of the database to grant the privilege on.

    privilege
        Privilege to grant. Can be one of 'read', 'write' or 'all'.

    username
        Name of the user to grant the privilege to.
    """
    client = _client(**client_args)
    client.revoke_privilege(privilege, database, username)

    return True


def continuous_query_exists(database, name, **client_args):
    """
    Check if continuous query with given name exists on the database.

    database
        Name of the database for which the continuous query was
        defined.

    name
        Name of the continuous query to check.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.continuous_query_exists metrics default
    """
    if get_continuous_query(database, name, **client_args):
        return True

    return False


def get_continuous_query(database, name, **client_args):
    """
    Get an existing continuous query.

    database
        Name of the database for which the continuous query was
        defined.

    name
        Name of the continuous query to get.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.get_continuous_query mydb cq_month
    """
    client = _client(**client_args)

    try:
        for db, cqs in client.query("SHOW CONTINUOUS QUERIES").items():
            if db[0] == database:
                return next(cq for cq in cqs if cq.get("name") == name)
    except StopIteration:
        return {}
    return {}


def create_continuous_query(
    database, name, query, resample_time=None, coverage_period=None, **client_args
):
    """
    Create a continuous query.

    database
        Name of the database for which the continuous query will be
        created on.

    name
        Name of the continuous query to create.

    query
        The continuous query string.

    resample_time : None
        Duration between continuous query resampling.

    coverage_period : None
        Duration specifying time period per sample.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.create_continuous_query mydb cq_month 'SELECT mean(*) INTO mydb.a_month.:MEASUREMENT FROM mydb.a_week./.*/ GROUP BY time(5m), *'"""
    client = _client(**client_args)
    full_query = "CREATE CONTINUOUS QUERY {name} ON {database}"
    if resample_time:
        full_query += " RESAMPLE EVERY {resample_time}"
    if coverage_period:
        full_query += " FOR {coverage_period}"
    full_query += " BEGIN {query} END"
    query = full_query.format(
        name=name,
        database=database,
        query=query,
        resample_time=resample_time,
        coverage_period=coverage_period,
    )
    client.query(query)
    return True


def drop_continuous_query(database, name, **client_args):
    """
    Drop a continuous query.

    database
        Name of the database for which the continuous query will
        be drop from.

    name
        Name of the continuous query to drop.

    CLI Example:

    .. code-block:: bash

        salt '*' influxdb.drop_continuous_query mydb my_cq
    """
    client = _client(**client_args)

    query = "DROP CONTINUOUS QUERY {} ON {}".format(name, database)
    client.query(query)
    return True


def _pull_query_results(resultset):
    """
    Parses a ResultSet returned from InfluxDB into a dictionary of results,
    grouped by series names and optional JSON-encoded grouping tags.
    """
    _results = collections.defaultdict(lambda: {})
    for _header, _values in resultset.items():
        _header, _group_tags = _header
        if _group_tags:
            _results[_header][salt.utils.json.dumps(_group_tags)] = [
                _value for _value in _values
            ]
        else:
            _results[_header] = [_value for _value in _values]
    return dict(sorted(_results.items()))


def query(database, query, **client_args):
    """
    Execute a query.

    database
        Name of the database to query on.

    query
        InfluxQL query string.
    """
    client = _client(**client_args)
    _result = client.query(query, database=database)

    if isinstance(_result, Sequence):
        return [
            _pull_query_results(_query_result)
            for _query_result in _result
            if _query_result
        ]
    return [_pull_query_results(_result) if _result else {}]
