# -*- coding: utf-8 -*-
'''
Kamatera Cloud Module
=========================

The Kamatera cloud module is used to control access to the Kamatera cloud.

USe of this module requires an API key and secret which you can by visiting
https://console.kamatera.com and adding a new key under API Keys.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-kamatera-config:
      driver: kamatera
      api_client_id: xxxxxxxxxxxxx
      api_secret: yyyyyyyyyyyyyyyyyyyyyy

'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import pprint
import re
import time
import datetime

# Import Salt Libs
import salt.config as config
from salt.ext import six
from salt.ext.six.moves import range
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudNotFound,
    SaltCloudSystemExit
)

# Get logging started
log = logging.getLogger(__name__)

# Human-readable status fields (documentation: https://www.linode.com/api/linode/linode.list)
LINODE_STATUS = {
    'boot_failed': {
        'code': -2,
        'descr': 'Boot Failed (not in use)',
    },
    'beeing_created': {
        'code': -1,
        'descr': 'Being Created',
    },
    'brand_new': {
        'code': 0,
        'descr': 'Brand New',
    },
    'running': {
        'code': 1,
        'descr': 'Running',
    },
    'poweroff': {
        'code': 2,
        'descr': 'Powered Off',
    },
    'shutdown': {
        'code': 3,
        'descr': 'Shutting Down (not in use)',
    },
    'save_to_disk': {
        'code': 4,
        'descr': 'Saved to Disk (not in use)',
    },
}

__virtualname__ = 'kamatera'


# Only load in this module if the Linode configurations are in place
def __virtual__():
    '''
    Check for Linode configs.
    '''
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
        ('api_client_id', 'api_secret',)
    )


def avail_images(call=None):
    '''
    Return available Kamatera images for a given location.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-kamatera-config --location=EU
        salt-cloud -f avail_images my-kamatera-config --location=EU
    '''
    if call == 'action':
        raise SaltCloudException('The avail_images function must be called with -f or --function.')
    elif not __opts__.get('location'):
        raise SaltCloudException('A location must be specified using --location=LOCATION')
    else:
        return {
            image['id']: image['name']
            for image in _request('service/server?images=1&datacenter=%s' % __opts__['location'])
        }


def avail_sizes(call=None):
    '''
    Return available Kamatera CPU types for a given location.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes my-kamatera-config --location=EU
        salt-cloud -f avail_sizes my-kamatera-config --location=EU
    '''
    if call == 'action':
        raise SaltCloudException('The avail_sizes function must be called with -f or --function.')
    elif not __opts__.get('location'):
        raise SaltCloudException('A location must be specified using --location=LOCATION')
    else:
        return {
            cpuType['id']: {
                k: (
                    str(v) if k in ['ramMB', 'cpuCores'] else v
                ) for k, v in cpuType.items()
                if k != 'id'
            }
            for cpuType in _request('service/server?capabilities=1&datacenter=%s' % __opts__['location'])['cpuTypes']
        }


def avail_server_options(kwargs=None, call=None):
    '''
    Return available Kamatera server options for a given location.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f avail_server_options my-kamatera-config --location=EU
    '''
    if call != 'function':
        raise SaltCloudException('The avail_server_options function must be called with -f or --function.')
    elif not __opts__.get('location'):
        raise SaltCloudException('A location must be specified using --location=LOCATION')
    else:
        return {
            k: (str(v) if k == 'diskSizeGB' else v)
            for k, v in _request('service/server?capabilities=1&datacenter=%s' % __opts__['location']).items()
            if k not in ['cpuTypes', 'defaultMonthlyTrafficPackage']
        }


def avail_locations(call=None):
    '''
    Return available Kamatera datacenter locations.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-kamatera-config
        salt-cloud -f avail_locations my-kamatera-config
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )
    else:
        return {
            datacenter.pop('id'): '%s, %s (%s)' % (datacenter['subCategory'], datacenter['name'], datacenter['category'])
            for datacenter in _request('service/server?datacenter=1')
        }


