# -*- coding: utf-8 -*-
'''
Azure Cloud Module
==================

The Azure cloud module is used to control access to Microsoft Azure

:depends:
    * `Microsoft Azure SDK for Python <https://pypi.python.org/pypi/azure/0.9.0>`_
    * python-requests, for Python < 2.7.9
:configuration:
    Required provider parameters:

    * ``apikey``
    * ``certificate_path``
    * ``subscription_id``
    * ``requests_lib``

    A Management Certificate (.pem and .crt files) must be created and the .pem
    file placed on the same machine that salt-cloud is run from. Information on
    creating the pem file to use, and uploading the associated cer file can be
    found at:

    http://www.windowsazure.com/en-us/develop/python/how-to-guides/service-management/

    For users with Python < 2.7.9, requests_lib must currently be set to True.

Example ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/azure.conf`` configuration:

.. code-block:: yaml

    my-azure-config:
      provider: azure
      subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
      certificate_path: /etc/salt/azure.pem
      management_host: management.core.windows.net
'''
# pylint: disable=E0102

# Import python libs
from __future__ import absolute_import
import copy
import logging
import pprint
import time

# Import salt libs
import salt.config as config
from salt.exceptions import SaltCloudSystemExit
import salt.utils.cloud
import salt.ext.six as six

# Import 3rd-party libs
import yaml

# Import azure libs
HAS_LIBS = False
try:
    import azure
    import azure.servicemanagement
    from azure import (WindowsAzureConflictError,
                       WindowsAzureMissingResourceError,
                       WindowsAzureError)
    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = 'azure'


# Get logging started
log = logging.getLogger(__name__)


# Only load in this module if the AZURE configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for Azure configurations.
    '''
    if not HAS_LIBS:
        return False

    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('subscription_id', 'certificate_path')
    )


def get_conn():
    '''
    Return a conn object for the passed VM data
    '''
    certificate_path = config.get_cloud_config_value(
        'certificate_path',
        get_configured_provider(), __opts__, search_global=False
    )
    subscription_id = config.get_cloud_config_value(
        'subscription_id',
        get_configured_provider(), __opts__, search_global=False
    )
    management_host = config.get_cloud_config_value(
        'management_host',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default='management.core.windows.net'
    )
    return azure.servicemanagement.ServiceManagementService(
        subscription_id, certificate_path, management_host
    )


def script(vm_):
    '''
    Return the script deployment object
    '''
    return salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )


def avail_locations(conn=None, call=None):
    '''
    List available locations for Azure
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    if not conn:
        conn = get_conn()

    ret = {}
    locations = conn.list_locations()
    for location in locations:
        ret[location.name] = {
            'name': location.name,
            'display_name': location.display_name,
            'available_services': location.available_services,
        }
    return ret


def avail_images(conn=None, call=None):
    '''
    List available images for Azure
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    if not conn:
        conn = get_conn()

    ret = {}
    for item in conn.list_os_images():
        ret[item.name] = object_to_dict(item)
    for item in conn.list_vm_images():
        ret[item.name] = object_to_dict(item)
    return ret


def avail_sizes(call=None):
    '''
    Return a list of sizes from Azure
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    conn = get_conn()
    data = conn.list_role_sizes()
    ret = {}
    for item in data.role_sizes:
        ret[item.name] = object_to_dict(item)
    return ret


def list_nodes(conn=None, call=None):
    '''
    List VMs on this Azure account
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    nodes = list_nodes_full(conn, call)
    for node in nodes:
        ret[node] = {}
        for prop in ('id', 'image', 'size', 'state', 'private_ips',
                     'public_ips'):
            ret[node][prop] = nodes[node][prop]
    return ret


def list_nodes_full(conn=None, call=None):
    '''
    List VMs on this Azure account, with full information
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    ret = {}
    services = list_hosted_services(conn=conn, call=call)
    for service in services:
        for deployment in services[service]['deployments']:
            deploy_dict = services[service]['deployments'][deployment]
            deploy_dict_no_role_info = copy.deepcopy(deploy_dict)
            del deploy_dict_no_role_info['role_list']
            del deploy_dict_no_role_info['role_instance_list']
            roles = deploy_dict['role_list']
            for role in roles:
                role_instances = deploy_dict['role_instance_list']
                ret[role] = roles[role]
                ret[role].update(role_instances[role])
                ret[role]['id'] = role
                ret[role]['hosted_service'] = service
                if role_instances[role]['power_state'] == 'Started':
                    ret[role]['state'] = 'running'
                elif role_instances[role]['power_state'] == 'Stopped':
                    ret[role]['state'] = 'stopped'
                else:
                    ret[role]['state'] = 'pending'
                ret[role]['private_ips'] = []
                ret[role]['public_ips'] = []
                ret[role]['deployment'] = deploy_dict_no_role_info
                ret[role]['url'] = deploy_dict['url']
                ip_address = role_instances[role]['ip_address']
                if ip_address:
                    if salt.utils.cloud.is_public_ip(ip_address):
                        ret[role]['public_ips'].append(ip_address)
                    else:
                        ret[role]['private_ips'].append(ip_address)
                ret[role]['size'] = role_instances[role]['instance_size']
                ret[role]['image'] = roles[role]['role_info']['os_virtual_hard_disk']['source_image_name']
    return ret


