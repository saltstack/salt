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
import re
import time
import datetime

# Import Salt Libs
import salt.config as config
import salt.ext.six as six
from salt.ext.six.moves import range
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudNotFound,
    SaltCloudSystemExit
)

# Import Salt-Cloud Libs
import salt.utils.cloud

# Get logging started
log = logging.getLogger(__name__)

# The epoch of the last time a query was made
LASTCALL = int(time.mktime(datetime.datetime.now().timetuple()))

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
        __active_provider_name__ or __virtualname__,
        ('apikey', 'password',)
    )


def avail_images(call=None):
    '''
    Return available Linode images.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-linode-config
        salt-cloud -f avail_images my-linode-config
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_images function must be called with -f or --function.'
        )

    response = _query('avail', 'distributions')

    ret = {}
    for item in response['DATA']:
        name = item['LABEL']
        ret[name] = item

    return ret


def avail_locations(call=None):
    '''
    Return available Linode datacenter locations.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-linode-config
        salt-cloud -f avail_locations my-linode-config
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )

    response = _query('avail', 'datacenters')

    ret = {}
    for item in response['DATA']:
        name = item['LOCATION']
        ret[name] = item

    return ret


def avail_sizes(call=None):
    '''
    Return available Linode sizes.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes my-linode-config
        salt-cloud -f avail_sizes my-linode-config
    '''
    if call == 'action':
        raise SaltCloudException(
            'The avail_locations function must be called with -f or --function.'
        )

    response = _query('avail', 'LinodePlans')

    ret = {}
    for item in response['DATA']:
        name = item['LABEL']
        ret[name] = item

    return ret


def boot(name=None, kwargs=None, call=None):
    '''
    Boot a Linode.

    name
        The name of the Linode to boot. Can be used instead of ``linode_id``.

    linode_id
        The ID of the Linode to boot. If provided, will be used as an
        alternative to ``name`` and reduces the number of API calls to
        Linode by one. Will be preferred over ``name``.

    config_id
        The ID of the Config to boot. Required.

    check_running
        Defaults to True. If set to False, overrides the call to check if
        the VM is running before calling the linode.boot API call. Change
        ``check_running`` to True is useful during the boot call in the
        create function, since the new VM will not be running yet.

    Can be called as an action (which requires a name):

    .. code-block:: bash

        salt-cloud -a boot my-instance config_id=10

    ...or as a function (which requires either a name or linode_id):

    .. code-block:: bash

        salt-cloud -f boot my-linode-config name=my-instance config_id=10
        salt-cloud -f boot my-linode-config linode_id=1225876 config_id=10
    '''
    if name is None and call == 'action':
        raise SaltCloudSystemExit(
            'The boot action requires a \'name\'.'
        )

    if kwargs is None:
        kwargs = {}

    linode_id = kwargs.get('linode_id', None)
    config_id = kwargs.get('config_id', None)
    check_running = kwargs.get('check_running', True)

    if call == 'function':
        name = kwargs.get('name', None)

    if name is None and linode_id is None:
        raise SaltCloudSystemExit(
            'The boot function requires either a \'name\' or a \'linode_id\'.'
        )

    if config_id is None:
        raise SaltCloudSystemExit(
            'The boot function requires a \'config_id\'.'
        )

    if linode_id is None:
        linode_id = get_linode_id_from_name(name)
        linode_item = name
    else:
        linode_item = linode_id

    # Check if Linode is running first
    if check_running is True:
        status = get_linode(kwargs={'linode_id': linode_id})['STATUS']
        if status == '1':
            raise SaltCloudSystemExit(
                'Cannot boot Linode {0}. '
                'Linode {0} is already running.'.format(linode_item)
            )

    # Boot the VM and get the JobID from Linode
    response = _query('linode', 'boot',
                      args={'LinodeID': linode_id,
                            'ConfigID': config_id})['DATA']
    boot_job_id = response['JobID']

    if not _wait_for_job(linode_id, boot_job_id):
        log.error('Boot failed for Linode {0}.'.format(linode_item))
        return False

    return True


