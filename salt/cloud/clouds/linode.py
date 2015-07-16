# -*- coding: utf-8 -*-
'''
Linode Cloud Module using Linode's REST API
===========================================

The Linode cloud module is used to control access to the Linode VPS system.

Use of this module only requires the ``apikey`` parameter. However, the default root password for new instances
also needs to be set. The password needs to be 8 characters and contain lowercase, uppercase, and numbers.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/linode.conf``:

.. code-block:: yaml

    my-linode-provider:
      apikey: f4ZsmwtB1c7f85Jdu43RgXVDFlNjuJaeIYV8QMftTqKScEB2vSosFSr...
      password: F00barbaz
      driver: linode
      ssh_key_file: /tmp/salt-cloud_pubkey
      ssh_pubkey: ssh-rsa AAAAB3NzaC1yc2EA...

    linode-profile:
      provider: my-linode-provider
      size: Linode 1024
      image: CentOS 7
      location: London, England, UK
      private_ip: true

To clone, add a profile with a ``clonefrom`` key, and a ``script_args: -C``. ``clonefrom`` should be the name of
the VM (*linode*) that is the source for the clone. ``script_args: -C`` passes a -C to the
bootstrap script, which only configures the minion and doesn't try to install a new copy of salt-minion. This way the
minion gets new keys and the keys get pre-seeded on the master, and the /etc/salt/minion file has the right
'id:' declaration.

Cloning requires a post 2015-02-01 salt-bootstrap.
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import pprint
import time

# Import Salt Libs
import salt.config as config
from salt.ext.six.moves import range
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudNotFound
)

# Import Salt-Cloud Libs
import salt.utils.cloud

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

__virtualname__ = 'linode'


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
        __active_provider_name__ or 'linode',
        ('apikey', 'password',)
    )


def avail_images():
    '''
    Return available Linode images.
    '''
    response = _query('avail', 'distributions')

    ret = {}
    for item in response['DATA']:
        name = item['LABEL']
        ret[name] = item

    return ret


def avail_locations():
    '''
    Return available Linode datacenter locations.
    '''
    response = _query('avail', 'datacenters')

    ret = {}
    for item in response['DATA']:
        name = item['LOCATION']
        ret[name] = item

    return ret


def avail_sizes():
    '''
    Return available Linode sizes.
    '''
    response = _query('avail', 'LinodePlans')

    ret = {}
    for item in response['DATA']:
        name = item['LABEL']
        ret[name] = item

    return ret


def boot(linode_id, config_id):
    '''
    Boot a Linode.

    linode_id
        The ID of the Linode to boot. Required.

    config_id
        The ID of the Config to boot. Required.
    '''
    response = _query('linode', 'boot', args={'LinodeID': linode_id,
                                              'ConfigID': config_id})

    return _clean_data(response)


def clone(linode_id, datacenter_id, plan_id):
    '''
    Clone a Linode.

    linode_id
        The ID of the Linode to clone. Required.

    datacenter_id
        The ID of the Datacenter where the Linode will be placed. Required.

    plan_id
        The ID of the plan (size) of the Linode. Required.
    '''
    clone_args = {
        'LinodeID': linode_id,
        'DatacenterID': datacenter_id,
        'PlanID': plan_id
    }

    return _query('linode', 'clone', args=clone_args)


def create(vm_):
    '''
    Create a single Linode VM.
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if config.is_profile_configured(__opts__,
                                        __active_provider_name__ or 'linode',
                                        vm_['profile']) is False:
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

    data = {}
    kwargs = {
        'name': vm_['name'],
        'image': vm_['image'],
        'size': vm_['size'],
    }

    plan_id = get_plan_id(vm_['size'])
    try:
        datacenter_id = get_datacenter_id(vm_['location'])
    except KeyError:
        # Linode's default datacenter is Dallas, but we still have to set one to
        # use the create function from Linode's API. Dallas's datacenter id is 2.
        datacenter_id = 2

    if 'clonefrom' in vm_:
        linode_id = get_linode_id_from_name(vm_['clonefrom'])
        clone_source = get_linode(linode_id)

        kwargs.update({'clonefrom': vm_['clonefrom']})
        kwargs['image'] = 'Clone of {0}'.format(vm_['clonefrom'])
        kwargs['size'] = clone_source['TOTALRAM']

        try:
            result = clone(linode_id, datacenter_id, plan_id)
        except Exception:
            log.error(
                'Error cloning {0} on Linode\n\n'
                'The following exception was thrown by Linode when trying to '
                'clone the specified machine:\n'.format(
                    vm_['clonefrom']
                ),
                exc_info_on_loglevel=logging.DEBUG
            )
            return False
    else:
        try:
            result = _query('linode', 'create', args={
                'PLANID': plan_id,
                'DATACENTERID': datacenter_id
            })
        except Exception:
            log.error(
                'Error creating {0} on Linode\n\n'
                'The following exception was thrown by Linode when trying to '
                'run the initial deployment:\n'.format(
                    vm_['name']
                ),
                exc_info_on_loglevel=logging.DEBUG
            )
            return False

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    node_id = _clean_data(result)['LinodeID']
    data['id'] = node_id

    if not _wait_for_status(node_id, status=(_get_status_id_by_name('brand_new'))):
        log.error(
            'Error creating {0} on LINODE\n\n'
            'while waiting for initial ready status'.format(vm_['name']),
            exc_info_on_loglevel=logging.DEBUG
        )

    # Update the Linode's Label to reflect the given VM name
    update_linode(node_id, update_args={'Label': vm_['name']})
    log.debug('Set name for {0} - was linode{1}.'.format(vm_['name'], node_id))

    # Create disks and get ids
    log.debug('Creating disks for {0}'.format(vm_['name']))
    root_disk_id = create_disk_from_distro(vm_, node_id)['DiskID']
    swap_disk_id = create_swap_disk(vm_, node_id)['DiskID']

    # Add private IP address if requested
    if get_private_ip(vm_):
        create_private_ip(vm_, node_id)

    # Create a ConfigID using disk ids
    config_id = create_config(vm_,
                              node_id,
                              root_disk_id,
                              swap_disk_id)['ConfigID']

    # Boot the VM and get the JobID from Linode
    boot_job_id = boot(node_id, config_id)['JobID']

    if not _wait_for_job(node_id, boot_job_id):
        log.error('Boot failed for {0}.'.format(vm_['name']))
        return False

    node_data = get_linode(node_id)
    ips = get_ips(node_id)
    state = int(node_data['STATUS'])

    data['image'] = vm_['image']
    data['name'] = node_data['LABEL']
    data['size'] = node_data['TOTALRAM']
    data['state'] = _get_status_descr_by_id(state)
    data['private_ips'] = ips['private_ips']
    data['public_ips'] = ips['public_ips']

    vm_['ssh_host'] = data['public_ips'][0]

    # If a password wasn't supplied in the profile or provider config, set it now.
    vm_['password'] = get_password(vm_)

    # Bootstrap!
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    ret.update(data)

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

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