def create(vm_):
    '''
    Create a single Kamatera server.
    '''
    name = vm_['name']
    profile = vm_.get('profile')
    if (not profile or not config.is_profile_configured(
        __opts__, __active_provider_name__ or 'kamatera', vm_['profile'], vm_=vm_)
    ):
        return False

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(name),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    log.info('Creating Cloud VM %s', name)

    def _getval(key, default=None):
        val = config.get_cloud_config_value(key, vm_, __opts__, default=None)
        if not val and default is None:
            raise SaltCloudException('missing required profile option: %s' % key)
        else:
            return val or default

    request_data = {
        "name": name,
        "password": _getval('password', '__generate__'),
        "passwordValidate": _getval('password', '__generate__'),
        'ssh-key': _getval('ssh_pub_key', ''),
        "datacenter": _getval('location'),
        "image": _getval('image'),
        "cpu": '%s%s' % (_getval('cpu_cores'), _getval('cpu_type')),
        "ram": _getval('ram_mb'),
        "disk": ' '.join([
            'size=%d' % disksize for disksize
            in [_getval('disk_size_gb')] + _getval('extra_disk_sizes_gb', [])
        ]),
        "dailybackup": 'yes' if _getval('daily_backup', False) else 'no',
        "managed": 'yes' if _getval('managed', False) else 'no',
        "network": ' '.join([','.join([
            '%s=%s' % (k, v) for k, v
            in network.items()]) for network in _getval('networks', [{'name': 'wan', 'ip': 'auto'}])]),
        "quantity": 1,
        "billingcycle": _getval('billing_cycle', 'hourly'),
        "monthlypackage": _getval('monthly_traffic_package', ''),
        "poweronaftercreate": 'yes'
    }
    response = _request('service/server', 'POST', request_data)
    if not _getval('password', ''):
        command_ids = response['commandIds']
        generated_password = response['password']
    else:
        command_ids = response
        generated_password = None
    if len(command_ids) != 1:
        raise SaltCloudException('invalid Kamatera response')
    command_id = command_ids[0]

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(name),
        args=__utils__['cloud.filter_event']('requesting', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    command = _wait_command(command_id, _getval)
    create_log = command['log']
    try:
        created_at = datetime.datetime.strptime(command['completed'], '%Y-%m-%d %H:%M:%S')
    except Exception:
        created_at = None
    name_lines = [line for line in create_log.split("\n") if line.startswith('Name: ')]
    if len(name_lines) != 1:
        raise SaltCloudException('invalid create log: ' + create_log)
    created_name = name_lines[0].replace('Name: ', '')
    tmp_servers = _list_servers(name_regex=created_name)
    if len(tmp_servers) != 1:
        raise SaltCloudException('invalid list servers response')
    server = tmp_servers[0]
    server['extra']['create_command'] = command
    server['extra']['created_at'] = created_at
    server['extra']['generated_password'] = generated_password
    public_ips = []
    private_ips = []
    for network in server['networks']:
        if network.get('network').startswith('wan-'):
            public_ips += network.get('ips', [])
        else:
            private_ips += network.get('ips', [])
    data = dict(
        image=_getval('image'),
        name=server['name'],
        size='%s%s-%smb-%sgb' % (server['cpu_cores'], server['cpu_type'], server['ram_mb'], server['disk_size_gb']),
        state=server['state'],
        private_ips=private_ips,
        public_ips=public_ips
    )
    # Pass the correct IP address to the bootstrap ssh_host key
    vm_['ssh_host'] = data['public_ips'][0]
    # If a password wasn't supplied in the profile or provider config, set it now.
    vm_['password'] = _getval('password', generated_password)
    # Make public_ips and private_ips available to the bootstrap script.
    vm_['public_ips'] = public_ips
    vm_['private_ips'] = private_ips

    # Send event that the instance has booted.
    __utils__['cloud.fire_event'](
        'event',
        'waiting for ssh',
        'salt/cloud/{0}/waiting_for_ssh'.format(name),
        sock_dir=__opts__['sock_dir'],
        args={'ip_address': vm_['ssh_host']},
        transport=__opts__['transport']
    )

    # Bootstrap!
    ret = __utils__['cloud.bootstrap'](vm_, __opts__)
    ret.update(data)

    log.info('Created Cloud VM \'%s\'', name)
    log.debug('\'%s\' VM creation details:\n%s', name, pprint.pformat(data))
    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(name),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def create_config(kwargs=None, call=None):
    '''
    Creates a Linode Configuration Profile.

    name
        The name of the VM to create the config for.

    linode_id
        The ID of the Linode to create the configuration for.

    root_disk_id
        The Root Disk ID to be used for this config.

    swap_disk_id
        The Swap Disk ID to be used for this config.

    data_disk_id
        The Data Disk ID to be used for this config.

    .. versionadded:: 2016.3.0

    kernel_id
        The ID of the kernel to use for this configuration profile.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The create_config function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    linode_id = kwargs.get('linode_id', None)
    root_disk_id = kwargs.get('root_disk_id', None)
    swap_disk_id = kwargs.get('swap_disk_id', None)
    data_disk_id = kwargs.get('data_disk_id', None)
    kernel_id = kwargs.get('kernel_id', None)

    if kernel_id is None:
        # 138 appears to always be the latest 64-bit kernel for Linux
        kernel_id = 138

    required_params = [name, linode_id, root_disk_id, swap_disk_id]
    for item in required_params:
        if item is None:
            raise SaltCloudSystemExit(
                'The create_config functions requires a \'name\', \'linode_id\', '
                '\'root_disk_id\', and \'swap_disk_id\'.'
            )

    disklist = '{0},{1}'.format(root_disk_id, swap_disk_id)
    if data_disk_id is not None:
        disklist = '{0},{1},{2}'.format(root_disk_id, swap_disk_id, data_disk_id)

    config_args = {'LinodeID': linode_id,
                   'KernelID': kernel_id,
                   'Label': name,
                   'DiskList': disklist
                  }

    result = _query('linode', 'config.create', args=config_args)

    return _clean_data(result)


def create_disk_from_distro(vm_, linode_id, swap_size=None):
    r'''
    Creates the disk for the Linode from the distribution.

    vm\_
        The VM profile to create the disk for.

    linode_id
        The ID of the Linode to create the distribution disk for. Required.

    swap_size
        The size of the disk, in MB.

    '''
    kwargs = {}

    if swap_size is None:
        swap_size = get_swap_size(vm_)

    pub_key = get_pub_key(vm_)
    root_password = get_password(vm_)

    if pub_key:
        kwargs.update({'rootSSHKey': pub_key})
    if root_password:
        kwargs.update({'rootPass': root_password})
    else:
        raise SaltCloudConfigError(
            'The Linode driver requires a password.'
        )

    kwargs.update({'LinodeID': linode_id,
                   'DistributionID': get_distribution_id(vm_),
                   'Label': vm_['name'],
                   'Size': get_disk_size(vm_, swap_size, linode_id)})

    result = _query('linode', 'disk.createfromdistribution', args=kwargs)

    return _clean_data(result)


def create_swap_disk(vm_, linode_id, swap_size=None):
    r'''
    Creates the disk for the specified Linode.

    vm\_
        The VM profile to create the swap disk for.

    linode_id
        The ID of the Linode to create the swap disk for.

    swap_size
        The size of the disk, in MB.
    '''
    kwargs = {}

    if not swap_size:
        swap_size = get_swap_size(vm_)

    kwargs.update({'LinodeID': linode_id,
                   'Label': vm_['name'],
                   'Type': 'swap',
                   'Size': swap_size
                  })

    result = _query('linode', 'disk.create', args=kwargs)

    return _clean_data(result)


def create_data_disk(vm_=None, linode_id=None, data_size=None):
    r'''
    Create a data disk for the linode (type is hardcoded to ext4 at the moment)

    .. versionadded:: 2016.3.0

    vm\_
        The VM profile to create the data disk for.

    linode_id
        The ID of the Linode to create the data disk for.

    data_size
        The size of the disk, in MB.

    '''
    kwargs = {}

    kwargs.update({'LinodeID': linode_id,
                   'Label': vm_['name']+"_data",
                   'Type': 'ext4',
                   'Size': data_size
                  })

    result = _query('linode', 'disk.create', args=kwargs)
    return _clean_data(result)


def create_private_ip(linode_id):
    r'''
    Creates a private IP for the specified Linode.

    linode_id
        The ID of the Linode to create the IP address for.
    '''
    kwargs = {'LinodeID': linode_id}
    result = _query('linode', 'ip.addprivate', args=kwargs)

    return _clean_data(result)


def destroy(name, call=None):
    '''
    Destroys a Linode by name.

    name
        The name of VM to be be destroyed.

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name
    '''
    if call == 'function':
        raise SaltCloudException(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    linode_id = get_linode_id_from_name(name)

    response = _query('linode', 'delete', args={'LinodeID': linode_id, 'skipChecks': True})

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], __opts__)

    return response


def get_config_id(kwargs=None, call=None):
    '''
    Returns a config_id for a given linode.

    .. versionadded:: 2015.8.0

    name
        The name of the Linode for which to get the config_id. Can be used instead
        of ``linode_id``.h

    linode_id
        The ID of the Linode for which to get the config_id. Can be used instead
        of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_config_id my-linode-config name=my-linode
        salt-cloud -f get_config_id my-linode-config linode_id=1234567
    '''
    if call == 'action':
        raise SaltCloudException(
            'The get_config_id function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    linode_id = kwargs.get('linode_id', None)
    if name is None and linode_id is None:
        raise SaltCloudSystemExit(
            'The get_config_id function requires either a \'name\' or a \'linode_id\' '
            'to be provided.'
        )
    if linode_id is None:
        linode_id = get_linode_id_from_name(name)

    response = _query('linode', 'config.list', args={'LinodeID': linode_id})['DATA']
    config_id = {'config_id': response[0]['ConfigID']}

    return config_id


def get_datacenter_id(location):
    '''
    Returns the Linode Datacenter ID.

    location
        The location, or name, of the datacenter to get the ID from.
    '''

    return avail_locations()[location]['DATACENTERID']


def get_disk_size(vm_, swap, linode_id):
    r'''
    Returns the size of of the root disk in MB.

    vm\_
        The VM to get the disk size for.
    '''
    disk_size = get_linode(kwargs={'linode_id': linode_id})['TOTALHD']
    return config.get_cloud_config_value(
        'disk_size', vm_, __opts__, default=disk_size - swap
    )


def get_data_disk_size(vm_, swap, linode_id):
    '''
    Return the size of of the data disk in MB

    .. versionadded:: 2016.3.0
    '''
    disk_size = get_linode(kwargs={'linode_id': linode_id})['TOTALHD']
    root_disk_size = config.get_cloud_config_value(
        'disk_size', vm_, __opts__, default=disk_size - swap
    )
    return disk_size - root_disk_size - swap


def get_distribution_id(vm_):
    r'''
    Returns the distribution ID for a VM

    vm\_
        The VM to get the distribution ID for
    '''
    distributions = _query('avail', 'distributions')['DATA']
    vm_image_name = config.get_cloud_config_value('image', vm_, __opts__)

    distro_id = ''

    for distro in distributions:
        if vm_image_name == distro['LABEL']:
            distro_id = distro['DISTRIBUTIONID']
            return distro_id

    if not distro_id:
        raise SaltCloudNotFound(
            'The DistributionID for the \'{0}\' profile could not be found.\n'
            'The \'{1}\' instance could not be provisioned. The following distributions '
            'are available:\n{2}'.format(
                vm_image_name,
                vm_['name'],
                pprint.pprint(sorted([distro['LABEL'].encode(__salt_system_encoding__) for distro in distributions]))
            )
        )


def get_ips(linode_id=None):
    '''
    Returns public and private IP addresses.

    linode_id
        Limits the IP addresses returned to the specified Linode ID.
    '''
    if linode_id:
        ips = _query('linode', 'ip.list', args={'LinodeID': linode_id})
    else:
        ips = _query('linode', 'ip.list')

    ips = ips['DATA']
    ret = {}

    for item in ips:
        node_id = six.text_type(item['LINODEID'])
        if item['ISPUBLIC'] == 1:
            key = 'public_ips'
        else:
            key = 'private_ips'

        if ret.get(node_id) is None:
            ret.update({node_id: {'public_ips': [], 'private_ips': []}})
        ret[node_id][key].append(item['IPADDRESS'])

    # If linode_id was specified, only return the ips, and not the
    # dictionary based on the linode ID as a key.
    if linode_id:
        _all_ips = {'public_ips': [], 'private_ips': []}
        matching_id = ret.get(six.text_type(linode_id))
        if matching_id:
            _all_ips['private_ips'] = matching_id['private_ips']
            _all_ips['public_ips'] = matching_id['public_ips']

        ret = _all_ips

    return ret


def get_linode(kwargs=None, call=None):
    '''
    Returns data for a single named Linode.

    name
        The name of the Linode for which to get data. Can be used instead
        ``linode_id``. Note this will induce an additional API call
        compared to using ``linode_id``.

    linode_id
        The ID of the Linode for which to get data. Can be used instead of
        ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_linode my-linode-config name=my-instance
        salt-cloud -f get_linode my-linode-config linode_id=1234567
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The get_linode function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    name = kwargs.get('name', None)
    linode_id = kwargs.get('linode_id', None)
    if name is None and linode_id is None:
        raise SaltCloudSystemExit(
            'The get_linode function requires either a \'name\' or a \'linode_id\'.'
        )

    if linode_id is None:
        linode_id = get_linode_id_from_name(name)

    result = _query('linode', 'list', args={'LinodeID': linode_id})

    return result['DATA'][0]


def get_linode_id_from_name(name):
    '''
    Returns the Linode ID for a VM from the provided name.

    name
        The name of the Linode from which to get the Linode ID. Required.
    '''
    nodes = _query('linode', 'list')['DATA']

    linode_id = ''
    for node in nodes:
        if name == node['LABEL']:
            linode_id = node['LINODEID']
            return linode_id

    if not linode_id:
        raise SaltCloudNotFound(
            'The specified name, {0}, could not be found.'.format(name)
        )


def _decode_linode_plan_label(label):
    '''
    Attempts to decode a user-supplied Linode plan label
    into the format in Linode API output

    label
        The label, or name, of the plan to decode.

    Example:
        `Linode 2048` will decode to `Linode 2GB`
    '''
    sizes = avail_sizes()

    if label not in sizes:
        if 'GB' in label:
            raise SaltCloudException(
                'Invalid Linode plan ({}) specified - call avail_sizes() for all available options'.format(label)
            )
        else:
            plan = label.split()

            if len(plan) != 2:
                raise SaltCloudException(
                    'Invalid Linode plan ({}) specified - call avail_sizes() for all available options'.format(label)
                )

            plan_type = plan[0]
            try:
                plan_size = int(plan[1])
            except TypeError:
                plan_size = 0
                log.debug('Failed to decode Linode plan label in Cloud Profile: %s', label)

            if plan_type == 'Linode' and plan_size == 1024:
                plan_type = 'Nanode'

            plan_size = plan_size/1024
            new_label = "{} {}GB".format(plan_type, plan_size)

            if new_label not in sizes:
                raise SaltCloudException(
                    'Invalid Linode plan ({}) specified - call avail_sizes() for all available options'.format(new_label)
                )

            log.warning(
                'An outdated Linode plan label was detected in your Cloud '
                'Profile (%s). Please update the profile to use the new '
                'label format (%s) for the requested Linode plan size.',
                label, new_label
            )

            label = new_label

    return sizes[label]['PLANID']


def get_private_ip(vm_):
    '''
    Return True if a private ip address is requested
    '''
    return config.get_cloud_config_value(
        'assign_private_ip', vm_, __opts__, default=False
    )


def get_data_disk(vm_):
    '''
    Return True if a data disk is requested

    .. versionadded:: 2016.3.0
    '''
    return config.get_cloud_config_value(
        'allocate_data_disk', vm_, __opts__, default=False
    )


def get_pub_key(vm_):
    r'''
    Return the SSH pubkey.

    vm\_
        The configuration to obtain the public key from.
    '''
    return config.get_cloud_config_value(
        'ssh_pubkey', vm_, __opts__, search_global=False
    )


def get_swap_size(vm_):
    r'''
    Returns the amoutn of swap space to be used in MB.

    vm\_
        The VM profile to obtain the swap size from.
    '''
    return config.get_cloud_config_value(
        'swap', vm_, __opts__, default=128
    )


def get_vm_size(vm_):
    r'''
    Returns the VM's size.

    vm\_
        The VM to get the size for.
    '''
    vm_size = config.get_cloud_config_value('size', vm_, __opts__)
    ram = avail_sizes()[vm_size]['RAM']

    if vm_size.startswith('Linode'):
        vm_size = vm_size.replace('Linode ', '')

    if ram == int(vm_size):
        return ram
    else:
        raise SaltCloudNotFound(
            'The specified size, {0}, could not be found.'.format(vm_size)
        )


def list_nodes(call=None):
    '''
    Returns a list of linodes, keeping only a brief listing.

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud --query
        salt-cloud -f list_nodes my-linode-config

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    '''
    if call == 'action':
        raise SaltCloudException(
            'The list_nodes function must be called with -f or --function.'
        )
    return _list_linodes(full=False)


def list_nodes_full(call=None):
    '''
    List linodes, with all available information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query
        salt-cloud -f list_nodes_full my-linode-config

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    '''
    if call == 'action':
        raise SaltCloudException(
            'The list_nodes_full function must be called with -f or --function.'
        )
    return _list_linodes(full=True)


def list_nodes_min(call=None):
    '''
    Return a list of the VMs that are on the provider. Only a list of VM names and
    their state is returned. This is the minimum amount of information needed to
    check for existing VMs.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-linode-config
        salt-cloud --function list_nodes_min my-linode-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )

    ret = {}
    nodes = _query('linode', 'list')['DATA']

    for node in nodes:
        name = node['LABEL']
        this_node = {
            'id': six.text_type(node['LINODEID']),
            'state': _get_status_descr_by_id(int(node['STATUS']))
        }

        ret[name] = this_node

    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields.
    '''
    return __utils__['cloud.list_nodes_select'](
        list_nodes_full(), __opts__['query.selection'], call,
    )


def reboot(name, call=None):
    '''
    Reboot a linode.

    .. versionadded:: 2015.8.0

    name
        The name of the VM to reboot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    '''
    if call != 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )

    node_id = get_linode_id_from_name(name)
    response = _query('linode', 'reboot', args={'LinodeID': node_id})
    data = _clean_data(response)
    reboot_jid = data['JobID']

    if not _wait_for_job(node_id, reboot_jid):
        log.error('Reboot failed for %s.', name)
        return False

    return data


