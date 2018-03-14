# -*- coding: utf-8 -*-
'''
Manage Glassfish/Payara server
.. versionadded:: Carbon

Management of glassfish using it's RESTful API
You can setup connection parameters like this

.. code-block:: yaml
    - server:
      - ssl: true
      - url: localhost
      - port: 4848
      - user: admin
      - password: changeit
'''
from __future__ import absolute_import, print_function, unicode_literals

try:
    import salt.utils.json
    from salt.ext import six
    from salt.exceptions import CommandExecutionError
    import requests
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


def __virtual__():
    '''
    Only load if glassfish module is available
    '''
    return 'glassfish.enum_connector_c_pool' in __salt__ and HAS_LIBS


def _json_to_unicode(data):
    '''
    Encode json values in unicode to match that of the API
    '''
    ret = {}
    for key, value in data.items():
        if not isinstance(value, six.text_type):
            if isinstance(value, dict):
                ret[key] = _json_to_unicode(value)
            else:
                ret[key] = six.text_type(value).lower()
        else:
            ret[key] = value
    return ret


def _is_updated(old_conf, new_conf):
    '''
    Compare the API results to the current statefile data
    '''
    changed = {}

    # Dirty json hacking to get parameters in the same format
    new_conf = _json_to_unicode(salt.utils.json.loads(
        salt.utils.json.dumps(new_conf, ensure_ascii=False)))
    old_conf = salt.utils.json.loads(salt.utils.json.dumps(old_conf, ensure_ascii=False))

    for key, value in old_conf.items():
        oldval = six.text_type(value).lower()
        if key in new_conf:
            newval = six.text_type(new_conf[key]).lower()
        if oldval == 'null' or oldval == 'none':
            oldval = ''
        if key in new_conf and newval != oldval:
            changed[key] = {'old': oldval, 'new': newval}
    return changed


def _do_element_present(name, elem_type, data, server=None):
    '''
    Generic function to create or update an element
    '''
    ret = {'changes': {}, 'update': False, 'create': False, 'error': None}
    try:
        elements = __salt__['glassfish.enum_{0}'.format(elem_type)]()
    except requests.ConnectionError as error:
        if __opts__['test']:
            ret['changes'] = {'Name': name, 'Params': data}
            ret['create'] = True
            return ret
        else:
            ret['error'] = "Can't connect to the server"
            return ret

    if not elements or name not in elements:
        ret['changes'] = {'Name': name, 'Params': data}
        ret['create'] = True
        if not __opts__['test']:
            try:
                __salt__['glassfish.create_{0}'.format(elem_type)](name, server=server, **data)
            except CommandExecutionError as error:
                ret['error'] = error
                return ret
    elif elements and any(data):
        current_data = __salt__['glassfish.get_{0}'.format(elem_type)](name, server=server)
        data_diff = _is_updated(current_data, data)
        if data_diff:
            ret['update'] = True
            ret['changes'] = data_diff
            if not __opts__['test']:
                try:
                    __salt__['glassfish.update_{0}'.format(elem_type)](name, server=server, **data)
                except CommandExecutionError as error:
                    ret['error'] = error
    return ret


def _do_element_absent(name, elem_type, data, server=None):
    '''
    Generic function to delete an element
    '''
    ret = {'delete': False, 'error': None}
    try:
        elements = __salt__['glassfish.enum_{0}'.format(elem_type)]()
    except requests.ConnectionError as error:
        if __opts__['test']:
            ret['create'] = True
            return ret
        else:
            ret['error'] = "Can't connect to the server"
            return ret

    if elements and name in elements:
        ret['delete'] = True
        if not __opts__['test']:
            try:
                __salt__['glassfish.delete_{0}'.format(elem_type)](name, server=server, **data)
            except CommandExecutionError as error:
                ret['error'] = error
    return ret


