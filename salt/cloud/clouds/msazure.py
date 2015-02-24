# -*- coding: utf-8 -*-
'''
Azure Cloud Module
==================

The Azure cloud module is used to control access to Microsoft Azure

:depends:
    * `Microsoft Azure SDK for Python <https://pypi.python.org/pypi/azure/0.9.0>`_
:configuration:
    Required provider parameters:

    * ``apikey``
    * ``certificate_path``
    * ``subscription_id``

    A Management Certificate (.pem and .crt files) must be created and the .pem
    file placed on the same machine that salt-cloud is run from. Information on
    creating the pem file to use, and uploading the associated cer file can be
    found at:

    http://www.windowsazure.com/en-us/develop/python/how-to-guides/service-management/

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

from __future__ import absolute_import

# Import python libs
import copy
import logging
import pprint
import time
import yaml

# Import salt libs
import salt.config as config
from salt.exceptions import SaltCloudSystemExit
import salt.utils.cloud

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
    images = conn.list_os_images()
    for image in images:
        ret[image.name] = {
            'category': image.category,
            'description': image.description.encode('ascii', 'replace'),
            'eula': image.eula,
            'label': image.label,
            'logical_size_in_gb': image.logical_size_in_gb,
            'name': image.name,
            'os': image.os,
        }
        if hasattr(image, 'affinity_group'):
            ret[image.name]['affinity_group'] = image.affinity_group
        if hasattr(image, 'location'):
            ret[image.name]['location'] = image.location
        if hasattr(image, 'media_link'):
            ret[image.name]['media_link'] = image.media_link
    return ret


def avail_sizes(call=None):
    '''
    Because sizes are built into images with Azure, there will be no sizes to
    return here
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    return {
        'ExtraSmall': {
            'name': 'ExtraSmall',
            'description': 'Extra Small (Shared core, 768MB RAM)',
        },
        'Small': {
            'name': 'Small',
            'description': 'Small (1 core, 1.75GB RAM)',
        },
        'Medium': {
            'name': 'Medium',
            'description': 'Medium (2 cores, 3.5GB RAM)',
        },
        'Large': {
            'name': 'Large',
            'description': 'Large (4 cores, 7GB RAM)',
        },
        'ExtraLarge': {
            'name': 'ExtraLarge',
            'description': 'Extra Large (8 cores, 14GB RAM)',
        },
        'A5': {
            'name': 'A5',
            'description': '2 cores, 14GB RAM',
        },
        'A6': {
            'name': 'A6',
            'description': '4 cores, 28GB RAM',
        },
        'A7': {
            'name': 'A7',
            'description': '8 cores, 56GB RAM',
        },
        'A8': {
            'name': 'A8',
            'description': '8 cores, 56GB RAM, 40 Gbit/s InfiniBand',
        },
        'A9': {
            'name': 'A9',
            'description': '16 cores, 112GB RAM, 40 Gbit/s InfiniBand',
        },
    }


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


def show_service(kwargs=None, conn=None, call=None):
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_service function must be called with -f or --function.'
        )

    if not conn:
        conn = get_conn()

    services = conn.list_hosted_services()
    for service in services:
        if kwargs['service_name'] != service.service_name:
            continue
        props = service.hosted_service_properties
        ret = {
            'affinity_group': props.affinity_group,
            'date_created': props.date_created,
            'date_last_modified': props.date_last_modified,
            'description': props.description,
            'extended_properties': props.extended_properties,
            'label': props.label,
            'location': props.location,
            'status': props.status,
        }
        return ret
    return None


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
        'location': vm_['location'],
    }

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

    linux_config = azure.servicemanagement.LinuxConfigurationSet(
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
        'system_config': linux_config,
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

    ret = {}
    # TODO: Add the ability to delete or not delete a hosted service when
    # deleting a VM
    try:
        result = conn.delete_role(service_name, service_name, name)
    except WindowsAzureError:
        result = conn.delete_deployment(service_name, service_name)
    _wait_for_async(conn, result.request_id)
    ret[name] = {
        'request_id': result.request_id,
    }
    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)
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


def list_disks(conn=None, call=None):
    '''
    Destroy a VM
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            ('The list_disks function must be called '
             'with -f or --function.')
        )

    if not conn:
        conn = get_conn()

    ret = {}
    disks = conn.list_disks()
    for disk in disks.disks:
        ret[disk.name] = {
            'affinity_group': disk.affinity_group,
            'attached_to': disk.attached_to,
            'has_operating_system': disk.has_operating_system,
            'is_corrupted': disk.is_corrupted,
            'label': disk.label,
            'location': disk.location,
            'logical_disk_size_in_gb': disk.logical_disk_size_in_gb,
            'media_link': disk.media_link,
            'name': disk.name,
            'os': disk.os,
            'source_image_name': disk.source_image_name,
        }
    return ret
