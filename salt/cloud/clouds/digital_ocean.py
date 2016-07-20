# -*- coding: utf-8 -*-
'''
DigitalOcean Cloud Module
=========================

The DigitalOcean cloud module is used to control access to the DigitalOcean VPS system.

Use of this module requires a requires a ``personal_access_token``, an ``ssh_key_file``,
and at least one SSH key name in ``ssh_key_names``. More ``ssh_key_names`` can be added
by separating each key with a comma. The ``personal_access_token`` can be found in the
DigitalOcean web interface in the "Apps & API" section. The SSH key name can be found
under the "SSH Keys" section.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-digital-ocean-config:
      personal_access_token: xxx
      ssh_key_file: /path/to/ssh/key/file
      ssh_key_names: my-key-name,my-key-name-2
      driver: digital_ocean

:depends: requests
'''

# Import Python Libs
from __future__ import absolute_import
import os
import time
import json
import pprint
import logging
import decimal

# Import Salt Libs
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)
from salt.ext.six import string_types

# Import Third Party Libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Import 3rd-party libs
import salt.ext.six as six

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'digital_ocean'


# Only load in this module if the DIGITAL_OCEAN configurations are in place
def __virtual__():
    '''
    Check for DigitalOcean configurations
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
        ('personal_access_token',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'requests': HAS_REQUESTS}
    )


def avail_locations(call=None):
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    items = query(method='regions')
    ret = {}
    for region in items['regions']:
        ret[region['name']] = {}
        for item in six.iterkeys(region):
            ret[region['name']][item] = str(region[item])

    return ret


def avail_images(call=None):
    '''
    Return a list of the images that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    fetch = True
    page = 1
    ret = {}

    while fetch:
        items = query(method='images', command='?page=' + str(page) + '&per_page=200')

        for image in items['images']:
            ret[image['name']] = {}
            for item in six.iterkeys(image):
                ret[image['name']][item] = image[item]

        page += 1
        try:
            fetch = 'next' in items['links']['pages']
        except KeyError:
            fetch = False

    return ret


