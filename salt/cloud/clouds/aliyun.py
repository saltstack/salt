# -*- coding: utf-8 -*-
'''
AliYun ECS Cloud Module
=======================

.. versionadded:: 2014.7.0

The Aliyun cloud module is used to control access to the aliyun ECS.
http://www.aliyun.com/

Use of this module requires the ``id`` and ``key`` parameter to be set.
Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/aliyun.conf``:

.. code-block:: yaml

    my-aliyun-config:
      # aliyun Access Key ID
      id: wFGEwgregeqw3435gDger
      # aliyun Access Key Secret
      key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg
      location: cn-qingdao
      driver: aliyun

:depends: requests
'''

# Import python libs
from __future__ import absolute_import
import time
import json
import pprint
import logging
import hmac
import uuid
import sys
import base64
from hashlib import sha1

# Import Salt libs
from salt.ext.six.moves.urllib.parse import quote as _quote  # pylint: disable=import-error,no-name-in-module

# Import salt cloud libs
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

# Get logging started
log = logging.getLogger(__name__)

ALIYUN_LOCATIONS = {
    # 'us-west-2': 'ec2_us_west_oregon',
    'cn-hangzhou': 'AliYun HangZhou Region',
    'cn-beijing': 'AliYun BeiJing Region',
    'cn-hongkong': 'AliYun HongKong Region',
    'cn-qingdao': 'AliYun QingDao Region',
    'cn-shanghai': 'AliYun ShangHai Region',
    'cn-shenzhen': 'AliYun ShenZheng Region',
    'ap-northeast-1': 'AliYun DongJing Region',
    'ap-southeast-1': 'AliYun XinJiaPo Region',
    'ap-southeast-2': 'AliYun XiNi Region',
    'eu-central-1': 'EU FalaKeFu Region',
    'me-east-1': 'ME DiBai Region',
    'us-east-1': 'US FuJiNiYa Region',
    'us-west-1': 'US GuiGu Region',
}
DEFAULT_LOCATION = 'cn-hangzhou'

DEFAULT_ALIYUN_API_VERSION = '2014-05-26'

__virtualname__ = 'aliyun'


# Only load in this module if the aliyun configurations are in place
def __virtual__():
    '''
    Check for aliyun configurations
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
        ('id', 'key')
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

    params = {'Action': 'DescribeRegions'}
    items = query(params=params)

    ret = {}
    for region in items['Regions']['Region']:
        ret[region['RegionId']] = {}
        for item in region:
            ret[region['RegionId']][item] = str(region[item])

    return ret


def avail_images(kwargs=None, call=None):
    '''
    Return a list of the images that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    if not isinstance(kwargs, dict):
        kwargs = {}

    provider = get_configured_provider()
    location = provider.get('location', DEFAULT_LOCATION)

    if 'location' in kwargs:
        location = kwargs['location']

    params = {
        'Action': 'DescribeImages',
        'RegionId': location,
        'PageSize': '100',
    }
    items = query(params=params)

    ret = {}
    for image in items['Images']['Image']:
        ret[image['ImageId']] = {}
        for item in image:
            ret[image['ImageId']][item] = str(image[item])

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

    params = {'Action': 'DescribeInstanceTypes'}
    items = query(params=params)

    ret = {}
    for image in items['InstanceTypes']['InstanceType']:
        ret[image['InstanceTypeId']] = {}
        for item in image:
            ret[image['InstanceTypeId']][item] = str(image[item])

    return ret


