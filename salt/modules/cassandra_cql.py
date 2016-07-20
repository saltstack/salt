# -*- coding: utf-8 -*-
'''
Cassandra Database Module

.. versionadded:: 2015.5.0

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
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import json

# Import Salt Libs
from salt.exceptions import CommandExecutionError
from salt.ext import six

log = logging.getLogger(__name__)

__virtualname__ = 'cassandra_cql'

HAS_DRIVER = False
try:
    # pylint: disable=import-error,no-name-in-module
    from cassandra.cluster import Cluster
    from cassandra.cluster import NoHostAvailable
    from cassandra.connection import ConnectionException, ConnectionShutdown
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.query import dict_factory
    # pylint: enable=import-error,no-name-in-module
    HAS_DRIVER = True
except ImportError:
    pass


def __virtual__():
    '''
    Return virtual name of the module only if the python driver can be loaded.

    :return: The virtual name of the module.
    :rtype:  str
    '''
    if HAS_DRIVER:
        return __virtualname__
    return False


def _load_properties(property_name, config_option, set_default=False, default=None):
    '''
    Load properties for the cassandra module from config or pillar.

    :param property_name: The property to load.
    :type  property_name: str or list of str
    :param config_option: The name of the config option.
    :type  config_option: str
    :param set_default:   Should a default be set if not found in config.
    :type  set_default:   bool
    :param default:       The default value to be set.
    :type  default:       str
    :return:              The property fetched from the configuration or default.
    :rtype:               str or list of str
    '''
    if not property_name:
        log.debug("No property specified in function, trying to load from salt configuration")
        try:
            options = __salt__['config.option']('cassandra')
        except BaseException as e:
            log.error("Failed to get cassandra config options. Reason: {0}".format(str(e)))
            raise

        loaded_property = options.get(config_option)
        if not loaded_property:
            if set_default:
                log.debug('Setting default Cassandra {0} to {1}'.format(config_option, default))
                loaded_property = default
            else:
                log.error('No cassandra {0} specified in the configuration or passed to the module.'.format(config_option))
                raise CommandExecutionError("ERROR: Cassandra {0} cannot be empty.".format(config_option))
        return loaded_property
    return property_name


def _connect(contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
    Connect to a Cassandra cluster.

    :param contact_points: The Cassandra cluster addresses, can either be a string or a list of IPs.
    :type  contact_points: str or list of str
    :param cql_user:       The Cassandra user if authentication is turned on.
    :type  cql_user:       str
    :param cql_pass:       The Cassandra user password if authentication is turned on.
    :type  cql_pass:       str
    :param port:           The Cassandra cluster port, defaults to None.
    :type  port:           int
    :return:               The session and cluster objects.
    :rtype:                cluster object, session object
    '''
    # Lazy load the Cassandra cluster and session for this module by creating a
    # cluster and session when cql_query is called the first time. Get the
    # Cassandra cluster and session from this module's __context__ after it is
    # loaded the first time cql_query is called.
    #
    # TODO: Call cluster.shutdown() when the module is unloaded on
    # master/minion shutdown. Currently, Master.shutdown() and Minion.shutdown()
    # do nothing to allow loaded modules to gracefully handle resources stored
    # in __context__ (i.e. connection pools). This means that the the connection
    # pool is orphaned and Salt relies on Cassandra to reclaim connections.
    # Perhaps if Master/Minion daemons could be enhanced to call an "__unload__"
    # function, or something similar for each loaded module, connection pools
    # and the like can be gracefully reclaimed/shutdown.
    if (__context__
        and 'cassandra_cql_returner_cluster' in __context__
        and 'cassandra_cql_returner_session' in __context__):
        return __context__['cassandra_cql_returner_cluster'], __context__['cassandra_cql_returner_session']
    else:
        contact_points = _load_properties(property_name=contact_points, config_option='cluster')
        contact_points = contact_points if isinstance(contact_points, list) else contact_points.split(',')
        port = _load_properties(property_name=port, config_option='port', set_default=True, default=9042)
        cql_user = _load_properties(property_name=cql_user, config_option='username', set_default=True, default="cassandra")
        cql_pass = _load_properties(property_name=cql_pass, config_option='password', set_default=True, default="cassandra")

        try:
            auth_provider = PlainTextAuthProvider(username=cql_user, password=cql_pass)
            cluster = Cluster(contact_points, port=port, auth_provider=auth_provider)
            session = cluster.connect()
            # TODO: Call cluster.shutdown() when the module is unloaded on shutdown.
            __context__['cassandra_cql_returner_cluster'] = cluster
            __context__['cassandra_cql_returner_session'] = session
            log.debug('Successfully connected to Cassandra cluster at {0}'.format(contact_points))
            return cluster, session
        except TypeError:
            pass
        except (ConnectionException, ConnectionShutdown, NoHostAvailable):
            log.error('Could not connect to Cassandra cluster at {0}'.format(contact_points))
            raise CommandExecutionError('ERROR: Could not connect to Cassandra cluster.')