def create_config(vm_, linode_id, root_disk_id, swap_disk_id, kernel_id=None):
    '''
    Creates a Linode Configuration Profile.

    vm_
        The VM profile to create the config for.

    linode_id
        The ID of the Linode to create the configuration for.

    root_disk_id
        The Root Disk ID to be used for this config.

    swap_disk_id
        The Swap Disk ID to be used for this config.

    kernel_id
        The ID of the kernel to use for this configuration profile.
    '''

    if kernel_id is None:
        # 138 appears to always be the latest 64-bit kernel for Linux
        kernel_id = 138

    config_args = {'LinodeID': linode_id,
                   'KernelID': kernel_id,
                   'Label': vm_['name'],
                   'DiskList': '{0},{1}'.format(root_disk_id, swap_disk_id)
                   }

    result = _query('linode', 'config.create', args=config_args)

    return _clean_data(result)


def create_disk_from_distro(vm_, linode_id, swap_size=None):
    '''
    Creates the disk for the Linode from the distribution.

    vm_
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

    distribution_id = get_distribution_id(vm_)

    kwargs.update({'LinodeID': linode_id,
                   'DistributionID': distribution_id,
                   'Label': vm_['name'],
                   'Size': get_disk_size(vm_, swap_size)})

    result = _query('linode', 'disk.createfromdistribution', args=kwargs)

    return _clean_data(result)


def create_swap_disk(vm_, linode_id, swap_size=None):
    '''
    Creates the disk for the specified Linode.

    vm_
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


