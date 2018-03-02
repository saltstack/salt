# -*- coding: utf-8 -*-
'''
QingCloud Cloud Module
======================

.. versionadded:: 2015.8.0

The QingCloud cloud module is used to control access to the QingCloud.
http://www.qingcloud.com/

Use of this module requires the ``access_key_id``, ``secret_access_key``,
``zone`` and ``key_filename`` parameter to be set.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/qingcloud.conf``:

.. code-block:: yaml

    my-qingcloud:
      driver: qingcloud
      access_key_id: AKIDMRTGYONNLTFFRBQJ
      secret_access_key: clYwH21U5UOmcov4aNV2V2XocaHCG3JZGcxEczFu
      zone: pek2
      key_filename: /path/to/your.pem

:depends: requests
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import time
import pprint
import logging
import hmac
import base64
from hashlib import sha256

# Import Salt Libs
from salt.ext import six
from salt.ext.six.moves.urllib.parse import quote as _quote  # pylint: disable=import-error,no-name-in-module
from salt.ext.six.moves import range
import salt.utils.cloud
import salt.utils.data
import salt.utils.json
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


# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = 'qingcloud'

DEFAULT_QINGCLOUD_API_VERSION = 1
DEFAULT_QINGCLOUD_SIGNATURE_VERSION = 1


# Only load in this module if the qingcloud configurations are in place
def __virtual__():
    '''
    Check for QingCloud configurations.
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
        ('access_key_id', 'secret_access_key', 'zone', 'key_filename')
    )


def get_dependencies():
    '''
    Warn if dependencies aren't met.
    '''
    return config.check_driver_dependencies(
        __virtualname__,
        {'requests': HAS_REQUESTS}
    )


def _compute_signature(parameters, access_key_secret, method, path):
    '''
    Generate an API request signature. Detailed document can be found at:

    https://docs.qingcloud.com/api/common/signature.html
    '''
    parameters['signature_method'] = 'HmacSHA256'

    string_to_sign = '{0}\n{1}\n'.format(method.upper(), path)

    keys = sorted(parameters.keys())
    pairs = []
    for key in keys:
        val = six.text_type(parameters[key]).encode('utf-8')
        pairs.append(_quote(key, safe='') + '=' + _quote(val, safe='-_~'))
    qs = '&'.join(pairs)
    string_to_sign += qs

    h = hmac.new(access_key_secret, digestmod=sha256)
    h.update(string_to_sign)

    signature = base64.b64encode(h.digest()).strip()

    return signature


def query(params=None):
    '''
    Make a web call to QingCloud IaaS API.
    '''
    path = 'https://api.qingcloud.com/iaas/'

    access_key_id = config.get_cloud_config_value(
        'access_key_id', get_configured_provider(), __opts__, search_global=False
    )
    access_key_secret = config.get_cloud_config_value(
        'secret_access_key', get_configured_provider(), __opts__, search_global=False
    )

    # public interface parameters
    real_parameters = {
        'access_key_id': access_key_id,
        'signature_version': DEFAULT_QINGCLOUD_SIGNATURE_VERSION,
        'time_stamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'version': DEFAULT_QINGCLOUD_API_VERSION,
    }

    # include action or function parameters
    if params:
        for key, value in params.items():
            if isinstance(value, list):
                for i in range(1, len(value) + 1):
                    if isinstance(value[i - 1], dict):
                        for sk, sv in value[i - 1].items():
                            if isinstance(sv, dict) or isinstance(sv, list):
                                sv = salt.utils.json.dumps(sv, separators=(',', ':'))
                            real_parameters['{0}.{1}.{2}'.format(key, i, sk)] = sv
                    else:
                        real_parameters['{0}.{1}'.format(key, i)] = value[i - 1]
            else:
                real_parameters[key] = value

    # Calculate the string for Signature
    signature = _compute_signature(real_parameters, access_key_secret, 'GET', '/iaas/')
    real_parameters['signature'] = signature

    # print('parameters:')
    # pprint.pprint(real_parameters)

    request = requests.get(path, params=real_parameters, verify=False)

    # print('url:')
    # print(request.url)

    if request.status_code != 200:
        raise SaltCloudSystemExit(
            'An error occurred while querying QingCloud. HTTP Code: {0}  '
            'Error: \'{1}\''.format(
                request.status_code,
                request.text
            )
        )

    log.debug(request.url)

    content = request.text
    result = salt.utils.json.loads(content)

    # print('response:')
    # pprint.pprint(result)

    if result['ret_code'] != 0:
        raise SaltCloudSystemExit(
            pprint.pformat(result.get('message', {}))
        )

    return result


