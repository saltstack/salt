# -*- coding: utf-8 -*-
'''
SoftLayer HW Cloud Module
=========================

The SoftLayer HW cloud module is used to control access to the SoftLayer
hardware cloud system

Use of this module only requires the ``apikey`` parameter. Set up the cloud
configuration at:

``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/softlayer.conf``:

.. code-block:: yaml

    my-softlayer-config:
      # SoftLayer account api key
      user: MYLOGIN
      apikey: JVkbSJDGHSDKUKSDJfhsdklfjgsjdkflhjlsdfffhgdgjkenrtuinv
      provider: softlayer_hw

The SoftLayer Python Library needs to be installed in order to use the
SoftLayer salt.cloud modules. See: https://pypi.python.org/pypi/SoftLayer

:depends: softlayer
'''
# pylint: disable=E0102

from __future__ import absolute_import

# Import python libs
import copy
import pprint
import logging
import time

# Import salt cloud libs
import salt.config as config
from salt.exceptions import SaltCloudSystemExit
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
from salt.utils import namespaced_function

# Attempt to import softlayer lib
try:
    import SoftLayer
    HAS_SLLIBS = True
except ImportError:
    HAS_SLLIBS = False

# Get logging started
log = logging.getLogger(__name__)


# Redirect SoftLayer functions to this module namespace
script = namespaced_function(script, globals())


