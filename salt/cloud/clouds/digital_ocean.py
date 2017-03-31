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
    SaltInvocationError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)
import salt.ext.six as six
from salt.ext.six.moves import zip
from salt.ext.six import string_types

# Import Third Party Libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

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
        if vm_image in (images[image]['name'],
                        images[image]['slug'],
                        images[image]['id']):
            if images[image]['slug'] is not None:
                return images[image]['slug']
            return int(images[image]['id'])
    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
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
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
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
        'The specified location, \'{0}\', could not be found.'.format(
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

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
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
            'The defined key_filename \'{0}\' does not exist'.format(
                key_filename
            )
        )

    if not __opts__.get('ssh_agent', False) and key_filename is None:
        raise SaltCloudConfigError(
            'The DigitalOcean driver requires an ssh_key_file and an ssh_key_name '
            'because it does not supply a root password upon building the server.'
        )

    ssh_interface = config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, search_global=False, default='public'
    )

    if ssh_interface in ['private', 'public']:
        log.info("ssh_interface: Setting interface for ssh to {}".format(ssh_interface))
        kwargs['ssh_interface'] = ssh_interface
    else:
        raise SaltCloudConfigError(
            "The DigitalOcean driver requires ssh_interface to be defined as 'public' or 'private'."
        )

    private_networking = config.get_cloud_config_value(
        'private_networking', vm_, __opts__, search_global=False, default=None,
    )

    if private_networking is not None:
        if not isinstance(private_networking, bool):
            raise SaltCloudConfigError("'private_networking' should be a boolean value.")
        kwargs['private_networking'] = private_networking

    if not private_networking and ssh_interface == 'private':
        raise SaltCloudConfigError(
                "The DigitalOcean driver requires ssh_interface if defined as 'private' "
                "then private_networking should be set as 'True'."
    )

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

    create_dns_record = config.get_cloud_config_value(
        'create_dns_record', vm_, __opts__, search_global=False, default=None,
    )

    if create_dns_record:
        log.info('create_dns_record: will attempt to write DNS records')
        default_dns_domain = None
        dns_domain_name = vm_['name'].split('.')
        if len(dns_domain_name) > 2:
            log.debug('create_dns_record: inferring default dns_hostname, dns_domain from minion name as FQDN')
            default_dns_hostname = '.'.join(dns_domain_name[:-2])
            default_dns_domain = '.'.join(dns_domain_name[-2:])
        else:
            log.debug("create_dns_record: can't infer dns_domain from {0}".format(vm_['name']))
            default_dns_hostname = dns_domain_name[0]

        dns_hostname = config.get_cloud_config_value(
            'dns_hostname', vm_, __opts__, search_global=False, default=default_dns_hostname,
        )
        dns_domain = config.get_cloud_config_value(
            'dns_domain', vm_, __opts__, search_global=False, default=default_dns_domain,
        )
        if dns_hostname and dns_domain:
            log.info('create_dns_record: using dns_hostname="{0}", dns_domain="{1}"'.format(dns_hostname, dns_domain))
            __add_dns_addr__ = lambda t, d: post_dns_record(dns_domain=dns_domain,
                                                            name=dns_hostname,
                                                            record_type=t,
                                                            record_data=d)

            log.debug('create_dns_record: {0}'.format(__add_dns_addr__))
        else:
            log.error('create_dns_record: could not determine dns_hostname and/or dns_domain')
            raise SaltCloudConfigError(
                '\'create_dns_record\' must be a dict specifying "domain" '
                'and "hostname" or the minion name must be an FQDN.'
            )

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('requesting', kwargs, kwargs.keys()),
        sock_dir=__opts__['sock_dir'],
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

    if not vm_.get('ssh_host'):
        vm_['ssh_host'] = None

    # add DNS records, set ssh_host, default to first found IP, preferring IPv4 for ssh bootstrap script target
    addr_families, dns_arec_types = (('v4', 'v6'), ('A', 'AAAA'))
    arec_map = dict(list(zip(addr_families, dns_arec_types)))
    for facing, addr_family, ip_address in [(net['type'], family, net['ip_address'])
                                            for family in addr_families
                                            for net in data['networks'][family]]:
        log.info('found {0} IP{1} interface for "{2}"'.format(facing, addr_family, ip_address))
        dns_rec_type = arec_map[addr_family]
        if facing == 'public':
            if create_dns_record:
                __add_dns_addr__(dns_rec_type, ip_address)
        if facing == ssh_interface:
            if not vm_['ssh_host']:
                vm_['ssh_host'] = ip_address

    if vm_['ssh_host'] is None:
        raise SaltCloudSystemExit(
            'No suitable IP addresses found for ssh minion bootstrapping: {0}'.format(repr(data['networks']))
        )

    log.debug('Found public IP address to use for ssh minion bootstrapping: {0}'.format(vm_['ssh_host']))

    vm_['key_filename'] = key_filename
    ret = __utils__['cloud.bootstrap'](vm_, __opts__)
    ret.update(data)

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data)
        )
    )

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
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
            'Error: \'{1}\''.format(
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
    __utils__['cloud.cache_node'](node, __active_provider_name__, __opts__)
    return node


def _get_node(name):
    attempts = 10
    while attempts >= 0:
        try:
            return list_nodes_full(for_output=False)[name]
        except KeyError:
            attempts -= 1
            log.debug(
                'Failed to get the data for node \'{0}\'. Remaining '
                'attempts: {1}'.format(
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

    fetch = True
    page = 1
    ret = {}

    while fetch:
        items = query(method='account/keys', command='?page=' + str(page) +
                      '&per_page=100')

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

        page += 1
        try:
            fetch = 'next' in items['links']['pages']
        except KeyError:
            fetch = False

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


def import_keypair(kwargs=None, call=None):
    '''
    Upload public key to cloud provider.
    Similar to EC2 import_keypair.

    .. versionadded:: 2016.11.0

    kwargs
        file(mandatory): public key file-name
        keyname(mandatory): public key name in the provider
    '''
    with salt.utils.fopen(kwargs['file'], 'r') as public_key_filename:
        public_key_content = public_key_filename.read()

    digital_ocean_kwargs = {
        'name': kwargs['keyname'],
        'public_key': public_key_content
    }

    created_result = create_key(digital_ocean_kwargs, call=call)
    return created_result


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

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    data = show_instance(name, call='action')
    node = query(method='droplets', droplet_id=data['id'], http_method='delete')

    ## This is all terribly optomistic:
    # vm_ = get_vm_config(name=name)
    # delete_dns_record = config.get_cloud_config_value(
    #     'delete_dns_record', vm_, __opts__, search_global=False, default=None,
    # )
    # TODO: when _vm config data can be made available, we should honor the configuration settings,
    # but until then, we should assume stale DNS records are bad, and default behavior should be to
    # delete them if we can. When this is resolved, also resolve the comments a couple of lines below.
    delete_dns_record = True

    if not isinstance(delete_dns_record, bool):
        raise SaltCloudConfigError(
            '\'delete_dns_record\' should be a boolean value.'
        )
    # When the "to do" a few lines up is resolved, remove these lines and use the if/else logic below.
    log.debug('Deleting DNS records for {0}.'.format(name))
    destroy_dns_records(name)

    # Until the "to do" from line 754 is taken care of, we don't need this logic.
    # if delete_dns_record:
    #    log.debug('Deleting DNS records for {0}.'.format(name))
    #    destroy_dns_records(name)
    # else:
    #    log.debug('delete_dns_record : {0}'.format(delete_dns_record))
    #    for line in pprint.pformat(dir()).splitlines():
    #       log.debug('delete  context: {0}'.format(line))

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

    return node


def post_dns_record(**kwargs):
    '''
    Creates a DNS record for the given name if the domain is managed with DO.
    '''
    if 'kwargs' in kwargs:  # flatten kwargs if called via salt-cloud -f
        f_kwargs = kwargs['kwargs']
        del kwargs['kwargs']
        kwargs.update(f_kwargs)
    mandatory_kwargs = ('dns_domain', 'name', 'record_type', 'record_data')
    for i in mandatory_kwargs:
        if kwargs[i]:
            pass
        else:
            error = '{0}="{1}" ## all mandatory args must be provided: {2}'.format(i, kwargs[i], str(mandatory_kwargs))
            raise SaltInvocationError(error)

    domain = query(method='domains', droplet_id=kwargs['dns_domain'])

    if domain:
        result = query(
            method='domains',
            droplet_id=kwargs['dns_domain'],
            command='records',
            args={'type': kwargs['record_type'], 'name': kwargs['name'], 'data': kwargs['record_data']},
            http_method='post'
        )
        return result

    return False


def destroy_dns_records(fqdn):
    '''
    Deletes DNS records for the given hostname if the domain is managed with DO.
    '''
    domain = '.'.join(fqdn.split('.')[-2:])
    hostname = '.'.join(fqdn.split('.')[:-2])
    # TODO: remove this when the todo on 754 is available
    try:
        response = query(method='domains', droplet_id=domain, command='records')
    except SaltCloudSystemExit:
        log.debug('Failed to find domains.')
        return False
    log.debug("found DNS records: {0}".format(pprint.pformat(response)))
    records = response['domain_records']

    if records:
        record_ids = [r['id'] for r in records if r['name'].decode() == hostname]
        log.debug("deleting DNS record IDs: {0}".format(repr(record_ids)))
        for id in record_ids:
            try:
                log.info('deleting DNS record {0}'.format(id))
                ret = query(
                    method='domains',
                    droplet_id=domain,
                    command='records/{0}'.format(id),
                    http_method='delete'
                )
            except SaltCloudSystemExit:
                log.error('failed to delete DNS domain {0} record ID {1}.'.format(domain, hostname))
            log.debug('DNS deletion REST call returned: {0}'.format(pprint.pformat(ret)))

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


def list_floating_ips(call=None):
    '''
    Return a list of the floating ips that are on the provider

    .. versionadded:: 2016.3.0

    CLI Examples:

    ... code-block:: bash

        salt-cloud -f list_floating_ips my-digitalocean-config
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_floating_ips function must be called with '
            '-f or --function, or with the --list-floating-ips option'
        )

    fetch = True
    page = 1
    ret = {}

    while fetch:
        items = query(method='floating_ips',
                      command='?page=' + str(page) + '&per_page=200')

        for floating_ip in items['floating_ips']:
            ret[floating_ip['ip']] = {}
            for item in six.iterkeys(floating_ip):
                ret[floating_ip['ip']][item] = floating_ip[item]

        page += 1
        try:
            fetch = 'next' in items['links']['pages']
        except KeyError:
            fetch = False

    return ret


def show_floating_ip(kwargs=None, call=None):
    '''
    Show the details of a floating IP

    .. versionadded:: 2016.3.0

    CLI Examples:

    ... code-block:: bash

        salt-cloud -f show_floating_ip my-digitalocean-config floating_ip='45.55.96.47'
    '''
    if call != 'function':
        log.error(
            'The show_floating_ip function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'floating_ip' not in kwargs:
        log.error('A floating IP is required.')
        return False

    floating_ip = kwargs['floating_ip']
    log.debug('Floating ip is {0}'.format(floating_ip))

    details = query(method='floating_ips', command=floating_ip)

    return details


def create_floating_ip(kwargs=None, call=None):
    '''
    Create a new floating IP

    .. versionadded:: 2016.3.0

    CLI Examples:

    ... code-block:: bash

        salt-cloud -f create_floating_ip my-digitalocean-config region='NYC2'

        salt-cloud -f create_floating_ip my-digitalocean-config droplet_id='1234567'
    '''
    if call != 'function':
        log.error(
            'The create_floating_ip function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'droplet_id' in kwargs:
        result = query(method='floating_ips',
                           args={'droplet_id': kwargs['droplet_id']},
                           http_method='post')

        return result

    elif 'region' in kwargs:
        result = query(method='floating_ips',
                           args={'region': kwargs['region']},
                           http_method='post')

        return result

    else:
        log.error('A droplet_id or region is required.')
        return False


def delete_floating_ip(kwargs=None, call=None):
    '''
    Delete a floating IP

    .. versionadded:: 2016.3.0

    CLI Examples:

    ... code-block:: bash

        salt-cloud -f delete_floating_ip my-digitalocean-config floating_ip='45.55.96.47'
    '''
    if call != 'function':
        log.error(
            'The delete_floating_ip function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'floating_ip' not in kwargs:
        log.error('A floating IP is required.')
        return False

    floating_ip = kwargs['floating_ip']
    log.debug('Floating ip is {0}'.format('floating_ip'))

    result = query(method='floating_ips',
                   command=floating_ip,
                   http_method='delete')

    return result


def assign_floating_ip(kwargs=None, call=None):
    '''
    Assign a floating IP

    .. versionadded:: 2016.3.0

    CLI Examples:

    ... code-block:: bash

        salt-cloud -f assign_floating_ip my-digitalocean-config droplet_id=1234567 floating_ip='45.55.96.47'
    '''
    if call != 'function':
        log.error(
            'The assign_floating_ip function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'floating_ip' and 'droplet_id' not in kwargs:
        log.error('A floating IP and droplet_id is required.')
        return False

    result = query(method='floating_ips',
                   command=kwargs['floating_ip'] + '/actions',
                   args={'droplet_id': kwargs['droplet_id'], 'type': 'assign'},
                   http_method='post')

    return result


def unassign_floating_ip(kwargs=None, call=None):
    '''
    Unassign a floating IP

    .. versionadded:: 2016.3.0

    CLI Examples:

    ... code-block:: bash

        salt-cloud -f unassign_floating_ip my-digitalocean-config floating_ip='45.55.96.47'
    '''
    if call != 'function':
        log.error(
            'The inassign_floating_ip function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'floating_ip' not in kwargs:
        log.error('A floating IP is required.')
        return False

    result = query(method='floating_ips',
                   command=kwargs['floating_ip'] + '/actions',
                   args={'type': 'unassign'},
                   http_method='post')

    return result


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
