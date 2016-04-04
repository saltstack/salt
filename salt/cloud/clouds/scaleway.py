# -*- coding: utf-8 -*-
'''
Scaleway Cloud Module
=====================

.. versionadded:: 2015.8.0

The Scaleway cloud module is used to interact with your Scaleway BareMetal
Servers.

Use of this module only requires the ``api_key`` parameter to be set. Set up
the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/scaleway.conf``:

.. code-block:: yaml

    scaleway-config:
      # Scaleway organization and token
      access_key: 0e604a2c-aea6-4081-acb2-e1d1258ef95c
      token: be8fd96b-04eb-4d39-b6ba-a9edbcf17f12
      driver: scaleway

:depends: requests
'''

# Import Python Libs
from __future__ import absolute_import
import json
import logging
import pprint
import time

# Import Salt Libs
from salt.ext.six.moves import range
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)

# Import Third Party Libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

log = logging.getLogger(__name__)

__virtualname__ = 'scaleway'


# Only load in this module if the Scaleway configurations are in place
def __virtual__():
    '''
    Check for Scaleway configurations.
    '''
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_configured_provider():
    ''' Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ('token',)
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'requests': HAS_REQUESTS}
    )


def avail_images(call=None):
    ''' Return a list of the images that are on the provider.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    items = query(method='images')
    ret = {}
    for image in items['images']:
        ret[image['id']] = {}
        for item in image:
            ret[image['id']][item] = str(image[item])

    return ret


def list_nodes(call=None):
    ''' Return a list of the BareMetal servers that are on the provider.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    items = query(method='servers')

    ret = {}
    for node in items['servers']:
        public_ips = []
        private_ips = []
        image_id = ''

        if node.get('public_ip'):
            public_ips = [node['public_ip']['address']]

        if node.get('private_ip'):
            private_ips = [node['private_ip']]

        if node.get('image'):
            image_id = node['image']['id']

        ret[node['name']] = {
            'id': node['id'],
            'image_id': image_id,
            'public_ips': public_ips,
            'private_ips': private_ips,
            'size': node['volumes']['0']['size'],
            'state': node['state'],
        }
    return ret


def list_nodes_full(call=None):
    ''' Return a list of the BareMetal servers that are on the provider.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'list_nodes_full must be called with -f or --function'
        )

    items = query(method='servers')

    # For each server, iterate on its parameters.
    ret = {}
    for node in items['servers']:
        ret[node['name']] = {}
        for item in node:
            value = node[item]
            ret[node['name']][item] = value
    return ret


def list_nodes_select(call=None):
    ''' Return a list of the BareMetal servers that are on the provider, with
    select fields.
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def get_image(server_):
    ''' Return the image object to use.
    '''
    images = avail_images()
    server_image = str(config.get_cloud_config_value(
        'image', server_, __opts__, search_global=False
    ))
    for image in images:
        if server_image in (images[image]['name'], images[image]['id']):
            return images[image]['id']
    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(server_image)
    )


def create_node(args):
    ''' Create a node.
    '''
    node = query(method='servers', args=args, http_method='post')

    action = query(
        method='servers',
        server_id=node['server']['id'],
        command='action',
        args={'action': 'poweron'},
        http_method='post'
    )
    return node


def create(server_):
    '''
    Create a single BareMetal server from a data dict.
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if server_['profile'] and config.is_profile_configured(__opts__,
                                                               __active_provider_name__ or 'scaleway',
                                                               server_['profile'],
                                                               vm_=server_) is False:
            return False
    except AttributeError:
        pass

    # Since using "provider: <provider-engine>" is deprecated, alias provider
    # to use driver: "driver: <provider-engine>"
    if 'provider' in server_:
        server_['driver'] = server_.pop('provider')

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(server_['name']),
        {
            'name': server_['name'],
            'profile': server_['profile'],
            'provider': server_['driver'],
        },
        transport=__opts__['transport']
    )

    log.info('Creating a BareMetal server {0}'.format(server_['name']))

    access_key = config.get_cloud_config_value(
        'access_key', get_configured_provider(), __opts__, search_global=False
    )

    kwargs = {
        'name': server_['name'],
        'organization': access_key,
        'image': get_image(server_),
    }

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(server_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport']
    )

    try:
        ret = create_node(kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on Scaleway\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: {1}'.format(
                server_['name'],
                str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    def __query_node_data(server_name):
        ''' Called to check if the server has a public IP address.
        '''
        data = show_instance(server_name, 'action')
        if data and data.get('public_ip'):
            return data
        return False

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(server_['name'],),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', server_, __opts__, default=10 * 60),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', server_, __opts__, default=10),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(server_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    server_['ssh_host'] = data['public_ip']['address']
    server_['ssh_password'] = config.get_cloud_config_value(
        'ssh_password', server_, __opts__
    )
    ret = salt.utils.cloud.bootstrap(server_, __opts__)

    ret.update(data)

    log.info('Created BareMetal server \'{0[name]}\''.format(server_))
    log.debug(
        '\'{0[name]}\' BareMetal server creation details:\n{1}'.format(
            server_, pprint.pformat(data)
        )
    )

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(server_['name']),
        {
            'name': server_['name'],
            'profile': server_['profile'],
            'provider': server_['driver'],
        },
        transport=__opts__['transport']
    )

    return ret


def query(method='servers', server_id=None, command=None, args=None,
          http_method='get'):
    ''' Make a call to the Scaleway API.
    '''
    base_path = str(config.get_cloud_config_value(
        'api_root',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default='https://api.scaleway.com'
    ))

    path = '{0}/{1}/'.format(base_path, method)

    if server_id:
        path += '{0}/'.format(server_id)

    if command:
        path += command

    if not isinstance(args, dict):
        args = {}

    token = config.get_cloud_config_value(
        'token', get_configured_provider(), __opts__, search_global=False
    )

    data = json.dumps(args)

    requester = getattr(requests, http_method)
    request = requester(
        path, data=data,
        headers={'X-Auth-Token': token, 'Content-Type': 'application/json'}
    )
    if request.status_code > 299:
        raise SaltCloudSystemExit(
            'An error occurred while querying Scaleway. HTTP Code: {0}  '
            'Error: \'{1}\''.format(
                request.getcode(),
                request.text
            )
        )

    log.debug(request.url)

    # success without data
    if request.status_code == 204:
        return True

    return request.json()


def script(server_):
    ''' Return the script deployment object.
    '''
    return salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', server_, __opts__),
        server_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, server_)
        )
    )


def show_instance(name, call=None):
    ''' Show the details from a Scaleway BareMetal server.
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )
    node = _get_node(name)
    salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)
    return node


def _get_node(name):
    for attempt in reversed(list(range(10))):
        try:
            return list_nodes_full()[name]
        except KeyError:
            log.debug(
                'Failed to get the data for node \'{0}\'. Remaining '
                'attempts: {1}'.format(
                    name, attempt
                )
            )
            # Just a little delay between attempts...
            time.sleep(0.5)
    return {}


def destroy(name, call=None):
    ''' Destroy a node. Will check termination protection and warn if enabled.

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
    node = query(
        method='servers', server_id=data['id'], command='action',
        args={'action': 'terminate'}, http_method='post'
    )

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name},
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(
            name, __active_provider_name__.split(':')[0], __opts__
        )

    return node