def show_instance(name, call=None):
    '''
    Displays details about a particular Linode VM. Either a name or a linode_id must
    be provided.

    .. versionadded:: 2015.8.0

    name
        The name of the VM for which to display details.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance vm_name

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    '''
    if call != 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )

    node_id = get_linode_id_from_name(name)
    node_data = get_linode(kwargs={'linode_id': node_id})
    ips = get_ips(node_id)
    state = int(node_data['STATUS'])

    ret = {'id': node_data['LINODEID'],
           'image': node_data['DISTRIBUTIONVENDOR'],
           'name': node_data['LABEL'],
           'size': node_data['TOTALRAM'],
           'state': _get_status_descr_by_id(state),
           'private_ips': ips['private_ips'],
           'public_ips': ips['public_ips']}

    return ret


def show_pricing(kwargs=None, call=None):
    '''
    Show pricing for a particular profile. This is only an estimate, based on
    unofficial pricing sources.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f show_pricing my-linode-config profile=my-linode-profile
    '''
    if call != 'function':
        raise SaltCloudException(
            'The show_instance action must be called with -f or --function.'
        )

    profile = __opts__['profiles'].get(kwargs['profile'], {})
    if not profile:
        raise SaltCloudNotFound(
            'The requested profile was not found.'
        )

    # Make sure the profile belongs to Linode
    provider = profile.get('provider', '0:0')
    comps = provider.split(':')
    if len(comps) < 2 or comps[1] != 'linode':
        raise SaltCloudException(
            'The requested profile does not belong to Linode.'
        )

    plan_id = get_plan_id(kwargs={'label': profile['size']})
    response = _query('avail', 'linodeplans', args={'PlanID': plan_id})['DATA'][0]

    ret = {}
    ret['per_hour'] = response['HOURLY']
    ret['per_day'] = ret['per_hour'] * 24
    ret['per_week'] = ret['per_day'] * 7
    ret['per_month'] = response['PRICE']
    ret['per_year'] = ret['per_month'] * 12

    return {profile['profile']: ret}