def avail_sizes(call=None):
    '''
    Return a list of the image sizes that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    items = query(method='sizes')
    ret = {}
    for size in items['sizes']:
        ret[size['slug']] = {}
        for item in six.iterkeys(size):
            ret[size['slug']][item] = str(size[item])

    return ret


def list_nodes(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )
    return _list_nodes()


def list_nodes_full(call=None, for_output=True):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )
    return _list_nodes(full=True, for_output=for_output)


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def get_image(vm_):
    '''
    Return the image object to use
    '''
    images = avail_images()
    vm_image = config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    )
    if not isinstance(vm_image, string_types):
        vm_image = str(vm_image)

    for image in images:
        if vm_image in (images[image]['name'], images[image]['slug'], images[image]['id']):
            if images[image]['slug'] is not None:
                return images[image]['slug']
            return int(images[image]['id'])
    raise SaltCloudNotFound(
        'The specified image, {0!r}, could not be found.'.format(vm_image)
    )


def get_size(vm_):
    '''
    Return the VM's size. Used by create_node().
    '''
    sizes = avail_sizes()
    vm_size = str(config.get_cloud_config_value(
        'size', vm_, __opts__, search_global=False
    ))
    for size in sizes:
        if vm_size.lower() == sizes[size]['slug']:
            return sizes[size]['slug']
    raise SaltCloudNotFound(
        'The specified size, {0!r}, could not be found.'.format(vm_size)
    )


def get_location(vm_):
    '''
    Return the VM's location
    '''
    locations = avail_locations()
    vm_location = str(config.get_cloud_config_value(
        'location', vm_, __opts__, search_global=False
    ))

    for location in locations:
        if vm_location in (locations[location]['name'],
                           locations[location]['slug']):
            return locations[location]['slug']
    raise SaltCloudNotFound(
        'The specified location, {0!r}, could not be found.'.format(
            vm_location
        )
    )


def create_node(args):
    '''
    Create a node
    '''
    node = query(method='droplets', args=args, http_method='post')
    return node


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'digital_ocean',
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

    kwargs = {
        'name': vm_['name'],
        'size': get_size(vm_),
        'image': get_image(vm_),
        'region': get_location(vm_),
        'ssh_keys': []
    }

    # backwards compat
    ssh_key_name = config.get_cloud_config_value(
        'ssh_key_name', vm_, __opts__, search_global=False
    )

    if ssh_key_name:
        kwargs['ssh_keys'].append(get_keyid(ssh_key_name))

    ssh_key_names = config.get_cloud_config_value(
        'ssh_key_names', vm_, __opts__, search_global=False, default=False
    )

    if ssh_key_names:
        for key in ssh_key_names.split(','):
            kwargs['ssh_keys'].append(get_keyid(key))

    key_filename = config.get_cloud_config_value(
        'ssh_key_file', vm_, __opts__, search_global=False, default=None
    )

    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )

    if key_filename is None:
        raise SaltCloudConfigError(
            'The DigitalOcean driver requires an ssh_key_file and an ssh_key_name '
            'because it does not supply a root password upon building the server.'
        )

    private_networking = config.get_cloud_config_value(
        'private_networking', vm_, __opts__, search_global=False, default=None,
    )

    if private_networking is not None:
        if not isinstance(private_networking, bool):
            raise SaltCloudConfigError("'private_networking' should be a boolean value.")
        kwargs['private_networking'] = private_networking

    backups_enabled = config.get_cloud_config_value(
        'backups_enabled', vm_, __opts__, search_global=False, default=None,
    )

    if backups_enabled is not None:
        if not isinstance(backups_enabled, bool):
            raise SaltCloudConfigError("'backups_enabled' should be a boolean value.")
        kwargs['backups'] = backups_enabled

    ipv6 = config.get_cloud_config_value(
        'ipv6', vm_, __opts__, search_global=False, default=None,
    )

    if ipv6 is not None:
        if not isinstance(ipv6, bool):
            raise SaltCloudConfigError("'ipv6' should be a boolean value.")
        kwargs['ipv6'] = ipv6

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    try:
        ret = create_node(kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on DIGITAL_OCEAN\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: {1}'.format(
                vm_['name'],
                str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    def __query_node_data(vm_name):
        data = show_instance(vm_name, 'action')
        if not data:
            # Trigger an error in the wait_for_ip function
            return False
        if data['networks'].get('v4'):
            for network in data['networks']['v4']:
                if network['type'] == 'public':
                    return data
        return False

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(vm_['name'],),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=10),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    for network in data['networks']['v4']:
        if network['type'] == 'public':
            ip_address = network['ip_address']
    vm_['key_filename'] = key_filename
    vm_['ssh_host'] = ip_address
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


def query(method='droplets', droplet_id=None, command=None, args=None, http_method='get'):
    '''
    Make a web call to DigitalOcean
    '''
    base_path = str(config.get_cloud_config_value(
        'api_root',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default='https://api.digitalocean.com/v2'
    ))

    path = '{0}/{1}/'.format(base_path, method)

    if droplet_id:
        path += '{0}/'.format(droplet_id)

    if command:
        path += command

    if not isinstance(args, dict):
        args = {}

    personal_access_token = config.get_cloud_config_value(
        'personal_access_token', get_configured_provider(), __opts__, search_global=False
    )

    data = json.dumps(args)

    requester = getattr(requests, http_method)
    request = requester(path, data=data, headers={'Authorization': 'Bearer ' + personal_access_token, 'Content-Type': 'application/json'})
    if request.status_code > 299:
        raise SaltCloudSystemExit(
            'An error occurred while querying DigitalOcean. HTTP Code: {0}  '
            'Error: {1!r}'.format(
                request.status_code,
                # request.read()
                request.text
            )
        )

    log.debug(request.url)

    # success without data
    if request.status_code == 204:
        return True

    content = request.text

    result = json.loads(content)
    if result.get('status', '').lower() == 'error':
        raise SaltCloudSystemExit(
            pprint.pformat(result.get('error_message', {}))
        )

    return result


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


def show_instance(name, call=None):
    '''
    Show the details from DigitalOcean concerning a droplet
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )
    node = _get_node(name)
    salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)
    return node


def _get_node(name):
    attempts = 10
    while attempts >= 0:
        try:
            return list_nodes_full(for_output=False)[name]
        except KeyError:
            attempts -= 1
            log.debug(
                'Failed to get the data for the node {0!r}. Remaining '
                'attempts {1}'.format(
                    name, attempts
                )
            )
            # Just a little delay between attempts...
            time.sleep(0.5)
    return {}