def avail_locations(call=None):
    '''
    Return a dict of all available locations on the provider with
    relevant data.

    CLI Examples:

    .. code-block:: bash

        salt-cloud --list-locations my-qingcloud
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_locations function must be called with '
            '-f or --function, or with the --list-locations option'
        )

    params = {
        'action': 'DescribeZones',
    }
    items = query(params=params)

    result = {}
    for region in items['zone_set']:
        result[region['zone_id']] = {}
        for key in region:
            result[region['zone_id']][key] = six.text_type(region[key])

    return result


def _get_location(vm_=None):
    '''
    Return the VM's location. Used by create().
    '''
    locations = avail_locations()

    vm_location = six.text_type(config.get_cloud_config_value(
        'zone', vm_, __opts__, search_global=False
    ))

    if not vm_location:
        raise SaltCloudNotFound('No location specified for this VM.')

    if vm_location in locations:
        return vm_location

    raise SaltCloudNotFound(
        'The specified location, \'{0}\', could not be found.'.format(
            vm_location
        )
    )


def _get_specified_zone(kwargs=None, provider=None):
    if provider is None:
        provider = get_configured_provider()

    if isinstance(kwargs, dict):
        zone = kwargs.get('zone', None)
        if zone is not None:
            return zone

    zone = provider['zone']
    return zone


def avail_images(kwargs=None, call=None):
    '''
    Return a list of the images that are on the provider.

    CLI Examples:

    .. code-block:: bash

        salt-cloud --list-images my-qingcloud
        salt-cloud -f avail_images my-qingcloud zone=gd1
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    if not isinstance(kwargs, dict):
        kwargs = {}

    params = {
        'action': 'DescribeImages',
        'provider': 'system',
        'zone': _get_specified_zone(kwargs, get_configured_provider()),
    }
    items = query(params=params)

    result = {}
    for image in items['image_set']:
        result[image['image_id']] = {}
        for key in image:
            result[image['image_id']][key] = image[key]

    return result


def _get_image(vm_):
    '''
    Return the VM's image. Used by create().
    '''
    images = avail_images()
    vm_image = six.text_type(config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    ))

    if not vm_image:
        raise SaltCloudNotFound('No image specified for this VM.')

    if vm_image in images:
        return vm_image

    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
    )


def show_image(kwargs, call=None):
    '''
    Show the details from QingCloud concerning an image.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f show_image my-qingcloud image=trustysrvx64c
        salt-cloud -f show_image my-qingcloud image=trustysrvx64c,coreos4
        salt-cloud -f show_image my-qingcloud image=trustysrvx64c zone=ap1
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_images function must be called with '
            '-f or --function'
        )

    if not isinstance(kwargs, dict):
        kwargs = {}

    images = kwargs['image']
    images = images.split(',')

    params = {
        'action': 'DescribeImages',
        'images': images,
        'zone': _get_specified_zone(kwargs, get_configured_provider()),
    }

    items = query(params=params)

    if len(items['image_set']) == 0:
        raise SaltCloudNotFound('The specified image could not be found.')

    result = {}
    for image in items['image_set']:
        result[image['image_id']] = {}
        for key in image:
            result[image['image_id']][key] = image[key]

    return result


# QingCloud doesn't provide an API of geting instance sizes
QINGCLOUD_SIZES = {
    'pek2': {
        'c1m1': {'cpu': 1, 'memory': '1G'},
        'c1m2': {'cpu': 1, 'memory': '2G'},
        'c1m4': {'cpu': 1, 'memory': '4G'},
        'c2m2': {'cpu': 2, 'memory': '2G'},
        'c2m4': {'cpu': 2, 'memory': '4G'},
        'c2m8': {'cpu': 2, 'memory': '8G'},
        'c4m4': {'cpu': 4, 'memory': '4G'},
        'c4m8': {'cpu': 4, 'memory': '8G'},
        'c4m16': {'cpu': 4, 'memory': '16G'},
    },
    'pek1': {
        'small_b': {'cpu': 1, 'memory': '1G'},
        'small_c': {'cpu': 1, 'memory': '2G'},
        'medium_a': {'cpu': 2, 'memory': '2G'},
        'medium_b': {'cpu': 2, 'memory': '4G'},
        'medium_c': {'cpu': 2, 'memory': '8G'},
        'large_a': {'cpu': 4, 'memory': '4G'},
        'large_b': {'cpu': 4, 'memory': '8G'},
        'large_c': {'cpu': 4, 'memory': '16G'},
    },
}
QINGCLOUD_SIZES['ap1'] = QINGCLOUD_SIZES['pek2']
QINGCLOUD_SIZES['gd1'] = QINGCLOUD_SIZES['pek2']


def avail_sizes(kwargs=None, call=None):
    '''
    Return a list of the instance sizes that are on the provider.

    CLI Examples:

    .. code-block:: bash

        salt-cloud --list-sizes my-qingcloud
        salt-cloud -f avail_sizes my-qingcloud zone=pek2
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    zone = _get_specified_zone(kwargs, get_configured_provider())

    result = {}
    for size_key in QINGCLOUD_SIZES[zone]:
        result[size_key] = {}
        for attribute_key in QINGCLOUD_SIZES[zone][size_key]:
            result[size_key][attribute_key] = QINGCLOUD_SIZES[zone][size_key][attribute_key]

    return result