def start(name, call=None):
    '''
    Start a VM in Linode.

    name
        The name of the VM to start.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    if call != 'action':
        raise SaltCloudException(
            'The start action must be called with -a or --action.'
        )

    node_id = get_linode_id_from_name(name)
    node = get_linode(kwargs={'linode_id': node_id})

    if node['STATUS'] == 1:
        return {'success': True,
                'action': 'start',
                'state': 'Running',
                'msg': 'Machine already running'}

    response = _query('linode', 'boot', args={'LinodeID': node_id})['DATA']

    if _wait_for_job(node_id, response['JobID']):
        return {'state': 'Running',
                'action': 'start',
                'success': True}
    else:
        return {'action': 'start',
                'success': False}


def stop(name, call=None):
    '''
    Stop a VM in Linode.

    name
        The name of the VM to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    if call != 'action':
        raise SaltCloudException(
            'The stop action must be called with -a or --action.'
        )

    node_id = get_linode_id_from_name(name)
    node = get_linode(kwargs={'linode_id': node_id})

    if node['STATUS'] == 2:
        return {'success': True,
                'state': 'Stopped',
                'msg': 'Machine already stopped'}

    response = _query('linode', 'shutdown', args={'LinodeID': node_id})['DATA']

    if _wait_for_job(node_id, response['JobID']):
        return {'state': 'Stopped',
                'action': 'stop',
                'success': True}
    else:
        return {'action': 'stop',
                'success': False}


