# -*- coding: utf-8 -*-
'''
Module for managing JBoss AS 7 through the CLI interface.

.. versionadded:: 2015.5.0

In order to run each function, jboss_config dictionary with the following properties must be passed:
 * cli_path: the path to jboss-cli script, for example: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
 * controller: the IP address and port of controller, for example: 10.11.12.13:9999
 * cli_user: username to connect to jboss administration console if necessary
 * cli_password: password to connect to jboss administration console if necessary

Example:

.. code-block:: yaml

   jboss_config:
      cli_path: '/opt/jboss/jboss-7.0/bin/jboss-cli.sh'
      controller: 10.11.12.13:9999
      cli_user: 'jbossadm'
      cli_password: 'jbossadm'

'''

# Import python libs
from __future__ import absolute_import
import re
import logging

# Import Salt libs
from salt.utils import dictdiffer

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)

__func_alias__ = {
    'reload_': 'reload'
}


def status(jboss_config):
    '''
    Get status of running jboss instance.

    jboss_config
        Configuration dictionary with properties specified above.

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.status '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}'

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.status")
    operation = ':read-attribute(name=server-state)'
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False, retries=0)


def stop_server(jboss_config):
    '''
    Stop running jboss instance

    jboss_config
        Configuration dictionary with properties specified above.

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.stop_server '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}'

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.stop_server")
    operation = ':shutdown'
    shutdown_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)
    # JBoss seems to occasionaly close the channel immediately when :shutdown is sent
    if shutdown_result['success'] or (not shutdown_result['success'] and 'Operation failed: Channel closed' in shutdown_result['stdout']):
        return shutdown_result
    else:
        raise Exception('''Cannot handle error, return code={retcode}, stdout='{stdout}', stderr='{stderr}' '''.format(**shutdown_result))


