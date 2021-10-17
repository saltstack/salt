"""
Cassandra Database Module

.. versionadded:: 2015.5.0

This module works with Cassandra v2 and v3 and hence generates
queries based on the internal schema of said version.

:depends: DataStax Python Driver for Apache Cassandra
          https://github.com/datastax/python-driver
          pip install cassandra-driver
:referenced by: Salt's cassandra_cql returner
:configuration:
    The Cassandra cluster members and connection port can either be specified
    in the master or minion config, the minion's pillar or be passed to the module.

    Example configuration in the config for a single node:

    .. code-block:: yaml

        cassandra:
          cluster: 192.168.50.10
          port: 9000

    Example configuration in the config for a cluster:

    .. code-block:: yaml

        cassandra:
          cluster:
            - 192.168.50.10
            - 192.168.50.11
            - 192.168.50.12
          port: 9000
          username: cas_admin

    .. versionchanged:: 2016.11.0

    Added support for ``ssl_options`` and ``protocol_version``.

    Example configuration with
    `ssl options <http://datastax.github.io/python-driver/api/cassandra/cluster.html#cassandra.cluster.Cluster.ssl_options>`_:

    If ``ssl_options`` are present in cassandra config the cassandra_cql returner
    will use SSL. SSL isn't used if ``ssl_options`` isn't specified.

    .. code-block:: yaml

        cassandra:
          cluster:
            - 192.168.50.10
            - 192.168.50.11
            - 192.168.50.12
          port: 9000
          username: cas_admin

          ssl_options:
            ca_certs: /etc/ssl/certs/ca-bundle.trust.crt

            # SSL version should be one from the ssl module
            # This is an optional parameter
            ssl_version: PROTOCOL_TLSv1

    Additionally you can also specify the ``protocol_version`` to
    `use <http://datastax.github.io/python-driver/api/cassandra/cluster.html#cassandra.cluster.Cluster.ssl_options>`_.

    .. code-block:: yaml

        cassandra:
          cluster:
            - 192.168.50.10
            - 192.168.50.11
            - 192.168.50.12
          port: 9000
          username: cas_admin

          # defaults to 4, if not set
          protocol_version: 3

"""

import logging
import re
import ssl

import salt.utils.json
import salt.utils.versions
from salt.exceptions import CommandExecutionError

SSL_VERSION = "ssl_version"

log = logging.getLogger(__name__)

__virtualname__ = "cassandra_cql"

HAS_DRIVER = False
try:
    # pylint: disable=import-error,no-name-in-module
    from cassandra.cluster import Cluster
    from cassandra.cluster import NoHostAvailable
    from cassandra.connection import (
        ConnectionException,
        ConnectionShutdown,
        OperationTimedOut,
    )
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.query import dict_factory

    # pylint: enable=import-error,no-name-in-module
    HAS_DRIVER = True
except ImportError:
    pass


def __virtual__():
    """
    Return virtual name of the module only if the python driver can be loaded.

    :return: The virtual name of the module.
    :rtype:  str
    """
    if HAS_DRIVER:
        return __virtualname__
    return (False, "Cannot load cassandra_cql module: python driver not found")


def _async_log_errors(errors):
    log.error("Cassandra_cql asynchronous call returned: %s", errors)


def _load_properties(property_name, config_option, set_default=False, default=None):
    """
    Load properties for the cassandra module from config or pillar.

    :param property_name: The property to load.
    :type  property_name: str or list of str
    :param config_option: The name of the config option.
    :type  config_option: str
    :param set_default:   Should a default be set if not found in config.
    :type  set_default:   bool
    :param default:       The default value to be set.
    :type  default:       str or int
    :return:              The property fetched from the configuration or default.
    :rtype:               str or list of str
    """
    if not property_name:
        log.debug(
            "No property specified in function, trying to load from salt configuration"
        )
        try:
            options = __salt__["config.option"]("cassandra")
        except BaseException as e:
            log.error("Failed to get cassandra config options. Reason: %s", e)
            raise

        loaded_property = options.get(config_option)
        if not loaded_property:
            if set_default:
                log.debug("Setting default Cassandra %s to %s", config_option, default)
                loaded_property = default
            else:
                log.error(
                    "No cassandra %s specified in the configuration or passed to the"
                    " module.",
                    config_option,
                )
                raise CommandExecutionError(
                    "ERROR: Cassandra {} cannot be empty.".format(config_option)
                )
        return loaded_property
    return property_name