def get_location(vm_=None):
    '''
    Return the aliyun region to use, in this order:
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


def list_availability_zones(call=None):
    '''
    List all availability zones in the current region
    '''
    ret = {}

    params = {'Action': 'DescribeZones',
              'RegionId': get_location()}
    items = query(params)

    for zone in items['Zones']['Zone']:
        ret[zone['ZoneId']] = {}
        for item in zone:
            ret[zone['ZoneId']][item] = str(zone[item])

    return ret


def list_nodes_min(call=None):
    '''
    Return a list of the VMs that are on the provider. Only a list of VM names,
    and their state, is returned. This is the minimum amount of information
    needed to check for existing VMs.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_min function must be called with -f or --function.'
        )

    ret = {}
    location = get_location()
    params = {
        'Action': 'DescribeInstanceStatus',
        'RegionId': location,
    }
    nodes = query(params)

    log.debug('Total {0} instance found in Region {1}'.format(
        nodes['TotalCount'], location)
    )
    if 'Code' in nodes or nodes['TotalCount'] == 0:
        return ret

    for node in nodes['InstanceStatuses']['InstanceStatus']:
        ret[node['InstanceId']] = {}
        for item in node:
            ret[node['InstanceId']][item] = node[item]

    return ret


def list_nodes(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    nodes = list_nodes_full()
    ret = {}
    for instanceId in nodes:
        node = nodes[instanceId]
        ret[node['name']] = {
            'id': node['id'],
            'name': node['name'],
            'public_ips': node['public_ips'],
            'private_ips': node['private_ips'],
            'size': node['size'],
            'state': str(node['state']),
        }
    return ret


def list_nodes_full(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f '
            'or --function.'
        )

    ret = {}
    location = get_location()
    params = {
        'Action': 'DescribeInstanceStatus',
        'RegionId': location,
        'PageSize': '50'
    }
    result = query(params=params)

    log.debug('Total {0} instance found in Region {1}'.format(
        result['TotalCount'], location)
    )
    if 'Code' in result or result['TotalCount'] == 0:
        return ret

    # aliyun max 100 top instance in api
    result_instancestatus = result['InstanceStatuses']['InstanceStatus']
    if result['TotalCount'] > 50:
        params['PageNumber'] = '2'
        result = query(params=params)
        result_instancestatus.update(result['InstanceStatuses']['InstanceStatus'])

    for node in result_instancestatus:

        instanceId = node.get('InstanceId', '')

        params = {
            'Action': 'DescribeInstanceAttribute',
            'InstanceId': instanceId
        }
        items = query(params=params)
        if 'Code' in items:
            log.warning('Query instance:{0} attribute failed'.format(instanceId))
            continue

        name = items['InstanceName']
        ret[name] = {
            'id': items['InstanceId'],
            'name': name,
            'image': items['ImageId'],
            'size': 'TODO',
            'state': items['Status']
        }
        for item in items:
            value = items[item]
            if value is not None:
                value = str(value)
            if item == "PublicIpAddress":
                ret[name]['public_ips'] = items[item]['IpAddress']
            if item == "InnerIpAddress" and 'private_ips' not in ret[name]:
                ret[name]['private_ips'] = items[item]['IpAddress']
            if item == 'VpcAttributes':
                vpc_ips = items[item]['PrivateIpAddress']['IpAddress']
                if len(vpc_ips) > 0:
                    ret[name]['private_ips'] = vpc_ips
            ret[name][item] = value

    provider = __active_provider_name__ or 'aliyun'
    if ':' in provider:
        comps = provider.split(':')
        provider = comps[0]

    __opts__['update_cachedir'] = True
    __utils__['cloud.cache_node_list'](ret, provider, __opts__)

    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full('function'), __opts__['query.selection'], call,
    )