def update_linode(linode_id, update_args=None):
    '''
    Updates a Linode's properties.

    linode_id
        The ID of the Linode to shutdown. Required.

    update_args
        The args to update the Linode with. Must be in dictionary form.
    '''
    update_args.update({'LinodeID': linode_id})

    result = _query('linode', 'update', args=update_args)

    return _clean_data(result)


def _clean_data(api_response):
    '''
    Returns the DATA response from a Linode API query as a single pre-formatted dictionary

    api_response
        The query to be cleaned.
    '''
    data = {}
    data.update(api_response['DATA'])

    if not data:
        response_data = api_response['DATA']
        data.update(response_data)

    return data


def _list_linodes(full=False):
    '''
    Helper function to format and parse linode data
    '''
    nodes = _query('linode', 'list')['DATA']
    ips = get_ips()

    ret = {}
    for node in nodes:
        this_node = {}
        linode_id = six.text_type(node['LINODEID'])

        this_node['id'] = linode_id
        this_node['image'] = node['DISTRIBUTIONVENDOR']
        this_node['name'] = node['LABEL']
        this_node['size'] = node['TOTALRAM']

        state = int(node['STATUS'])
        this_node['state'] = _get_status_descr_by_id(state)

        for key, val in six.iteritems(ips):
            if key == linode_id:
                this_node['private_ips'] = val['private_ips']
                this_node['public_ips'] = val['public_ips']

        if full:
            this_node['extra'] = node

        ret[node['LABEL']] = this_node

    return ret