def reload_(jboss_config):
    '''
    Reload running jboss instance

    jboss_config
        Configuration dictionary with properties specified above.

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.reload '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}'

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.reload")
    operation = ':reload'
    reload_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)
    # JBoss seems to occasionaly close the channel immediately when :reload is sent
    if reload_result['success'] or (not reload_result['success'] and
                                         ('Operation failed: Channel closed' in reload_result['stdout'] or
                                          'Communication error: java.util.concurrent.ExecutionException: Operation failed' in reload_result['stdout'])):
        return reload_result
    else:
        raise Exception('''Cannot handle error, return code={retcode}, stdout='{stdout}', stderr='{stderr}' '''.format(**reload_result))


def create_datasource(jboss_config, name, datasource_properties):
    '''
    Create datasource in running jboss instance

    jboss_config
        Configuration dictionary with properties specified above.
    name
        Datasource name
    datasource_properties
        A dictionary of datasource properties to be created:
          - driver-name: mysql
          - connection-url: 'jdbc:mysql://localhost:3306/sampleDatabase'
          - jndi-name: 'java:jboss/datasources/sampleDS'
          - user-name: sampleuser
          - password: secret
          - min-pool-size: 3
          - use-java-context: True

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.create_datasource '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' 'my_datasource' '{"driver-name": "mysql", "connection-url": "jdbc:mysql://localhost:3306/sampleDatabase", "jndi-name": "java:jboss/datasources/sampleDS", "user-name": "sampleuser", "password": "secret", "min-pool-size": 3, "use-java-context": True}'
    '''
    log.debug("======================== MODULE FUNCTION: jboss7.create_datasource, name=%s", name)
    ds_resource_description = __get_datasource_resource_description(jboss_config, name)

    operation = '/subsystem=datasources/data-source="{name}":add({properties})'.format(
                name=name,
                properties=__get_properties_assignment_string(datasource_properties, ds_resource_description)
    )

    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)


def __get_properties_assignment_string(datasource_properties, ds_resource_description):
    assignment_strings = []
    ds_attributes = ds_resource_description['attributes']
    for key, val in six.iteritems(datasource_properties):
        assignment_strings.append(__get_single_assignment_string(key, val, ds_attributes))

    return ','.join(assignment_strings)


def __get_single_assignment_string(key, val, ds_attributes):
    return '{0}={1}'.format(key, __format_value(key, val, ds_attributes))


def __format_value(key, value, ds_attributes):
    type_ = ds_attributes[key]['type']
    if type_ == 'BOOLEAN':
        if value in ('true', 'false'):
            return value
        elif isinstance(value, bool):
            if value:
                return 'true'
            else:
                return 'false'
        else:
            raise Exception("Don't know how to convert {0} to BOOLEAN type".format(value))

    elif type_ == 'INT':
        return str(value)
    elif type_ == 'STRING':
        return '"{0}"'.format(value)
    else:
        raise Exception("Don't know how to format value {0} of type {1}".format(value, type_))


def update_datasource(jboss_config, name, new_properties):
    '''
    Update an existing datasource in running jboss instance.
    If the property doesn't exist if will be created, if it does, it will be updated with the new value

    jboss_config
        Configuration dictionary with properties specified above.
    name
        Datasource name
    new_properties
        A dictionary of datasource properties to be updated. For example:
          - driver-name: mysql
          - connection-url: 'jdbc:mysql://localhost:3306/sampleDatabase'
          - jndi-name: 'java:jboss/datasources/sampleDS'
          - user-name: sampleuser
          - password: secret
          - min-pool-size: 3
          - use-java-context: True

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.update_datasource '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' 'my_datasource' '{"driver-name": "mysql", "connection-url": "jdbc:mysql://localhost:3306/sampleDatabase", "jndi-name": "java:jboss/datasources/sampleDS", "user-name": "sampleuser", "password": "secret", "min-pool-size": 3, "use-java-context": True}'

    '''
    log.debug("======================== MODULE FUNCTION: jboss7.update_datasource, name=%s", name)
    ds_result = __read_datasource(jboss_config, name)
    current_properties = ds_result['result']
    diff = dictdiffer.DictDiffer(new_properties, current_properties)
    changed_properties = diff.changed()

    ret = {
        'success': True,
        'comment': ''
    }
    if len(changed_properties) > 0:
        ds_resource_description = __get_datasource_resource_description(jboss_config, name)
        ds_attributes = ds_resource_description['attributes']
        for key in changed_properties:
            update_result = __update_datasource_property(jboss_config, name, key, new_properties[key], ds_attributes)
            if not update_result['success']:
                ret['result'] = False
                ret['comment'] = ret['comment'] + ('Could not update datasource property {0} with value {1},\n stdout: {2}\n'.format(key, new_properties[key], update_result['stdout']))

    return ret


def __get_datasource_resource_description(jboss_config, name):
    log.debug("======================== MODULE FUNCTION: jboss7.__get_datasource_resource_description, name=%s", name)
    operation = '/subsystem=datasources/data-source="{name}":read-resource-description'.format(name=name)
    operation_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation)
    if operation_result['outcome']:
        return operation_result['result']


def read_datasource(jboss_config, name):
    '''
    Read datasource properties in the running jboss instance.

    jboss_config
        Configuration dictionary with properties specified above.
    name
        Datasource name

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.read_datasource '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}'
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.read_datasource, name=%s", name)
    return __read_datasource(jboss_config, name)


def create_simple_binding(jboss_config, binding_name, value):
    '''
    Create a simple jndi binding in the running jboss instance

    jboss_config
        Configuration dictionary with properties specified above.
    binding_name
        Binding name to be created
    value
        Binding value

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.create_simple_binding \\
                '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", \\
                "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' \\
                my_binding_name my_binding_value
    '''
    log.debug("======================== MODULE FUNCTION: jboss7.create_simple_binding, binding_name=%s, value=%s", binding_name, value)
    operation = '/subsystem=naming/binding="{binding_name}":add(binding-type=simple, value="{value}")'.format(
          binding_name=binding_name,
          value=__escape_binding_value(value)
    )
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation)