# Only load in this module if the SoftLayer configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for SoftLayer configurations.
    '''
    if not HAS_SLLIBS:
        return False

    if get_configured_provider() is False:
        return False

    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'softlayer_hw',
        ('apikey',)
    )


def get_conn(service='SoftLayer_Hardware'):
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
    conn = get_conn(service='SoftLayer_Product_Package')

    locations = conn.getLocations(id=50)
    for location in locations:
        ret[location['id']] = {
            'id': location['id'],
            'name': location['name'],
            'location': location['longName'],
        }

    available = conn.getAvailableLocations(id=50)
    for location in available:
        ret[location['locationId']]['available'] = True

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
        'Bare Metal Instance': {
            '1921': {
                'id': '1921',
                'name': '2 x 2.0 GHz Core Bare Metal Instance - 2 GB Ram'},
            '1922': {
                'id': '1922',
                'name': '4 x 2.0 GHz Core Bare Metal Instance - 4 GB Ram'},
            '1923': {
                'id': '1923',
                'name': '8 x 2.0 GHz Core Bare Metal Instance - 8 GB Ram'},
            '1924': {
                'id': '1924',
                'name': '16 x 2.0 GHz Core Bare Metal Instance - 16 GB Ram'},
            '2164': {
                'id': '2164',
                'name': '2 x 2.0 GHz Core Bare Metal Instance - 8 GB Ram '},
            '2165': {
                'id': '2165',
                'name': '4 x 2.0 GHz Core Bare Metal Instance - 16 GB Ram'},
            '2166': {
                'id': '2166',
                'name': '8 x 2.0 GHz Core Bare Metal Instance - 32 GB Ram'},
            '2167': {
                'id': '2167',
                'name': '16 x 2.0 GHz Core Bare Metal Instance - 64 GB Ram'},
            }
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

    ret = {'Operating System': {
        '13962': {
            'id': '13962',
            'name': 'CentOS 6.0 - Minimal Install (32 bit)'},
        '13963': {
            'id': '13963',
            'name': 'CentOS 6.0 - Minimal Install (64 bit)'},
        '13960': {
            'id': '13960',
            'name': 'CentOS 6.0 - LAMP Install (32 bit)'},
        '13961': {
            'id': '13961',
            'name': 'CentOS 6.0 - LAMP Install (64 bit)'},
        '1930': {
            'id': '1930',
            'name': 'CentOS 5 - Minimal Install (32 bit)'},
        '1931': {
            'id': '1931',
            'name': 'CentOS 5 - Minimal Install (64 bit)'},
        '1928': {
            'id': '1928',
            'name': 'CentOS 5 - LAMP Install (32 bit)'},
        '1929': {
            'id': '1929',
            'name': 'CentOS 5 - LAMP Install (64 bit)'},
        '14075': {
            'id': '14075',
            'name': 'Debian GNU/Linux 6.0 Squeeze/Stable - Minimal Install (32 bit)'},
        '14077': {
            'id': '14077',
            'name': 'Debian GNU/Linux 6.0 Squeeze/Stable - Minimal Install (64 bit)'},
        '14074': {
            'id': '14074',
            'name': 'Debian GNU/Linux 6.0 Squeeze/Stable - LAMP Install (32 bit)'},
        '14076': {
            'id': '14076',
            'name': 'Debian GNU/Linux 6.0 Squeeze/Stable - LAMP Install (64 bit)'},
        '21774': {
            'id': '21774',
            'name': 'CloudLinux 6 (32 bit)'},
        '21777': {
            'id': '21777',
            'name': 'CloudLinux 6 (64 bit)'},
        '21768': {
            'id': '21768',
            'name': 'CloudLinux 5 (32 bit)'},
        '21771': {
            'id': '21771',
            'name': 'CloudLinux 5 (64 bit)'},
        '22247': {
            'id': '22247',
            'name': 'Debian GNU/Linux 7.0 Wheezy/Stable - Minimal Install (32 bit)'},
        '22251': {
            'id': '22251',
            'name': 'Debian GNU/Linux 7.0 Wheezy/Stable - Minimal Install (64 bit)'},
        '21265': {
            'id': '21265',
            'name': 'FreeBSD 9 Latest (32 bit)'},
        '21269': {
            'id': '21269',
            'name': 'FreeBSD 9 Latest (64 bit)'},
        '21257': {
            'id': '21257',
            'name': 'FreeBSD 8 Latest (32 bit)'},
        '21261': {
            'id': '21261',
            'name': 'FreeBSD 8 Latest (64 bit)'},
        '2143': {
            'id': '2143',
            'name': 'Ubuntu Linux 10.04 LTS Lucid Lynx - Minimal Install (32 bit)'},
        '2145': {
            'id': '2145',
            'name': 'Ubuntu Linux 10.04 LTS Lucid Lynx - Minimal Install (64 bit)'},
        '2138': {
            'id': '2138',
            'name': 'Ubuntu Linux 10.04 LTS Lucid Lynx - LAMP Install (32 bit)'},
        '2141': {
            'id': '2141',
            'name': 'Ubuntu Linux 10.04 LTS Lucid Lynx - LAMP Install (64 bit)'},
        '17436': {
            'id': '17436',
            'name': 'Ubuntu Linux 12.04 LTS Precise Pangolin - Minimal Install (32 bit)'},
        '17438': {
            'id': '17438',
            'name': 'Ubuntu Linux 12.04 LTS Precise Pangolin - Minimal Install (64 bit)'},
        '17432': {
            'id': '17432',
            'name': 'Ubuntu Linux 12.04 LTS Precise Pangolin - LAMP Install (32 bit)'},
        '17434': {
            'id': '17434',
            'name': 'Ubuntu Linux 12.04 LTS Precise Pangolin - LAMP Install (64 bit)'},
        '20948': {
            'id': '20948',
            'name': 'Windows Server 2012 Standard Edition (64 bit)'},
        '21074': {
            'id': '21074',
            'name': 'Windows Server 2008 Standard SP1 with R2 (64 bit)'},
        '1857': {
            'id': '1857',
            'name': 'Windows Server 2008 R2 Standard Edition (64bit)'},
        '1860': {
            'id': '1860',
            'name': 'Windows Server 2008 R2 Enterprise Edition (64bit)'},
        '1742': {
            'id': '1742',
            'name': 'Windows Server 2008 Standard Edition SP2 (32bit)'},
        '1752': {
            'id': '1752',
            'name': 'Windows Server 2008 Standard Edition SP2 (64bit)'},
        '1756': {
            'id': '1756',
            'name': 'Windows Server 2008 Enterprise Edition SP2 (32bit)'},
        '1761': {
            'id': '1761',
            'name': 'Windows Server 2008 Enterprise Edition SP2 (64bit)'},
        '1766': {
            'id': '1766',
            'name': 'Windows Server 2008 Datacenter Edition SP2 (32bit)'},
        '1770': {
            'id': '1770',
            'name': 'Windows Server 2008 Datacenter Edition SP2 (64bit)'},
        '21060': {
            'id': '21060',
            'name': 'Windows Server 2012 Datacenter Edition With Hyper-V (64bit)'},
        '20971': {
            'id': '20971',
            'name': 'Windows Server 2012 Datacenter Edition (64bit)'},
        '21644': {
            'id': '21644',
            'name': 'Windows Server 2008 R2 Datacenter Edition With Hyper-V (64bit)'},
        '13866': {
            'id': '13866',
            'name': 'Windows Server 2008 R2 Datacenter Edition (64bit)'},
        '1700': {
            'id': '1700',
            'name': 'Windows Server 2003 Standard SP2 with R2 (32 bit)'},
        '1701': {
            'id': '1701',
            'name': 'Windows Server 2003 Standard SP2 with R2 (64 bit)'},
        '1716': {
            'id': '1716',
            'name': 'Windows Server 2003 Datacenter SP2 with R2 (32 bit)'},
        '1715': {
            'id': '1715',
            'name': 'Windows Server 2003 Datacenter SP2 with R2 (64 bit)'},
        '1702': {
            'id': '1702',
            'name': 'Windows Server 2003 Enterprise SP2 with R2 (32 bit)'},
        '1703': {
            'id': '1703',
            'name': 'Windows Server 2003 Enterprise SP2 with R2 (64 bit)'},
        '22418': {
            'id': '22418',
            'name': 'Citrix XenServer 6.2'},
        '21133': {
            'id': '21133',
            'name': 'Citrix XenServer 6.1'},
        '17228': {
            'id': '17228',
            'name': 'Citrix XenServer 6.0.2'},
        '14059': {
            'id': '14059',
            'name': 'Citrix XenServer 6.0.0'},
        '13891': {
            'id': '13891',
            'name': 'Citrix XenServer 5.6.2'},
        '2380': {
            'id': '2380',
            'name': 'Citrix XenServer 5.6.1'},
        '2214': {
            'id': '2214',
            'name': 'Citrix XenServer 5.6'},
        '1806': {
            'id': '1806',
            'name': 'Citrix XenServer 5.5'},
        '21158': {
            'id': '21158',
            'name': 'VMware ESXi 5.1'},
        '14048': {
            'id': '14048',
            'name': 'VMware ESX 4.1'},
        '2032': {
            'id': '2032',
            'name': 'VMware ESX 4.0'},
        '21396': {
            'id': '21396',
            'name': 'Vyatta 6.5 Community Edition (64 bit)'},
        '22177': {
            'id': '22177',
            'name': 'Vyatta 6.x Subscription Edition (64 bit)'},
        }
    }
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
    conn = get_conn(service='SoftLayer_Product_Order')
    kwargs = {
        'complexType': 'SoftLayer_Container_Product_Order_Hardware_Server',
        'quantity': 1,
        'hardware': [{
            'hostname': vm_['name'],
            'domain': vm_['domain'],
        }],
        'packageId': 50,  # Baremetal Package
        'prices': [
            # Size Ex: 1921: 2 x 2.0 GHz Core Bare Metal Instance - 2 GB Ram
            {'id': vm_['size']},
            # HDD Ex: 19: 250GB SATA II
            {'id': vm_['hdd']},
            # Image Ex: 13963: CentOS 6.0 - Minimal Install (64 bit)
            {'id': vm_['image']},

            # The following items are currently required
            # Reboot / Remote Console
            {'id': '905'},
            # 1 IP Address
            {'id': '21'},
            # Host Ping Monitoring
            {'id': '55'},
            # Email and Ticket Notifications
            {'id': '57'},
            # Automated Notification Response
            {'id': '58'},
            # Unlimited SSL VPN Users & 1 PPTP VPN User per account
            {'id': '420'},
            # Nessus Vulnerability Assessment & Reporting
            {'id': '418'},
        ],
    }

    optional_products = config.get_cloud_config_value(
        'optional_products', vm_, __opts__, default=True
    )
    for product in optional_products:
        kwargs['prices'].append({'id': product})

    # Default is 273 (100 Mbps Public & Private Networks)
    port_speed = config.get_cloud_config_value(
        'port_speed', vm_, __opts__, default=273
    )
    kwargs['prices'].append({'id': port_speed})

    # Default is 248 (5000 GB Bandwidth)
    bandwidth = config.get_cloud_config_value(
        'bandwidth', vm_, __opts__, default=248
    )
    kwargs['prices'].append({'id': bandwidth})

    vlan_id = config.get_cloud_config_value(
        'vlan', vm_, __opts__, default=False
    )
    if vlan_id:
        kwargs['primaryNetworkComponent'] = {
            'networkVlan': {
                'id': vlan_id,
            }
        }

    location = get_location(vm_)
    if location:
        kwargs['location'] = location

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    try:
        response = conn.placeOrder(kwargs)
        # Leaving the following line in, commented, for easy debugging
        #response = conn.verifyOrder(kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on SoftLayer\n\n'
            'The following exception was thrown by libcloud when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    def wait_for_ip():
        '''
        Wait for the IP address to become available
        '''
        nodes = list_nodes_full()
        if 'primaryIpAddress' in nodes[vm_['name']]:
            return nodes[vm_['name']]['primaryIpAddress']
        time.sleep(1)
        return False

    ip_address = salt.utils.cloud.wait_for_fun(
        wait_for_ip,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )

    ssh_connect_timeout = config.get_cloud_config_value(
        'ssh_connect_timeout', vm_, __opts__, 900   # 15 minutes
    )
    if not salt.utils.cloud.wait_for_port(ip_address,
                                         timeout=ssh_connect_timeout):
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

    def get_passwd():
        '''
        Wait for the password to become available
        '''
        node_info = pass_conn.getVirtualGuests(id=response['id'], mask=mask)
        for node in node_info:
            if node['id'] == response['id']:
                if 'passwords' in node['operatingSystem'] and len(node['operatingSystem']['passwords']) > 0:
                    return node['operatingSystem']['passwords'][0]['password']
        time.sleep(5)
        return False

    passwd = salt.utils.cloud.wait_for_fun(
        get_passwd,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )
    response['password'] = passwd
    response['public_ip'] = ip_address

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    ret = {}
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'opts': __opts__,
            'host': ip_address,
            'username': ssh_username,
            'password': passwd,
            'script': deploy_script.script,
            'name': vm_['name'],
            'tmp_dir': config.get_cloud_config_value(
                'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
            ),
            'deploy_command': config.get_cloud_config_value(
                'deploy_command', vm_, __opts__,
                default='/tmp/.saltcloud/deploy.sh',
            ),
            'start_action': __opts__['start_action'],
            'parallel': __opts__['parallel'],
            'sock_dir': __opts__['sock_dir'],
            'conf_file': __opts__['conf_file'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
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
            'script_env': config.get_cloud_config_value('script_env', vm_, __opts__),
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

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(response)
        )
    )

    ret.update(response)

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


def list_nodes_full(mask='mask[id, hostname, primaryIpAddress, \
        primaryBackendIpAddress, processorPhysicalCoreAmount, memoryCount]',
        call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    ret = {}
    conn = get_conn(service='SoftLayer_Account')
    response = conn.getHardware(mask=mask)

    for node in response:
        ret[node['hostname']] = node
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
            'ram': nodes[node]['memoryCount'],
            'cpus': nodes[node]['processorPhysicalCoreAmount'],
        }
        if 'primaryIpAddress' in nodes[node]:
            ret[node]['public_ips'] = nodes[node]['primaryIpAddress']
        if 'primaryBackendIpAddress' in nodes[node]:
            ret[node]['private_ips'] = nodes[node]['primaryBackendIpAddress']
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
    conn = get_conn(service='SoftLayer_Ticket')
    response = conn.createCancelServerTicket(
        {
            'id': node['id'],
            'reason': 'Salt Cloud Hardware Server Cancellation',
            'content': 'Please cancel this server',
            'cancelAssociatedItems': True,
            'attachmentType': 'HARDWARE',
        }
    )

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