def cql_query(query, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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
    '''
    try:
        cluster, session = _connect(contact_points=contact_points, port=port, cql_user=cql_user, cql_pass=cql_pass)
    except CommandExecutionError:
        log.critical('Could not get Cassandra cluster session.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while getting Cassandra cluster session: {0}'.format(str(e)))
        raise

    session.row_factory = dict_factory
    ret = []

    try:
        results = session.execute(query)
    except BaseException as e:
        log.error('Failed to execute query: {0}\n reason: {1}'.format(query, str(e)))
        msg = "ERROR: Cassandra query failed: {0} reason: {1}".format(query, str(e))
        raise CommandExecutionError(msg)

    if results:
        for result in results:
            values = {}
            for key, value in six.iteritems(result):
                # Salt won't return dictionaries with odd types like uuid.UUID
                if not isinstance(value, six.text_type):
                    # Must support Cassandra collection types.
                    # Namely, Cassandras set, list, and map collections.
                    if not isinstance(value, (set, list, dict)):
                        value = str(value)
                values[key] = value
            ret.append(values)

    return ret


def version(contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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
    '''
    query = '''select release_version
                 from system.local
                limit 1;'''

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not get Cassandra version.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while getting Cassandra version: {0}'.format(str(e)))
        raise

    return ret[0].get('release_version')


def info(contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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
    '''

    query = '''select cluster_name,
                      data_center,
                      partitioner,
                      host_id,
                      rack,
                      release_version,
                      cql_version,
                      schema_version,
                      thrift_version
                 from system.local
                limit 1;'''

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not list Cassandra info.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while listing Cassandra info: {0}'.format(str(e)))
        raise

    return ret


def list_keyspaces(contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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
    '''
    query = '''select keyspace_name
                 from system.schema_keyspaces;'''

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not list keyspaces.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while listing keyspaces: {0}'.format(str(e)))
        raise

    return ret


def list_column_families(keyspace=None, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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
    '''
    where_clause = "where keyspace_name = '{0}'".format(keyspace) if keyspace else ""

    query = '''select columnfamily_name
                 from system.schema_columnfamilies
                {0};'''.format(where_clause)

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not list column families.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while listing column families: {0}'.format(str(e)))
        raise

    return ret


def keyspace_exists(keyspace, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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

        salt 'minion1' cassandra_cql.list_keyspaces keyspace=system contact_points=minion1
    '''
    # Only project the keyspace_name to make the query efficien.
    # Like an echo
    query = '''select keyspace_name
                 from system.schema_keyspaces
                where keyspace_name = '{0}';'''.format(keyspace)

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not determine if keyspace exists.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while determining if keyspace exists: {0}'.format(str(e)))
        raise

    return True if ret else False


def create_keyspace(keyspace, replication_strategy='SimpleStrategy', replication_factor=1, replication_datacenters=None,
                    contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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

    .. code-block:: bash

        salt 'minion1' cassandra_cql.create_keyspace keyspace=newkeyspace

        salt 'minion1' cassandra_cql.create_keyspace keyspace=newkeyspace replication_strategy=NetworkTopologyStrategy \
        replication_datacenters='{"datacenter_1": 3, "datacenter_2": 2}'
    '''
    existing_keyspace = keyspace_exists(keyspace, contact_points, port)
    if not existing_keyspace:
        # Add the strategy, replication_factor, etc.
        replication_map = {
            'class': replication_strategy
        }

        if replication_datacenters:
            if isinstance(replication_datacenters, six.string_types):
                try:
                    replication_datacenter_map = json.loads(replication_datacenters)
                    replication_map.update(**replication_datacenter_map)
                except BaseException:  # pylint: disable=W0703
                    log.error("Could not load json replication_datacenters.")
                    return False
            else:
                replication_map.update(**replication_datacenters)
        else:
            replication_map['replication_factor'] = replication_factor

        query = '''create keyspace {0}
                     with replication = {1}
                      and durable_writes = true;'''.format(keyspace, replication_map)

        try:
            cql_query(query, contact_points, port, cql_user, cql_pass)
        except CommandExecutionError:
            log.critical('Could not create keyspace.')
            raise
        except BaseException as e:
            log.critical('Unexpected error while creating keyspace: {0}'.format(str(e)))
            raise


def drop_keyspace(keyspace, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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
    '''
    existing_keyspace = keyspace_exists(keyspace, contact_points, port)
    if existing_keyspace:
        query = '''drop keyspace {0};'''.format(keyspace)
        try:
            cql_query(query, contact_points, port, cql_user, cql_pass)
        except CommandExecutionError:
            log.critical('Could not drop keyspace.')
            raise
        except BaseException as e:
            log.critical('Unexpected error while dropping keyspace: {0}'.format(str(e)))
            raise

    return True


def list_users(contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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

    .. code-block:: bash

        salt 'minion1' cassandra_cql.list_users

        salt 'minion1' cassandra_cql.list_users contact_points=minion1
    '''
    query = "list users;"

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not list users.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while listing users: {0}'.format(str(e)))
        raise

    return ret


def create_user(username, password, superuser=False, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
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

    .. code-block:: bash

        salt 'minion1' cassandra_cql.create_user username=joe password=secret

        salt 'minion1' cassandra_cql.create_user username=joe password=secret superuser=True

        salt 'minion1' cassandra_cql.create_user username=joe password=secret superuser=True contact_points=minion1
    '''
    superuser_cql = 'superuser' if superuser else 'nosuperuser'
    query = '''create user if not exists {0} with password '{1}' {2};'''.format(username, password, superuser_cql)
    log.debug("Attempting to create a new user with username={0} superuser={1}".format(username, superuser_cql))

    # The create user query doesn't actually return anything if the query succeeds.
    # If the query fails, catch the exception, log a messange and raise it again.
    try:
        cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not create user.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while creating user: {0}'.format(str(e)))
        raise

    return True


def list_permissions(username=None, resource=None, resource_type='keyspace', permission=None, contact_points=None,
                     port=None, cql_user=None, cql_pass=None):
    '''
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

    .. code-block:: bash

        salt 'minion1' cassandra_cql.list_permissions

        salt 'minion1' cassandra_cql.list_permissions username=joe resource=test_keyspace permission=select

        salt 'minion1' cassandra_cql.list_permissions username=joe resource=test_table resource_type=table \
        permission=select contact_points=minion1
    '''
    keyspace_cql = "{0} {1}".format(resource_type, resource) if resource else "all keyspaces"
    permission_cql = "{0} permission".format(permission) if permission else "all permissions"
    query = "list {0} on {1}".format(permission_cql, keyspace_cql)

    if username:
        query = "{0} of {1}".format(query, username)

    log.debug("Attempting to list permissions with query '{0}'".format(query))

    ret = {}

    try:
        ret = cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not list permissions.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while listing permissions: {0}'.format(str(e)))
        raise

    return ret


def grant_permission(username, resource=None, resource_type='keyspace', permission=None, contact_points=None, port=None,
                     cql_user=None, cql_pass=None):
    '''
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

    .. code-block:: bash

        salt 'minion1' cassandra_cql.grant_permission

        salt 'minion1' cassandra_cql.grant_permission username=joe resource=test_keyspace permission=select

        salt 'minion1' cassandra_cql.grant_permission username=joe resource=test_table resource_type=table \
        permission=select contact_points=minion1
    '''
    permission_cql = "grant {0}".format(permission) if permission else "grant all permissions"
    resource_cql = "on {0} {1}".format(resource_type, resource) if resource else "on all keyspaces"
    query = "{0} {1} to {2}".format(permission_cql, resource_cql, username)
    log.debug("Attempting to grant permissions with query '{0}'".format(query))

    try:
        cql_query(query, contact_points, port, cql_user, cql_pass)
    except CommandExecutionError:
        log.critical('Could not grant permissions.')
        raise
    except BaseException as e:
        log.critical('Unexpected error while granting permissions: {0}'.format(str(e)))
        raise

    return True