def _get_ssl_opts():
    """
    Parse out ssl_options for Cassandra cluster connection.
    Make sure that the ssl_version (if any specified) is valid.
    """
    sslopts = __salt__["config.option"]("cassandra").get("ssl_options", None)
    ssl_opts = {}

    if sslopts:
        ssl_opts["ca_certs"] = sslopts["ca_certs"]
        if SSL_VERSION in sslopts:
            if not sslopts[SSL_VERSION].startswith("PROTOCOL_"):
                valid_opts = ", ".join(
                    [x for x in dir(ssl) if x.startswith("PROTOCOL_")]
                )
                raise CommandExecutionError(
                    "Invalid protocol_version specified! Please make sure "
                    "that the ssl protocol version is one from the SSL "
                    "module. Valid options are {}".format(valid_opts)
                )
            else:
                ssl_opts[SSL_VERSION] = getattr(ssl, sslopts[SSL_VERSION])
        return ssl_opts
    else:
        return None


def _connect(
    contact_points=None, port=None, cql_user=None, cql_pass=None, protocol_version=None
):
    """
    Connect to a Cassandra cluster.

    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str or list of str
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :param protocol_version:  Cassandra protocol version to use.
    :type  port:           int
    :return:               The session and cluster objects.
    :rtype:                cluster object, session object
    """
    # Lazy load the Cassandra cluster and session for this module by creating a
    # cluster and session when cql_query is called the first time. Get the
    # Cassandra cluster and session from this module's __context__ after it is
    # loaded the first time cql_query is called.
    #
    # TODO: Call cluster.shutdown() when the module is unloaded on
    # master/minion shutdown. Currently, Master.shutdown() and Minion.shutdown()
    # do nothing to allow loaded modules to gracefully handle resources stored
    # in __context__ (i.e. connection pools). This means that the connection
    # pool is orphaned and Salt relies on Cassandra to reclaim connections.
    # Perhaps if Master/Minion daemons could be enhanced to call an "__unload__"
    # function, or something similar for each loaded module, connection pools
    # and the like can be gracefully reclaimed/shutdown.
    if (
        __context__
        and "cassandra_cql_returner_cluster" in __context__
        and "cassandra_cql_returner_session" in __context__
    ):
        return (
            __context__["cassandra_cql_returner_cluster"],
            __context__["cassandra_cql_returner_session"],
        )
    else:

        contact_points = _load_properties(
            property_name=contact_points, config_option="cluster"
        )
        contact_points = (
            contact_points
            if isinstance(contact_points, list)
            else contact_points.split(",")
        )
        port = _load_properties(
            property_name=port, config_option="port", set_default=True, default=9042
        )
        cql_user = _load_properties(
            property_name=cql_user,
            config_option="username",
            set_default=True,
            default="cassandra",
        )
        cql_pass = _load_properties(
            property_name=cql_pass,
            config_option="password",
            set_default=True,
            default="cassandra",
        )
        protocol_version = _load_properties(
            property_name=protocol_version,
            config_option="protocol_version",
            set_default=True,
            default=4,
        )

        try:
            auth_provider = PlainTextAuthProvider(username=cql_user, password=cql_pass)
            ssl_opts = _get_ssl_opts()
            if ssl_opts:
                cluster = Cluster(
                    contact_points,
                    port=port,
                    auth_provider=auth_provider,
                    ssl_options=ssl_opts,
                    protocol_version=protocol_version,
                    compression=True,
                )
            else:
                cluster = Cluster(
                    contact_points,
                    port=port,
                    auth_provider=auth_provider,
                    protocol_version=protocol_version,
                    compression=True,
                )
            for recontimes in range(1, 4):
                try:
                    session = cluster.connect()
                    break
                except OperationTimedOut:
                    log.warning(
                        "Cassandra cluster.connect timed out, try %s", recontimes
                    )
                    if recontimes >= 3:
                        raise

            # TODO: Call cluster.shutdown() when the module is unloaded on shutdown.
            __context__["cassandra_cql_returner_cluster"] = cluster
            __context__["cassandra_cql_returner_session"] = session
            __context__["cassandra_cql_prepared"] = {}

            log.debug(
                "Successfully connected to Cassandra cluster at %s", contact_points
            )
            return cluster, session
        except TypeError:
            pass
        except (ConnectionException, ConnectionShutdown, NoHostAvailable):
            log.error("Could not connect to Cassandra cluster at %s", contact_points)
            raise CommandExecutionError(
                "ERROR: Could not connect to Cassandra cluster."
            )


