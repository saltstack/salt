# -*- coding: utf-8 -*-
"""
Scaleway Cloud Module
==========================

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
      provider: scaleway

:depends: requests
"""

from __future__ import absolute_import

import copy
import json
import logging
import os
import pprint
import time

try:
    import requests
except ImportError:
    requests = None

import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout
)
import salt.utils.cloud


log = logging.getLogger(__name__)


# Only load in this module if the Scaleway configurations are in place
def __virtual__():
    """ Check for Scaleway configurations.
    """
    if requests is None:
        return False

    if get_configured_provider() is False:
        return False

    return True


def get_configured_provider():
    """ Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'scaleway',
        ('token',)
    )

# def avail_locations(call=None):


def avail_images(call=None):
    """ Return a list of the images that are on the provider.
    """
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

# def avail_sizes(call=None):


def list_nodes(call=None):
    """ Return a list of the BareMetal servers that are on the provider.
    """
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    items = query(method='servers')

    ret = {}
    for node in items['servers']:
        private_ips = []
        public_ips = []
        image_id = ''

        if 'public_ip' in node and node['public_ip'] is not None:
            public_ips.append(node['public_ip']['address'])

        if 'private_ip' in node and node['private_ip'] is not None:
            private_ips.append(node['private_ip'])

        if 'image' in node and node['image'] is not None:
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
    """ Return a list of the BareMetal servers that are on the provider.
    """
    if call == 'action':
        raise SaltCloudSystemExit(
            'list_nodes_full must be called with -f or --function'
        )

    items = query(method='servers')

    ret = {}
    for node in items['servers']:
        ret[node['name']] = {}
        for item in node:
            value = node[item]
            if value is not None:
                value = value
            ret[node['name']][item] = value
    return ret


def list_nodes_select(call=None):
    """ Return a list of the BareMetal servers that are on the provider, with
    select fields.
    """
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def get_image(vm_):
    """ Return the image object to use.
    """
    images = avail_images()
    vm_image = str(config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    ))
    for image in images:
        if vm_image in (images[image]['name'], images[image]['id']):
            return images[image]['id']
    raise SaltCloudNotFound(
        'The specified image, {0!r}, could not be found.'.format(vm_image)
    )


def create_node(args):
    """ Create a node.
    """
    node = query(method='servers', args=args, http_method='post')

    action = query(
        method='servers',
        server_id=node['server']['id'],
        command='action',
        args={'action': 'poweron'},
        http_method='post'
    )
    return node


def create(vm_):
    """ Create a single VM from a data dict.
    """
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

    access_key = config.get_cloud_config_value(
        'access_key', get_configured_provider(), __opts__, search_global=False
    )

    kwargs = {
        'name': vm_['name'],
        'organization': access_key,
        'image': get_image(vm_),
    }

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
            'Error creating {0} on Scaleway\n\n'
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

        if data.get('public_ip') is not None:
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
        if data.get('public_ip') is not None:
            ip_address = data['public_ip']['address']

        deploy_kwargs = {
            'opts': __opts__,
            'host': ip_address,
            'username': ssh_username,
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
            'script_env': config.get_cloud_config_value('script_env', vm_,
                                                        __opts__),
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


def query(method='servers', server_id=None, command=None, args=None,
          http_method='get'):
    """ Make a call to the Scaleway API.
    """
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
            'Error: {1!r}'.format(
                request.getcode(),
                request.text
            )
        )

    log.debug(request.url)

    # success without data
    if request.status_code == 204:
        return True

    return request.json()


def script(vm_):
    """ Return the script deployment object.
    """
    return salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )


def show_instance(name, call=None):
    """ Show the details from a Scaleway BareMetal server.
    """
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
            return list_nodes_full()[name]
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


def destroy(name, call=None):
    """ Destroy a node. Will check termination protection and warn if enabled.

    CLI Example:
    .. code-block:: bash
        salt-cloud --destroy mymachine
    """
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
