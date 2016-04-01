# -*- coding: utf-8 -*-
'''
SoftLayer Cloud Module
======================

The SoftLayer cloud module is used to control access to the SoftLayer VPS
system.

Use of this module only requires the ``apikey`` parameter. Set up the cloud
configuration at:

``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/softlayer.conf``:

.. code-block:: yaml

    my-softlayer-config:
      # SoftLayer account api key
      user: MYLOGIN
      apikey: JVkbSJDGHSDKUKSDJfhsdklfjgsjdkflhjlsdfffhgdgjkenrtuinv
      driver: softlayer

The SoftLayer Python Library needs to be installed in order to use the
SoftLayer salt.cloud modules. See: https://pypi.python.org/pypi/SoftLayer

:depends: softlayer
'''

# Import python libs
from __future__ import absolute_import
import logging
import time

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.exceptions import SaltCloudSystemExit

# Attempt to import softlayer lib
try:
    import SoftLayer
    HAS_SLLIBS = True
except ImportError:
    HAS_SLLIBS = False

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'softlayer'


# Only load in this module if the SoftLayer configurations are in place
def __virtual__():
    '''
    Check for SoftLayer configurations.
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('apikey',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'softlayer': HAS_SLLIBS}
    )


def script(vm_):
    '''
    Return the script deployment object
    '''
    deploy_script = salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )
    return deploy_script


def get_conn(service='SoftLayer_Virtual_Guest'):
    '''
    Return a conn object for the passed VM data
    '''
    client = SoftLayer.Client(
        username=config.get_cloud_config_value(
            'user', get_configured_provider(), __opts__, search_global=False
        ),
        api_key=config.get_cloud_config_value(
            'apikey', get_configured_provider(), __opts__, search_global=False
        ),
    )
    return client[service]


def avail_locations(call=None):
    '''
    List all available locations
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    ret = {}
    conn = get_conn()
    response = conn.getCreateObjectOptions()
    #return response
    for datacenter in response['datacenters']:
        #return data center
        ret[datacenter['template']['datacenter']['name']] = {
            'name': datacenter['template']['datacenter']['name'],
        }
    return ret


def avail_sizes(call=None):
    '''
    Return a dict of all available VM sizes on the cloud provider with
    relevant data. This data is provided in three dicts.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    ret = {
        'block devices': {},
        'memory': {},
        'processors': {},
    }
    conn = get_conn()
    response = conn.getCreateObjectOptions()
    for device in response['blockDevices']:
        #return device['template']['blockDevices']
        ret['block devices'][device['itemPrice']['item']['description']] = {
            'name': device['itemPrice']['item']['description'],
            'capacity':
                device['template']['blockDevices'][0]['diskImage']['capacity'],
        }
    for memory in response['memory']:
        ret['memory'][memory['itemPrice']['item']['description']] = {
            'name': memory['itemPrice']['item']['description'],
            'maxMemory': memory['template']['maxMemory'],
        }
    for processors in response['processors']:
        ret['processors'][processors['itemPrice']['item']['description']] = {
            'name': processors['itemPrice']['item']['description'],
            'start cpus': processors['template']['startCpus'],
        }
    return ret


def avail_images(call=None):
    '''
    Return a dict of all available VM images on the cloud provider.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    ret = {}
    conn = get_conn()
    response = conn.getCreateObjectOptions()
    for image in response['operatingSystems']:
        ret[image['itemPrice']['item']['description']] = {
            'name': image['itemPrice']['item']['description'],
            'template': image['template']['operatingSystemReferenceCode'],
        }
    return ret