def list_securitygroup(call=None):
    '''
    Return a list of security group
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    params = {
        'Action': 'DescribeSecurityGroups',
        'RegionId': get_location(),
        'PageSize': '50',
    }

    result = query(params)
    if 'Code' in result:
        return {}

    ret = {}
    for sg in result['SecurityGroups']['SecurityGroup']:
        ret[sg['SecurityGroupId']] = {}
        for item in sg:
            ret[sg['SecurityGroupId']][item] = sg[item]

    return ret


def get_image(vm_):
    '''
    Return the image object to use
    '''
    images = avail_images()
    vm_image = str(config.get_cloud_config_value(
        'image', vm_, __opts__, search_global=False
    ))

    if not vm_image:
        raise SaltCloudNotFound('No image specified for this VM.')

    if vm_image and str(vm_image) in images:
        return images[vm_image]['ImageId']
    raise SaltCloudNotFound(
        'The specified image, \'{0}\', could not be found.'.format(vm_image)
    )


def get_securitygroup(vm_):
    '''
    Return the security group
    '''
    sgs = list_securitygroup()
    securitygroup = config.get_cloud_config_value(
        'securitygroup', vm_, __opts__, search_global=False
    )

    if not securitygroup:
        raise SaltCloudNotFound('No securitygroup ID specified for this VM.')

    if securitygroup and str(securitygroup) in sgs:
        return sgs[securitygroup]['SecurityGroupId']
    raise SaltCloudNotFound(
        'The specified security group, \'{0}\', could not be found.'.format(
            securitygroup)
    )


def get_size(vm_):
    '''
    Return the VM's size. Used by create_node().
    '''
    sizes = avail_sizes()
    vm_size = str(config.get_cloud_config_value(
        'size', vm_, __opts__, search_global=False
    ))

    if not vm_size:
        raise SaltCloudNotFound('No size specified for this VM.')

    if vm_size and str(vm_size) in sizes:
        return sizes[vm_size]['InstanceTypeId']

    raise SaltCloudNotFound(
        'The specified size, \'{0}\', could not be found.'.format(vm_size)
    )


def __get_location(vm_):
    '''
    Return the VM's location
    '''
    locations = avail_locations()
    vm_location = str(config.get_cloud_config_value(
        'location', vm_, __opts__, search_global=False
    ))

    if not vm_location:
        raise SaltCloudNotFound('No location specified for this VM.')

    if vm_location and str(vm_location) in locations:
        return locations[vm_location]['RegionId']
    raise SaltCloudNotFound(
        'The specified location, \'{0}\', could not be found.'.format(
            vm_location
        )
    )


def start(name, call=None):
    '''
    Start a node

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a start myinstance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Starting node {0}'.format(name))

    instanceId = _get_node(name)['InstanceId']

    params = {'Action': 'StartInstance',
              'InstanceId': instanceId}
    result = query(params)

    return result


def stop(name, force=False, call=None):
    '''
    Stop a node

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a stop myinstance
        salt-cloud -a stop myinstance force=True
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Stopping node {0}'.format(name))

    instanceId = _get_node(name)['InstanceId']

    params = {
        'Action': 'StopInstance',
        'InstanceId': instanceId,
        'ForceStop': str(force).lower()
    }
    result = query(params)

    return result


def reboot(name, call=None):
    '''
    Reboot a node

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a reboot myinstance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Rebooting node {0}'.format(name))

    instance_id = _get_node(name)['InstanceId']

    params = {'Action': 'RebootInstance',
              'InstanceId': instance_id}
    result = query(params)

    return result


def create_node(kwargs):
    '''
    Convenience function to make the rest api call for node creation.
    '''
    if not isinstance(kwargs, dict):
        kwargs = {}

    # Required parameters
    params = {
        'Action': 'CreateInstance',
        'InstanceType': kwargs.get('size_id', ''),
        'RegionId': kwargs.get('region_id', DEFAULT_LOCATION),
        'ImageId': kwargs.get('image_id', ''),
        'SecurityGroupId': kwargs.get('securitygroup_id', ''),
        'InstanceName': kwargs.get('name', ''),
    }

    # Optional parameters'
    optional = [
        'InstanceName', 'InternetChargeType',
        'InternetMaxBandwidthIn', 'InternetMaxBandwidthOut',
        'HostName', 'Password', 'SystemDisk.Category', 'VSwitchId'
        # 'DataDisk.n.Size', 'DataDisk.n.Category', 'DataDisk.n.SnapshotId'
    ]

    for item in optional:
        if item in kwargs:
            params.update({item: kwargs[item]})

    # invoke web call
    result = query(params)
    return result['InstanceId']


