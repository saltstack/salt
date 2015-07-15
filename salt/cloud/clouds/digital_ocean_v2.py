# -*- coding: utf-8 -*-
'''
DigitalOcean Cloud Module v2
============================

The DigitalOcean cloud module is used to control access to the DigitalOcean
VPS system.

Use of this module only requires the ``personal_access_token`` parameter to be set. Set up the
cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/digital_ocean.conf``:

.. code-block:: yaml

    my-digital-ocean-config:
      personal_access_token: xxx
      provider: digital_ocean

:depends: requests
'''
from __future__ import absolute_import

# Import python libs
import os
import copy
import time
import json
import pprint
import logging

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'digital_ocean'


# Only load in this module if the DIGITAL_OCEAN configurations are in place
def __virtual__():
    '''
    Check for DigitalOcean configurations
    '''
    if not HAS_REQUESTS:
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
        __active_provider_name__ or 'digital_ocean',
        ('personal_access_token',)
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
        for item in region.keys():
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
            ret[image['id']] = {}
            for item in image.keys():
                ret[image['id']][item] = str(image[item])

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
        for item in size.keys():
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

    fetch = True
    page = 1
    ret = {}

    while fetch:
        items = query(method='droplets', command='?page=' + str(page) + '&per_page=200')
        for node in items['droplets']:
            ret[node['name']] = {
                'id': node['id'],
                'image': node['image']['name'],
                'networks': str(node['networks']),
                'size': node['size_slug'],
                'state': str(node['status']),
            }
        page += 1
        try:
            fetch = 'next' in items['links']['pages']
        except KeyError:
            fetch = False

    return ret


def list_nodes_full(call=None, forOutput=True):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    fetch = True
    page = 1
    ret = {}

    while fetch:
        items = query(method='droplets', command='?page=' + str(page) + '&per_page=200')
        for node in items['droplets']:
            ret[node['name']] = {}
            for item in node.keys():
                value = node[item]
                if value is not None and forOutput:
                    value = str(value)
                ret[node['name']][item] = value
        page += 1
        try:
            fetch = 'next' in items['links']['pages']
        except KeyError:
            fetch = False
    return ret


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
    vm_image = str(config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    ))
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
    kwargs = {
        'name': vm_['name'],
        'size': get_size(vm_),
        'image': get_image(vm_),
        'region': get_location(vm_),
    }

    kwargs['ssh_keys'] = []
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

    ssh_username = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__, default='root'
    )

    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        for network in data['networks']['v4']:
            if network['type'] == 'public':
                ip_address = network['ip_address']

        create_record = config.get_cloud_config_value(
            'create_dns_record', vm_, __opts__, search_global=False, default=None,
        )
        if create_record is not None:
            if not isinstance(create_record, bool):
                raise SaltCloudConfigError("'create_dns_record' should be a boolean value.")

        if create_record:
            create_dns_record(vm_['name'], ip_address)

        deploy_kwargs = {
            'opts': __opts__,
            'host': ip_address,
            'username': ssh_username,
            'key_filename': key_filename,
            'script': deploy_script,
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
            'display_ssh_output': config.get_cloud_config_value(
                'display_ssh_output', vm_, __opts__, default=True
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
            'provider': vm_['provider'],
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
            return list_nodes_full(forOutput=False)[name]
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
    for keypair in items['ssh_keys']:
        ret[keypair['name']] = {}
        for item in keypair.keys():
            ret[keypair['name']][item] = str(keypair[item])

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
    if delete_record is not None:
        if not isinstance(delete_record, bool):
            raise SaltCloudConfigError("'delete_dns_record' should be a boolean value.")

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
        result = query(method='domains', droplet_id=domainname, command='records', args={'type': 'A', 'name': subdomain, 'data': ip_address}, http_method='post')
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
                return query(method='domains', droplet_id=domainname, command='records/' + str(record['id']), http_method='delete')

    return False