def create_private_ip(vm_, linode_id):
    '''
    Creates a private IP for the specified Linode.

    vm_
        The VM profile to create the swap disk for.

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

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    linode_id = get_linode_id_from_name(name)

    response = _query('linode', 'delete', args={'LinodeID': linode_id, 'skipChecks': True})

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


def get_datacenter_id(location):
    '''
    Returns the Linode Datacenter ID.

    location
        The location, or name, of the datacenter to get the ID from.
    '''

    return avail_locations()[location]['DATACENTERID']


def get_disk_size(vm_, swap):
    '''
    Returns the size of of the root disk in MB.

    vm_
        The VM to get the disk size for.
    '''
    vm_size = get_vm_size(vm_)
    disk_size = vm_size
    return config.get_cloud_config_value(
        'disk_size', vm_, __opts__, default=disk_size - swap
    )


def get_distribution_id(vm_):
    '''
    Returns the distribution ID for a VM

    vm_
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
            'The DistributionID for the {0} profile could not be found.\n'
            'The {1} instance could not be provisioned.'.format(
                vm_image_name,
                vm_['name']
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
    all_ips = []

    for item in ips:
        node_id = str(item['LINODEID'])
        if item['ISPUBLIC'] == 1:
            key = 'public_ips'
        else:
            key = 'private_ips'

        data = {node_id: {'public_ips': [], 'private_ips': []}}
        data[node_id][key].append(item['IPADDRESS'])
        all_ips.append(data)

    # If linode_id was specified, only return the ips, and not the
    # dictionary based on the linode ID as a key.
    if linode_id:
        _all_ips = {'public_ips': [], 'private_ips': []}
        for item in all_ips:
            for addr_type, addr_list in item.popitem()[1].items():
                _all_ips[addr_type].extend(addr_list)
        all_ips = _all_ips

    return all_ips


def get_linode(linode_id):
    '''
    Returns data for a single named Linode.

    linode_id
        The ID of the Linode to get data for.
    '''
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


def get_password(vm_):
    '''
    Return the password to use for a VM.

    vm_
        The configuration to obtain the password from.
    '''
    return config.get_cloud_config_value(
        'password', vm_, __opts__,
        default=config.get_cloud_config_value(
            'passwd', vm_, __opts__,
            search_global=False
        ),
        search_global=False
    )


def get_plan_id(label):
    '''
    Returns the Linode Plan ID.

    label
        The label, or name, of the plan to get the ID from.
    '''
    return avail_sizes()[label]['PLANID']


def get_private_ip(vm_):
    '''
    Return True if a private ip address is requested
    '''
    return config.get_cloud_config_value(
        'private_ip', vm_, __opts__, default=False
    )


def get_pub_key(vm_):
    '''
    Return the SSH pubkey.

    vm_
        The configuration to obtain the public key from.
    '''
    return config.get_cloud_config_value(
        'ssh_pubkey', vm_, __opts__, search_global=False
    )


def get_swap_size(vm_):
    '''
    Returns the amoutn of swap space to be used in MB.

    vm_
        The VM profile to obtain the swap size from.
    '''
    return config.get_cloud_config_value(
        'wap', vm_, __opts__, default=128
    )


def get_vm_size(vm_):
    '''
    Returns the VM's size.

    vm_
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


def list_nodes_full():
    '''
    List linodes, with all available information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    '''
    return _list_linodes(full=True)


def reboot(name=None, linode_id=None, call=None):
    '''
    Reboot a linode. Either a name or a linode_id must be provided.

    .. versionadded:: 2015.8.0

    name
        The name of the VM to reboot.

    linode_id
        The Linode ID of the VM to reboot. Can be provided instead of a name.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
        salt-cloud -a reboot linode_id
    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )

    if not name and not linode_id:
        raise SaltCloudException(
            'Either a name or a linode_id must be specified.'
        )

    node_id = _check_and_set_node_id(name, linode_id)
    response = _query('linode', 'reboot', args={'LinodeID': node_id})
    data = _clean_data(response)

    reboot_jid = data['JobID']

    if not name:
        name = get_linode(linode_id)['LABEL']

    if not _wait_for_job(node_id, reboot_jid):
        log.error('Reboot failed for {0}.'.format(name))
        return False

    return data