def connection_factory_present(name,
                               restype='connection_factory',
                               description='',
                               enabled=True,
                               min_size=1,
                               max_size=250,
                               resize_quantity=2,
                               idle_timeout=300,
                               wait_timeout=60,
                               reconnect_on_failure=False,
                               transaction_support='',
                               connection_validation=False,
                               server=None):
    '''
    Ensures that the Connection Factory is present

    name
        Name of the connection factory

    restype
        Type of the connection factory, can be either ``connection_factory``,
        ``queue_connection_factory` or ``topic_connection_factory``,
        defaults to ``connection_factory``

    description
        Description of the connection factory

    enabled
        Is the connection factory enabled? defaults to ``true``

    min_size
        Minimum and initial number of connections in the pool, defaults to ``1``

    max_size
        Maximum number of connections that can be created in the pool, defaults to ``250``

    resize_quantity
        Number of connections to be removed when idle_timeout expires, defaults to ``2``

    idle_timeout
        Maximum time a connection can remain idle in the pool, in seconds, defaults to ``300``

    wait_timeout
        Maximum time a caller can wait before timeout, in seconds, defaults to ``60``

    reconnect_on_failure
        Close all connections and reconnect on failure (or reconnect only when used), defaults to ``false``
    transaction_support
        Level of transaction support, can be either ``XATransaction``, ``LocalTransaction`` or ``NoTransaction``

    connection_validation
        Connection validation is required, defaults to ``false``
    '''
    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}

    # Manage parameters
    pool_data = {}
    res_data = {}
    pool_name = '{0}-Connection-Pool'.format(name)
    if restype == 'topic_connection_factory':
        pool_data['connectionDefinitionName'] = 'javax.jms.TopicConnectionFactory'
    elif restype == 'queue_connection_factory':
        pool_data['connectionDefinitionName'] = 'javax.jms.QueueConnectionFactory'
    elif restype == 'connection_factory':
        pool_data['connectionDefinitionName'] = 'javax.jms.ConnectionFactory'
    else:
        ret['result'] = False
        ret['comment'] = 'Invalid restype'
        return ret
    pool_data['description'] = description
    res_data['description'] = description
    res_data['enabled'] = enabled
    res_data['poolName'] = pool_name
    pool_data['steadyPoolSize'] = min_size
    pool_data['maxPoolSize'] = max_size
    pool_data['poolResizeQuantity'] = resize_quantity
    pool_data['idleTimeoutInSeconds'] = idle_timeout
    pool_data['maxWaitTimeInMillis'] = wait_timeout*1000
    pool_data['failAllConnections'] = reconnect_on_failure
    if transaction_support:
        if transaction_support == 'xa_transaction':
            pool_data['transactionSupport'] = 'XATransaction'
        elif transaction_support == 'local_transaction':
            pool_data['transactionSupport'] = 'LocalTransaction'
        elif transaction_support == 'no_transaction':
            pool_data['transactionSupport'] = 'NoTransaction'
        else:
            ret['result'] = False
            ret['comment'] = 'Invalid transaction_support'
            return ret
    pool_data['isConnectionValidationRequired'] = connection_validation

    pool_ret = _do_element_present(pool_name, 'connector_c_pool', pool_data, server)
    res_ret = _do_element_present(name, 'connector_resource', res_data, server)

    if not pool_ret['error'] and not res_ret['error']:
        if not __opts__['test']:
            ret['result'] = True

        if pool_ret['create'] or res_ret['create']:
            ret['changes']['pool'] = pool_ret['changes']
            ret['changes']['resource'] = res_ret['changes']
            if __opts__['test']:
                ret['comment'] = 'Connection factory set to be created'
            else:
                ret['comment'] = 'Connection factory created'
        elif pool_ret['update'] or res_ret['update']:
            ret['changes']['pool'] = pool_ret['changes']
            ret['changes']['resource'] = res_ret['changes']
            if __opts__['test']:
                ret['comment'] = 'Connection factory set to be updated'
            else:
                ret['comment'] = 'Connection factory updated'
        else:
            ret['result'] = True
            ret['changes'] = None
            ret['comment'] = 'Connection factory is already up-to-date'
    else:
        ret['result'] = False
        ret['comment'] = 'ERROR: {0} // {1}'.format(pool_ret['error'], res_ret['error'])

    return ret