def cql_query(query, contact_points=None, port=None, cql_user=None, cql_pass=None):
    """
    Run a query on a Cassandra cluster and return a dictionary.

    :param query:          The query to execute.
    :type  query:          str
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :param params:         The parameters for the query, optional.
    :type  params:         str
    :return:               A dictionary from the return values of the query
    :rtype:                list[dict]

    CLI Example:

    .. code-block:: bash

         salt 'cassandra-server' cassandra_cql.cql_query "SELECT * FROM users_by_name WHERE first_name = 'jane'"
    """
    try:
        cluster, session = _connect(
            contact_points=contact_points,
            port=port,
            cql_user=cql_user,
            cql_pass=cql_pass,
        )
    except CommandExecutionError:
        log.critical("Could not get Cassandra cluster session.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while getting Cassandra cluster session: %s", e)
        raise

    session.row_factory = dict_factory
    ret = []

    # Cassandra changed their internal schema from v2 to v3
    # If the query contains a dictionary sorted by versions
    # Find the query for the current cluster version.
    # https://issues.apache.org/jira/browse/CASSANDRA-6717
    if isinstance(query, dict):
        cluster_version = version(
            contact_points=contact_points,
            port=port,
            cql_user=cql_user,
            cql_pass=cql_pass,
        )
        match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", cluster_version)
        major, minor, point = match.groups()
        # try to find the specific version in the query dictionary
        # then try the major version
        # otherwise default to the highest version number
        try:
            query = query[cluster_version]
        except KeyError:
            query = query.get(major, max(query))
        log.debug("New query is: %s", query)

    try:
        results = session.execute(query)
    except BaseException as e:
        log.error("Failed to execute query: %s\n reason: %s", query, e)
        msg = "ERROR: Cassandra query failed: {} reason: {}".format(query, e)
        raise CommandExecutionError(msg)

    if results:
        for result in results:
            values = {}
            for key, value in result.items():
                # Salt won't return dictionaries with odd types like uuid.UUID
                if not isinstance(value, str):
                    # Must support Cassandra collection types.
                    # Namely, Cassandras set, list, and map collections.
                    if not isinstance(value, (set, list, dict)):
                        value = str(value)
                values[key] = value
            ret.append(values)

    return ret


def cql_query_with_prepare(
    query,
    statement_name,
    statement_arguments,
    asynchronous=False,
    callback_errors=None,
    contact_points=None,
    port=None,
    cql_user=None,
    cql_pass=None,
    **kwargs
):
    """
    Run a query on a Cassandra cluster and return a dictionary.

    This function should not be used asynchronously for SELECTs -- it will not
    return anything and we don't currently have a mechanism for handling a future
    that will return results.

    :param query:          The query to execute.
    :type  query:          str
    :param statement_name: Name to assign the prepared statement in the __context__ dictionary
    :type  statement_name: str
    :param statement_arguments: Bind parameters for the SQL statement
    :type  statement_arguments: list[str]
    :param asynchronous:          Run this query in asynchronous mode
    :type  asynchronous:          bool
    :param async:                 Run this query in asynchronous mode (an alias to 'asynchronous')
                                  NOTE: currently it overrides 'asynchronous' and it will be dropped in version 3001!
    :type  async:          bool
    :param callback_errors: Function to call after query runs if there is an error
    :type  callback_errors: Function callable
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :param params:         The parameters for the query, optional.
    :type  params:         str
    :return:               A dictionary from the return values of the query
    :rtype:                list[dict]

    CLI Example:

    .. code-block:: bash

        # Insert data asynchronously
        salt this-node cassandra_cql.cql_query_with_prepare "name_insert" "INSERT INTO USERS (first_name, last_name) VALUES (?, ?)" \
            statement_arguments=['John','Doe'], asynchronous=True

        # Select data, should not be asynchronous because there is not currently a facility to return data from a future
        salt this-node cassandra_cql.cql_query_with_prepare "name_select" "SELECT * FROM USERS WHERE first_name=?" \
            statement_arguments=['John']
    """
    # Backward-compatibility with Python 3.7: "async" is a reserved word
    if "async" in kwargs:
        asynchronous = kwargs.get("async", False)
    try:
        cluster, session = _connect(
            contact_points=contact_points,
            port=port,
            cql_user=cql_user,
            cql_pass=cql_pass,
        )
    except CommandExecutionError:
        log.critical("Could not get Cassandra cluster session.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while getting Cassandra cluster session: %s", e)
        raise

    if statement_name not in __context__["cassandra_cql_prepared"]:
        try:
            bound_statement = session.prepare(query)
            __context__["cassandra_cql_prepared"][statement_name] = bound_statement
        except BaseException as e:
            log.critical("Unexpected error while preparing SQL statement: %s", e)
            raise
    else:
        bound_statement = __context__["cassandra_cql_prepared"][statement_name]

    session.row_factory = dict_factory
    ret = []

    try:
        if asynchronous:
            future_results = session.execute_async(
                bound_statement.bind(statement_arguments)
            )
            # future_results.add_callbacks(_async_log_errors)
        else:
            results = session.execute(bound_statement.bind(statement_arguments))
    except BaseException as e:
        log.error("Failed to execute query: %s\n reason: %s", query, e)
        msg = "ERROR: Cassandra query failed: {} reason: {}".format(query, e)
        raise CommandExecutionError(msg)

    if not asynchronous and results:
        for result in results:
            values = {}
            for key, value in result.items():
                # Salt won't return dictionaries with odd types like uuid.UUID
                if not isinstance(value, str):
                    # Must support Cassandra collection types.
                    # Namely, Cassandras set, list, and map collections.
                    if not isinstance(value, (set, list, dict)):
                        value = str(value)
                values[key] = value
            ret.append(values)

    # If this was a synchronous call, then we either have an empty list
    # because there was no return, or we have a return
    # If this was an asynchronous call we only return the empty list
    return ret