def list_custom_images(call=None):
    '''
    Return a dict of all custom VM images on the cloud provider.
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_vlans function must be called with -f or --function.'
        )

    ret = {}
    conn = get_conn('SoftLayer_Account')
    response = conn.getBlockDeviceTemplateGroups()
    for image in response:
        if 'globalIdentifier' not in image:
            continue
        ret[image['name']] = {
            'id': image['id'],
            'name': image['name'],
            'globalIdentifier': image['globalIdentifier'],
        }
        if 'note' in image:
            ret[image['name']]['note'] = image['note']
    return ret


def get_location(vm_=None):
    '''
    Return the location to use, in this order:
        - CLI parameter
        - VM parameter
        - Cloud profile setting
    '''
    return __opts__.get(
        'location',
        config.get_cloud_config_value(
            'location',
            vm_ or get_configured_provider(),
            __opts__,
            #default=DEFAULT_LOCATION,
            search_global=False
        )
    )


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'softlayer',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    conn = get_conn()
    kwargs = {
        'hostname': vm_['name'],
        'domain': vm_['domain'],
        'startCpus': vm_['cpu_number'],
        'maxMemory': vm_['ram'],
        'hourlyBillingFlag': vm_['hourly_billing'],
    }

    local_disk_flag = config.get_cloud_config_value(
        'local_disk', vm_, __opts__, default=False
    )
    kwargs['localDiskFlag'] = local_disk_flag

    if 'image' in vm_:
        kwargs['operatingSystemReferenceCode'] = vm_['image']
        kwargs['blockDevices'] = []
        disks = vm_['disk_size']

        if isinstance(disks, int):
            disks = [str(disks)]
        elif isinstance(disks, str):
            disks = [size.strip() for size in disks.split(',')]

        count = 0
        for disk in disks:
            # device number '1' is reserved for the SWAP disk
            if count == 1:
                count += 1
            block_device = {'device': str(count),
                            'diskImage': {'capacity': str(disk)}}
            kwargs['blockDevices'].append(block_device)
            count += 1

            # Upper bound must be 5 as we're skipping '1' for the SWAP disk ID
            if count > 5:
                log.warning('More that 5 disks were specified for {0} .'
                            'The first 5 disks will be applied to the VM, '
                            'but the remaining disks will be ignored.\n'
                            'Please adjust your cloud configuration to only '
                            'specify a maximum of 5 disks.'.format(vm_['name']))
                break

    elif 'global_identifier' in vm_:
        kwargs['blockDeviceTemplateGroup'] = {
            'globalIdentifier': vm_['global_identifier']
        }

    location = get_location(vm_)
    if location:
        kwargs['datacenter'] = {'name': location}

    private_vlan = config.get_cloud_config_value(
        'private_vlan', vm_, __opts__, default=False
    )
    if private_vlan:
        kwargs['primaryBackendNetworkComponent'] = {
            'networkVlan': {
                'id': private_vlan,
            }
        }

    private_network = config.get_cloud_config_value(
        'private_network', vm_, __opts__, default=False
    )
    if bool(private_network) is True:
        kwargs['privateNetworkOnlyFlag'] = 'True'

    public_vlan = config.get_cloud_config_value(
        'public_vlan', vm_, __opts__, default=False
    )
    if public_vlan:
        kwargs['primaryNetworkComponent'] = {
            'networkVlan': {
                'id': public_vlan,
            }
        }

    max_net_speed = config.get_cloud_config_value(
        'max_net_speed', vm_, __opts__, default=10
    )
    if max_net_speed:
        kwargs['networkComponents'] = [{
            'maxSpeed': int(max_net_speed)
        }]

    post_uri = config.get_cloud_config_value(
        'post_uri', vm_, __opts__, default=None
    )
    if post_uri:
        kwargs['postInstallScriptUri'] = post_uri

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    try:
        response = conn.createObject(kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on SoftLayer\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    ip_type = 'primaryIpAddress'
    private_ssh = config.get_cloud_config_value(
        'private_ssh', vm_, __opts__, default=False
    )
    private_wds = config.get_cloud_config_value(
        'private_windows', vm_, __opts__, default=False
    )
    if private_ssh or private_wds:
        ip_type = 'primaryBackendIpAddress'

    def wait_for_ip():
        '''
        Wait for the IP address to become available
        '''
        nodes = list_nodes_full()
        if ip_type in nodes[vm_['name']]:
            return nodes[vm_['name']][ip_type]
        time.sleep(1)
        return False

    ip_address = salt.utils.cloud.wait_for_fun(
        wait_for_ip,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )
    if config.get_cloud_config_value('deploy', vm_, __opts__) is not True:
        return show_instance(vm_['name'], call='action')

    SSH_PORT = 22
    WINDOWS_DS_PORT = 445
    managing_port = SSH_PORT
    if config.get_cloud_config_value('windows', vm_, __opts__) or \
            config.get_cloud_config_value('win_installer', vm_, __opts__):
        managing_port = WINDOWS_DS_PORT

    ssh_connect_timeout = config.get_cloud_config_value(
        'ssh_connect_timeout', vm_, __opts__, 15 * 60
    )
    connect_timeout = config.get_cloud_config_value(
        'connect_timeout', vm_, __opts__, ssh_connect_timeout
    )
    if not salt.utils.cloud.wait_for_port(ip_address,
                                          port=managing_port,
                                          timeout=connect_timeout):
        raise SaltCloudSystemExit(
            'Failed to authenticate against remote ssh'
        )

    pass_conn = get_conn(service='SoftLayer_Account')
    mask = {
        'virtualGuests': {
            'powerState': '',
            'operatingSystem': {
                'passwords': ''
            },
        },
    }

    def get_credentials():
        '''
        Wait for the password to become available
        '''
        node_info = pass_conn.getVirtualGuests(id=response['id'], mask=mask)
        for node in node_info:
            if node['id'] == response['id'] and \
                            'passwords' in node['operatingSystem'] and \
                            len(node['operatingSystem']['passwords']) > 0:
                return node['operatingSystem']['passwords'][0]['username'], node['operatingSystem']['passwords'][0]['password']
        time.sleep(5)
        return False

    username, passwd = salt.utils.cloud.wait_for_fun(  # pylint: disable=W0633
        get_credentials,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )
    response['username'] = username
    response['password'] = passwd
    response['public_ip'] = ip_address

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default=username
    )

    vm_['ssh_host'] = ip_address
    vm_['password'] = passwd
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    ret.update(response)

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )

    return ret


def list_nodes_full(mask='mask[id]', call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    ret = {}
    conn = get_conn(service='SoftLayer_Account')
    response = conn.getVirtualGuests()
    for node_id in response:
        ret[node_id['hostname']] = node_id
    salt.utils.cloud.cache_node_list(ret, __active_provider_name__.split(':')[0], __opts__)
    return ret


def list_nodes(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    nodes = list_nodes_full()
    if 'error' in nodes:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                nodes['error']['Errors']['Error']['Message']
            )
        )
    for node in nodes:
        ret[node] = {
            'id': nodes[node]['hostname'],
            'ram': nodes[node]['maxMemory'],
            'cpus': nodes[node]['maxCpu'],
        }
        if 'primaryIpAddress' in nodes[node]:
            ret[node]['public_ips'] = nodes[node]['primaryIpAddress']
        if 'primaryBackendIpAddress' in nodes[node]:
            ret[node]['private_ips'] = nodes[node]['primaryBackendIpAddress']
        if 'status' in nodes[node]:
            ret[node]['state'] = str(nodes[node]['status']['name'])
    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__['query.selection'], call,
    )


def show_instance(name, call=None):
    '''
    Show the details from SoftLayer concerning a guest
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    nodes = list_nodes_full()
    salt.utils.cloud.cache_node(nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def destroy(name, call=None):
    '''
    Destroy a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    node = show_instance(name, call='action')
    conn = get_conn()
    response = conn.deleteObject(id=node['id'])

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )
    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return response


def list_vlans(call=None):
    '''
    List all VLANs associated with the account
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_vlans function must be called with -f or --function.'
        )

    conn = get_conn(service='SoftLayer_Account')
    return conn.getNetworkVlans()