def _get_size(vm_):
    '''
    Return the VM's size. Used by create().
    '''
    sizes = avail_sizes()

    vm_size = six.text_type(config.get_cloud_config_value(
        'size', vm_, __opts__, search_global=False
    ))

    if not vm_size:
        raise SaltCloudNotFound('No size specified for this instance.')

    if vm_size in sizes.keys():
        return vm_size

    raise SaltCloudNotFound(
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
    )


def _show_normalized_node(full_node):
    '''
    Normalize the QingCloud instance data. Used by list_nodes()-related
    functions.
    '''
    public_ips = full_node.get('eip', [])
    if public_ips:
        public_ip = public_ips['eip_addr']
        public_ips = [public_ip, ]

    private_ips = []
    for vxnet in full_node.get('vxnets', []):
        private_ip = vxnet.get('private_ip', None)
        if private_ip:
            private_ips.append(private_ip)

    normalized_node = {
        'id': full_node['instance_id'],
        'image': full_node['image']['image_id'],
        'size': full_node['instance_type'],
        'state': full_node['status'],
        'private_ips': private_ips,
        'public_ips': public_ips,
    }

    return normalized_node


def list_nodes_full(call=None):
    '''
    Return a list of the instances that are on the provider.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -F my-qingcloud
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    zone = _get_specified_zone()

    params = {
        'action': 'DescribeInstances',
        'zone': zone,
        'status': ['pending', 'running', 'stopped', 'suspended'],
    }
    items = query(params=params)

    log.debug('Total %s instances found in zone %s', items['total_count'], zone)

    result = {}

    if items['total_count'] == 0:
        return result

    for node in items['instance_set']:
        normalized_node = _show_normalized_node(node)
        node.update(normalized_node)

        result[node['instance_id']] = node

    provider = __active_provider_name__ or 'qingcloud'
    if ':' in provider:
        comps = provider.split(':')
        provider = comps[0]

    __opts__['update_cachedir'] = True
    __utils__['cloud.cache_node_list'](result, provider, __opts__)

    return result


def list_nodes(call=None):
    '''
    Return a list of the instances that are on the provider.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -Q my-qingcloud
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    nodes = list_nodes_full()

    ret = {}
    for instance_id, full_node in nodes.items():
        ret[instance_id] = {
            'id': full_node['id'],
            'image': full_node['image'],
            'size': full_node['size'],
            'state': full_node['state'],
            'public_ips': full_node['public_ips'],
            'private_ips': full_node['private_ips'],
        }

    return ret


def list_nodes_min(call=None):
    '''
    Return a list of the instances that are on the provider. Only a list of
    instances names, and their state, is returned.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-qingcloud
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )

    nodes = list_nodes_full()

    result = {}
    for instance_id, full_node in nodes.items():
        result[instance_id] = {
            'name': full_node['instance_name'],
            'status': full_node['status'],
        }

    return result


def list_nodes_select(call=None):
    '''
    Return a list of the instances that are on the provider, with selected
    fields.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -S my-qingcloud
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'),
        __opts__['query.selection'],
        call,
    )