def list_hosted_services(conn=None, call=None):
    '''
    List VMs on this Azure account, with full information
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_hosted_services function must be called with '
            '-f or --function'
        )

    if not conn:
        conn = get_conn()

    ret = {}
    services = conn.list_hosted_services()
    for service in services:
        props = service.hosted_service_properties
        ret[service.service_name] = {
            'name': service.service_name,
            'url': service.url,
            'affinity_group': props.affinity_group,
            'date_created': props.date_created,
            'date_last_modified': props.date_last_modified,
            'description': props.description,
            'extended_properties': props.extended_properties,
            'label': props.label,
            'location': props.location,
            'status': props.status,
            'deployments': {},
        }
        deployments = conn.get_hosted_service_properties(
            service_name=service.service_name, embed_detail=True
        )
        for deployment in deployments.deployments:
            ret[service.service_name]['deployments'][deployment.name] = {
                'configuration': deployment.configuration,
                'created_time': deployment.created_time,
                'deployment_slot': deployment.deployment_slot,
                'extended_properties': deployment.extended_properties,
                'input_endpoint_list': deployment.input_endpoint_list,
                'label': deployment.label,
                'last_modified_time': deployment.last_modified_time,
                'locked': deployment.locked,
                'name': deployment.name,
                'persistent_vm_downtime_info': deployment.persistent_vm_downtime_info,
                'private_id': deployment.private_id,
                'role_instance_list': {},
                'role_list': {},
                'rollback_allowed': deployment.rollback_allowed,
                'sdk_version': deployment.sdk_version,
                'status': deployment.status,
                'upgrade_domain_count': deployment.upgrade_domain_count,
                'upgrade_status': deployment.upgrade_status,
                'url': deployment.url,
            }
            for role_instance in deployment.role_instance_list:
                ret[service.service_name]['deployments'][deployment.name]['role_instance_list'][role_instance.role_name] = {
                    'fqdn': role_instance.fqdn,
                    'instance_error_code': role_instance.instance_error_code,
                    'instance_fault_domain': role_instance.instance_fault_domain,
                    'instance_name': role_instance.instance_name,
                    'instance_size': role_instance.instance_size,
                    'instance_state_details': role_instance.instance_state_details,
                    'instance_status': role_instance.instance_status,
                    'instance_upgrade_domain': role_instance.instance_upgrade_domain,
                    'ip_address': role_instance.ip_address,
                    'power_state': role_instance.power_state,
                    'role_name': role_instance.role_name,
                }
            for role in deployment.role_list:
                ret[service.service_name]['deployments'][deployment.name]['role_list'][role.role_name] = {
                    'role_name': role.role_name,
                    'os_version': role.os_version,
                }
                role_info = conn.get_role(
                    service_name=service.service_name,
                    deployment_name=deployment.name,
                    role_name=role.role_name,
                )
                ret[service.service_name]['deployments'][deployment.name]['role_list'][role.role_name]['role_info'] = {
                    'availability_set_name': role_info.availability_set_name,
                    'configuration_sets': role_info.configuration_sets,
                    'data_virtual_hard_disks': role_info.data_virtual_hard_disks,
                    'os_version': role_info.os_version,
                    'role_name': role_info.role_name,
                    'role_size': role_info.role_size,
                    'role_type': role_info.role_type,
                }
                ret[service.service_name]['deployments'][deployment.name]['role_list'][role.role_name]['role_info']['os_virtual_hard_disk'] = {
                    'disk_label': role_info.os_virtual_hard_disk.disk_label,
                    'disk_name': role_info.os_virtual_hard_disk.disk_name,
                    'host_caching': role_info.os_virtual_hard_disk.host_caching,
                    'media_link': role_info.os_virtual_hard_disk.media_link,
                    'os': role_info.os_virtual_hard_disk.os,
                    'source_image_name': role_info.os_virtual_hard_disk.source_image_name,
                }
    return ret


def list_nodes_select(conn=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if not conn:
        conn = get_conn()

    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(conn, 'function'), __opts__['query.selection'], call,
    )


def show_instance(name, call=None):
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    nodes = list_nodes_full()
    # Find under which cloud service the name is listed, if any
    if name not in nodes:
        return {}
    salt.utils.cloud.cache_node(nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()

    label = vm_.get('label', vm_['name'])
    service_name = vm_.get('service_name', vm_['name'])
    service_kwargs = {
        'service_name': service_name,
        'label': label,
        'description': vm_.get('desc', vm_['name']),
    }

    loc_error = False
    if 'location' in vm_:
        if 'affinity_group' in vm_:
            loc_error = True
        else:
            service_kwargs['location'] = vm_['location']
    elif 'affinity_group' in vm_:
        service_kwargs['affiinity_group'] = vm_['affiinity_group']
    else:
        loc_error = True

    if loc_error:
        raise SaltCloudSystemExit(
            'Either a location or affinity group must be specified, but not both'
        )

    return
    ssh_port = config.get_cloud_config_value('port', vm_, __opts__,
                                             default='22', search_global=True)

    ssh_endpoint = azure.servicemanagement.ConfigurationSetInputEndpoint(
        name='SSH',
        protocol='TCP',
        port=ssh_port,
        local_port='22',
    )

    network_config = azure.servicemanagement.ConfigurationSet()
    network_config.input_endpoints.input_endpoints.append(ssh_endpoint)
    network_config.configuration_set_type = 'NetworkConfiguration'

    if 'win_username' in vm_:
        system_config = azure.servicemanagement.WindowsConfigurationSet(
            computer_name=vm_['name'],
            admin_username=vm_['win_username'],
            admin_password=vm_['win_password'],
        )
        # Domain and WinRM configuration not yet supported by Salt Cloud
        system_config.domain_join = None
        system_config.win_rm = None
    else:
        system_config = azure.servicemanagement.LinuxConfigurationSet(
            host_name=vm_['name'],
            user_name=vm_['ssh_username'],
            user_password=vm_['ssh_password'],
            disable_ssh_password_authentication=False,
        )

    # TODO: Might need to create a storage account
    media_link = vm_['media_link']
    # TODO: Probably better to use more than just the name in the media_link
    media_link += '/{0}.vhd'.format(vm_['name'])
    os_hd = azure.servicemanagement.OSVirtualHardDisk(vm_['image'], media_link)

    vm_kwargs = {
        'service_name': service_name,
        'deployment_name': service_name,
        'deployment_slot': vm_['slot'],
        'label': label,
        'role_name': vm_['name'],
        'system_config': system_config,
        'os_virtual_hard_disk': os_hd,
        'role_size': vm_['size'],
        'network_config': network_config,
    }
    log.debug('vm_kwargs: {0}'.format(vm_kwargs))

    event_kwargs = {'service_kwargs': service_kwargs.copy(),
                    'vm_kwargs': vm_kwargs.copy()}
    del event_kwargs['vm_kwargs']['system_config']
    del event_kwargs['vm_kwargs']['os_virtual_hard_disk']
    del event_kwargs['vm_kwargs']['network_config']
    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        event_kwargs,
        transport=__opts__['transport']
    )
    log.debug('vm_kwargs: {0}'.format(vm_kwargs))

    # Azure lets you open winrm on a new VM
    # Can open up specific ports in Azure; but not on Windows

    try:
        conn.create_hosted_service(**service_kwargs)
    except WindowsAzureConflictError:
        log.debug('Cloud service already exists')
    except Exception as exc:
        error = 'The hosted service name is invalid.'
        if error in str(exc):
            log.error(
                'Error creating {0} on Azure.\n\n'
                'The hosted service name is invalid. The name can contain '
                'only letters, numbers, and hyphens. The name must start with '
                'a letter and must end with a letter or a number.'.format(
                    vm_['name']
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
        else:
            log.error(
                'Error creating {0} on Azure\n\n'
                'The following exception was thrown when trying to '
                'run the initial deployment: \n{1}'.format(
                    vm_['name'], str(exc)
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
        return False
    try:
        result = conn.create_virtual_machine_deployment(**vm_kwargs)
        log.debug('Request ID for machine: {0}'.format(result.request_id))
        _wait_for_async(conn, result.request_id)
    except WindowsAzureConflictError:
        log.debug('Conflict error. The deployment may already exist, trying add_role')
        # Deleting two useless keywords
        del vm_kwargs['deployment_slot']
        del vm_kwargs['label']
        result = conn.add_role(**vm_kwargs)
        _wait_for_async(conn, result.request_id)
    except Exception as exc:
        error = 'The hosted service name is invalid.'
        if error in str(exc):
            log.error(
                'Error creating {0} on Azure.\n\n'
                'The VM name is invalid. The name can contain '
                'only letters, numbers, and hyphens. The name must start with '
                'a letter and must end with a letter or a number.'.format(
                    vm_['name']
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
        else:
            log.error(
                'Error creating {0} on Azure.\n\n'
                'The Virtual Machine could not be created. If you '
                'are using an already existing Cloud Service, '
                'make sure you set up the `port` variable corresponding '
                'to the SSH port exists and that the port number is not '
                'already in use.\nThe following exception was thrown when trying to '
                'run the initial deployment: \n{1}'.format(
                    vm_['name'], str(exc)
                ),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
        return False

    def wait_for_hostname():
        '''
        Wait for the IP address to become available
        '''
        try:
            conn.get_role(service_name, service_name, vm_['name'])
            data = show_instance(vm_['name'], call='action')
            if 'url' in data and data['url'] != str(''):
                return data['url']
        except WindowsAzureMissingResourceError:
            pass
        time.sleep(1)
        return False

    hostname = salt.utils.cloud.wait_for_fun(
        wait_for_hostname,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )

    if not hostname:
        log.error('Failed to get a value for the hostname.')
        return False

    hostname = hostname.replace('http://', '').replace('/', '')

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )
    ssh_password = config.get_cloud_config_value(
        'ssh_password', vm_, __opts__
    )

    ret = {}
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'opts': __opts__,
            'host': hostname,
            'port': int(ssh_port),
            'username': ssh_username,
            'password': ssh_password,
            'script': deploy_script,
            'name': vm_['name'],
            'start_action': __opts__['start_action'],
            'parallel': __opts__['parallel'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'tmp_dir': config.get_cloud_config_value(
                'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
            ),
            'deploy_command': config.get_cloud_config_value(
                'deploy_command', vm_, __opts__,
                default='/tmp/.saltcloud/deploy.sh',
            ),
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(ssh_username != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=False
            ),
            'display_ssh_output': config.get_cloud_config_value(
                'display_ssh_output', vm_, __opts__, default=True
            ),
            'script_args': config.get_cloud_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_cloud_config_value(
                'script_env', vm_, __opts__
            ),
            'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_),
            'has_ssh_agent': False
        }

        # Deploy salt-master files, if necessary
        if config.get_cloud_config_value('make_master', vm_, __opts__) is True:
            deploy_kwargs['make_master'] = True
            deploy_kwargs['master_pub'] = vm_['master_pub']
            deploy_kwargs['master_pem'] = vm_['master_pem']
            master_conf = salt.utils.cloud.master_config(__opts__, vm_)
            deploy_kwargs['master_conf'] = master_conf

            if master_conf.get('syndic_master', None):
                deploy_kwargs['make_syndic'] = True

        deploy_kwargs['make_minion'] = config.get_cloud_config_value(
            'make_minion', vm_, __opts__, default=True
        )

        # Check for Windows install params
        win_installer = config.get_cloud_config_value('win_installer', vm_, __opts__)
        if win_installer:
            deploy_kwargs['win_installer'] = win_installer
            minion = salt.utils.cloud.minion_config(__opts__, vm_)
            deploy_kwargs['master'] = minion['master']
            deploy_kwargs['username'] = config.get_cloud_config_value(
                'win_username', vm_, __opts__, default='Administrator'
            )
            deploy_kwargs['password'] = config.get_cloud_config_value(
                'win_password', vm_, __opts__, default=''
            )

        # Store what was used to the deploy the VM
        event_kwargs = copy.deepcopy(deploy_kwargs)
        del event_kwargs['minion_pem']
        del event_kwargs['minion_pub']
        del event_kwargs['sudo_password']
        if 'password' in event_kwargs:
            del event_kwargs['password']
        ret['deploy_kwargs'] = event_kwargs

        salt.utils.cloud.fire_event(
            'event',
            'executing deploy script',
            'salt/cloud/{0}/deploying'.format(vm_['name']),
            {'kwargs': event_kwargs},
            transport=__opts__['transport']
        )

        deployed = False
        if win_installer:
            deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
        else:
            deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

        if deployed:
            log.info('Salt installed on {0}'.format(vm_['name']))
        else:
            log.error(
                'Failed to start Salt on Cloud VM {0}'.format(
                    vm_['name']
                )
            )

    # Attaching volumes
    volumes = config.get_cloud_config_value(
        'volumes', vm_, __opts__, search_global=True
    )
    if volumes:
        salt.utils.cloud.fire_event(
            'event',
            'attaching volumes',
            'salt/cloud/{0}/attaching_volumes'.format(vm_['name']),
            {'volumes': volumes},
            transport=__opts__['transport']
        )

        log.info('Create and attach volumes to node {0}'.format(vm_['name']))
        created = create_attach_volumes(
            vm_['name'],
            {
                'volumes': volumes,
                'service_name': service_name,
                'deployment_name': vm_['name'],
                'media_link': media_link,
                'role_name': vm_['name'],
                'del_all_vols_on_destroy': vm_.get('set_del_all_vols_on_destroy', False)
            },
            call='action'
        )
        ret['Attached Volumes'] = created

    data = show_instance(vm_['name'], call='action')
    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    ret.update(data)

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )

    return ret


def create_attach_volumes(name, kwargs, call=None, wait_to_finish=True):
    '''
    Create and attach volumes to created node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The create_attach_volumes action must be called with '
            '-a or --action.'
        )

    if isinstance(kwargs['volumes'], str):
        volumes = yaml.safe_load(kwargs['volumes'])
    else:
        volumes = kwargs['volumes']

    # From the Azure .NET SDK doc
    #
    # The Create Data Disk operation adds a data disk to a virtual
    # machine. There are three ways to create the data disk using the
    # Add Data Disk operation.
    #    Option 1 - Attach an empty data disk to
    # the role by specifying the disk label and location of the disk
    # image. Do not include the DiskName and SourceMediaLink elements in
    # the request body. Include the MediaLink element and reference a
    # blob that is in the same geographical region as the role. You can
    # also omit the MediaLink element. In this usage, Azure will create
    # the data disk in the storage account configured as default for the
    # role.
    #    Option 2 - Attach an existing data disk that is in the image
    # repository. Do not include the DiskName and SourceMediaLink
    # elements in the request body. Specify the data disk to use by
    # including the DiskName element. Note: If included the in the
    # response body, the MediaLink and LogicalDiskSizeInGB elements are
    # ignored.
    #    Option 3 - Specify the location of a blob in your storage
    # account that contain a disk image to use. Include the
    # SourceMediaLink element. Note: If the MediaLink element
    # isincluded, it is ignored.  (see
    # http://msdn.microsoft.com/en-us/library/windowsazure/jj157199.aspx
    # for more information)
    #
    # Here only option 1 is implemented
    conn = get_conn()
    ret = []
    for volume in volumes:
        if "disk_name" in volume:
            log.error("You cannot specify a disk_name. Only new volumes are allowed")
            return False
        # Use the size keyword to set a size, but you can use the
        # azure name too. If neither is set, the disk has size 100GB
        volume.setdefault("logical_disk_size_in_gb", volume.get("size", 100))
        volume.setdefault("host_caching", "ReadOnly")
        volume.setdefault("lun", 0)
        # The media link is vm_name-disk-[0-15].vhd
        volume.setdefault("media_link",
                          kwargs["media_link"][:-4] + "-disk-{0}.vhd".format(volume["lun"]))
        volume.setdefault("disk_label",
                          kwargs["role_name"] + "-disk-{0}".format(volume["lun"]))
        volume_dict = {
            'volume_name': volume["lun"],
            'disk_label': volume["disk_label"]
        }

        # Preparing the volume dict to be passed with **
        kwargs_add_data_disk = ["lun", "host_caching", "media_link",
                                "disk_label", "disk_name",
                                "logical_disk_size_in_gb",
                                "source_media_link"]
        for key in set(volume.keys()) - set(kwargs_add_data_disk):
            del volume[key]

        attach = conn.add_data_disk(kwargs["service_name"], kwargs["deployment_name"], kwargs["role_name"],
                                    **volume)
        log.debug(attach)

        # If attach is None then everything is fine
        if attach:
            msg = (
                '{0} attached to {1} (aka {2})'.format(
                    volume_dict['volume_name'],
                    kwargs['role_name'],
                    name,
                )
            )
            log.info(msg)
            ret.append(msg)
        else:
            log.error('Error attaching {0} on Azure'.format(volume_dict))
    return ret