def connection_factory_absent(name, both=True, server=None):
    '''
    Ensures the transaction factory is absent.

    name
        Name of the connection factory

    both
        Delete both the pool and the resource, defaults to ``true``
    '''
    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    pool_name = '{0}-Connection-Pool'.format(name)
    pool_ret = _do_element_absent(pool_name, 'connector_c_pool', {'cascade': both}, server)

    if not pool_ret['error']:
        if __opts__['test'] and pool_ret['delete']:
            ret['comment'] = 'Connection Factory set to be deleted'
        elif pool_ret['delete']:
            ret['result'] = True
            ret['comment'] = 'Connection Factory deleted'
        else:
            ret['result'] = True
            ret['comment'] = 'Connection Factory doesn\'t exist'
    else:
        ret['result'] = False
        ret['comment'] = 'Error: {0}'.format(pool_ret['error'])
    return ret


def destination_present(name,
                        physical,
                        restype='queue',
                        description='',
                        enabled=True,
                        server=None):
    '''
    Ensures that the JMS Destination Resource (queue or topic) is present

    name
        The JMS Queue/Topic name

    physical
        The Physical destination name

    restype
        The JMS Destination resource type, either ``queue`` or ``topic``, defaults is ``queue``

    description
        A description of the resource

    enabled
        Defaults to ``True``
    '''
    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}

    params = {}
    # Set parameters dict
    if restype == 'queue':
        params['resType'] = 'javax.jms.Queue'
        params['className'] = 'com.sun.messaging.Queue'
    elif restype == 'topic':
        params['resType'] = 'javax.jms.Topic'
        params['className'] = 'com.sun.messaging.Topic'
    else:
        ret['result'] = False
        ret['comment'] = 'Invalid restype'
        return ret
    params['properties'] = {'Name': physical}
    params['description'] = description
    params['enabled'] = enabled

    jms_ret = _do_element_present(name, 'admin_object_resource', params, server)
    if not jms_ret['error']:
        if not __opts__['test']:
            ret['result'] = True
        if jms_ret['create'] and __opts__['test']:
            ret['comment'] = 'JMS Queue set to be created'
        elif jms_ret['create']:
            ret['changes'] = jms_ret['changes']
            ret['comment'] = 'JMS queue created'
        elif jms_ret['update'] and __opts__['test']:
            ret['comment'] = 'JMS Queue set to be updated'
        elif jms_ret['update']:
            ret['changes'] = jms_ret['changes']
            ret['comment'] = 'JMS Queue updated'
        else:
            ret['result'] = True
            ret['comment'] = 'JMS Queue already up-to-date'
    else:
        ret['result'] = False
        ret['comment'] = 'Error from API: {0}'.format(jms_ret['error'])
    return ret


def destination_absent(name, server=None):
    '''
    Ensures that the JMS Destination doesn't exists

    name
        Name of the JMS Destination
    '''
    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    jms_ret = _do_element_absent(name, 'admin_object_resource', {}, server)
    if not jms_ret['error']:
        if __opts__['test'] and jms_ret['delete']:
            ret['comment'] = 'JMS Queue set to be deleted'
        elif jms_ret['delete']:
            ret['result'] = True
            ret['comment'] = 'JMS Queue deleted'
        else:
            ret['result'] = True
            ret['comment'] = 'JMS Queue doesn\'t exist'
    else:
        ret['result'] = False
        ret['comment'] = 'Error: {0}'.format(jms_ret['error'])
    return ret