def show_instance(name=None, linode_id=None, call=None):
    '''
    Displays details about a particular Linode VM. Either a name or a linode_id must
    be provided.

    .. versionadded:: 2015.8.0

    name
        The name of the VM for which to display details.

    linode_id
        The Linode ID of the VM for which to display details. Can be provided instead
        of a name.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance vm_name
        salt-cloud -a show_instance linode_id

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    '''
    if call == 'function':
        raise SaltCloudException(
            'The show_instance action must be called with -a or --action.'
        )

    if not name and not linode_id:
        raise SaltCloudException(
            'Either a name or a linode_id must be specified.'
        )

    node_id = _check_and_set_node_id(name, linode_id)
    node_data = get_linode(node_id)
    ips = get_ips(node_id)
    state = int(node_data['STATUS'])

    ret = {}
    ret['id'] = node_data['LINODEID']
    ret['image'] = node_data['DISTRIBUTIONVENDOR']
    ret['name'] = node_data['LABEL']
    ret['size'] = node_data['TOTALRAM']
    ret['state'] = _get_status_descr_by_id(state)
    ret['private_ips'] = ips['private_ips']
    ret['public_ips'] = ips['public_ips']

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
    profile = __opts__['profiles'].get(kwargs['profile'], {})
    if not profile:
        return {'Error': 'The requested profile was not found.'}

    # Make sure the profile belongs to Linode
    provider = profile.get('provider', '0:0')
    comps = provider.split(':')
    if len(comps) < 2 or comps[1] != 'linode':
        return {'Error': 'The requested profile does not belong to Linode.'}

    plan_id = get_plan_id(profile['size'])
    response = _query('avail', 'linodeplans', args={'PlanID': plan_id})['DATA'][0]

    ret = {}
    ret['per_hour'] = response['HOURLY']
    ret['per_day'] = ret['per_hour'] * 24
    ret['per_week'] = ret['per_day'] * 7
    ret['per_month'] = response['PRICE']
    ret['per_year'] = ret['per_month'] * 12

    return {profile['profile']: ret}


def start(name=None, linode_id=None, call=None):
    '''
    Start a VM in Linode. Either a name or a linode_id must be provided.

    name
        The name of the VM to start.

    linode_id
        The Linode ID of the VM to start. Can be provided instead of name.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
        salt-cloud -a stop linode_id
    '''
    if not name and not linode_id:
        raise SaltCloudException(
            'Either a name or a linode_id must be specified.'
        )

    node_id = _check_and_set_node_id(name, linode_id)
    node = get_linode(node_id)

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


def stop(name=None, linode_id=None, call=None):
    '''
    Stop a VM in Linode. Either a name or a linode_id must be provided.

    name
        The name of the VM to stop.

    linode_id
        The Linode ID of the VM to stop. Can be provided instead of name.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
        salt-cloud -a stop linode_id
    '''
    if not name and not linode_id:
        raise SaltCloudException(
            'Either a name or a linode_id must be specified.'
        )

    node_id = _check_and_set_node_id(name, linode_id)
    node = get_linode(node_id)

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
    if update_args is None:
        update_args = {}

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
        linode_id = str(node['LINODEID'])

        this_node['id'] = linode_id
        this_node['image'] = node['DISTRIBUTIONVENDOR']
        this_node['name'] = node['LABEL']
        this_node['size'] = node['TOTALRAM']

        state = int(node['STATUS'])
        this_node['state'] = _get_status_descr_by_id(state)

        key = ''
        for item in ips:
            for id_ in item:
                key = id_
            if key == linode_id:
                this_node['private_ips'] = item[key]['private_ips']
                this_node['public_ips'] = item[key]['public_ips']

        if full:
            this_node['extra'] = node

        ret[node['LABEL']] = this_node

    return ret