def create_attach_volumes(name, kwargs, call=None, wait_to_finish=True):
    '''
    Create and attach volumes to created node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The create_attach_volumes action must be called with '
            '-a or --action.'
        )

    if isinstance(kwargs['volumes'], str):
        volumes = yaml.safe_load(kwargs['volumes'])
    else:
        volumes = kwargs['volumes']

    # From the Azure .NET SDK doc
    #
    # The Create Data Disk operation adds a data disk to a virtual
    # machine. There are three ways to create the data disk using the
    # Add Data Disk operation.
    #    Option 1 - Attach an empty data disk to
    # the role by specifying the disk label and location of the disk
    # image. Do not include the DiskName and SourceMediaLink elements in
    # the request body. Include the MediaLink element and reference a
    # blob that is in the same geographical region as the role. You can
    # also omit the MediaLink element. In this usage, Azure will create
    # the data disk in the storage account configured as default for the
    # role.
    #    Option 2 - Attach an existing data disk that is in the image
    # repository. Do not include the DiskName and SourceMediaLink
    # elements in the request body. Specify the data disk to use by
    # including the DiskName element. Note: If included the in the
    # response body, the MediaLink and LogicalDiskSizeInGB elements are
    # ignored.
    #    Option 3 - Specify the location of a blob in your storage
    # account that contain a disk image to use. Include the
    # SourceMediaLink element. Note: If the MediaLink element
    # isincluded, it is ignored.  (see
    # http://msdn.microsoft.com/en-us/library/windowsazure/jj157199.aspx
    # for more information)
    #
    # Here only option 1 is implemented
    conn = get_conn()
    ret = []
    for volume in volumes:
        if "disk_name" in volume:
            log.error("You cannot specify a disk_name. Only new volumes are allowed")
            return False
        # Use the size keyword to set a size, but you can use the
        # azure name too. If neither is set, the disk has size 100GB
        volume.setdefault("logical_disk_size_in_gb", volume.get("size", 100))
        volume.setdefault("host_caching", "ReadOnly")
        volume.setdefault("lun", 0)
        # The media link is vm_name-disk-[0-15].vhd
        volume.setdefault("media_link",
                          kwargs["media_link"][:-4] + "-disk-{0}.vhd".format(volume["lun"]))
        volume.setdefault("disk_label",
                          kwargs["role_name"] + "-disk-{0}".format(volume["lun"]))
        volume_dict = {
            'volume_name': volume["lun"],
            'disk_label': volume["disk_label"]
        }

        # Preparing the volume dict to be passed with **
        kwargs_add_data_disk = ["lun", "host_caching", "media_link",
                                "disk_label", "disk_name",
                                "logical_disk_size_in_gb",
                                "source_media_link"]
        for key in set(volume.keys()) - set(kwargs_add_data_disk):
            del volume[key]

        result = conn.add_data_disk(kwargs["service_name"],
                                    kwargs["deployment_name"],
                                    kwargs["role_name"],
                                    **volume)
        _wait_for_async(conn, result.request_id)

        msg = (
                '{0} attached to {1} (aka {2})'.format(
                    volume_dict['volume_name'],
                    kwargs['role_name'],
                    name)
               )
        log.info(msg)
        ret.append(msg)
    return ret


# Helper function for azure tests
def _wait_for_async(conn, request_id):
    '''
    Helper function for azure tests
    '''
    count = 0
    log.debug('Waiting for asynchronous operation to complete')
    result = conn.get_operation_status(request_id)
    while result.status == 'InProgress':
        count = count + 1
        if count > 120:
            raise ValueError('Timed out waiting for async operation to complete.')
        time.sleep(5)
        result = conn.get_operation_status(request_id)

    if result.status != 'Succeeded':
        raise WindowsAzureError('Operation failed. {message} ({code})'
                                .format(message=result.error.message,
                                        code=result.error.code))


def destroy(name, conn=None, call=None, kwargs=None):
    '''
    Destroy a VM

    CLI Examples::

        salt-cloud -d myminion
        salt-cloud -a destroy myminion service_name=myservice
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    if not conn:
        conn = get_conn()

    if kwargs is None:
        kwargs = {}

    instance_data = show_instance(name, call='action')
    service_name = instance_data['deployment']['name']
    disk_name = instance_data['role_info']['os_virtual_hard_disk']['disk_name']

    ret = {}
    # TODO: Add the ability to delete or not delete a hosted service when
    # deleting a VM
    try:
        log.debug('Deleting role')
        result = conn.delete_role(service_name, service_name, name)
        delete_type = 'delete_role'
    except WindowsAzureError:
        log.debug('Failed to delete role, deleting deployment')
        try:
            result = conn.delete_deployment(service_name, service_name)
        except WindowsAzureConflictError as exc:
            log.error(exc.message)
            return {'Error': exc.message}
        delete_type = 'delete_deployment'
    _wait_for_async(conn, result.request_id)
    ret[name] = {
        delete_type: {'request_id': result.request_id},
    }
    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    cleanup_disks = config.get_cloud_config_value(
        'cleanup_disks',
        get_configured_provider(), __opts__, search_global=False, default=False,
    )
    if cleanup_disks:
        cleanup_vhds = kwargs.get('delete_vhd', config.get_cloud_config_value(
            'cleanup_vhds',
            get_configured_provider(), __opts__, search_global=False, default=False,
        ))
        log.debug('Deleting disk {0}'.format(disk_name))
        if cleanup_vhds:
            log.debug('Deleting vhd')

        def wait_for_destroy():
            '''
            Wait for the VM to be deleted
            '''
            try:
                data = delete_disk(kwargs={'name': disk_name, 'delete_vhd': cleanup_vhds}, call='function')
                return data
            except WindowsAzureConflictError:
                log.debug('Waiting for VM to be destroyed...')
            time.sleep(5)
            return False

        data = salt.utils.cloud.wait_for_fun(
            wait_for_destroy,
            timeout=config.get_cloud_config_value(
                'wait_for_fun_timeout', {}, __opts__, default=15 * 60),
        )
        ret[name]['delete_disk'] = {
            'name': disk_name,
            'delete_vhd': cleanup_vhds,
            'data': data
        }

        # Services can't be cleaned up unless disks are too
        cleanup_services = config.get_cloud_config_value(
            'cleanup_services',
            get_configured_provider(), __opts__, search_global=False, default=False
        )
        if cleanup_services:
            log.debug('Deleting service {0}'.format(service_name))

            def wait_for_disk_delete():
                '''
                Wait for the disk to be deleted
                '''
                try:
                    data = delete_service(kwargs={'name': service_name}, call='function')
                    return data
                except WindowsAzureConflictError:
                    log.debug('Waiting for disk to be deleted...')
                time.sleep(5)
                return False

            data = salt.utils.cloud.wait_for_fun(
                wait_for_disk_delete,
                timeout=config.get_cloud_config_value(
                    'wait_for_fun_timeout', {}, __opts__, default=15 * 60),
            )
            ret[name]['delete_services'] = {
                'name': service_name,
                'data': data
            }

    return ret


