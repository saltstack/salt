# -*- coding: utf-8 -*-
'''
Vultr Cloud Module using python-vultr bindings
==============================================

.. versionadded:: Boron

The Vultr cloud module is used to control access to the Vultr VPS system.

Use of this module only requires the ``api_key`` parameter.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/vultr.conf``:

.. code-block:: yaml

my-vultr-config:
  # Vultr account api key
  api_key: <supersecretapi_key>
  driver: vultr

'''

# Import python libs
from __future__ import absolute_import
import pprint
import logging
import time
import urllib

# Import salt cloud libs
import salt.config as config
import salt.utils.cloud
from salt.exceptions import SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'vultr'


def __virtual__():
    '''
    Set up the Vultr functions and check for configurations
    '''
    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    '''
    Return the first configured instance
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'vultr',
        ('api_key',)
    )


def avail_locations(conn=None):
    '''
    return available datacenter locations
    '''
    return _query('regions/list')


def avail_sizes(conn=None):
    '''
    Return available sizes ("plans" in VultrSpeak)
    '''
    return _query('plans/list')


def avail_images():
    '''
    Return available images
    '''
    return _query('os/list')


def list_nodes(**kwargs):
    '''
    Return basic data on nodes
    '''
    ret = {}

    nodes = list_nodes_full()
    for node in nodes:
        ret[node] = {}
        for prop in 'id', 'image', 'size', 'state', 'private_ips', 'public_ips':
            ret[node][prop] = nodes[node][prop]

    return ret


def list_nodes_full(**kwargs):
    '''
    Return all data on nodes
    '''
    nodes = _query('server/list')
    ret = {}

    for node in nodes:
        name = nodes[node]['label']
        ret[name] = nodes[node].copy()
        ret[name]['id'] = node
        ret[name]['image'] = nodes[node]['os']
        ret[name]['size'] = nodes[node]['VPSPLANID']
        ret[name]['state'] = nodes[node]['status']
        ret[name]['private_ips'] = []
        ret[name]['public_ips'] = nodes[node]['main_ip']

    return ret


def list_nodes_select(conn=None, call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__['query.selection'], call,
    )


def destroy(name):
    '''
    Remove a node from Vultr
    '''
    node = show_instance(name, call='action')
    params = {'SUBID': node['SUBID']}
    return _query('server/destroy', method='POST', decode=False, data=urllib.urlencode(params))


def stop(*args, **kwargs):
    '''
    Execute a "stop" action on a VM
    '''
    return _query('server/halt')


def start(*args, **kwargs):
    '''
    Execute a "start" action on a VM
    '''
    return _query('server/start')


def show_instance(name, call=None):
    '''
    Show the details from the provider concerning an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    nodes = list_nodes_full()
    # Find under which cloud service the name is listed, if any
    if name not in nodes:
        return {}
    salt.utils.cloud.cache_node(nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    if 'driver' not in vm_:
        vm_['driver'] = vm_['provider']

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

    kwargs = {
        'label': vm_['name'],
        'OSID': vm_['image'],
        'VPSPLANID': vm_['size'],
        'DCID': vm_['location'],
    }

    log.info('Creating Cloud VM {0}'.format(vm_['name']))

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': kwargs},
        transport=__opts__['transport'],
    )

    try:
        data = _query('server/create', method='POST', data=urllib.urlencode(kwargs))
    except Exception as exc:
        log.error(
            'Error creating {0} on Vultr\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: \n{1}'.format(
                vm_['name'], str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False

    def wait_for_hostname():
        '''
        Wait for the IP address to become available
        '''
        data = show_instance(vm_['name'], call='action')
        pprint.pprint(data)
        if str(data.get('main_ip', '0')) == '0':
            time.sleep(3)
            return False
        return data['main_ip']

    def wait_for_default_password():
        '''
        Wait for the IP address to become available
        '''
        data = show_instance(vm_['name'], call='action')
        pprint.pprint(data)
        if str(data.get('default_password', '')) == '':
            time.sleep(1)
            return False
        if '!' not in data['default_password']:
            time.sleep(1)
            return False
        return data['default_password']

    vm_['ssh_host'] = salt.utils.cloud.wait_for_fun(
        wait_for_hostname,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )
    vm_['password'] = salt.utils.cloud.wait_for_fun(
        wait_for_default_password,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60),
    )
    __opts__['hard_timeout'] = config.get_cloud_config_value(
        'hard_timeout',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=15,
    )

    # Bootstrap
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

    ret.update(show_instance(vm_['name'], call='action'))

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
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


def _query(path, method='GET', data=None, params=None, header_dict=None, decode=True):
    '''
    Perform a query directly against the Vultr REST API
    '''
    api_key = config.get_cloud_config_value(
        'api_key',
        get_configured_provider(),
        __opts__,
        search_global=False,
    )
    management_host = config.get_cloud_config_value(
        'management_host',
        get_configured_provider(),
        __opts__,
        search_global=False,
        default='api.vultr.com'
    )
    url = 'https://{management_host}/v1/{path}?api_key={api_key}'.format(
        management_host=management_host,
        path=path,
        api_key=api_key,
    )

    if header_dict is None:
        header_dict = {}

    result = salt.utils.http.query(
        url,
        method=method,
        params=params,
        data=data,
        header_dict=header_dict,
        port=443,
        text=True,
        decode=decode,
        decode_type='json',
        hide_fields=['api_key'],
        opts=__opts__,
    )

    if 'dict' in result:
        return result['dict']

    return
