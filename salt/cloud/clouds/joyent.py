# -*- coding: utf-8 -*-
'''
Joyent Cloud Module
===================

The Joyent Cloud module is used to interact with the Joyent cloud system.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/joyent.conf``:

.. code-block:: yaml

    my-joyent-config:
      driver: joyent
      # The Joyent login user
      user: fred
      # The Joyent user's password
      password: saltybacon
      # The location of the ssh private key that can log into the new VM
      private_key: /root/mykey.pem
      # The name of the private key
      private_key: mykey

When creating your profiles for the joyent cloud, add the location attribute to
the profile, this will automatically get picked up when performing tasks
associated with that vm. An example profile might look like:

.. code-block:: yaml

      joyent_512:
        provider: my-joyent-config
        size: Extra Small 512 MB
        image: centos-6
        location: us-east-1

This driver can also be used with the Joyent SmartDataCenter project. More
details can be found at:

.. _`SmartDataCenter`: https://github.com/joyent/sdc

Using SDC requires that an api_host_suffix is set. The default value for this is
`.api.joyentcloud.com`. All characters, including the leading `.`, should be
included:

.. code-block:: yaml

      api_host_suffix: .api.myhostname.com

:depends: PyCrypto
'''
# pylint: disable=invalid-name,function-redefined

# Import python libs
from __future__ import absolute_import
import os
import json
import logging
import base64
import pprint
import inspect
import yaml
import datetime
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

# Import salt libs
import salt.ext.six as six
from salt.ext.six.moves import http_client  # pylint: disable=import-error,no-name-in-module
import salt.utils.http
import salt.utils.cloud
import salt.config as config
from salt.utils.cloud import is_public_ip
from salt.cloud.libcloudfuncs import node_state
from salt.exceptions import (
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
)

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'joyent'

JOYENT_API_HOST_SUFFIX = '.api.joyentcloud.com'
JOYENT_API_VERSION = '~7.2'

JOYENT_LOCATIONS = {
    'us-east-1': 'North Virginia, USA',
    'us-west-1': 'Bay Area, California, USA',
    'us-sw-1': 'Las Vegas, Nevada, USA',
    'eu-ams-1': 'Amsterdam, Netherlands'
}
DEFAULT_LOCATION = 'us-east-1'

# joyent no longer reports on all data centers, so setting this value to true
# causes the list_nodes function to get information on machines from all
# data centers
POLL_ALL_LOCATIONS = True

VALID_RESPONSE_CODES = [
    http_client.OK,
    http_client.ACCEPTED,
    http_client.CREATED,
    http_client.NO_CONTENT
]

DEFAULT_NETWORKS = ['Joyent-SDC-Public']