def list_storage_services(conn=None, call=None):
    '''
    List VMs on this Azure account, with full information
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            ('The list_storage_services function must be called '
             'with -f or --function.')
        )

    if not conn:
        conn = get_conn()

    ret = {}
    accounts = conn.list_storage_accounts()
    for service in accounts.storage_services:
        ret[service.service_name] = {
            'capabilities': service.capabilities,
            'service_name': service.service_name,
            'storage_service_properties': service.storage_service_properties,
            'extended_properties': service.extended_properties,
            'storage_service_keys': service.storage_service_keys,
            'url': service.url,
        }
    return ret


def get_operation_status(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: 2015.2

    Get Operation Status, based on a request ID

    CLI Example::

        salt-cloud -f get_operation_status my-azure id=0123456789abcdef0123456789abcdef
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_instance function must be called with -f or --function.'
        )

    if 'id' not in kwargs:
        raise SaltCloudSystemExit('A request ID must be specified as "id"')

    if not conn:
        conn = get_conn()

    data = conn.get_operation_status(kwargs['id'])
    ret = {
        'http_status_code': data.http_status_code,
        'id': kwargs['id'],
        'status': data.status
    }
    if hasattr(data.error, 'code'):
        ret['error'] = {
            'code': data.error.code,
            'message': data.error.message,
        }

    return ret


def list_storage(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List storage accounts associated with the account

    CLI Example::

        salt-cloud -f list_storage my-azure
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_storage function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    data = conn.list_storage_accounts()
    pprint.pprint(dir(data))
    ret = {}
    for item in data.storage_services:
        ret[item.service_name] = object_to_dict(item)
    return ret


def show_storage(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List storage service properties

    CLI Example::

        salt-cloud -f show_storage my-azure name=my_storage
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_storage function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    data = conn.get_storage_account_properties(
        kwargs['name'],
    )
    return object_to_dict(data)


# To reflect the Azure API
get_storage = show_storage


def show_storage_keys(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Show storage account keys

    CLI Example::

        salt-cloud -f show_storage_keys my-azure name=my_storage
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_storage_keys function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    try:
        data = conn.get_storage_account_keys(
            kwargs['name'],
        )
    except WindowsAzureMissingResourceError as exc:
        storage_data = show_storage(kwargs={'name': kwargs['name']}, call='function')
        if storage_data['storage_service_properties']['status'] == 'Creating':
            return {'Error': 'The storage account keys have not yet been created'}
        else:
            return {'Error': exc.message}
    return object_to_dict(data)


# To reflect the Azure API
get_storage_keys = show_storage_keys


def create_storage(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Create a new storage account

    CLI Example::

        salt-cloud -f create_storage my-azure name=my_storage label=my_storage location='West US'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_storage function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'description' not in kwargs:
        raise SaltCloudSystemExit('A description must be specified as "description"')

    if 'label' not in kwargs:
        raise SaltCloudSystemExit('A label must be specified as "label"')

    if 'location' not in kwargs and 'affinity_group' not in kwargs:
        raise SaltCloudSystemExit('Either a location or an affinity_group '
                                  'must be specified (but not both)')

    try:
        data = conn.create_storage_account(
            service_name=kwargs['name'],
            label=kwargs['label'],
            description=kwargs.get('description', None),
            location=kwargs.get('location', None),
            affinity_group=kwargs.get('affinity_group', None),
            extended_properties=kwargs.get('extended_properties', None),
            geo_replication_enabled=kwargs.get('geo_replication_enabled', None),
            account_type=kwargs.get('account_type', 'Standard_GRS'),
        )
        return {'Success': 'The storage account was successfully created'}
    except WindowsAzureConflictError as exc:
        return {'Error': 'There was a Conflict. This usually means that the storage account already exists.'}


def update_storage(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Update a storage account's properties

    CLI Example::

        salt-cloud -f update_storage my-azure name=my_storage label=my_storage
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_storage function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    data = conn.update_storage_account(
        service_name=kwargs['name'],
        label=kwargs.get('label', None),
        description=kwargs.get('description', None),
        extended_properties=kwargs.get('extended_properties', None),
        geo_replication_enabled=kwargs.get('geo_replication_enabled', None),
        account_type=kwargs.get('account_type', 'Standard_GRS'),
    )
    return show_storage(kwargs={'name': kwargs['name']}, call='function')


def regenerate_storage_keys(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Create a new storage account

    CLI Example::

        salt-cloud -f regenerate_storage_keys my-azure name=my_storage key_type=primary
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_storage function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'key_type' not in kwargs or kwargs['key_type'] not in ('primary', 'secondary'):
        raise SaltCloudSystemExit('A key_type must be specified ("primary" or "secondary")')

    try:
        data = conn.regenerate_storage_account_keys(
            service_name=kwargs['name'],
            key_type=kwargs['key_type'],
        )
        return show_storage_keys(kwargs={'name': kwargs['name']}, call='function')
    except WindowsAzureConflictError as exc:
        return {'Error': 'There was a Conflict. This usually means that the storage account already exists.'}


def delete_storage(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete a specific storage account

    CLI Examples::

        salt-cloud -f delete_storage my-azure name=my_storage
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_storage function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if not conn:
        conn = get_conn()

    try:
        data = conn.delete_storage_account(kwargs['name'])
        return {'Success': 'The storage account was successfully deleted'}
    except WindowsAzureMissingResourceError as exc:
        return {'Error': exc.message}


def list_services(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List hosted services associated with the account

    CLI Example::

        salt-cloud -f list_services my-azure
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_services function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    data = conn.list_hosted_services()
    ret = {}
    for item in data.hosted_services:
        ret[item.service_name] = object_to_dict(item)
        ret[item.service_name]['name'] = item.service_name
    return ret


def show_service(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List hosted service properties

    CLI Example::

        salt-cloud -f show_service my-azure name=my_service
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_service function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    data = conn.get_hosted_service_properties(
        kwargs['name'],
        kwargs.get('details', False)
    )
    ret = object_to_dict(data)
    return ret


def create_service(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Create a new hosted service

    CLI Example::

        salt-cloud -f create_service my-azure name=my_service label=my_service location='West US'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_service function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'label' not in kwargs:
        raise SaltCloudSystemExit('A label must be specified as "label"')

    if 'location' not in kwargs and 'affinity_group' not in kwargs:
        raise SaltCloudSystemExit('Either a location or an affinity_group '
                                  'must be specified (but not both)')

    try:
        data = conn.create_hosted_service(
            kwargs['name'],
            kwargs['label'],
            kwargs.get('description', None),
            kwargs.get('location', None),
            kwargs.get('affinity_group', None),
            kwargs.get('extended_properties', None),
        )
        return {'Success': 'The service was successfully created'}
    except WindowsAzureConflictError as exc:
        return {'Error': 'There was a Conflict. This usually means that the service already exists.'}


def delete_service(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete a specific service associated with the account

    CLI Examples::

        salt-cloud -f delete_service my-azure name=my_service
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_service function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if not conn:
        conn = get_conn()

    try:
        data = conn.delete_hosted_service(kwargs['name'])
        return {'Success': 'The service was successfully deleted'}
    except WindowsAzureMissingResourceError as exc:
        return {'Error': exc.message}


def list_disks(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List disks associated with the account

    CLI Example::

        salt-cloud -f list_disks my-azure
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_disks function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    data = conn.list_disks()
    ret = {}
    for item in data.disks:
        ret[item.name] = object_to_dict(item)
    return ret


def show_disk(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Return information about a disk

    CLI Example::

        salt-cloud -f show_disk my-azure name=my_disk
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_disk function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    data = conn.get_disk(kwargs['name'])
    return object_to_dict(data)


# For consistency with Azure SDK
get_disk = show_disk


def cleanup_unattached_disks(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Cleans up all disks associated with the account, which are not attached.
    *** CAUTION *** This is a destructive function with no undo button, and no
    "Are you sure?" confirmation!

    CLI Examples::

        salt-cloud -f cleanup_unattached_disks my-azure name=my_disk
        salt-cloud -f cleanup_unattached_disks my-azure name=my_disk delete_vhd=True
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_disk function must be called with -f or --function.'
        )

    disks = list_disks(kwargs=kwargs, conn=conn, call='function')
    for disk in disks:
        if disks[disk]['attached_to'] is None:
            del_kwargs = {
                'name': disks[disk]['name'][0],
                'delete_vhd': kwargs.get('delete_vhd', False)
            }
            log.info('Deleting disk {name}, deleting VHD: {delete_vhd}'.format(**del_kwargs))
            data = delete_disk(kwargs=del_kwargs, call='function')
    return True


def delete_disk(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete a specific disk associated with the account

    CLI Examples::

        salt-cloud -f delete_disk my-azure name=my_disk
        salt-cloud -f delete_disk my-azure name=my_disk delete_vhd=True
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_disk function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if not conn:
        conn = get_conn()

    try:
        data = conn.delete_disk(kwargs['name'], kwargs.get('delete_vhd', False))
        return {'Success': 'The disk was successfully deleted'}
    except WindowsAzureMissingResourceError as exc:
        return {'Error': exc.message}


def update_disk(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Update a disk's properties

    CLI Example::

        salt-cloud -f update_disk my-azure name=my_disk label=my_disk
        salt-cloud -f update_disk my-azure name=my_disk new_name=another_disk
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_disk function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    old_data = show_disk(kwargs={'name': kwargs['name']}, call='function')
    data = conn.update_disk(
        disk_name=kwargs['name'],
        has_operating_system=kwargs.get('has_operating_system', old_data['has_operating_system']),
        label=kwargs.get('label', old_data['label']),
        media_link=kwargs.get('media_link', old_data['media_link']),
        name=kwargs.get('new_name', old_data['name']),
        os=kwargs.get('os', old_data['os']),
    )
    return show_disk(kwargs={'name': kwargs['name']}, call='function')


def list_service_certificates(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List certificates associated with the service

    CLI Example::

        salt-cloud -f list_service_certificates my-azure name=my_service
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_service_certificates function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A service name must be specified as "name"')

    if not conn:
        conn = get_conn()

    data = conn.list_service_certificates(service_name=kwargs['name'])
    ret = {}
    for item in data.certificates:
        ret[item.thumbprint] = object_to_dict(item)
    return ret


def show_service_certificate(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Return information about a service certificate

    CLI Example::

        salt-cloud -f show_service_certificate my-azure name=my_service_certificate \
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_service_certificate function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A service name must be specified as "name"')

    if 'thumbalgorithm' not in kwargs:
        raise SaltCloudSystemExit('A thumbalgorithm must be specified as "thumbalgorithm"')

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    data = conn.get_service_certificate(
        kwargs['name'],
        kwargs['thumbalgorithm'],
        kwargs['thumbprint'],
    )
    return object_to_dict(data)


# For consistency with Azure SDK
get_service_certificate = show_service_certificate


def add_service_certificate(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Add a new service certificate

    CLI Example::

        salt-cloud -f add_service_certificate my-azure name=my_service_certificate \
            data='...CERT_DATA...' certificate_format=sha1 password=verybadpass
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The add_service_certificate function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'data' not in kwargs:
        raise SaltCloudSystemExit('Certificate data must be specified as "data"')

    if 'certificate_format' not in kwargs:
        raise SaltCloudSystemExit('A certificate_format must be specified as "certificate_format"')

    if 'password' not in kwargs:
        raise SaltCloudSystemExit('A password must be specified as "password"')

    try:
        data = conn.add_service_certificate(
            kwargs['name'],
            kwargs['data'],
            kwargs['certificate_format'],
            kwargs['password'],
        )
        return {'Success': 'The service certificate was successfully added'}
    except WindowsAzureConflictError as exc:
        return {'Error': 'There was a Conflict. This usually means that the service certificate already exists.'}


def delete_service_certificate(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete a specific certificate associated with the service

    CLI Examples::

        salt-cloud -f delete_service_certificate my-azure name=my_service_certificate \
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_service_certificate function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'thumbalgorithm' not in kwargs:
        raise SaltCloudSystemExit('A thumbalgorithm must be specified as "thumbalgorithm"')

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    if not conn:
        conn = get_conn()

    try:
        data = conn.delete_service_certificate(
            kwargs['name'],
            kwargs['thumbalgorithm'],
            kwargs['thumbprint'],
        )
        return {'Success': 'The service certificate was successfully deleted'}
    except WindowsAzureMissingResourceError as exc:
        return {'Error': exc.message}


def list_management_certificates(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List management certificates associated with the subscription

    CLI Example::

        salt-cloud -f list_management_certificates my-azure name=my_management
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_management_certificates function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    data = conn.list_management_certificates()
    ret = {}
    for item in data.subscription_certificates:
        ret[item.subscription_certificate_thumbprint] = object_to_dict(item)
    return ret


def show_management_certificate(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Return information about a management_certificate

    CLI Example::

        salt-cloud -f get_management_certificate my-azure name=my_management_certificate \
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_management_certificate function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    data = conn.get_management_certificate(kwargs['thumbprint'])
    return object_to_dict(data)


# For consistency with Azure SDK
get_management_certificate = show_management_certificate


def add_management_certificate(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Add a new management certificate

    CLI Example::

        salt-cloud -f add_management_certificate my-azure public_key='...PUBKEY...' \
            thumbprint=0123456789ABCDEF data='...CERT_DATA...'
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The add_management_certificate function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'public_key' not in kwargs:
        raise SaltCloudSystemExit('A public_key must be specified as "public_key"')

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    if 'data' not in kwargs:
        raise SaltCloudSystemExit('Certificate data must be specified as "data"')

    try:
        data = conn.add_management_certificate(
            kwargs['name'],
            kwargs['thumbprint'],
            kwargs['data'],
        )
        return {'Success': 'The management certificate was successfully added'}
    except WindowsAzureConflictError as exc:
        return {'Error': 'There was a Conflict. This usually means that the management certificate already exists.'}


def delete_management_certificate(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete a specific certificate associated with the management

    CLI Examples::

        salt-cloud -f delete_management_certificate my-azure name=my_management_certificate \
            thumbalgorithm=sha1 thumbprint=0123456789ABCDEF
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_management_certificate function must be called with -f or --function.'
        )

    if 'thumbprint' not in kwargs:
        raise SaltCloudSystemExit('A thumbprint must be specified as "thumbprint"')

    if not conn:
        conn = get_conn()

    try:
        data = conn.delete_management_certificate(kwargs['thumbprint'])
        return {'Success': 'The management certificate was successfully deleted'}
    except WindowsAzureMissingResourceError as exc:
        return {'Error': exc.message}


def list_virtual_networks(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List input endpoints associated with the deployment

    CLI Example::

        salt-cloud -f list_virtual_networks my-azure service=myservice deployment=mydeployment
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_virtual_networks function must be called with -f or --function.'
        )

    path = 'services/networking/virtualnetwork'
    data = query(path)
    return data


def list_input_endpoints(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List input endpoints associated with the deployment

    CLI Example::

        salt-cloud -f list_input_endpoints my-azure service=myservice deployment=mydeployment
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_input_endpoints function must be called with -f or --function.'
        )

    if 'service' not in kwargs:
        raise SaltCloudSystemExit('A service name must be specified as "service"')

    if 'deployment' not in kwargs:
        raise SaltCloudSystemExit('A deployment name must be specified as "deployment"')

    path = 'services/hostedservices/{0}/deployments/{1}'.format(
        kwargs['service'],
        kwargs['deployment'],
    )
    data = query(path)

    ret = {}
    for item in data:
        if 'Role' not in item:
            continue
        input_endpoint = item['Role']['ConfigurationSets']['ConfigurationSet']['InputEndpoints']['InputEndpoint']
        if not isinstance(input_endpoint, list):
            input_endpoint = [input_endpoint]
        for endpoint in input_endpoint:
            ret[endpoint['Name']] = endpoint
    return ret


def show_input_endpoint(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Show an input endpoint associated with the deployment

    CLI Example::

        salt-cloud -f show_input_endpoint my-azure service=myservice \
            deployment=mydeployment name=SSH
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_input_endpoint function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('An endpoint name must be specified as "name"')

    data = list_input_endpoints(kwargs=kwargs, call='function')
    return data.get(kwargs['name'], None)


# For consistency with Azure SDK
get_input_endpoint = show_input_endpoint


def update_input_endpoint(kwargs=None, conn=None, call=None, activity='update'):
    '''
    .. versionadded:: Beryllium

    Update an input endpoint associated with the deployment. Please note that
    there may be a delay before the changes show up.

    CLI Example::

        salt-cloud -f update_input_endpoint my-azure service=myservice \
            deployment=mydeployment role=myrole name=HTTP local_port=80 \
            port=80 protocol=tcp enable_direct_server_return=False \
            timeout_for_tcp_idle_connection=4
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The update_input_endpoint function must be called with -f or --function.'
        )

    if 'service' not in kwargs:
        raise SaltCloudSystemExit('A service name must be specified as "service"')

    if 'deployment' not in kwargs:
        raise SaltCloudSystemExit('A deployment name must be specified as "deployment"')

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('An endpoint name must be specified as "name"')

    if 'role' not in kwargs:
        raise SaltCloudSystemExit('An role name must be specified as "role"')

    if activity != 'delete':
        if 'port' not in kwargs:
            raise SaltCloudSystemExit('An endpoint port must be specified as "port"')

        if 'protocol' not in kwargs:
            raise SaltCloudSystemExit('An endpoint protocol (tcp or udp) must be specified as "protocol"')

        if 'local_port' not in kwargs:
            kwargs['local_port'] = kwargs['port']

        if 'enable_direct_server_return' not in kwargs:
            kwargs['enable_direct_server_return'] = False
        kwargs['enable_direct_server_return'] = str(kwargs['enable_direct_server_return']).lower()

        if 'timeout_for_tcp_idle_connection' not in kwargs:
            kwargs['timeout_for_tcp_idle_connection'] = 4

    old_endpoints = list_input_endpoints(kwargs, call='function')

    endpoints_xml = ''
    endpoint_xml = '''
        <InputEndpoint>
          <LocalPort>{local_port}</LocalPort>
          <Name>{name}</Name>
          <Port>{port}</Port>
          <Protocol>{protocol}</Protocol>
          <EnableDirectServerReturn>{enable_direct_server_return}</EnableDirectServerReturn>
          <IdleTimeoutInMinutes>{timeout_for_tcp_idle_connection}</IdleTimeoutInMinutes>
        </InputEndpoint>'''

    if activity == 'add':
        old_endpoints[kwargs['name']] = kwargs
        old_endpoints[kwargs['name']]['Name'] = kwargs['name']

    for endpoint in old_endpoints:
        if old_endpoints[endpoint]['Name'] == kwargs['name']:
            if activity != 'delete':
                this_endpoint_xml = endpoint_xml.format(**kwargs)
                endpoints_xml += this_endpoint_xml
        else:
            this_endpoint_xml = endpoint_xml.format(
                local_port=old_endpoints[endpoint]['LocalPort'],
                name=old_endpoints[endpoint]['Name'],
                port=old_endpoints[endpoint]['Port'],
                protocol=old_endpoints[endpoint]['Protocol'],
                enable_direct_server_return=old_endpoints[endpoint]['EnableDirectServerReturn'],
                timeout_for_tcp_idle_connection=old_endpoints[endpoint].get('IdleTimeoutInMinutes', 4),
            )
            endpoints_xml += this_endpoint_xml

    request_xml = '''<PersistentVMRole xmlns="http://schemas.microsoft.com/windowsazure"
xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
  <ConfigurationSets>
    <ConfigurationSet>
      <ConfigurationSetType>NetworkConfiguration</ConfigurationSetType>
      <InputEndpoints>{0}
      </InputEndpoints>
    </ConfigurationSet>
  </ConfigurationSets>
  <OSVirtualHardDisk>
  </OSVirtualHardDisk>
</PersistentVMRole>'''.format(endpoints_xml)

    path = 'services/hostedservices/{0}/deployments/{1}/roles/{2}'.format(
        kwargs['service'],
        kwargs['deployment'],
        kwargs['role'],
    )
    query(
        path=path,
        method='PUT',
        header_dict={'Content-Type': 'application/xml'},
        data=request_xml,
        decode=False,
    )
    return True