def _check_and_set_node_id(name, linode_id):
    '''
    Helper function that checks against name and linode_id collisions and returns a node_id.
    '''
    node_id = ''
    if linode_id and name is None:
        node_id = linode_id
    elif name:
        node_id = get_linode_id_from_name(name)

    if linode_id and (linode_id != node_id):
        raise SaltCloudException(
            'A name and a linode_id were provided, but the provided linode_id, {0}, '
            'does not match the linode_id found for the provided '
            'name: \'{1}\': \'{2}\'. Nothing was done.'.format(
                linode_id, name, node_id
            )
        )

    return node_id


def _query(action=None,
           command=None,
           args=None,
           method='GET',
           header_dict=None,
           data=None,
           url='https://api.linode.com/'):
    '''
    Make a web call to the Linode API.
    '''
    vm_ = get_configured_provider()

    apikey = config.get_cloud_config_value(
        'apikey', vm_, __opts__, search_global=False
    )

    if not isinstance(args, dict):
        args = {}

    if 'api_key' not in args.keys():
        args['api_key'] = apikey

    if action:
        if 'api_action' not in args.keys():
            args['api_action'] = '{0}.{1}'.format(action, command)

    if header_dict is None:
        header_dict = {}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    result = salt.utils.http.query(
        url,
        method,
        params=args,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type='json',
        text=True,
        status=True,
        opts=__opts__,
    )
    log.debug(
        'Linode Response Status Code: {0}'.format(
            result['status']
        )
    )

    return result['dict']


def _wait_for_job(linode_id, job_id, timeout=300, quiet=True):
    '''
    Wait for a Job to return.

    linode_id
        The ID of the Linode to wait on. Required.

    job_id
        The ID of the job to wait for.

    timeout
        The amount of time to wait for a status to update.

    quiet
        Log status updates to debug logs when True. Otherwise, logs to info.
    '''
    interval = 5
    iterations = int(timeout / interval)

    for i in range(0, iterations):
        jobs_result = _query('linode',
                             'job.list',
                             args={'LinodeID': linode_id})['DATA']
        if jobs_result[0]['JOBID'] == job_id:
            if jobs_result[0]['HOST_SUCCESS'] == 1:
                return True

        time.sleep(interval)
        if not quiet:
            log.info('Still waiting on Job {0} for Linode {1}.'.format(
                job_id,
                linode_id)
            )
        else:
            log.debug('Still waiting on Job {0} for Linode {1}.'.format(
                job_id,
                linode_id)
            )
    return False


def _wait_for_status(linode_id, status=None, timeout=300, quiet=True):
    '''
    Wait for a certain status from Linode.

    linode_id
        The ID of the Linode to wait on. Required.

    status
        The status to look for to update.

    timeout
        The amount of time to wait for a status to update.

    quiet
        Log status updates to debug logs when False. Otherwise, logs to info.
    '''
    if status is None:
        status = _get_status_id_by_name('brand_new')

    status_desc_waiting = _get_status_descr_by_id(status)

    interval = 5
    iterations = int(timeout / interval)

    for i in range(0, iterations):
        result = get_linode(linode_id)

        if result['STATUS'] == status:
            return True

        status_desc_result = _get_status_descr_by_id(result['STATUS'])

        time.sleep(interval)
        if quiet:
            log.info('Status for Linode {0} is \'{1}\', waiting for \'{2}\'.'.format(
                linode_id,
                status_desc_result,
                status_desc_waiting)
            )
        else:
            log.debug('Status for Linode {0} is \'{1}\', waiting for \'{2}\'.'.format(
                linode_id,
                status_desc_result,
                status_desc_waiting)
            )

    return False


def _get_status_descr_by_id(status_id):
    '''
    Return linode status by ID

    status_id
        linode VM status ID
    '''
    for status_name, status_data in LINODE_STATUS.iteritems():
        if status_data['code'] == int(status_id):
            return status_data['descr']
    return LINODE_STATUS.get(status_id, None)


def _get_status_id_by_name(status_name):
    '''
    Return linode status description by internalstatus name

    status_name
        internal linode VM status name
    '''
    return LINODE_STATUS.get(status_name, {}).get('code', None)