def version(contact_points=None, port=None, cql_user=None, cql_pass=None):
    """
    Show the Cassandra version.

    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The version for this Cassandra cluster.
    :rtype:                str

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.version

        salt 'minion1' cassandra_cql.version contact_points=minion1
    """
    query = "select release_version from system.local limit 1;"

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not get Cassandra version.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while getting Cassandra version: %s", e)
        raise

    return ret[0].get("release_version")


def info(contact_points=None, port=None, cql_user=None, cql_pass=None):
    """
    Show the Cassandra information for this cluster.

    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The information for this Cassandra cluster.
    :rtype:                dict

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.info

        salt 'minion1' cassandra_cql.info contact_points=minion1
    """

    query = """select cluster_name,
                      data_center,
                      partitioner,
                      host_id,
                      rack,
                      release_version,
                      cql_version,
                      schema_version,
                      thrift_version
                 from system.local
                limit 1;"""

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not list Cassandra info.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while listing Cassandra info: %s", e)
        raise

    return ret


def list_keyspaces(contact_points=None, port=None, cql_user=None, cql_pass=None):
    """
    List keyspaces in a Cassandra cluster.

    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The keyspaces in this Cassandra cluster.
    :rtype:                list[dict]

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.list_keyspaces

        salt 'minion1' cassandra_cql.list_keyspaces contact_points=minion1 port=9000
    """
    query = {
        "2": "select keyspace_name from system.schema_keyspaces;",
        "3": "select keyspace_name from system_schema.keyspaces;",
    }

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not list keyspaces.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while listing keyspaces: %s", e)
        raise

    return ret


def list_column_families(
    keyspace=None, contact_points=None, port=None, cql_user=None, cql_pass=None
):
    """
    List column families in a Cassandra cluster for all keyspaces or just the provided one.

    :param keyspace:       The keyspace to provide the column families for, optional.
    :type  keyspace:       str
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The column families in this Cassandra cluster.
    :rtype:                list[dict]

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.list_column_families

        salt 'minion1' cassandra_cql.list_column_families contact_points=minion1

        salt 'minion1' cassandra_cql.list_column_families keyspace=system
    """
    where_clause = "where keyspace_name = '{}'".format(keyspace) if keyspace else ""

    query = {
        "2": "select columnfamily_name from system.schema_columnfamilies {};".format(
            where_clause
        ),
        "3": "select column_name from system_schema.columns {};".format(where_clause),
    }

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not list column families.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while listing column families: %s", e)
        raise

    return ret