def update_simple_binding(jboss_config, binding_name, value):
    '''
    Update the simple jndi binding in the running jboss instance

    jboss_config
        Configuration dictionary with properties specified above.
    binding_name
        Binding name to be updated
    value
        New binding value

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.update_simple_binding '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' my_binding_name my_binding_value
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.update_simple_binding, binding_name=%s, value=%s", binding_name, value)
    operation = '/subsystem=naming/binding="{binding_name}":write-attribute(name=value, value="{value}")'.format(
        binding_name=binding_name,
        value=__escape_binding_value(value)
    )
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation)


def read_simple_binding(jboss_config, binding_name):
    '''
    Read jndi binding in the running jboss instance

    jboss_config
        Configuration dictionary with properties specified above.
    binding_name
        Binding name to be created

    CLI Example:

        .. code-block:: bash

        salt '*' jboss7.read_simple_binding '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' my_binding_name
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.read_simple_binding, %s", binding_name)
    return __read_simple_binding(jboss_config, binding_name)


def __read_simple_binding(jboss_config, binding_name):
    operation = '/subsystem=naming/binding="{binding_name}":read-resource'.format(binding_name=binding_name)
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation)


def __update_datasource_property(jboss_config, datasource_name, name, value, ds_attributes):
    log.debug("======================== MODULE FUNCTION: jboss7.__update_datasource_property, datasource_name=%s, name=%s, value=%s", datasource_name, name, value)
    operation = '/subsystem=datasources/data-source="{datasource_name}":write-attribute(name="{name}",value={value})'.format(
                  datasource_name=datasource_name,
                  name=name,
                  value=__format_value(name, value, ds_attributes)
            )
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)


def __read_datasource(jboss_config, name):
    operation = '/subsystem=datasources/data-source="{name}":read-resource'.format(name=name)
    operation_result = __salt__['jboss7_cli.run_operation'](jboss_config, operation)

    return operation_result


def __escape_binding_value(binding_name):
    result = binding_name.replace('\\', '\\\\\\\\')  # replace \ -> \\\\

    return result


def remove_datasource(jboss_config, name):
    '''
    Remove an existing datasource from the running jboss instance.

    jboss_config
        Configuration dictionary with properties specified above.
    name
        Datasource name

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.remove_datasource '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' my_datasource_name
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.remove_datasource, name=%s", name)
    operation = '/subsystem=datasources/data-source={name}:remove'.format(name=name)
    return __salt__['jboss7_cli.run_operation'](jboss_config, operation, fail_on_error=False)


def deploy(jboss_config, source_file):
    '''
    Deploy the application on the jboss instance from the local file system where minion is running.

    jboss_config
        Configuration dictionary with properties specified above.
    source_file
        Source file to deploy from

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.deploy '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' /opt/deploy_files/my_deploy
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.deploy, source_file=%s", source_file)
    command = 'deploy {source_file} --force '.format(source_file=source_file)
    return __salt__['jboss7_cli.run_command'](jboss_config, command, fail_on_error=False)


def list_deployments(jboss_config):
    '''
    List all deployments on the jboss instance

    jboss_config
        Configuration dictionary with properties specified above.

     CLI Example:

     .. code-block:: bash

         salt '*' jboss7.list_deployments '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}'

       '''
    log.debug("======================== MODULE FUNCTION: jboss7.list_deployments")
    command_result = __salt__['jboss7_cli.run_command'](jboss_config, 'deploy')
    deployments = []
    if len(command_result['stdout']) > 0:
        deployments = re.split('\\s*', command_result['stdout'])
    log.debug('deployments=%s', str(deployments))
    return deployments


def undeploy(jboss_config, deployment):
    '''
    Undeploy the application from jboss instance

    jboss_config
        Configuration dictionary with properties specified above.
    deployment
        Deployment name to undeploy

    CLI Example:

    .. code-block:: bash

        salt '*' jboss7.undeploy '{"cli_path": "integration.modules.sysmod.SysModuleTest.test_valid_docs", "controller": "10.11.12.13:9999", "cli_user": "jbossadm", "cli_password": "jbossadm"}' my_deployment
       '''
    log.debug("======================== MODULE FUNCTION: jboss7.undeploy, deployment=%s", deployment)
    command = 'undeploy {deployment} '.format(deployment=deployment)
    return __salt__['jboss7_cli.run_command'](jboss_config, command)