def list_keypairs(call=None):
    '''
    Return a dict of all available VM locations on the cloud provider with
    relevant data
    '''
    if call != 'function':
        log.error(
            'The list_keypairs function must be called with -f or --function.'
        )
        return False

    items = query(method='account/keys')
    ret = {}
    for key_pair in items['ssh_keys']:
        name = key_pair['name']
        if name in ret:
            raise SaltCloudSystemExit(
                'A duplicate key pair name, \'{0}\', was found in DigitalOcean\'s '
                'key pair list. Please change the key name stored by DigitalOcean. '
                'Be sure to adjust the value of \'ssh_key_file\' in your cloud '
                'profile or provider configuration, if necessary.'.format(
                    name
                )
            )
        ret[name] = {}
        for item in six.iterkeys(key_pair):
            ret[name][item] = str(key_pair[item])

    return ret


def show_keypair(kwargs=None, call=None):
    '''
    Show the details of an SSH keypair
    '''
    if call != 'function':
        log.error(
            'The show_keypair function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    keypairs = list_keypairs(call='function')
    keyid = keypairs[kwargs['keyname']]['id']
    log.debug('Key ID is {0}'.format(keyid))

    details = query(method='account/keys', command=keyid)

    return details


def create_key(kwargs=None, call=None):
    '''
    Upload a public key
    '''
    if call != 'function':
        log.error(
            'The create_key function must be called with -f or --function.'
        )
        return False

    try:
        result = query(
            method='account',
            command='keys',
            args={'name': kwargs['name'],
                  'public_key': kwargs['public_key']},
            http_method='post'
        )
    except KeyError:
        log.info('`name` and `public_key` arguments must be specified')
        return False

    return result


def remove_key(kwargs=None, call=None):
    '''
    Delete public key
    '''
    if call != 'function':
        log.error(
            'The create_key function must be called with -f or --function.'
        )
        return False

    try:
        result = query(
            method='account',
            command='keys/' + kwargs['id'],
            http_method='delete'
        )
    except KeyError:
        log.info('`id` argument must be specified')
        return False

    return result


def get_keyid(keyname):
    '''
    Return the ID of the keyname
    '''
    if not keyname:
        return None
    keypairs = list_keypairs(call='function')
    keyid = keypairs[keyname]['id']
    if keyid:
        return keyid
    raise SaltCloudNotFound('The specified ssh key could not be found.')


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

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

    data = show_instance(name, call='action')
    node = query(method='droplets', droplet_id=data['id'], http_method='delete')

    delete_record = config.get_cloud_config_value(
        'delete_dns_record', get_configured_provider(), __opts__, search_global=False, default=None,
    )

    if delete_record and not isinstance(delete_record, bool):
        raise SaltCloudConfigError(
            '\'delete_dns_record\' should be a boolean value.'
        )

    if delete_record:
        delete_dns_record(name)

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return node


def create_dns_record(hostname, ip_address):
    '''
    Creates a DNS record for the given hostname if the domain is managed with DO.
    '''
    domainname = '.'.join(hostname.split('.')[-2:])
    subdomain = '.'.join(hostname.split('.')[:-2])
    domain = query(method='domains', droplet_id=domainname)

    if domain:
        result = query(
            method='domains',
            droplet_id=domainname,
            command='records',
            args={'type': 'A', 'name': subdomain, 'data': ip_address},
            http_method='post'
        )
        return result

    return False


def delete_dns_record(hostname):
    '''
    Deletes a DNS for the given hostname if the domain is managed with DO.
    '''
    domainname = '.'.join(hostname.split('.')[-2:])
    subdomain = '.'.join(hostname.split('.')[:-2])
    records = query(method='domains', droplet_id=domainname, command='records')

    if records:
        for record in records['domain_records']:
            if record['name'] == subdomain:
                return query(
                    method='domains',
                    droplet_id=domainname,
                    command='records/' + str(record['id']),
                    http_method='delete'
                )

    return False


def show_pricing(kwargs=None, call=None):
    '''
    Show pricing for a particular profile. This is only an estimate, based on
    unofficial pricing sources.

    .. versionadded:: 2015.8.0

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f show_pricing my-digitalocean-config profile=my-profile
    '''
    profile = __opts__['profiles'].get(kwargs['profile'], {})
    if not profile:
        return {'Error': 'The requested profile was not found'}

    # Make sure the profile belongs to Digital Ocean
    provider = profile.get('provider', '0:0')
    comps = provider.split(':')
    if len(comps) < 2 or comps[1] != 'digital_ocean':
        return {'Error': 'The requested profile does not belong to Digital Ocean'}

    raw = {}
    ret = {}
    sizes = avail_sizes()
    ret['per_hour'] = decimal.Decimal(sizes[profile['size']]['price_hourly'])

    ret['per_day'] = ret['per_hour'] * 24
    ret['per_week'] = ret['per_day'] * 7
    ret['per_month'] = decimal.Decimal(sizes[profile['size']]['price_monthly'])
    ret['per_year'] = ret['per_week'] * 52

    if kwargs.get('raw', False):
        ret['_raw'] = raw

    return {profile['profile']: ret}


def _list_nodes(full=False, for_output=False):
    '''
    Helper function to format and parse node data.
    '''
    fetch = True
    page = 1
    ret = {}

    while fetch:
        items = query(method='droplets',
                      command='?page=' + str(page) + '&per_page=200')
        for node in items['droplets']:
            name = node['name']
            ret[name] = {}
            if full:
                ret[name] = _get_full_output(node, for_output=for_output)
            else:
                public_ips, private_ips = _get_ips(node['networks'])
                ret[name] = {
                    'id': node['id'],
                    'image': node['image']['name'],
                    'name': name,
                    'private_ips': private_ips,
                    'public_ips': public_ips,
                    'size': node['size_slug'],
                    'state': str(node['status']),
                }

        page += 1
        try:
            fetch = 'next' in items['links']['pages']
        except KeyError:
            fetch = False

    return ret


def reboot(name, call=None):
    '''
    Reboot a droplet in DigitalOcean.

    .. versionadded:: 2015.8.8

    name
        The name of the droplet to restart.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot droplet_name
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The restart action must be called with -a or --action.'
        )

    data = show_instance(name, call='action')
    if data.get('status') == 'off':
        return {'success': True,
                'action': 'stop',
                'status': 'off',
                'msg': 'Machine is already off.'}

    ret = query(droplet_id=data['id'],
                command='actions',
                args={'type': 'reboot'},
                http_method='post')

    return {'success': True,
            'action': ret['action']['type'],
            'state': ret['action']['status']}


def start(name, call=None):
    '''
    Start a droplet in DigitalOcean.

    .. versionadded:: 2015.8.8

    name
        The name of the droplet to start.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start droplet_name
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    data = show_instance(name, call='action')
    if data.get('status') == 'active':
        return {'success': True,
                'action': 'start',
                'status': 'active',
                'msg': 'Machine is already running.'}

    ret = query(droplet_id=data['id'],
                command='actions',
                args={'type': 'power_on'},
                http_method='post')

    return {'success': True,
            'action': ret['action']['type'],
            'state': ret['action']['status']}


def stop(name, call=None):
    '''
    Stop a droplet in DigitalOcean.

    .. versionadded:: 2015.8.8

    name
        The name of the droplet to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop droplet_name
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    data = show_instance(name, call='action')
    if data.get('status') == 'off':
        return {'success': True,
                'action': 'stop',
                'status': 'off',
                'msg': 'Machine is already off.'}

    ret = query(droplet_id=data['id'],
                command='actions',
                args={'type': 'shutdown'},
                http_method='post')

    return {'success': True,
            'action': ret['action']['type'],
            'state': ret['action']['status']}


def _get_full_output(node, for_output=False):
    '''
    Helper function for _list_nodes to loop through all node information.
    Returns a dictionary containing the full information of a node.
    '''
    ret = {}
    for item in six.iterkeys(node):
        value = node[item]
        if value is not None and for_output:
            value = str(value)
        ret[item] = value
    return ret


def _get_ips(networks):
    '''
    Helper function for list_nodes. Returns public and private ip lists based on a
    given network dictionary.
    '''
    v4s = networks.get('v4')
    v6s = networks.get('v6')
    public_ips = []
    private_ips = []

    if v4s:
        for item in v4s:
            ip_type = item.get('type')
            ip_address = item.get('ip_address')
            if ip_type == 'public':
                public_ips.append(ip_address)
            if ip_type == 'private':
                private_ips.append(ip_address)

    if v6s:
        for item in v6s:
            ip_type = item.get('type')
            ip_address = item.get('ip_address')
            if ip_type == 'public':
                public_ips.append(ip_address)
            if ip_type == 'private':
                private_ips.append(ip_address)

    return public_ips, private_ips