def _request(path, method='GET', request_data=None):
    '''
    Make a web call to the Kamatera API.
    '''
    vm_ = get_configured_provider()
    api_client_id = config.get_cloud_config_value(
        'api_client_id', vm_, __opts__, search_global=False,
    )
    api_secret = config.get_cloud_config_value(
        'api_secret', vm_, __opts__, search_global=False,
    )
    api_url = config.get_cloud_config_value(
        'api_url', vm_, __opts__, search_global=False, default='https://cloudcli.cloudwm.com',
    )
    url = api_url.strip('/') + '/' + path.strip('/')
    headers = dict(AuthClientId=api_client_id, AuthSecret=api_secret, Accept='application/json')
    headers['Content-Type'] = 'application/json'
    headers['X-CLOUDCLI-STATUSINJSON'] = 'true'
    result = __utils__['http.query'](
        url,
        method,
        data=__utils__['json.dumps'](request_data) if request_data is not None else None,
        header_dict=headers,
        decode=True,
        decode_type='json',
        text=True,
        status=True,
        opts=__opts__,
    )
    if result['status'] != 200 or result.get('error') or not result.get('dict'):
        raise SaltCloudException(result.get('error') or 'Unexpected response from Kamatera API')
    elif result['dict']['status'] != 200:
        try:
            message = result['dict']['response']['message']
        except Exception:
            message = 'Unexpected response from Kamatera API (status=%s)' % result['dict']['status']
        raise SaltCloudException(message)
    else:
        return result['dict']['response']