def show_instance(instance_id, call=None, kwargs=None):
    '''
    Show the details from QingCloud concerning an instance.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a show_instance i-2f733r5n
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    params = {
        'action': 'DescribeInstances',
        'instances.1': instance_id,
        'zone': _get_specified_zone(kwargs=None, provider=get_configured_provider()),
    }
    items = query(params=params)

    if items['total_count'] == 0:
        raise SaltCloudNotFound(
            'The specified instance, \'{0}\', could not be found.'.format(instance_id)
        )

    full_node = items['instance_set'][0]
    normalized_node = _show_normalized_node(full_node)
    full_node.update(normalized_node)

    result = full_node

    return result


def _query_node_data(instance_id):
    data = show_instance(instance_id, call='action')

    if not data:
        return False

    if data.get('private_ips', []):
        return data


def create(vm_):
    '''
    Create a single instance from a data dict.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -p qingcloud-ubuntu-c1m1 hostname1
        salt-cloud -m /path/to/mymap.sls -P
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'qingcloud',
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

    log.info('Creating Cloud VM %s', vm_['name'])

    # params
    params = {
        'action': 'RunInstances',
        'instance_name': vm_['name'],
        'zone': _get_location(vm_),
        'instance_type': _get_size(vm_),
        'image_id': _get_image(vm_),
        'vxnets.1': vm_['vxnets'],
        'login_mode': vm_['login_mode'],
        'login_keypair': vm_['login_keypair'],
    }

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args={
            'kwargs': __utils__['cloud.filter_event']('requesting', params, list(params)),
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    result = query(params)
    new_instance_id = result['instances'][0]

    try:
        data = salt.utils.cloud.wait_for_ip(
            _query_node_data,
            update_args=(new_instance_id,),
            timeout=config.get_cloud_config_value(
                'wait_for_ip_timeout', vm_, __opts__, default=10 * 60
            ),
            interval=config.get_cloud_config_value(
                'wait_for_ip_interval', vm_, __opts__, default=10
            ),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(six.text_type(exc))

    private_ip = data['private_ips'][0]

    log.debug('VM %s is now running', private_ip)

    vm_['ssh_host'] = private_ip

    # The instance is booted and accessible, let's Salt it!
    __utils__['cloud.bootstrap'](vm_, __opts__)

    log.info('Created Cloud VM \'%s\'', vm_['name'])

    log.debug('\'%s\' VM creation details:\n%s', vm_['name'], pprint.pformat(data))

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return data


def script(vm_):
    '''
    Return the script deployment object.
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


def start(instance_id, call=None):
    '''
    Start an instance.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a start i-2f733r5n
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Starting instance %s', instance_id)

    params = {
        'action': 'StartInstances',
        'zone': _get_specified_zone(provider=get_configured_provider()),
        'instances.1': instance_id,
    }
    result = query(params)

    return result


def stop(instance_id, force=False, call=None):
    '''
    Stop an instance.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a stop i-2f733r5n
        salt-cloud -a stop i-2f733r5n force=True
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Stopping instance %s', instance_id)

    params = {
        'action': 'StopInstances',
        'zone': _get_specified_zone(provider=get_configured_provider()),
        'instances.1': instance_id,
        'force': int(force),
    }
    result = query(params)

    return result


def reboot(instance_id, call=None):
    '''
    Reboot an instance.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a reboot i-2f733r5n
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Rebooting instance %s', instance_id)

    params = {
        'action': 'RestartInstances',
        'zone': _get_specified_zone(provider=get_configured_provider()),
        'instances.1': instance_id,
    }
    result = query(params)

    return result


def destroy(instance_id, call=None):
    '''
    Destroy an instance.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a destroy i-2f733r5n
        salt-cloud -d i-2f733r5n
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    instance_data = show_instance(instance_id, call='action')
    name = instance_data['instance_name']

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    params = {
        'action': 'TerminateInstances',
        'zone': _get_specified_zone(provider=get_configured_provider()),
        'instances.1': instance_id,
    }
    result = query(params)

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return result