def jdbc_datasource_present(name,
                            description='',
                            enabled=True,
                            restype='datasource',
                            vendor='mysql',
                            sql_url='',
                            sql_user='',
                            sql_password='',
                            min_size=8,
                            max_size=32,
                            resize_quantity=2,
                            idle_timeout=300,
                            wait_timeout=60,
                            non_transactional=False,
                            transaction_isolation='',
                            isolation_guaranteed=True,
                            server=None):
    '''
    Ensures that the JDBC Datasource exists

    name
        Name of the datasource

    description
        Description of the datasource

    enabled
        Is the datasource enabled? defaults to ``true``

    restype
        Resource type, can be ``datasource``, ``xa_datasource``,
        ``connection_pool_datasource`` or ``driver``, defaults to ``datasource``

    vendor
        SQL Server type, currently supports ``mysql``,
        ``postgresql`` and ``mssql``, defaults to ``mysql``

    sql_url
        URL of the server in jdbc form

    sql_user
        Username for the server

    sql_password
        Password for that username

    min_size
        Minimum and initial number of connections in the pool, defaults to ``8``

    max_size
        Maximum number of connections that can be created in the pool, defaults to ``32``

    resize_quantity
        Number of connections to be removed when idle_timeout expires, defaults to ``2``

    idle_timeout
        Maximum time a connection can remain idle in the pool, in seconds, defaults to ``300``

    wait_timeout
        Maximum time a caller can wait before timeout, in seconds, defaults to ``60``

    non_transactional
        Return non-transactional connections

    transaction_isolation
        Defaults to the JDBC driver default

    isolation_guaranteed
        All connections use the same isolation level
    '''
    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}

    # Manage parameters
    res_name = 'jdbc/{0}'.format(name)
    pool_data = {}
    pool_data_properties = {}
    res_data = {}
    if restype == 'datasource':
        pool_data['resType'] = 'javax.sql.DataSource'
    elif restype == 'xa_datasource':
        pool_data['resType'] = 'javax.sql.XADataSource'
    elif restype == 'connection_pool_datasource':
        pool_data['resType'] = 'javax.sql.ConnectionPoolDataSource'
    elif restype == 'driver':
        pool_data['resType'] = 'javax.sql.Driver'

    datasources = {}
    datasources['mysql'] = {
        'driver': 'com.mysql.jdbc.Driver',
        'datasource': 'com.mysql.jdbc.jdbc2.optional.MysqlDataSource',
        'xa_datasource': 'com.mysql.jdbc.jdbc2.optional.MysqlXADataSource',
        'connection_pool_datasource': 'com.mysql.jdbc.jdbc2.optional.MysqlConnectionPoolDataSource'
    }
    datasources['postgresql'] = {
        'driver': 'org.postgresql.Driver',
        'datasource': 'org.postgresql.ds.PGSimpleDataSource',
        'xa_datasource': 'org.postgresql.xa.PGXADataSource',
        'connection_pool_datasource': 'org.postgresql.ds.PGConnectionPoolDataSource'
    }
    datasources['mssql'] = {
        'driver': 'com.microsoft.sqlserver.jdbc.SQLServerDriver',
        'datasource': 'com.microsoft.sqlserver.jdbc.SQLServerDataSource',
        'xa_datasource': 'com.microsoft.sqlserver.jdbc.SQLServerXADataSource',
        'connection_pool_datasource': 'com.microsoft.sqlserver.jdbc.SQLServerConnectionPoolDataSource'
    }

    if restype == 'driver':
        pool_data['driverClassname'] = datasources[vendor]['driver']
    else:
        pool_data['datasourceClassname'] = datasources[vendor][restype]

    pool_data_properties['url'] = sql_url
    pool_data_properties['user'] = sql_user
    pool_data_properties['password'] = sql_password
    pool_data['properties'] = pool_data_properties
    pool_data['description'] = description
    res_data['description'] = description
    res_data['poolName'] = name
    res_data['enabled'] = enabled
    pool_data['steadyPoolSize'] = min_size
    pool_data['maxPoolSize'] = max_size
    pool_data['poolResizeQuantity'] = resize_quantity
    pool_data['idleTimeoutInSeconds'] = idle_timeout
    pool_data['maxWaitTimeInMillis'] = wait_timeout*1000
    pool_data['nonTransactionalConnections'] = non_transactional
    pool_data['transactionIsolationLevel'] = transaction_isolation
    pool_data['isIsolationLevelGuaranteed'] = isolation_guaranteed

    pool_ret = _do_element_present(name, 'jdbc_connection_pool', pool_data, server)
    res_ret = _do_element_present(res_name, 'jdbc_resource', res_data, server)

    if not pool_ret['error'] and not res_ret['error']:
        if not __opts__['test']:
            ret['result'] = True

        if pool_ret['create'] or res_ret['create']:
            ret['changes']['pool'] = pool_ret['changes']
            ret['changes']['resource'] = res_ret['changes']
            if __opts__['test']:
                ret['comment'] = 'JDBC Datasource set to be created'
            else:
                ret['comment'] = 'JDBC Datasource created'
        elif pool_ret['update'] or res_ret['update']:
            ret['changes']['pool'] = pool_ret['changes']
            ret['changes']['resource'] = res_ret['changes']
            if __opts__['test']:
                ret['comment'] = 'JDBC Datasource set to be updated'
            else:
                ret['comment'] = 'JDBC Datasource updated'
        else:
            ret['result'] = True
            ret['changes'] = None
            ret['comment'] = 'JDBC Datasource is already up-to-date'
    else:
        ret['result'] = False
        ret['comment'] = 'ERROR: {0} // {1}'.format(pool_ret['error'], res_ret['error'])

    return ret