def create(vm_):
    '''
    Create a single VM from a data dict
    '''
    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'aliyun',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args={
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    log.info('Creating Cloud VM {0}'.format(vm_['name']))
    kwargs = {
        'name': vm_['name'],
        'size_id': get_size(vm_),
        'image_id': get_image(vm_),
        'region_id': __get_location(vm_),
        'securitygroup_id': get_securitygroup(vm_),
    }
    if 'vswitch_id' in vm_:
        kwargs['VSwitchId'] = vm_['vswitch_id']
    if 'internet_chargetype' in vm_:
        kwargs['InternetChargeType'] = vm_['internet_chargetype']
    if 'internet_maxbandwidthin' in vm_:
        kwargs['InternetMaxBandwidthIn'] = str(vm_['internet_maxbandwidthin'])
    if 'internet_maxbandwidthout' in vm_:
        kwargs['InternetMaxBandwidthOut'] = str(vm_['internet_maxbandwidthOut'])
    if 'hostname' in vm_:
        kwargs['HostName'] = vm_['hostname']
    if 'password' in vm_:
        kwargs['Password'] = vm_['password']
    if 'instance_name' in vm_:
        kwargs['InstanceName'] = vm_['instance_name']
    if 'systemdisk_category' in vm_:
        kwargs['SystemDisk.Category'] = vm_['systemdisk_category']

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args={'kwargs': kwargs},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    try:
        ret = create_node(kwargs)
    except Exception as exc:
        log.error(
            'Error creating {0} on Aliyun ECS\n\n'
            'The following exception was thrown when trying to '
            'run the initial deployment: {1}'.format(
                vm_['name'],
                str(exc)
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return False
    # repair ip address error and start vm
    time.sleep(8)
    params = {'Action': 'StartInstance',
              'InstanceId': ret}
    query(params)

    def __query_node_data(vm_name):
        data = show_instance(vm_name, call='action')
        if not data:
            # Trigger an error in the wait_for_ip function
            return False
        if data.get('PublicIpAddress', None) is not None:
            return data

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

    if len(data['public_ips']) > 0:
        ssh_ip = data['public_ips'][0]
    elif len(data['private_ips']) > 0:
        ssh_ip = data['private_ips'][0]
    else:
        log.info('No available ip:cant connect to salt')
        return False
    log.debug('VM {0} is now running'.format(ssh_ip))
    vm_['ssh_host'] = ssh_ip

    # The instance is booted and accessible, let's Salt it!
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
        args={
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['driver'],
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return ret


def _compute_signature(parameters, access_key_secret):
    '''
    Generate aliyun request signature
    '''

    def percent_encode(line):
        if not isinstance(line, str):
            return line

        s = line
        if sys.stdin.encoding is None:
            s = line.decode().encode('utf8')
        else:
            s = line.decode(sys.stdin.encoding).encode('utf8')
        res = _quote(s, '')
        res = res.replace('+', '%20')
        res = res.replace('*', '%2A')
        res = res.replace('%7E', '~')
        return res

    sortedParameters = sorted(list(parameters.items()), key=lambda items: items[0])

    canonicalizedQueryString = ''
    for k, v in sortedParameters:
        canonicalizedQueryString += '&' + percent_encode(k) \
            + '=' + percent_encode(v)

    # All aliyun API only support GET method
    stringToSign = 'GET&%2F&' + percent_encode(canonicalizedQueryString[1:])

    h = hmac.new(access_key_secret + "&", stringToSign, sha1)
    signature = base64.encodestring(h.digest()).strip()
    return signature


def query(params=None):
    '''
    Make a web call to aliyun ECS REST API
    '''
    path = 'https://ecs-cn-hangzhou.aliyuncs.com'

    access_key_id = config.get_cloud_config_value(
        'id', get_configured_provider(), __opts__, search_global=False
    )
    access_key_secret = config.get_cloud_config_value(
        'key', get_configured_provider(), __opts__, search_global=False
    )

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # public interface parameters
    parameters = {
        'Format': 'JSON',
        'Version': DEFAULT_ALIYUN_API_VERSION,
        'AccessKeyId': access_key_id,
        'SignatureVersion': '1.0',
        'SignatureMethod': 'HMAC-SHA1',
        'SignatureNonce': str(uuid.uuid1()),
        'TimeStamp': timestamp,
    }

    # include action or function parameters
    if params:
        parameters.update(params)

    # Calculate the string for Signature
    signature = _compute_signature(parameters, access_key_secret)
    parameters['Signature'] = signature

    request = requests.get(path, params=parameters, verify=True)
    if request.status_code != 200:
        raise SaltCloudSystemExit(
            'An error occurred while querying aliyun ECS. HTTP Code: {0}  '
            'Error: \'{1}\''.format(
                request.status_code,
                request.text
            )
        )

    log.debug(request.url)

    content = request.text

    result = json.loads(content, object_hook=salt.utils.decode_dict)
    if 'Code' in result:
        raise SaltCloudSystemExit(
            pprint.pformat(result.get('Message', {}))
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


def show_disk(name, call=None):
    '''
    Show the disk details of the instance

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a show_disk aliyun myinstance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_disks action must be called with -a or --action.'
        )

    ret = {}
    params = {
        'Action': 'DescribeInstanceDisks',
        'InstanceId': name
    }
    items = query(params=params)

    for disk in items['Disks']['Disk']:
        ret[disk['DiskId']] = {}
        for item in disk:
            ret[disk['DiskId']][item] = str(disk[item])

    return ret


def list_monitor_data(kwargs=None, call=None):
    '''
    Get monitor data of the instance. If instance name is
    missing, will show all the instance monitor data on the region.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f list_monitor_data aliyun
        salt-cloud -f list_monitor_data aliyun name=AY14051311071990225bd
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The list_monitor_data must be called with -f or --function.'
        )

    if not isinstance(kwargs, dict):
        kwargs = {}

    ret = {}
    params = {
        'Action': 'GetMonitorData',
        'RegionId': get_location()
    }
    if 'name' in kwargs:
        params['InstanceId'] = kwargs['name']

    items = query(params=params)

    monitorData = items['MonitorData']

    for data in monitorData['InstanceMonitorData']:
        ret[data['InstanceId']] = {}
        for item in data:
            ret[data['InstanceId']][item] = str(data[item])

    return ret


def show_instance(name, call=None):
    '''
    Show the details from aliyun instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    return _get_node(name)


def _get_node(name):
    attempts = 5
    while attempts >= 0:
        try:
            return list_nodes_full()[name]
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
    raise SaltCloudNotFound(
        'The specified instance {0} not found'.format(name)
    )


def show_image(kwargs, call=None):
    '''
    Show the details from aliyun image
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_images function must be called with '
            '-f or --function'
        )

    if not isinstance(kwargs, dict):
        kwargs = {}

    location = get_location()
    if 'location' in kwargs:
        location = kwargs['location']

    params = {
        'Action': 'DescribeImages',
        'RegionId': location,
        'ImageId': kwargs['image']
    }

    ret = {}
    items = query(params=params)
    # DescribeImages so far support input multi-image. And
    # if not found certain image, the response will include
    # blank image list other than 'not found' error message
    if 'Code' in items or len(items['Images']['Image']) == 0:
        raise SaltCloudNotFound('The specified image could not be found.')

    log.debug('Total {0} image found in Region {1}'.format(
        items['TotalCount'], location)
    )

    for image in items['Images']['Image']:
        ret[image['ImageId']] = {}
        for item in image:
            ret[image['ImageId']][item] = str(image[item])

    return ret


def destroy(name, call=None):
    '''
    Destroy a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a destroy myinstance
        salt-cloud -d myinstance
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

    instanceId = _get_node(name)['InstanceId']

    # have to stop instance before del it
    stop_params = {
        'Action': 'StopInstance',
        'InstanceId': instanceId
    }
    query(stop_params)

    params = {
        'Action': 'DeleteInstance',
        'InstanceId': instanceId
    }

    node = query(params)

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    return node