def add_input_endpoint(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Add an input endpoint to the deployment. Please note that
    there may be a delay before the changes show up.

    CLI Example::

        salt-cloud -f add_input_endpoint my-azure service=myservice \
            deployment=mydeployment role=myrole name=HTTP local_port=80 \
            port=80 protocol=tcp enable_direct_server_return=False \
            timeout_for_tcp_idle_connection=4
    '''
    return update_input_endpoint(
        kwargs=kwargs,
        conn=conn,
        call='function',
        activity='add',
    )


def delete_input_endpoint(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete an input endpoint from the deployment. Please note that
    there may be a delay before the changes show up.

    CLI Example::

        salt-cloud -f delete_input_endpoint my-azure service=myservice \
            deployment=mydeployment role=myrole name=HTTP
    '''
    return update_input_endpoint(
        kwargs=kwargs,
        conn=conn,
        call='function',
        activity='delete',
    )


def show_deployment(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Return information about a deployment

    CLI Example::

        salt-cloud -f show_deployment my-azure name=my_deployment
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The get_deployment function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'service_name' not in kwargs:
        raise SaltCloudSystemExit('A service name must be specified as "service_name"')

    if 'deployment_name' not in kwargs:
        raise SaltCloudSystemExit('A deployment name must be specified as "deployment_name"')

    data = conn.get_deployment_by_name(
        service_name=kwargs['service_name'],
        deployment_name=kwargs['deployment_name'],
    )
    return object_to_dict(data)


# For consistency with Azure SDK
get_deployment = show_deployment


def list_affinity_groups(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    List input endpoints associated with the deployment

    CLI Example::

        salt-cloud -f list_affinity_groups my-azure
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_affinity_groups function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    data = conn.list_affinity_groups()
    ret = {}
    for item in data.affinity_groups:
        ret[item.name] = object_to_dict(item)
    return ret


def show_affinity_group(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Show an affinity group associated with the account

    CLI Example::

        salt-cloud -f show_affinity_group my-azure service=myservice \
            deployment=mydeployment name=SSH
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_affinity_group function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('An affinity group name must be specified as "name"')

    data = conn.get_affinity_group_properties(affinity_group_name=kwargs['name'])
    return object_to_dict(data)


# For consistency with Azure SDK
get_affinity_group = show_affinity_group


def create_affinity_group(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Create a new affinity group

    CLI Example::

        salt-cloud -f create_affinity_group my-azure name=my_affinity_group
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_affinity_group function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'label' not in kwargs:
        raise SaltCloudSystemExit('A label must be specified as "label"')

    if 'location' not in kwargs:
        raise SaltCloudSystemExit('A location must be specified as "location"')

    try:
        data = conn.create_affinity_group(
            kwargs['name'],
            kwargs['label'],
            kwargs['location'],
            kwargs.get('description', None),
        )
        return {'Success': 'The affinity group was successfully created'}
    except WindowsAzureConflictError as exc:
        return {'Error': 'There was a Conflict. This usually means that the affinity group already exists.'}


def update_affinity_group(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Update an affinity group's properties

    CLI Example::

        salt-cloud -f update_affinity_group my-azure name=my_group label=my_group
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The update_affinity_group function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if 'label' not in kwargs:
        raise SaltCloudSystemExit('A label must be specified as "label"')

    data = conn.update_affinity_group(
        affinity_group_name=kwargs['name'],
        label=kwargs['label'],
        description=kwargs.get('description', None),
    )
    return show_affinity_group(kwargs={'name': kwargs['name']}, call='function')


def delete_affinity_group(kwargs=None, conn=None, call=None):
    '''
    .. versionadded:: Beryllium

    Delete a specific affinity group associated with the account

    CLI Examples::

        salt-cloud -f delete_affinity_group my-azure name=my_affinity_group
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The delete_affinity_group function must be called with -f or --function.'
        )

    if 'name' not in kwargs:
        raise SaltCloudSystemExit('A name must be specified as "name"')

    if not conn:
        conn = get_conn()

    try:
        data = conn.delete_affinity_group(kwargs['name'])
        return {'Success': 'The affinity group was successfully deleted'}
    except WindowsAzureMissingResourceError as exc:
        return {'Error': exc.message}


def object_to_dict(obj):
    '''
    .. versionadded:: Beryllium

    Convert an object to a dictionary
    '''
    if isinstance(obj, list):
        ret = []
        for item in obj:
            ret.append(obj.__dict__[item])
    elif isinstance(obj, six.text_type):
        ret = obj.encode('ascii', 'replace'),
    elif isinstance(obj, six.string_types):
        ret = obj
    else:
        ret = {}
        for item in dir(obj):
            if item.startswith('__'):
                continue
            # This is ugly, but inspect.isclass() doesn't seem to work
            if 'class' in str(type(obj.__dict__[item])):
                ret[item] = object_to_dict(obj.__dict__[item])
            elif isinstance(obj.__dict__[item], six.text_type):
                ret[item] = obj.__dict__[item].encode('ascii', 'replace'),
            else:
                ret[item] = obj.__dict__[item]
    return ret


def query(path, method='GET', data=None, params=None, header_dict=None, decode=True):
    '''
    Perform a query directly against the Azure REST API
    '''
    certificate_path = config.get_cloud_config_value(
        'certificate_path',
        get_configured_provider(), __opts__, search_global=False
    )
    subscription_id = config.get_cloud_config_value(
        'subscription_id',
        get_configured_provider(), __opts__, search_global=False
    )
    management_host = config.get_cloud_config_value(
        'management_host',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default='management.core.windows.net'
    )
    requests_lib = config.get_cloud_config_value(
        'requests_lib',
        get_configured_provider(), __opts__, search_global=False
    )
    url = 'https://{management_host}/{subscription_id}/{path}'.format(
        management_host=management_host,
        subscription_id=subscription_id,
        path=path,
    )

    if header_dict is None:
        header_dict = {}

    header_dict['x-ms-version'] = '2014-06-01'

    result = salt.utils.http.query(
        url,
        method=method,
        params=params,
        data=data,
        header_dict=header_dict,
        port=443,
        text=True,
        cert=certificate_path,
        requests_lib=requests_lib,
        decode=decode,
        decode_type='xml',
    )
    if 'dict' in result:
        return result['dict']
    return