def keyspace_exists(
    keyspace, contact_points=None, port=None, cql_user=None, cql_pass=None
):
    """
    Check if a keyspace exists in a Cassandra cluster.

    :param keyspace        The keyspace name to check for.
    :type  keyspace:       str
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The info for the keyspace or False if it does not exist.
    :rtype:                dict

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.keyspace_exists keyspace=system
    """
    query = {
        "2": (
            "select keyspace_name from system.schema_keyspaces where keyspace_name ="
            " '{}';".format(keyspace)
        ),
        "3": (
            "select keyspace_name from system_schema.keyspaces where keyspace_name ="
            " '{}';".format(keyspace)
        ),
    }

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not determine if keyspace exists.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while determining if keyspace exists: %s", e)
        raise

    return True if ret else False


def create_keyspace(
    keyspace,
    replication_strategy="SimpleStrategy",
    replication_factor=1,
    replication_datacenters=None,
    contact_points=None,
    port=None,
    cql_user=None,
    cql_pass=None,
):
    """
    Create a new keyspace in Cassandra.

    :param keyspace:                The keyspace name
    :type  keyspace:                str
    :param replication_strategy:    either `SimpleStrategy` or `NetworkTopologyStrategy`
    :type  replication_strategy:    str
    :param replication_factor:      number of replicas of data on multiple nodes. not used if using NetworkTopologyStrategy
    :type  replication_factor:      int
    :param replication_datacenters: string or dict of datacenter names to replication factors, required if using
                                    NetworkTopologyStrategy (will be a dict if coming from state file).
    :type  replication_datacenters: str | dict[str, int]
    :param contact_points:          The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points:          str | list[str]
    :param cql_user:                The Cassandra user if authentication is turned on.
    :type  cql_user:                str
    :param cql_pass:                The Cassandra user password if authentication is turned on.
    :type  cql_pass:                str
    :param port:                    The Cassandra cluster port, defaults to None.
    :type  port:                    int
    :return:                        The info for the keyspace or False if it does not exist.
    :rtype:                         dict

    CLI Example:

    .. code-block:: bash

        # CLI Example:
        salt 'minion1' cassandra_cql.create_keyspace keyspace=newkeyspace

        salt 'minion1' cassandra_cql.create_keyspace keyspace=newkeyspace replication_strategy=NetworkTopologyStrategy \
        replication_datacenters='{"datacenter_1": 3, "datacenter_2": 2}'
    """
    existing_keyspace = keyspace_exists(keyspace, contact_points, port)
    if not existing_keyspace:
        # Add the strategy, replication_factor, etc.
        replication_map = {"class": replication_strategy}

        if replication_datacenters:
            if isinstance(replication_datacenters, str):
                try:
                    replication_datacenter_map = salt.utils.json.loads(
                        replication_datacenters
                    )
                    replication_map.update(**replication_datacenter_map)
                except BaseException:  # pylint: disable=W0703
                    log.error("Could not load json replication_datacenters.")
                    return False
            else:
                replication_map.update(**replication_datacenters)
        else:
            replication_map["replication_factor"] = replication_factor

        query = """create keyspace {} with replication = {} and durable_writes = true;""".format(
            keyspace, replication_map
        )

        try:
            cql_query(query, contact_points, port, cql_user, cql_pass)
        except CommandExecutionError:
            log.critical("Could not create keyspace.")
            raise
        except BaseException as e:
            log.critical("Unexpected error while creating keyspace: %s", e)
            raise


def drop_keyspace(
    keyspace, contact_points=None, port=None, cql_user=None, cql_pass=None
):
    """
    Drop a keyspace if it exists in a Cassandra cluster.

    :param keyspace:       The keyspace to drop.
    :type  keyspace:       str
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The info for the keyspace or False if it does not exist.
    :rtype:                dict

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.drop_keyspace keyspace=test

        salt 'minion1' cassandra_cql.drop_keyspace keyspace=test contact_points=minion1
    """
    existing_keyspace = keyspace_exists(keyspace, contact_points, port)
    if existing_keyspace:
        query = """drop keyspace {};""".format(keyspace)
        try:
            cql_query(query, contact_points, port, cql_user, cql_pass)
        except CommandExecutionError:
            log.critical("Could not drop keyspace.")
            raise
        except BaseException as e:
            log.critical("Unexpected error while dropping keyspace: %s", e)
            raise

    return True