# Only load in this module if the Joyent configurations are in place
def __virtual__():
    '''
    Check for Joyent configs
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
        ('user', 'password')
    )


def get_image(vm_):
    '''
    Return the image object to use
    '''
    images = avail_images()

    vm_image = config.get_cloud_config_value('image', vm_, __opts__)

    if vm_image and str(vm_image) in images:
        images[vm_image]['name'] = images[vm_image]['id']
        return images[vm_image]

    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
    )


def get_size(vm_):
    '''
    Return the VM's size object
    '''
    sizes = avail_sizes()
    vm_size = config.get_cloud_config_value('size', vm_, __opts__)
    if not vm_size:
        raise SaltCloudNotFound('No size specified for this VM.')

    if vm_size and str(vm_size) in sizes:
        return sizes[vm_size]

    raise SaltCloudNotFound(
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
    )


def query_instance(vm_=None, call=None):
    '''
    Query an instance upon creation from the Joyent API
    '''
    if isinstance(vm_, six.string_types) and call == 'action':
        vm_ = {'name': vm_, 'provider': 'joyent'}

    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The query_instance action must be called with -a or --action.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'querying instance',
        'salt/cloud/{0}/querying'.format(vm_['name']),
        transport=__opts__['transport']
    )

    def _query_ip_address():
        data = show_instance(vm_['name'], call='action')
        if not data:
            log.error(
                'There was an error while querying Joyent. Empty response'
            )
            # Trigger a failure in the wait for IP function
            return False

        if isinstance(data, dict) and 'error' in data:
            log.warning(
                'There was an error in the query {0}'.format(data.get('error'))
            )
            # Trigger a failure in the wait for IP function
            return False

        log.debug('Returned query data: {0}'.format(data))

        if 'primaryIp' in data[1]:
            return data[1]['primaryIp']
        return None

    try:
        data = salt.utils.cloud.wait_for_ip(
            _query_ip_address,
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=10),
            interval_multiplier=config.get_cloud_config_value(
                'wait_for_ip_interval_multiplier', vm_, __opts__, default=1),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            pass
            #destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    return data


def create(vm_):
    '''
    Create a single VM from a data dict

    CLI Example:

    .. code-block:: bash

        salt-cloud -p profile_name vm_name
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'joyent',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in vm_:
        vm_['driver'] = vm_.pop('provider')

    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )

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

    log.info(
        'Creating Cloud VM {0} in {1}'.format(
            vm_['name'],
            vm_.get('location', DEFAULT_LOCATION)
        )
    )

    # added . for fqdn hostnames
    salt.utils.cloud.check_name(vm_['name'], 'a-zA-Z0-9-.')
    kwargs = {
        'name': vm_['name'],
        'networks': vm_.get('networks', DEFAULT_NETWORKS),
        'image': get_image(vm_),
        'size': get_size(vm_),
        'location': vm_.get('location', DEFAULT_LOCATION)

    }

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    try:
        data = create_node(**kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on JOYENT\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    query_instance(vm_)
    data = show_instance(vm_['name'], call='action')

    vm_['key_filename'] = key_filename
    vm_['ssh_host'] = data[1]['primaryIp']

    salt.utils.cloud.bootstrap(vm_, __opts__)

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

    return data[1]


def create_node(**kwargs):
    '''
    convenience function to make the rest api call for node creation.
    '''
    name = kwargs['name']
    size = kwargs['size']
    image = kwargs['image']
    location = kwargs['location']
    networks = kwargs['networks']

    data = json.dumps({
        'name': name,
        'package': size['name'],
        'image': image['name'],
        'networks': networks
    })

    try:
        ret = query(command='/my/machines', data=data, method='POST',
                     location=location)
        if ret[0] in VALID_RESPONSE_CODES:
            return ret[1]
    except Exception as exc:
        log.error(
            'Failed to create node {0}: {1}'.format(name, exc)
        )

    return {}


def destroy(name, call=None):
    '''
    destroy a machine by name

    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: array of booleans , true if successfully stopped and true if
             successfully removed

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name

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

    node = get_node(name)
    ret = query(command='my/machines/{0}'.format(node['id']),
                 location=node['location'], method='DELETE')

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return ret[0] in VALID_RESPONSE_CODES


def reboot(name, call=None):
    '''
    reboot a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    '''
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST',
                      command='/my/machines/{0}'.format(node['id']),
                      location=node['location'], data={'action': 'reboot'})
    return ret[0] in VALID_RESPONSE_CODES


def stop(name, call=None):
    '''
    stop a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    '''
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST',
                      command='/my/machines/{0}'.format(node['id']),
                      location=node['location'], data={'action': 'stop'})
    return ret[0] in VALID_RESPONSE_CODES


def start(name, call=None):
    '''
    start a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    '''
    node = get_node(name)
    ret = take_action(name=name, call=call, method='POST',
                      command='/my/machines/{0}'.format(node['id']),
                      location=node['location'], data={'action': 'start'})
    return ret[0] in VALID_RESPONSE_CODES


def take_action(name=None, call=None, command=None, data=None, method='GET',
                location=DEFAULT_LOCATION):

    '''
    take action call used by start,stop, reboot
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :command: api path
    :data: any data to be passed to the api, must be in json format
    :method: GET,POST,or DELETE
    :location: data center to execute the command on
    :return: true if successful
    '''
    caller = inspect.stack()[1][3]

    if call != 'action':
        raise SaltCloudSystemExit(
            'This action must be called with -a or --action.'
        )

    if data:
        data = json.dumps(data)

    ret = []
    try:

        ret = query(command=command, data=data, method=method,
                     location=location)
        log.info('Success {0} for node {1}'.format(caller, name))
    except Exception as exc:
        if 'InvalidState' in str(exc):
            ret = [200, {}]
        else:
            log.error(
                'Failed to invoke {0} node {1}: {2}'.format(caller, name, exc),
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG
            )
            ret = [100, {}]

    return ret


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def get_location(vm_=None):
    '''
    Return the joyent data center to use, in this order:
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
            default=DEFAULT_LOCATION,
            search_global=False
        )
    )


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
    for key in JOYENT_LOCATIONS:
        ret[key] = {
            'name': key,
            'region': JOYENT_LOCATIONS[key]
        }

    # this can be enabled when the bug in the joyent get data centers call is
    # corrected, currently only the European dc (new api) returns the correct
    # values
    # ret = {}
    # rcode, datacenters = query(
    #     command='my/datacenters', location=DEFAULT_LOCATION, method='GET'
    # )
    # if rcode in VALID_RESPONSE_CODES and isinstance(datacenters, dict):
    #     for key in datacenters:
    #     ret[key] = {
    #         'name': key,
    #         'url': datacenters[key]
    #     }
    return ret


