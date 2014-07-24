# -*- coding: utf-8 -*-
'''
Azure Cloud Module
==================

The Azure cloud module is used to control access to Microsoft Azure

Use of this module only requires the ``apikey`` parameter. Set up the cloud
configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/azure.conf``:

.. code-block:: yaml

    my-azure-config:
      provider: azure
      subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
      certificate_path: /etc/salt/azure.pem
      management_host: management.core.windows.net

Information on creating the pem file to use, and uploading the associated cer
file can be found at:

http://www.windowsazure.com/en-us/develop/python/how-to-guides/service-management/
'''
# pylint: disable=E0102

# Import python libs
import time
import copy
import pprint
import logging

# Import salt cloud libs
import salt.config as config
import salt.utils.cloud
from salt.cloud.exceptions import SaltCloudSystemExit

# Import azure libs
HAS_LIBS = False
try:
    import azure
    import azure.servicemanagement
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
            'description': image.description.encode('utf-8'),
            'eula': image.eula,
            'label': image.label,
            'logical_size_in_gb': image.logical_size_in_gb,
            'name': image.name,
            'os': image.os,
        }
        if image.affinity_group:
            ret[image.name] = image.affinity_group
        if image.location:
            ret[image.name] = image.location
        if image.media_link:
            ret[image.name] = image.media_link
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
            ret[deployment] = deploy_dict
            ret[deployment]['id'] = deployment
            ret[deployment]['hosted_service'] = service
            ret[deployment]['state'] = ret[deployment]['status']
            ret[deployment]['private_ips'] = []
            ret[deployment]['public_ips'] = []
            role_instances = deploy_dict['role_instance_list']
            for role_instance in role_instances:
                ip_address = role_instances[role_instance]['ip_address']
                if salt.utils.cloud.is_public_ip(ip_address):
                    ret[deployment]['public_ips'].append(ip_address)
                else:
                    ret[deployment]['private_ips'].append(ip_address)
                ret[deployment]['size'] = role_instances[role_instance]['instance_size']
            roles = deploy_dict['role_list']
            for role in roles:
                ret[deployment]['image'] = roles[role]['role_info']['os_virtual_hard_disk']['source_image_name']
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
    service_kwargs = {
        'service_name': vm_['name'],
        'label': label,
        'description': vm_.get('desc', vm_['name']),
        'location': vm_['location'],
    }

    ssh_endpoint = azure.servicemanagement.ConfigurationSetInputEndpoint(
        name='SSH',
        protocol='TCP',
        port='22',
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
        'service_name': vm_['name'],
        'deployment_name': vm_['name'],
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
        hosted_service = conn.create_hosted_service(**service_kwargs)
        vm_deployment = conn.create_virtual_machine_deployment(**vm_kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on Azure\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], exc.message
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return False

    def wait_for_hostname():
        '''
        Wait for the IP address to become available
        '''
        try:
            data = show_instance(vm_['name'], call='action')
        except Exception:
            pass
        if 'url' in data and data['url'] != str(''):
            return data['url']
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
            'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_)
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


def destroy(name, conn=None, call=None):
    '''
    Destroy a VM
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    if not conn:
        conn = get_conn()

    ret = {}
    # TODO: Add the ability to delete or not delete a hosted service when
    # deleting a VM
    del_vm = conn.delete_deployment(service_name=name, deployment_name=name)
    del_service = conn.delete_hosted_service
    ret[name] = {
        'request_id': del_vm.request_id,
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
