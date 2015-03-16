# -*- coding: utf-8 -*-
'''
Cassandra Database Module

:depends: DataStax Python Driver for Apache Cassandra
          https://github.com/datastax/python-driver
          pip install cassandra-driver
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
import logging
import json
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = 'cassandra'

HAS_DRIVER = False
try:
    from cassandra.cluster import Cluster
    from cassandra.cluster import NoHostAvailable
    from cassandra.connection import ConnectionException, ConnectionShutdown
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.query import dict_factory
    HAS_DRIVER = True
except ImportError:
    pass


def __virtual__():
    '''
    Return virtual name of the module only if the python driver can be loaded.

    :return: The virtual name of the module.
    :rtype:  str
    '''
    if not HAS_DRIVER:
        return False

    if HAS_DRIVER:
        return __virtualname__
    return False


def _loadproperties(property_name, config_option, set_default=False, default=None):
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
        options = __salt__['config.option']('cassandra')
        loaded_property = options.get(config_option)
        if not loaded_property:
            if set_default:
                log.debug('Setting default Cassandra %s to %s', config_option, default)
                loaded_property = default
            else:
                log.error('No cassandra %s specified in the configuration or passed to the module.', config_option)
                msg = "ERROR: Cassandra %s cannot be empty." % config_option
                raise CommandExecutionError(msg)
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

    contact_points = _loadproperties(property_name=contact_points, config_option='cluster')
    contact_points = contact_points if isinstance(contact_points, list) else contact_points.split(',')
    port = _loadproperties(property_name=port, config_option='port', set_default=True, default=9042)
    cql_user = _loadproperties(property_name=cql_user, config_option='username', set_default=True, default="cassandra")
    cql_pass = _loadproperties(property_name=cql_pass, config_option='password', set_default=True, default="cassandra")

    try:
        auth_provider = PlainTextAuthProvider(username=cql_user, password=cql_pass)
        cluster = Cluster(contact_points, port=port, auth_provider=auth_provider)
        session = cluster.connect()
        log.debug('Successfully connected to Cassandra cluster at %s', contact_points)
        return cluster, session
    except (ConnectionException, ConnectionShutdown, NoHostAvailable):
        log.error('Could not connect to Cassandra cluster at %s', contact_points)
        raise CommandExecutionError('ERROR: Could not connect to Cassandra cluster.')


def _query(query, contact_points=None, port=None, cql_user=None, cql_pass=None):
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
    cluster, session = _connect(contact_points=contact_points, port=port, cql_user=cql_user, cql_pass=cql_pass)

    session.row_factory = dict_factory
    ret = []

    try:
        results = session.execute(query)
    except BaseException as e:
        log.error('Something went wrong when executing the following query: %s', query)
        msg = "ERROR: Cassandra query failed: %s" % query
        raise CommandExecutionError(msg, e)

    if results:
        for index in range(0, len(results)):
            result = results[index]
            values = {}
            for key, value in result.iteritems():
                # Salt won't return dictionaries with odd types like uuid.UUID
                if not isinstance(value, unicode):
                    value = str(value)
                values[key] = value
            ret.append(values)
    cluster.shutdown()
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

        salt 'minion1' cassandra.version

        salt 'minion1' cassandra.version contact_points=minion1
    '''
    query = 'select release_version from system.local limit 1'
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    if ret:
        return ret[0].get('release_version')
    else:
        return False


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

        salt 'minion1' cassandra.info

        salt 'minion1' cassandra.info contact_points=minion1
    '''

    query = 'select cluster_name, \
             data_center, \
             partitioner, \
             host_id, \
             rack, \
             release_version, \
             cql_version, \
             schema_version, \
             thrift_version from system.local limit 1'
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    if ret:
        return ret[0]


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

        salt 'minion1' cassandra.list_keyspaces

        salt 'minion1' cassandra.list_keyspaces contact_points=minion1 port=9000
    '''
    query = 'select keyspace_name from system.schema_keyspaces'
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    if ret:
        return ret
    else:
        return False