def has_method(obj, method_name):
    '''
    Find if the provided object has a specific method
    '''
    if method_name in dir(obj):
        return True

    log.error(
        'Method \'{0}\' not yet supported!'.format(
            method_name
        )
    )
    return False


def key_list(items=None):
    '''
    convert list to dictionary using the key as the identifier
    :param items: array to iterate over
    :return: dictionary
    '''
    if items is None:
        items = []

    ret = {}
    if items and isinstance(items, list):
        for item in items:
            if 'name' in item:
                # added for consistency with old code
                if 'id' not in item:
                    item['id'] = item['name']
                ret[item['name']] = item
    return ret


def get_node(name):
    '''
    gets the node from the full node list by name
    :param name: name of the vm
    :return: node object
    '''
    nodes = list_nodes()
    if name in nodes:
        return nodes[name]
    return None


def show_instance(name, call=None):
    '''
    get details about a machine
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: machine information

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance vm_name
    '''
    node = get_node(name)
    ret = query(command='my/machines/{0}'.format(node['id']),
                location=node['location'], method='GET')

    return ret


def joyent_node_state(id_):
    '''
    Convert joyent returned state to state common to other data center return
    values for consistency

    :param id_: joyent state value
    :return: state value
    '''
    states = {'running': 0,
              'stopped': 2,
              'stopping': 2,
              'provisioning': 3,
              'deleted': 2,
              'unknown': 4}

    if id_ not in states:
        id_ = 'unknown'

    return node_state(states[id_])


def reformat_node(item=None, full=False):
    '''
    Reformat the returned data from joyent, determine public/private IPs and
    strip out fields if necessary to provide either full or brief content.

    :param item: node dictionary
    :param full: full or brief output
    :return: dict
    '''
    desired_keys = [
        'id', 'name', 'state', 'public_ips', 'private_ips', 'size', 'image',
        'location'
    ]
    item['private_ips'] = []
    item['public_ips'] = []
    if 'ips' in item:
        for ip in item['ips']:
            if is_public_ip(ip):
                item['public_ips'].append(ip)
            else:
                item['private_ips'].append(ip)

    # add any undefined desired keys
    for key in desired_keys:
        if key not in item:
            item[key] = None

    # remove all the extra key value pairs to provide a brief listing
    to_del = []
    if not full:
        for key in six.iterkeys(item):  # iterate over a copy of the keys
            if key not in desired_keys:
                to_del.append(key)

    for key in to_del:
        del item[key]

    if 'state' in item:
        item['state'] = joyent_node_state(item['state'])

    return item


def list_nodes(full=False, call=None):
    '''
    list of nodes, keeping only a brief listing

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    if POLL_ALL_LOCATIONS:
        for location in JOYENT_LOCATIONS:
            result = query(command='my/machines', location=location,
                            method='GET')
            nodes = result[1]
            for node in nodes:
                if 'name' in node:
                    node['location'] = location
                    ret[node['name']] = reformat_node(item=node, full=full)

    else:
        result = query(command='my/machines', location=DEFAULT_LOCATION,
                        method='GET')
        nodes = result[1]
        for node in nodes:
            if 'name' in node:
                node['location'] = DEFAULT_LOCATION
                ret[node['name']] = reformat_node(item=node, full=full)
    return ret


def list_nodes_full(call=None):
    '''
    list of nodes, maintaining all content provided from joyent listings

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    return list_nodes(full=True)


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def _get_proto():
    '''
    Checks configuration to see whether the user has SSL turned on. Default is:

    .. code-block:: yaml

        use_ssl: True
    '''
    use_ssl = config.get_cloud_config_value(
        'use_ssl',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=True
    )
    if use_ssl is True:
        return 'https'
    return 'http'


def avail_images(call=None):
    '''
    Get list of available images

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images

    Can use a custom URL for images. Default is:

    .. code-block:: yaml

        image_url: images.joyent.com/image
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    user = config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    )

    img_url = config.get_cloud_config_value(
        'image_url',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default='{0}{1}/{2}/images'.format(DEFAULT_LOCATION, JOYENT_API_HOST_SUFFIX, user)
    )

    if not img_url.startswith('http://') and not img_url.startswith('https://'):
        img_url = '{0}://{1}'.format(_get_proto(), img_url)

    rcode, data = query(command='my/images', method='GET')
    log.debug(data)

    ret = {}
    for image in data:
        ret[image['name']] = image
    return ret


def avail_sizes(call=None):
    '''
    get list of available packages

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    rcode, items = query(command='/my/packages')
    if rcode not in VALID_RESPONSE_CODES:
        return {}
    return key_list(items=items)