def jdbc_datasource_absent(name, both=True, server=None):
    '''
    Ensures the JDBC Datasource doesn't exists

    name
        Name of the datasource
    both
        Delete both the pool and the resource, defaults to ``true``
    '''
    ret = {'name': name, 'result': None, 'comment': None, 'changes': {}}
    pool_ret = _do_element_absent(name, 'jdbc_connection_pool', {'cascade': both}, server)

    if not pool_ret['error']:
        if __opts__['test'] and pool_ret['delete']:
            ret['comment'] = 'JDBC Datasource set to be deleted'
        elif pool_ret['delete']:
            ret['result'] = True
            ret['comment'] = 'JDBC Datasource deleted'
        else:
            ret['result'] = True
            ret['comment'] = 'JDBC Datasource doesn\'t exist'
    else:
        ret['result'] = False
        ret['comment'] = 'Error: {0}'.format(pool_ret['error'])
    return ret


def system_properties_present(server=None, **kwargs):
    '''
    Ensures that the system properties are present

    properties
        The system properties
    '''
    ret = {'name': '', 'result': None, 'comment': None, 'changes': {}}

    del kwargs['name']
    try:
        data = __salt__['glassfish.get_system_properties'](server=server)
    except requests.ConnectionError as error:
        if __opts__['test']:
            ret['changes'] = kwargs
            ret['result'] = None
            return ret
        else:
            ret['error'] = "Can't connect to the server"
            return ret

    ret['changes'] = {'data': data, 'kwargs': kwargs}
    if not data == kwargs:
        data.update(kwargs)
        if not __opts__['test']:
            try:
                __salt__['glassfish.update_system_properties'](data, server=server)
                ret['changes'] = kwargs
                ret['result'] = True
                ret['comment'] = 'System properties updated'
            except CommandExecutionError as error:
                ret['comment'] = error
                ret['result'] = False
        else:
            ret['result'] = None
            ret['changes'] = kwargs
            ret['coment'] = 'System properties would have been updated'
    else:
        ret['changes'] = None
        ret['result'] = True
        ret['comment'] = 'System properties are already up-to-date'
    return ret


def system_properties_absent(name, server=None):
    '''
    Ensures that the system property doesn't exists

    name
        Name of the system property
    '''
    ret = {'name': '', 'result': None, 'comment': None, 'changes': {}}

    try:
        data = __salt__['glassfish.get_system_properties'](server=server)
    except requests.ConnectionError as error:
        if __opts__['test']:
            ret['changes'] = {'Name': name}
            ret['result'] = None
            return ret
        else:
            ret['error'] = "Can't connect to the server"
            return ret

    if name in data:
        if not __opts__['test']:
            try:
                __salt__['glassfish.delete_system_properties'](name, server=server)
                ret['result'] = True
                ret['comment'] = 'System properties deleted'
            except CommandExecutionError as error:
                ret['comment'] = error
                ret['result'] = False
        else:
            ret['result'] = None
            ret['comment'] = 'System properties would have been deleted'
        ret['changes'] = {'Name': name}
    else:
        ret['result'] = True
        ret['comment'] = 'System properties are already absent'
    return ret