def list_column_families(keyspace=None, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
    List column families in a Cassandra cluster for all keyspaces or just the provided one.

    :param keyspace        The keyspace to provide the column families for, optional.
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

        salt 'minion1' cassandra.list_column_families

        salt 'minion1' cassandra.list_column_families contact_points=minion1

        salt 'minion1' cassandra.list_column_families keyspace=system
    '''
    query = 'select columnfamily_name from system.schema_columnfamilies'
    if keyspace:
        where_clause = 'where keyspace_name = \'%s\'' % keyspace
        query = query + ' ' + where_clause
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    if ret:
        return ret
    else:
        return False


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

        salt 'minion1' cassandra.keyspace_exists keyspace=system

        salt 'minion1' cassandra.list_keyspaces keyspace=system contact_points=minion1
    '''
    query = 'select * from system.schema_keyspaces where keyspace_name = \'%s\'' % keyspace
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    if ret:
        return ret[0]
    else:
        return False


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

        salt 'minion1' cassandra.create_keyspace keyspace=newkeyspace

        salt 'minion1' cassandra.create_keyspace keyspace=newkeyspace replication_strategy=NetworkTopologyStrategy \
        replication_datacenters='{"datacenter_1": 3, "datacenter_2": 2}'
    '''
    existing_keyspace = keyspace_exists(keyspace, contact_points, port)
    if not existing_keyspace:
        # Add the strategy, replication_factor, etc.
        replication_map = {
            'class': replication_strategy
        }
        if replication_datacenters:
            if isinstance(replication_datacenters, basestring):
                try:
                    replication_datacenter_map = json.loads(replication_datacenters)
                    replication_map.update(**replication_datacenter_map)
                except:
                    log.error("Could not load json replication_datacenters.")
                    return False
            else:
                replication_map.update(**replication_datacenters)
        else:
            replication_map['replication_factor'] = replication_factor
        query = "create keyspace %s with replication = %s and durable_writes = true;" % (keyspace, replication_map)
        _query(query, contact_points, cql_user, cql_pass, port)
        return keyspace_exists(keyspace, contact_points, port, cql_user, cql_pass)
    else:
        return existing_keyspace


def drop_keyspace(keyspace, contact_points=None, port=None, cql_user=None, cql_pass=None):
    '''
    Drop a keyspace if it exists in a Cassandra cluster.

    :param keyspace        The keyspace to drop.
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

        salt 'minion1' cassandra.drop_keyspace keyspace=test

        salt 'minion1' cassandra.drop_keyspace keyspace=test contact_points=minion1
    '''
    existing_keyspace = keyspace_exists(keyspace, contact_points, port)
    if existing_keyspace:
        query = 'drop keyspace %s' % keyspace
        ret = _query(query, contact_points, port, cql_user, cql_pass)
        # The drop keyspace query doesn't actually return anything if the query succeeds.
        # So if ret is empty, then the drop worked. Hence returning True for the function.
        return True if not ret else ret
    else:
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

        salt 'minion1' cassandra.list_users

        salt 'minion1' cassandra.list_users contact_points=minion1
    '''
    query = "list users;"
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    return ret if ret else False


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

        salt 'minion1' cassandra.create_user username=joe password=secret

        salt 'minion1' cassandra.create_user username=joe password=secret superuser=True

        salt 'minion1' cassandra.create_user username=joe password=secret superuser=True contact_points=minion1
    '''
    superuser_cql = 'superuser' if superuser else 'nosuperuser'
    query = "create user if not exists %s with password '%s' %s;" % (username, password, superuser_cql)
    log.debug('Attempting to create a new user with username=%s superuser=%s', username, superuser_cql)
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    # The create user query doesn't actually return anything if the query succeeds.
    # So if ret is empty, then the user creation worked. Hence returning True for the function.
    return True if not ret else ret


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
        salt 'minion1' cassandra.list_permissions

        salt 'minion1' cassandra.list_permissions username=joe resource=test_keyspace permission=select

        salt 'minion1' cassandra.list_permissions username=joe resource=test_table resource_type=table \
        permission=select contact_points=minion1
    '''
    cql_template = "list %s on %s"

    keyspace_cql = "%s %s" % (resource_type, resource) if resource else "all keyspaces"
    permission_cql = "%s permission" % permission if permission else "all permissions"

    query = cql_template % (permission_cql, keyspace_cql)
    if username:
        query = "%s of %s" % (query, username)
    log.debug('Attempting to list permissions with query "%s"', query)
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    return ret if ret else False

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
        salt 'minion1' cassandra.grant_permission

        salt 'minion1' cassandra.grant_permission username=joe resource=test_keyspace permission=select

        salt 'minion1' cassandra.grant_permission username=joe resource=test_table resource_type=table \
        permission=select contact_points=minion1
    '''
    permission_cql = "grant %s" % permission if permission else "grant all permissions"
    resource_cql = "on %s %s" % (resource_type, resource) if resource else "on all keyspaces"

    query = "%s %s to %s" % (permission_cql, resource_cql, username)
    log.debug('Attempting to grant permissions with query "%s"', query)
    ret = _query(query, contact_points, port, cql_user, cql_pass)
    return True if not ret else ret