def list_keys(kwargs=None, call=None):
    '''
    List the keys available
    '''
    if call != 'function':
        log.error(
            'The list_keys function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    ret = {}
    rcode, data = query(command='my/keys', method='GET')
    for pair in data:
        ret[pair['name']] = pair['key']
    return {'keys': ret}


def show_key(kwargs=None, call=None):
    '''
    List the keys available
    '''
    if call != 'function':
        log.error(
            'The list_keys function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    rcode, data = query(
        command='my/keys/{0}'.format(kwargs['keyname']),
        method='GET',
    )
    return {'keys': {data['name']: data['key']}}


def import_key(kwargs=None, call=None):
    '''
    List the keys available

    CLI Example:

    .. code-block:: bash

        salt-cloud -f import_key joyent keyname=mykey keyfile=/tmp/mykey.pub
    '''
    if call != 'function':
        log.error(
            'The import_key function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    if 'keyfile' not in kwargs:
        log.error('The location of the SSH keyfile is required.')
        return False

    if not os.path.isfile(kwargs['keyfile']):
        log.error('The specified keyfile ({0}) does not exist.'.format(
            kwargs['keyfile']
        ))
        return False

    with salt.utils.fopen(kwargs['keyfile'], 'r') as fp_:
        kwargs['key'] = fp_.read()

    send_data = {'name': kwargs['keyname'], 'key': kwargs['key']}
    kwargs['data'] = json.dumps(send_data)

    rcode, data = query(
        command='my/keys',
        method='POST',
        data=kwargs['data'],
    )
    log.debug(pprint.pformat(data))
    return {'keys': {data['name']: data['key']}}


def delete_key(kwargs=None, call=None):
    '''
    List the keys available

    CLI Example:

    .. code-block:: bash

        salt-cloud -f delete_key joyent keyname=mykey
    '''
    if call != 'function':
        log.error(
            'The delete_keys function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    rcode, data = query(
        command='my/keys/{0}'.format(kwargs['keyname']),
        method='DELETE',
    )
    return data


def get_location_path(location=DEFAULT_LOCATION, api_host_suffix=JOYENT_API_HOST_SUFFIX):
    '''
    create url from location variable
    :param location: joyent data center location
    :return: url
    '''
    return '{0}://{1}{2}'.format(_get_proto(), location, api_host_suffix)


def query(action=None,
          command=None,
          args=None,
          method='GET',
          location=None,
          data=None):
    '''
    Make a web call to Joyent
    '''
    user = config.get_cloud_config_value(
        'user', get_configured_provider(), __opts__, search_global=False
    )

    password = config.get_cloud_config_value(
        'password', get_configured_provider(), __opts__,
        search_global=False
    )

    verify_ssl = config.get_cloud_config_value(
        'verify_ssl', get_configured_provider(), __opts__,
        search_global=False, default=True
    )

    ssh_keyfile = config.get_cloud_config_value(
        'private_key', get_configured_provider(), __opts__,
        search_global=False, default=True
    )

    ssh_keyname = config.get_cloud_config_value(
        'keyname', get_configured_provider(), __opts__,
        search_global=False, default=True
    )

    if not location:
        location = get_location()

    api_host_suffix = config.get_cloud_config_value(
        'api_host_suffix', get_configured_provider(), __opts__,
        search_global=False, default=JOYENT_API_HOST_SUFFIX
    )

    path = get_location_path(location=location, api_host_suffix=api_host_suffix)

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('User: \'{0}\' on PATH: {1}'.format(user, path))

    timenow = datetime.datetime.utcnow()
    timestamp = timenow.strftime('%a, %d %b %Y %H:%M:%S %Z').strip()
    with salt.utils.fopen(ssh_keyfile, 'r') as kh_:
        rsa_key = RSA.importKey(kh_)
    rsa_ = PKCS1_v1_5.new(rsa_key)
    hash_ = SHA256.new()
    hash_.update(timestamp)
    signed = base64.b64encode(rsa_.sign(hash_))
    keyid = '/{0}/keys/{1}'.format(user, ssh_keyname)

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Api-Version': JOYENT_API_VERSION,
        'Date': timestamp,
        'Authorization': 'Signature keyId="{0}",algorithm="rsa-sha256" {1}'.format(
            keyid,
            signed
        ),
    }

    if not isinstance(args, dict):
        args = {}

    # post form data
    if not data:
        data = json.dumps({})

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        params=args,
        header_dict=headers,
        data=data,
        decode=False,
        text=True,
        status=True,
        headers=True,
        verify_ssl=verify_ssl,
        opts=__opts__,
    )
    log.debug(
        'Joyent Response Status Code: {0}'.format(
            result['status']
        )
    )
    if 'Content-Length' in result['headers']:
        content = result['text']
        return_content = yaml.safe_load(content)

    return [result['status'], return_content]