def clone(kwargs=None, call=None):
    '''
    Clone a Linode.

    linode_id
        The ID of the Linode to clone. Required.

    datacenter_id
        The ID of the Datacenter where the Linode will be placed. Required.

    plan_id
        The ID of the plan (size) of the Linode. Required.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f clone my-linode-config linode_id=1234567 datacenter_id=2 plan_id=5
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The clone function must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    linode_id = kwargs.get('linode_id', None)
    datacenter_id = kwargs.get('datacenter_id', None)
    plan_id = kwargs.get('plan_id', None)
    required_params = [linode_id, datacenter_id, plan_id]

    for item in required_params:
        if item is None:
            raise SaltCloudSystemExit(
                'The clone function requires a \'linode_id\', \'datacenter_id\', '
                'and \'plan_id\' to be provided.'
            )

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
    name = vm_['name']
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'linode',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    if _validate_name(name) is False:
        return False

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(name),
        {
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(name))

    data = {}
    kwargs = {'name': name}

    plan_id = None
    size = vm_.get('size')
    if size:
        kwargs['size'] = size
        plan_id = get_plan_id(kwargs={'label': size})

    datacenter_id = None
    location = vm_.get('location')
    if location:
        try:
            datacenter_id = get_datacenter_id(location)
        except KeyError:
            # Linode's default datacenter is Dallas, but we still have to set one to
            # use the create function from Linode's API. Dallas's datacenter id is 2.
            datacenter_id = 2

    clonefrom_name = vm_.get('clonefrom')
    cloning = True if clonefrom_name else False
    if cloning:
        linode_id = get_linode_id_from_name(clonefrom_name)
        clone_source = get_linode(kwargs={'linode_id': linode_id})

        kwargs = {
            'clonefrom': clonefrom_name,
            'image': 'Clone of {0}'.format(clonefrom_name),
        }

        if size is None:
            size = clone_source['TOTALRAM']
            kwargs['size'] = size
            plan_id = clone_source['PLANID']

        if location is None:
            datacenter_id = clone_source['DATACENTERID']

        # Create new Linode from cloned Linode
        try:
            result = clone(kwargs={'linode_id': linode_id,
                                   'datacenter_id': datacenter_id,
                                   'plan_id': plan_id})
        except Exception as err:
            log.error(
                'Error cloning \'{0}\' on Linode.\n\n'
                'The following exception was thrown by Linode when trying to '
                'clone the specified machine:\n'
                '{1}'.format(
                    clonefrom_name,
                    err
                ),
                exc_info_on_loglevel=logging.DEBUG
            )
            return False
    else:
        kwargs['image'] = vm_['image']

        # Create Linode
        try:
            result = _query('linode', 'create', args={
                'PLANID': plan_id,
                'DATACENTERID': datacenter_id
            })
        except Exception as err:
            log.error(
                'Error creating {0} on Linode\n\n'
                'The following exception was thrown by Linode when trying to '
                'run the initial deployment:\n'
                '{1}'.format(
                    name,
                    err
                ),
                exc_info_on_loglevel=logging.DEBUG
            )
            return False

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(name),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    node_id = _clean_data(result)['LinodeID']
    data['id'] = node_id

    if not _wait_for_status(node_id, status=(_get_status_id_by_name('brand_new'))):
        log.error(
            'Error creating {0} on LINODE\n\n'
            'while waiting for initial ready status'.format(name),
            exc_info_on_loglevel=logging.DEBUG
        )

    # Update the Linode's Label to reflect the given VM name
    update_linode(node_id, update_args={'Label': name})
    log.debug('Set name for {0} - was linode{1}.'.format(name, node_id))

    # Add private IP address if requested
    if get_private_ip(vm_):
        create_private_ip(vm_, node_id)

    if cloning:
        config_id = get_config_id(kwargs={'linode_id': node_id})['config_id']
    else:
        # Create disks and get ids
        log.debug('Creating disks for {0}'.format(name))
        root_disk_id = create_disk_from_distro(vm_, node_id)['DiskID']
        swap_disk_id = create_swap_disk(vm_, node_id)['DiskID']

        # Create a ConfigID using disk ids
        config_id = create_config(kwargs={'name': name,
                                          'linode_id': node_id,
                                          'root_disk_id': root_disk_id,
                                          'swap_disk_id': swap_disk_id})['ConfigID']

    # Boot the Linode
    boot(kwargs={'linode_id': node_id,
                 'config_id': config_id,
                 'check_running': False})

    node_data = get_linode(kwargs={'linode_id': node_id})
    ips = get_ips(node_id)
    state = int(node_data['STATUS'])

    data['image'] = kwargs['image']
    data['name'] = name
    data['size'] = size
    data['state'] = _get_status_descr_by_id(state)
    data['private_ips'] = ips['private_ips']
    data['public_ips'] = ips['public_ips']

    vm_['ssh_host'] = data['public_ips'][0]

    # If a password wasn't supplied in the profile or provider config, set it now.
    vm_['password'] = get_password(vm_)

    # Bootstrap!
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    ret.update(data)

    log.info('Created Cloud VM {0!r}'.format(name))
    log.debug(
        '{0!r} VM creation details:\n{1}'.format(
            name, pprint.pformat(data)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(name),
        {
            'name': name,
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
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

    config_args = {'LinodeID': linode_id,
                   'KernelID': kernel_id,
                   'Label': name,
                   'DiskList': '{0},{1}'.format(root_disk_id, swap_disk_id)
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


def create_private_ip(vm_, linode_id):
    r'''
    Creates a private IP for the specified Linode.

    vm\_
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
            'The \'{1}\' instance could not be provisioned.'.format(
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
    ret = {}

    for item in ips:
        node_id = str(item['LINODEID'])
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
        matching_id = ret.get(str(linode_id))
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


def get_password(vm_):
    r'''
    Return the password to use for a VM.

    vm\_
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


def get_plan_id(kwargs=None, call=None):
    '''
    Returns the Linode Plan ID.

    label
        The label, or name, of the plan to get the ID from.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_plan_id linode label="Linode 1024"
    '''
    if call == 'action':
        raise SaltCloudException(
            'The show_instance action must be called with -f or --function.'
        )

    if kwargs is None:
        kwargs = {}

    label = kwargs.get('label', None)
    if label is None:
        raise SaltCloudException(
            'The get_plan_id function requires a \'label\'.'
        )

    return avail_sizes()[label]['PLANID']


def get_private_ip(vm_):
    '''
    Return True if a private ip address is requested
    '''
    return config.get_cloud_config_value(
        'private_ip', vm_, __opts__, default=False
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
            'id': str(node['LINODEID']),
            'state': _get_status_descr_by_id(int(node['STATUS']))
        }

        ret[name] = this_node

    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields.
    '''
    return salt.utils.cloud.list_nodes_select(
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
        log.error('Reboot failed for {0}.'.format(name))
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
        linode_id = str(node['LINODEID'])

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
    global LASTCALL
    vm_ = get_configured_provider()

    ratelimit_sleep = config.get_cloud_config_value(
        'ratelimit_sleep', vm_, __opts__, search_global=False, default=0,
    )
    apikey = config.get_cloud_config_value(
        'apikey', vm_, __opts__, search_global=False
    )

    if not isinstance(args, dict):
        args = {}

    if 'api_key' not in args.keys():
        args['api_key'] = apikey

    if action and 'api_action' not in args.keys():
        args['api_action'] = '{0}.{1}'.format(action, command)

    if header_dict is None:
        header_dict = {}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    now = int(time.mktime(datetime.datetime.now().timetuple()))
    if LASTCALL >= now:
        time.sleep(ratelimit_sleep)

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
        hide_fields=['api_key', 'rootPass'],
        opts=__opts__,
    )
    LASTCALL = int(time.mktime(datetime.datetime.now().timetuple()))
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
        if jobs_result[0]['JOBID'] == job_id and jobs_result[0]['HOST_SUCCESS'] == 1:
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
        result = get_linode(kwargs={'linode_id': linode_id})

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


def _validate_name(name):
    '''
    Checks if the provided name fits Linode's labeling parameters.

    .. versionadded:: 2015.5.6

    name
        The VM name to validate
    '''
    name = str(name)
    name_length = len(name)
    regex = re.compile(r'^[a-zA-Z0-9][A-Za-z0-9_-]*[a-zA-Z0-9]$')

    if name_length < 3 or name_length > 48:
        ret = False
    elif not re.match(regex, name):
        ret = False
    else:
        ret = True

    if ret is False:
        log.warning(
            'A Linode label may only contain ASCII letters or numbers, dashes, and '
            'underscores, must begin and end with letters or numbers, and be at least '
            'three characters in length.'
        )

    return ret