def list_users(contact_points=None, port=None, cql_user=None, cql_pass=None):
    """
    List existing users in this Cassandra cluster.

    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :return:               The list of existing users.
    :rtype:                dict

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.list_users

        salt 'minion1' cassandra_cql.list_users contact_points=minion1
    """
    query = "list users;"

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not list users.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while listing users: %s", e)
        raise

    return ret


def create_user(
    username,
    password,
    superuser=False,
    contact_points=None,
    port=None,
    cql_user=None,
    cql_pass=None,
):
    """
    Create a new cassandra user with credentials and superuser status.

    :param username:       The name of the new user.
    :type  username:       str
    :param password:       The password of the new user.
    :type  password:       str
    :param superuser:      Is the new user going to be a superuser? default: False
    :type  superuser:      bool
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:
    :rtype:

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.create_user username=joe password=secret

        salt 'minion1' cassandra_cql.create_user username=joe password=secret superuser=True

        salt 'minion1' cassandra_cql.create_user username=joe password=secret superuser=True contact_points=minion1
    """
    superuser_cql = "superuser" if superuser else "nosuperuser"
    query = """create user if not exists {} with password '{}' {};""".format(
        username, password, superuser_cql
    )
    log.debug(
        "Attempting to create a new user with username=%s superuser=%s",
        username,
        superuser_cql,
    )

    # The create user query doesn't actually return anything if the query succeeds.
    # If the query fails, catch the exception, log a messange and raise it again.
    try:
        cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not create user.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while creating user: %s", e)
        raise

    return True


def list_permissions(
    username=None,
    resource=None,
    resource_type="keyspace",
    permission=None,
    contact_points=None,
    port=None,
    cql_user=None,
    cql_pass=None,
):
    """
    List permissions.

    :param username:       The name of the user to list permissions for.
    :type  username:       str
    :param resource:       The resource (keyspace or table), if None, permissions for all resources are listed.
    :type  resource:       str
    :param resource_type:  The resource_type (keyspace or table), defaults to 'keyspace'.
    :type  resource_type:  str
    :param permission:     A permission name (e.g. select), if None, all permissions are listed.
    :type  permission:     str
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               Dictionary of permissions.
    :rtype:                dict

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.list_permissions

        salt 'minion1' cassandra_cql.list_permissions username=joe resource=test_keyspace permission=select

        salt 'minion1' cassandra_cql.list_permissions username=joe resource=test_table resource_type=table \
          permission=select contact_points=minion1
    """
    keyspace_cql = (
        "{} {}".format(resource_type, resource) if resource else "all keyspaces"
    )
    permission_cql = (
        "{} permission".format(permission) if permission else "all permissions"
    )
    query = "list {} on {}".format(permission_cql, keyspace_cql)

    if username:
        query = "{} of {}".format(query, username)

    log.debug("Attempting to list permissions with query '%s'", query)

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not list permissions.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while listing permissions: %s", e)
        raise

    return ret


def grant_permission(
    username,
    resource=None,
    resource_type="keyspace",
    permission=None,
    contact_points=None,
    port=None,
    cql_user=None,
    cql_pass=None,
):
    """
    Grant permissions to a user.

    :param username:       The name of the user to grant permissions to.
    :type  username:       str
    :param resource:       The resource (keyspace or table), if None, permissions for all resources are granted.
    :type  resource:       str
    :param resource_type:  The resource_type (keyspace or table), defaults to 'keyspace'.
    :type  resource_type:  str
    :param permission:     A permission name (e.g. select), if None, all permissions are granted.
    :type  permission:     str
    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str | list[str]
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:
    :rtype:

    CLI Example:

    .. code-block:: bash

        salt 'minion1' cassandra_cql.grant_permission

        salt 'minion1' cassandra_cql.grant_permission username=joe resource=test_keyspace permission=select

        salt 'minion1' cassandra_cql.grant_permission username=joe resource=test_table resource_type=table \
        permission=select contact_points=minion1
    """
    permission_cql = (
        "grant {}".format(permission) if permission else "grant all permissions"
    )
    resource_cql = (
        "on {} {}".format(resource_type, resource) if resource else "on all keyspaces"
    )
    query = "{} {} to {}".format(permission_cql, resource_cql, username)
    log.debug("Attempting to grant permissions with query '%s'", query)

    try:
        cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical("Could not grant permissions.")
        raise
    except BaseException as e:
        log.critical("Unexpected error while granting permissions: %s", e)
        raise

    return True