def _get_command_status(command_id):
    response = _request('/service/queue?id=' + str(command_id))
    if len(response) != 1:
        raise SaltCloudException('invalid response for command id ' + str(command_id))
    return response[0]


def _wait_command(command_id, _getval):
    wait_poll_interval_seconds = _getval('wait_poll_interval_seconds', 2)
    wait_timeout_seconds = _getval('wait_timeout_seconds', 600)
    start_time = datetime.datetime.now()
    time.sleep(wait_poll_interval_seconds)
    while True:
        max_time = start_time + datetime.timedelta(seconds=wait_timeout_seconds)
        if max_time < datetime.datetime.now():
            raise SaltCloudException('Timeout waiting for command (timeout_seconds=%s, command_id=%s)' % (str(wait_timeout_seconds), str(command_id)))
        time.sleep(wait_poll_interval_seconds)
        command = _get_command_status(command_id)
        status = command.get('status')
        if status == 'complete':
            return command
        elif status == 'error':
            raise SaltCloudException('Command failed: ' + command.get('log'))


def _list_servers(name_regex=None, names=None):
    request_data = {'allow-no-servers': True}
    if names:
        servers = []
        for name in names:
            for server in _list_servers(name_regex=name):
                servers.append(server)
        return servers
    else:
        if not name_regex:
            name_regex = '.*'
        request_data['name'] = name_regex
    return list(map(_get_server, _request('/service/server/info', method='POST', request_data=request_data)))


def _get_server(server):
    server_cpu = server.pop('cpu')
    server_disk_sizes = server.pop('diskSizes')
    res_server = dict(
        id=server.pop('id'),
        name=server.pop('name'),
        state='running' if server.pop('power') == 'on' else 'stopped',
        datacenter=server.pop('datacenter'),
        cpu_type=server_cpu[-1],
        cpu_cores=int(server_cpu[:-1]),
        ram_mb=int(server.pop('ram')),
        disk_size_gb=int(server_disk_sizes[0]),
        extra_disk_sizes_gb=list(map(int, server_disk_sizes[1:])),
        networks=server.pop('networks'),
        daily_backup=server.pop('backup') == "1",
        managed=server.pop('managed') == "1",
        billing_cycle=server.pop('billing'),
        monthly_traffic_package=server.pop('traffic'),
        price_monthly_on=server.pop('priceMonthlyOn'),
        price_hourly_on=server.pop('priceHourlyOn'),
        price_hourly_off=server.pop('priceHourlyOff')
    )
    res_server['extra'] = server
    return res_server
