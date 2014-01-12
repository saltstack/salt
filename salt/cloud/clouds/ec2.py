# -*- coding: utf-8 -*-
'''
The EC2 Cloud Module
====================

The EC2 cloud module is used to interact with the Amazon Elastic Cloud
Computing. This driver is highly experimental! Use at your own risk!

To use the EC2 cloud module, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/ec2.conf``:

.. code-block:: yaml

    my-ec2-config:
      # The EC2 API authentication id
      id: GKTADJGHEIQSXMKKRBJ08H
      # The EC2 API authentication key
      key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
      # The ssh keyname to use
      keyname: default
      # The amazon security group
      securitygroup: ssh_open
      # The location of the private key which corresponds to the keyname
      private_key: /root/default.pem

      # Be default, service_url is set to amazonaws.com. If you are using this
      # driver for something other than Amazon EC2, change it here:
      service_url: amazonaws.com

      # The endpoint that is ultimately used is usually formed using the region
      # and the service_url. If you would like to override that entirely, you
      # can explicitly define the endpoint:
      endpoint: myendpoint.example.com:1138/services/Cloud

      provider: ec2

'''
# pylint: disable=E0102

# Import python libs
import os
import copy
import sys
import stat
import time
import uuid
import pprint
import logging
import yaml

# Import libs for talking to the EC2 API
import hmac
import hashlib
import binascii
import datetime
import urllib
import urllib2

# Import salt libs
from salt._compat import ElementTree as ET

# Import salt.cloud libs
import salt.utils.cloud
import salt.config as config
from salt.cloud.libcloudfuncs import *   # pylint: disable=W0614,W0401
from salt.cloud.exceptions import (
    SaltCloudException,
    SaltCloudSystemExit,
    SaltCloudConfigError,
    SaltCloudExecutionTimeout,
    SaltCloudExecutionFailure
)


# Get logging started
log = logging.getLogger(__name__)

SIZE_MAP = {
    'Micro Instance': 't1.micro',
    'Small Instance': 'm1.small',
    'Medium Instance': 'm1.medium',
    'Large Instance': 'm1.large',
    'Extra Large Instance': 'm1.xlarge',
    'High-CPU Medium Instance': 'c1.medium',
    'High-CPU Extra Large Instance': 'c1.xlarge',
    'High-Memory Extra Large Instance': 'm2.xlarge',
    'High-Memory Double Extra Large Instance': 'm2.2xlarge',
    'High-Memory Quadruple Extra Large Instance': 'm2.4xlarge',
    'Cluster GPU Quadruple Extra Large Instance': 'cg1.4xlarge',
    'Cluster Compute Quadruple Extra Large Instance': 'cc1.4xlarge',
    'Cluster Compute Eight Extra Large Instance': 'cc2.8xlarge',
}


EC2_LOCATIONS = {
    'ap-northeast-1': Provider.EC2_AP_NORTHEAST,
    'ap-southeast-1': Provider.EC2_AP_SOUTHEAST,
    'eu-west-1': Provider.EC2_EU_WEST,
    'sa-east-1': Provider.EC2_SA_EAST,
    'us-east-1': Provider.EC2_US_EAST,
    'us-west-1': Provider.EC2_US_WEST,
    'us-west-2': Provider.EC2_US_WEST_OREGON
}
DEFAULT_LOCATION = 'us-east-1'

DEFAULT_EC2_API_VERSION = '2013-10-01'

if hasattr(Provider, 'EC2_AP_SOUTHEAST2'):
    EC2_LOCATIONS['ap-southeast-2'] = Provider.EC2_AP_SOUTHEAST2


# Only load in this module if the EC2 configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for EC2 configurations
    '''
    if get_configured_provider() is False:
        log.debug(
            'There is no EC2 cloud provider configuration available. Not '
            'loading module'
        )
        return False

    for provider, details in __opts__['providers'].iteritems():
        if 'provider' not in details or details['provider'] != 'ec2':
            continue

        if not os.path.exists(details['private_key']):
            raise SaltCloudException(
                'The EC2 key file {0!r} used in the {1!r} provider '
                'configuration does not exist\n'.format(
                    details['private_key'],
                    provider
                )
            )

        keymode = str(
            oct(stat.S_IMODE(os.stat(details['private_key']).st_mode))
        )
        if keymode not in ('0400', '0600'):
            raise SaltCloudException(
                'The EC2 key file {0!r} used in the {1!r} provider '
                'configuration needs to be set to mode 0400 or 0600\n'.format(
                    details['private_key'],
                    provider
                )
            )

    log.debug('Loading EC2 cloud compute module')
    return True


def get_configured_provider():
    '''
    Return the first configured instance.
    '''
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or 'ec2',
        ('id', 'key', 'keyname', 'private_key')
    )


def _xml_to_dict(xmltree):
    '''
    Convert an XML tree into a dict
    '''
    if sys.version_info < (2, 7):
        children_len = len(xmltree.getchildren())
    else:
        children_len = len(xmltree)

    if children_len < 1:
        name = xmltree.tag
        if '}' in name:
            comps = name.split('}')
            name = comps[1]
        return {name: xmltree.text}

    xmldict = {}
    for item in xmltree:
        name = item.tag
        if '}' in name:
            comps = name.split('}')
            name = comps[1]
        if not name in xmldict.keys():
            if sys.version_info < (2, 7):
                children_len = len(item.getchildren())
            else:
                children_len = len(item)

            if children_len > 0:
                xmldict[name] = _xml_to_dict(item)
            else:
                xmldict[name] = item.text
        else:
            if type(xmldict[name]) is not list:
                tempvar = xmldict[name]
                xmldict[name] = []
                xmldict[name].append(tempvar)
            xmldict[name].append(_xml_to_dict(item))
    return xmldict


def query(params=None, setname=None, requesturl=None, location=None,
          return_url=False, return_root=False):

    provider = get_configured_provider()
    service_url = provider.get('service_url', 'amazonaws.com')

    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    if not location:
        location = get_location()

    if not requesturl:
        method = 'GET'

        endpoint = provider.get(
            'endpoint',
            'ec2.{0}.{1}'.format(location, service_url)
        )

        ec2_api_version = provider.get(
            'ec2_api_version',
            DEFAULT_EC2_API_VERSION
        )

        params['AWSAccessKeyId'] = provider['id']
        params['SignatureVersion'] = '2'
        params['SignatureMethod'] = 'HmacSHA256'
        params['Timestamp'] = '{0}'.format(timestamp)
        params['Version'] = ec2_api_version
        keys = sorted(params.keys())
        values = map(params.get, keys)
        querystring = urllib.urlencode(list(zip(keys, values)))

        uri = '{0}\n{1}\n/\n{2}'.format(method.encode('utf-8'),
                                        endpoint.encode('utf-8'),
                                        querystring.encode('utf-8'))

        hashed = hmac.new(provider['key'], uri, hashlib.sha256)
        sig = binascii.b2a_base64(hashed.digest())
        params['Signature'] = sig.strip()

        querystring = urllib.urlencode(params)
        requesturl = 'https://{0}/?{1}'.format(endpoint, querystring)

    log.debug('EC2 Request: {0}'.format(requesturl))
    try:
        result = urllib2.urlopen(requesturl)
        log.debug(
            'EC2 Response Status Code: {0}'.format(
                result.getcode()
            )
        )
    except urllib2.URLError as exc:
        root = ET.fromstring(exc.read())
        data = _xml_to_dict(root)
        log.error(
            'EC2 Response Status Code and Error: [{0} {1}] {2}'.format(
                exc.code, exc.msg, data
            )
        )
        if return_url is True:
            return {'error': data}, requesturl
        return {'error': data}

    response = result.read()
    result.close()

    root = ET.fromstring(response)
    items = root[1]
    if return_root is True:
        items = root

    if setname:
        if sys.version_info < (2, 7):
            children_len = len(root.getchildren())
        else:
            children_len = len(root)

        for item in range(0, children_len):
            comps = root[item].tag.split('}')
            if comps[1] == setname:
                items = root[item]

    ret = []
    for item in items:
        ret.append(_xml_to_dict(item))

    if return_url is True:
        return ret, requesturl

    return ret


def _wait_for_spot_instance(update_callback,
                            update_args=None,
                            update_kwargs=None,
                            timeout=10 * 60,
                            interval=30,
                            interval_multiplier=1,
                            max_failures=10):
    '''
    Helper function that waits for a spot instance request to become active
    for a specific maximum amount of time.

    :param update_callback: callback function which queries the cloud provider
                            for spot instance request. It must return None if the
                            required data, running instance included, is not
                            available yet.
    :param update_args: Arguments to pass to update_callback
    :param update_kwargs: Keyword arguments to pass to update_callback
    :param timeout: The maximum amount of time(in seconds) to wait for the IP
                    address.
    :param interval: The looping interval, ie, the amount of time to sleep
                     before the next iteration.
    :param interval_multiplier: Increase the interval by this multiplier after
                                each request; helps with throttling
    :param max_failures: If update_callback returns ``False`` it's considered
                         query failure. This value is the amount of failures
                         accepted before giving up.
    :returns: The update_callback returned data
    :raises: SaltCloudExecutionTimeout

    '''
    if update_args is None:
        update_args = ()
    if update_kwargs is None:
        update_kwargs = {}

    duration = timeout
    while True:
        log.debug(
            'Waiting for spot instance reservation. Giving up in '
            '00:{0:02d}:{1:02d}'.format(
                int(timeout // 60),
                int(timeout % 60)
            )
        )
        data = update_callback(*update_args, **update_kwargs)
        if data is False:
            log.debug(
                'update_callback has returned False which is considered a '
                'failure. Remaining Failures: {0}'.format(max_failures)
            )
            max_failures -= 1
            if max_failures <= 0:
                raise SaltCloudExecutionFailure(
                    'Too many failures occurred while waiting for '
                    'the spot instance reservation to become active.'
                )
        elif data is not None:
            return data

        if timeout < 0:
            raise SaltCloudExecutionTimeout(
                'Unable to get an active spot instance request for '
                '00:{0:02d}:{1:02d}'.format(
                    int(duration // 60),
                    int(duration % 60)
                )
            )
        time.sleep(interval)
        timeout -= interval

        if interval_multiplier > 1:
            interval *= interval_multiplier
            if interval > timeout:
                interval = timeout + 1
            log.info('Interval multiplier in effect; interval is '
                     'now {0}s'.format(interval))


def avail_sizes(call=None):
    '''
    Return a dict of all available VM sizes on the cloud provider with
    relevant data. Latest version can be found at:

    http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_sizes function must be called with '
            '-f or --function, or with the --list-sizes option'
        )

    sizes = {
        'Cluster Compute': {
            'cc2.8xlarge': {
                'id': 'cc2.8xlarge',
                'cores': '16 (2 x Intel Xeon E5-2670, eight-core with '
                         'hyperthread)',
                'disk': '3360 GiB (4 x 840 GiB)',
                'ram': '60.5 GiB'
            },
            'cc1.4xlarge': {
                'id': 'cc1.4xlarge',
                'cores': '8 (2 x Intel Xeon X5570, quad-core with '
                         'hyperthread)',
                'disk': '1690 GiB (2 x 840 GiB)',
                'ram': '22.5 GiB'
            },
        },
        'Cluster CPU': {
            'cg1.4xlarge': {
                'id': 'cg1.4xlarge',
                'cores': '8 (2 x Intel Xeon X5570, quad-core with '
                         'hyperthread), plus 2 NVIDIA Tesla M2050 GPUs',
                'disk': '1680 GiB (2 x 840 GiB)',
                'ram': '22.5 GiB'
            },
        },
        'High CPU': {
            'c1.xlarge': {
                'id': 'c1.xlarge',
                'cores': '8 (with 2.5 ECUs each)',
                'disk': '1680 GiB (4 x 420 GiB)',
                'ram': '8 GiB'
            },
            'c1.medium': {
                'id': 'c1.medium',
                'cores': '2 (with 2.5 ECUs each)',
                'disk': '340 GiB (1 x 340 GiB)',
                'ram': '1.7 GiB'
            },
        },
        'High I/O': {
            'hi1.4xlarge': {
                'id': 'hi1.4xlarge',
                'cores': '8 (with 4.37 ECUs each)',
                'disk': '2 TiB',
                'ram': '60.5 GiB'
            },
        },
        'High Memory': {
            'm2.2xlarge': {
                'id': 'm2.2xlarge',
                'cores': '4 (with 3.25 ECUs each)',
                'disk': '840 GiB (1 x 840 GiB)',
                'ram': '34.2 GiB'
            },
            'm2.xlarge': {
                'id': 'm2.xlarge',
                'cores': '2 (with 3.25 ECUs each)',
                'disk': '410 GiB (1 x 410 GiB)',
                'ram': '17.1 GiB'
            },
            'm2.4xlarge': {
                'id': 'm2.4xlarge',
                'cores': '8 (with 3.25 ECUs each)',
                'disk': '1680 GiB (2 x 840 GiB)',
                'ram': '68.4 GiB'
            },
        },
        'High-Memory Cluster': {
            'cr1.8xlarge': {
                'id': 'cr1.8xlarge',
                'cores': '16 (2 x Intel Xeon E5-2670, eight-core)',
                'disk': '240 GiB (2 x 120 GiB SSD)',
                'ram': '244 GiB'
            },
        },
        'High Storage': {
            'hs1.8xlarge': {
                'id': 'hs1.8xlarge',
                'cores': '16 (8 cores + 8 hyperthreads)',
                'disk': '48 TiB (24 x 2 TiB hard disk drives)',
                'ram': '117 GiB'
            },
        },
        'Micro': {
            't1.micro': {
                'id': 't1.micro',
                'cores': '1',
                'disk': 'EBS',
                'ram': '615 MiB'
            },
        },
        'Standard': {
            'm1.xlarge': {
                'id': 'm1.xlarge',
                'cores': '4 (with 2 ECUs each)',
                'disk': '1680 GB (4 x 420 GiB)',
                'ram': '15 GiB'
            },
            'm1.large': {
                'id': 'm1.large',
                'cores': '2 (with 2 ECUs each)',
                'disk': '840 GiB (2 x 420 GiB)',
                'ram': '7.5 GiB'
            },
            'm1.medium': {
                'id': 'm1.medium',
                'cores': '1',
                'disk': '400 GiB',
                'ram': '3.75 GiB'
            },
            'm1.small': {
                'id': 'm1.small',
                'cores': '1',
                'disk': '150 GiB',
                'ram': '1.7 GiB'
            },
            'm3.2xlarge': {
                'id': 'm3.2xlarge',
                'cores': '8 (with 3.25 ECUs each)',
                'disk': 'EBS',
                'ram': '30 GiB'
            },
            'm3.xlarge': {
                'id': 'm3.xlarge',
                'cores': '4 (with 3.25 ECUs each)',
                'disk': 'EBS',
                'ram': '15 GiB'
            },
        }
    }
    return sizes


def avail_images(kwargs=None, call=None):
    '''
    Return a dict of all available VM images on the cloud provider.
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The avail_images function must be called with '
            '-f or --function, or with the --list-images option'
        )

    if type(kwargs) is not dict:
        kwargs = {}

    if 'owner' in kwargs:
        owner = kwargs['owner']
    else:
        provider = get_configured_provider()

        owner = config.get_cloud_config_value(
            'owner', provider, __opts__, default='amazon'
        )

    ret = {}
    params = {'Action': 'DescribeImages',
              'Owner': owner}
    images = query(params)
    for image in images:
        ret[image['imageId']] = image
    return ret


def script(vm_):
    '''
    Return the script deployment object
    '''
    return salt.utils.cloud.os_script(
        config.get_cloud_config_value('script', vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        )
    )


def keyname(vm_):
    '''
    Return the keyname
    '''
    return config.get_cloud_config_value(
        'keyname', vm_, __opts__, search_global=False
    )


def securitygroup(vm_):
    '''
    Return the security group
    '''
    return config.get_cloud_config_value(
        'securitygroup', vm_, __opts__, search_global=False
    )


def iam_profile(vm_):
    '''
    Return the IAM profile.

    The IAM instance profile to associate with the instances.
    This is either the Amazon Resource Name (ARN) of the instance profile
    or the name of the role.

    Type: String

    Default: None

    Required: No

    Example: arn:aws:iam::111111111111:instance-profile/s3access

    Example: s3access

    '''
    return config.get_cloud_config_value(
        'iam_profile', vm_, __opts__, search_global=False
    )


def ssh_username(vm_):
    '''
    Return the ssh_username. Defaults to a built-in list of users for trying.
    '''
    usernames = config.get_cloud_config_value(
        'ssh_username', vm_, __opts__
    )

    if not isinstance(usernames, list):
        usernames = [usernames]

    # get rid of None's or empty names
    usernames = filter(lambda x: x, usernames)
    # Keep a copy of the usernames the user might have provided
    initial = usernames[:]

    # Add common usernames to the list to be tested
    for name in ('ec2-user', 'ubuntu', 'admin', 'bitnami', 'root'):
        if name not in usernames:
            usernames.append(name)
    # Add the user provided usernames to the end of the list since enough time
    # might need to pass before the remote service is available for logins and
    # the proper username might have passed it's iteration.
    # This has detected in a CentOS 5.7 EC2 image
    usernames.extend(initial)
    return usernames


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
    Return the EC2 region to use, in this order:
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

    params = {'Action': 'DescribeRegions'}
    result = query(params)

    for region in result:
        ret[region['regionName']] = {
            'name': region['regionName'],
            'endpoint': region['regionEndpoint'],
        }

    return ret


def get_availability_zone(vm_):
    '''
    Return the availability zone to use
    '''
    avz = config.get_cloud_config_value(
        'availability_zone', vm_, __opts__, search_global=False
    )

    if avz is None:
        return None

    zones = list_availability_zones()

    # Validate user-specified AZ
    if avz not in zones.keys():
        raise SaltCloudException(
            'The specified availability zone isn\'t valid in this region: '
            '{0}\n'.format(
                avz
            )
        )

    # check specified AZ is available
    elif zones[avz] != 'available':
        raise SaltCloudException(
            'The specified availability zone isn\'t currently available: '
            '{0}\n'.format(
                avz
            )
        )

    return avz


def get_tenancy(vm_):
    '''
    Returns the Tenancy to use.

    Can be "dedicated" or "default". Cannot be present for spot instances.
    '''
    return config.get_cloud_config_value(
        'tenancy', vm_, __opts__, search_global=False
    )


def get_subnetid(vm_):
    '''
    Returns the SubnetId to use
    '''
    return config.get_cloud_config_value(
        'subnetid', vm_, __opts__, search_global=False
    )


def securitygroupid(vm_):
    '''
    Returns the SecurityGroupId
    '''
    return config.get_cloud_config_value(
        'securitygroupid', vm_, __opts__, search_global=False
    )


def get_spot_config(vm_):
    '''
    Returns the spot instance configuration for the provided vm
    '''
    return config.get_cloud_config_value(
        'spot_config', vm_, __opts__, search_global=False
    )


def list_availability_zones():
    '''
    List all availability zones in the current region
    '''
    ret = {}

    params = {'Action': 'DescribeAvailabilityZones',
              'Filter.0.Name': 'region-name',
              'Filter.0.Value.0': get_location()}
    result = query(params)

    for zone in result:
        ret[zone['zoneName']] = zone['zoneState']

    return ret


def block_device_mappings(vm_):
    '''
    Return the block device mapping:

    ::

        [{'DeviceName': '/dev/sdb', 'VirtualName': 'ephemeral0'},
          {'DeviceName': '/dev/sdc', 'VirtualName': 'ephemeral1'}]
    '''
    return config.get_cloud_config_value(
        'block_device_mappings', vm_, __opts__, search_global=True
    )


def _param_from_config(key, data):
    '''
    Return EC2 API parameters based on the given config data.

    Examples:
    1. List of dictionaries
    >>> data = [
    ...     {'DeviceIndex': 0, 'SubnetId': 'subid0', 'AssociatePublicIpAddress': True},
    ...     {'DeviceIndex': 1, 'SubnetId': 'subid1', 'PrivateIpAddress': '192.168.1.128'}
    ... ]
    >>> _param_from_config('NetworkInterface', data)
    {'NetworkInterface.0.SubnetId': 'subid0', 'NetworkInterface.0.DeviceIndex': 0, 'NetworkInterface.1.SubnetId': 'subid1', 'NetworkInterface.1.PrivateIpAddress': '192.168.1.128', 'NetworkInterface.0.AssociatePublicIpAddress': 'true', 'NetworkInterface.1.DeviceIndex': 1}

    2. List of nested dictionaries
    >>> data = [
    ...     {'DeviceName': '/dev/sdf', 'Ebs': {'SnapshotId': 'dummy0', 'VolumeSize': 200, 'VolumeType': 'standard'}},
    ...     {'DeviceName': '/dev/sdg', 'Ebs': {'SnapshotId': 'dummy1', 'VolumeSize': 100, 'VolumeType': 'standard'}}
    ... ]
    >>> _param_from_config('BlockDeviceMapping', data)
    {'BlockDeviceMapping.0.Ebs.VolumeType': 'standard', 'BlockDeviceMapping.1.Ebs.SnapshotId': 'dummy1', 'BlockDeviceMapping.0.Ebs.VolumeSize': 200, 'BlockDeviceMapping.0.Ebs.SnapshotId': 'dummy0', 'BlockDeviceMapping.1.Ebs.VolumeType': 'standard', 'BlockDeviceMapping.1.DeviceName': '/dev/sdg', 'BlockDeviceMapping.1.Ebs.VolumeSize': 100, 'BlockDeviceMapping.0.DeviceName': '/dev/sdf'}

    3. Dictionary of dictionaries
    >>> data = { 'Arn': 'dummyarn', 'Name': 'Tester' }
    >>> _param_from_config('IamInstanceProfile', data)
    {'IamInstanceProfile.Arn': 'dummyarn', 'IamInstanceProfile.Name': 'Tester'}

    '''

    param = {}

    if isinstance(data, dict):
        for k, v in data.items():
            param.update(_param_from_config('{0}.{1}'.format(key, k), v))

    elif isinstance(data, list) or isinstance(data, tuple):
        for idx, conf_item in enumerate(data):
            prefix = '{0}.{1}'.format(key, idx)
            param.update(_param_from_config(prefix, conf_item))

    else:
        if isinstance(data, bool):
            # convert boolean Trur/False to 'true'/'false'
            param.update({key: str(data).lower()})
        else:
            param.update({key: data})

    return param


def create(vm_=None, call=None):
    '''
    Create a single VM from a data dict
    '''
    if call:
        raise SaltCloudSystemExit(
            'You cannot create an instance with -a or -f.'
        )

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
    )

    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined key_filename {0!r} does not exist'.format(
                key_filename
            )
        )

    location = get_location(vm_)
    log.info('Creating Cloud VM {0} in {1}'.format(vm_['name'], location))
    usernames = ssh_username(vm_)

    # do we launch a regular vm or a spot instance?
    # see http://goo.gl/hYZ13f for more information on EC2 API
    spot_config = get_spot_config(vm_)
    if spot_config is not None:
        if 'spot_price' not in spot_config:
            raise SaltCloudSystemExit(
                'Spot instance config for {0} requires a spot_price '
                'attribute.'.format(vm_['name'])
            )

        params = {'Action': 'RequestSpotInstances',
                  'InstanceCount': '1',
                  'Type': spot_config['type'] if 'type' in spot_config else 'one-time',
                  'SpotPrice': spot_config['spot_price']}

        # All of the necessary launch parameters for a VM when using
        # spot instances are the same except for the prefix below
        # being tacked on.
        spot_prefix = 'LaunchSpecification.'

    # regular EC2 instance
    else:
        params = {'Action': 'RunInstances',
                  'MinCount': '1',
                  'MaxCount': '1'}

        # Normal instances should have no prefix.
        spot_prefix = ''

    image_id = vm_['image']
    params[spot_prefix + 'ImageId'] = image_id

    vm_size = config.get_cloud_config_value(
        'size', vm_, __opts__, search_global=False
    )
    if vm_size in SIZE_MAP:
        vm_size = SIZE_MAP[vm_size]
    params[spot_prefix + 'InstanceType'] = vm_size

    ex_keyname = keyname(vm_)
    if ex_keyname:
        params[spot_prefix + 'KeyName'] = ex_keyname

    ex_securitygroup = securitygroup(vm_)
    if ex_securitygroup:
        if not isinstance(ex_securitygroup, list):
            params[spot_prefix + 'SecurityGroup.1'] = ex_securitygroup
        else:
            for counter, sg_ in enumerate(ex_securitygroup):
                params[spot_prefix + 'SecurityGroup.{0}'.format(counter)] = sg_

    ex_iam_profile = iam_profile(vm_)
    if ex_iam_profile:
        try:
            if ex_iam_profile.startswith('arn:aws:iam:'):
                params[spot_prefix + 'IamInstanceProfile.Arn'] = ex_iam_profile
            else:
                params[spot_prefix + 'IamInstanceProfile.Name'] = ex_iam_profile
        except AttributeError:
            raise SaltCloudConfigError(
                '\'iam_profile\' should be a string value.'
            )

    az_ = get_availability_zone(vm_)
    if az_ is not None:
        params[spot_prefix + 'Placement.AvailabilityZone'] = az_

    tenancy_ = get_tenancy(vm_)
    if tenancy_ is not None:
        if spot_config is not None:
            raise SaltCloudConfigError(
                'Spot instance config for {0} does not support '
                'specifying tenancy.'.format(vm_['name'])
            )
        params['Placement.Tenancy'] = tenancy_

    subnetid_ = get_subnetid(vm_)
    if subnetid_ is not None:
        params[spot_prefix + 'SubnetId'] = subnetid_

    ex_securitygroupid = securitygroupid(vm_)
    if ex_securitygroupid:
        if not isinstance(ex_securitygroupid, list):
            params[spot_prefix + 'SecurityGroupId.1'] = ex_securitygroupid
        else:
            for (counter, sg_) in enumerate(ex_securitygroupid):
                params[spot_prefix + 'SecurityGroupId.{0}'.format(counter)] = sg_

    ex_blockdevicemappings = block_device_mappings(vm_)
    if ex_blockdevicemappings:
        params.update(_param_from_config(spot_prefix + 'BlockDeviceMapping', ex_blockdevicemappings))

    network_interfaces = config.get_cloud_config_value(
        'network_interfaces', vm_, __opts__, search_global=False
    )

    if network_interfaces:
        params.update(_param_from_config(spot_prefix + 'NetworkInterface', network_interfaces))

    set_ebs_optimized = config.get_cloud_config_value(
        'ebs_optimized', vm_, __opts__, search_global=False
    )

    if set_ebs_optimized is not None:
        if not isinstance(set_ebs_optimized, bool):
            raise SaltCloudConfigError(
                '\'ebs_optimized\' should be a boolean value.'
            )
        params[spot_prefix + 'EbsOptimized'] = set_ebs_optimized

    set_del_root_vol_on_destroy = config.get_cloud_config_value(
        'del_root_vol_on_destroy', vm_, __opts__, search_global=False
    )

    if set_del_root_vol_on_destroy is not None:
        if not isinstance(set_del_root_vol_on_destroy, bool):
            raise SaltCloudConfigError(
                '\'del_root_vol_on_destroy\' should be a boolean value.'
            )

    if set_del_root_vol_on_destroy:
        # first make sure to look up the root device name
        # as Ubuntu and CentOS (and most likely other OSs)
        # use different device identifiers

        log.info('Attempting to look up root device name for image id {0} on '
                 'VM {1}'.format(image_id, vm_['name']))

        rd_params = {
            'Action': 'DescribeImages',
            'ImageId.1': image_id
        }
        try:
            rd_data = query(rd_params, location=location)
            if 'error' in rd_data:
                return rd_data['error']
            log.debug('EC2 Response: {0!r}'.format(rd_data))
        except Exception as exc:
            log.error(
                'Error getting root device name for image id {0} for '
                'VM {1}: \n{2}'.format(image_id, vm_['name'], exc),
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            raise

        # make sure we have a response
        if not rd_data:
            err_msg = 'There was an error querying EC2 for the root device ' \
                      'of image id {0}. Empty response.'.format(image_id)
            raise SaltCloudSystemExit(err_msg)

        # pull the root device name from the result and use it when
        # launching the new VM
        if rd_data[0]['blockDeviceMapping'] is None:
            # Some ami instances do not have a root volume. Ignore such cases
            rd_name = None
        elif type(rd_data[0]['blockDeviceMapping']['item']) is list:
            rd_name = rd_data[0]['blockDeviceMapping']['item'][0]['deviceName']
        else:
            rd_name = rd_data[0]['blockDeviceMapping']['item']['deviceName']
        log.info('Found root device name: {0}'.format(rd_name))

        if rd_name is not None:
            if ex_blockdevicemappings:
                dev_list = [dev['DeviceName'] for dev in ex_blockdevicemappings]
            else:
                dev_list = []

            if rd_name in dev_list:
                dev_index = dev_list.index(rd_name)
                termination_key = spot_prefix + 'BlockDeviceMapping.%d.Ebs.DeleteOnTermination' % dev_index
                params[termination_key] = str(set_del_root_vol_on_destroy).lower()
            else:
                dev_index = len(dev_list)
                params[spot_prefix + 'BlockDeviceMapping.%d.DeviceName' % dev_index] = rd_name
                params[spot_prefix + 'BlockDeviceMapping.%d.Ebs.DeleteOnTermination' % dev_index] = str(
                    set_del_root_vol_on_destroy
                ).lower()

    set_del_all_vols_on_destroy = config.get_cloud_config_value(
        'del_all_vols_on_destroy', vm_, __opts__, search_global=False
    )

    if set_del_all_vols_on_destroy is not None:
        if not isinstance(set_del_all_vols_on_destroy, bool):
            raise SaltCloudConfigError(
                '\'del_all_vols_on_destroy\' should be a boolean value.'
            )

    tags = config.get_cloud_config_value('tag', vm_, __opts__, {}, search_global=False)
    if not isinstance(tags, dict):
        raise SaltCloudConfigError(
                '\'tag\' should be a dict.'
        )

    for value in tags.values():
        if not isinstance(value, str):
            raise SaltCloudConfigError(
                '\'tag\' values must be strings. Try quoting the values. e.g. "2013-09-19T20:09:46Z".'
            )

    tags['Name'] = vm_['name']

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': params, 'location': location},
    )

    try:
        data = query(params, 'instancesSet', location=location)
        if 'error' in data:
            return data['error']
    except Exception as exc:
        log.error(
            'Error creating {0} on EC2 when trying to run the initial '
            'deployment: \n{1}'.format(
                vm_['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        raise

    # if we're using spot instances, we need to wait for the spot request
    # to become active before we continue
    if spot_config:
        sir_id = data[0]['spotInstanceRequestId']

        def __query_spot_instance_request(sir_id, location):
            params = {'Action': 'DescribeSpotInstanceRequests',
                      'SpotInstanceRequestId.1': sir_id}
            data = query(params, location=location)
            if not data:
                log.error(
                    'There was an error while querying EC2. Empty response'
                )
                # Trigger a failure in the wait for spot instance method
                return False

            if isinstance(data, dict) and 'error' in data:
                log.warn(
                    'There was an error in the query. {0}'.format(data['error'])
                )
                # Trigger a failure in the wait for spot instance method
                return False

            log.debug('Returned query data: {0}'.format(data))

            if 'state' in data[0]:
                state = data[0]['state']

            if state == 'active':
                return data

            if state == 'open':
                # Still waiting for an active state
                log.info('Spot instance status: {0}'.format(
                    data[0]['status']['message']
                ))
                return None

            if state in ['cancelled', 'failed', 'closed']:
                # Request will never be active, fail
                log.error('Spot instance request resulted in state \'{0}\'. '
                          'Nothing else we can do here.')
                return False

        salt.utils.cloud.fire_event(
            'event',
            'waiting for spot instance',
            'salt/cloud/{0}/waiting_for_spot'.format(vm_['name']),
        )

        try:
            data = _wait_for_spot_instance(
                __query_spot_instance_request,
                update_args=(sir_id, location),
                timeout=config.get_cloud_config_value(
                    'wait_for_spot_timeout', vm_, __opts__, default=10 * 60),
                interval=config.get_cloud_config_value(
                    'wait_for_spot_interval', vm_, __opts__, default=30),
                interval_multiplier=config.get_cloud_config_value(
                    'wait_for_spot_interval_multiplier', vm_, __opts__, default=1),
                max_failures=config.get_cloud_config_value(
                    'wait_for_spot_max_failures', vm_, __opts__, default=10),
            )
            log.debug('wait_for_spot_instance data {0}'.format(data))

        except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
            try:
                # Cancel the existing spot instance request
                params = {'Action': 'CancelSpotInstanceRequests',
                          'SpotInstanceRequestId.1': sir_id}
                data = query(params, location=location)

                log.debug('Canceled spot instance request {0}. Data '
                          'returned: {1}'.format(sir_id, data))

            except SaltCloudSystemExit:
                pass
            finally:
                raise SaltCloudSystemExit(exc.message)

    # Pull the instance ID, valid for both spot and normal instances
    instance_id = data[0]['instanceId']

    salt.utils.cloud.fire_event(
        'event',
        'querying instance',
        'salt/cloud/{0}/querying'.format(vm_['name']),
        {'instance_id': instance_id},
    )

    log.debug('The new VM instance_id is {0}'.format(instance_id))

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}

    attempts = 5
    while attempts > 0:
        data, requesturl = query(params, location=location, return_url=True)
        log.debug('The query returned: {0}'.format(data))

        if isinstance(data, dict) and 'error' in data:
            log.warn(
                'There was an error in the query. {0} attempts '
                'remaining: {1}'.format(
                    attempts, data['error']
                )
            )
            attempts -= 1
            continue

        if isinstance(data, list) and not data:
            log.warn(
                'Query returned an empty list. {0} attempts '
                'remaining.'.format(attempts)
            )
            attempts -= 1
            continue

        break
    else:
        raise SaltCloudSystemExit(
            'An error occurred while creating VM: {0}'.format(data['error'])
        )

    def __query_ip_address(params, url):
        data = query(params, requesturl=url)
        if not data:
            log.error(
                'There was an error while querying EC2. Empty response'
            )
            # Trigger a failure in the wait for IP function
            return False

        if isinstance(data, dict) and 'error' in data:
            log.warn(
                'There was an error in the query. {0}'.format(data['error'])
            )
            # Trigger a failure in the wait for IP function
            return False

        log.debug('Returned query data: {0}'.format(data))

        if 'ipAddress' in data[0]['instancesSet']['item']:
            return data
        if ssh_interface(vm_) == 'private_ips' and \
           'privateIpAddress' in data[0]['instancesSet']['item']:
            return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_ip_address,
            update_args=(params, requesturl),
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
            destroy(vm_['name'])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(exc.message)

    salt.utils.cloud.fire_event(
        'event',
        'setting tags',
        'salt/cloud/{0}/tagging'.format(vm_['name']),
        {'tags': tags},
    )

    set_tags(
        vm_['name'], tags,
        instance_id=instance_id, call='action', location=location
    )
    log.info('Created node {0}'.format(vm_['name']))

    if ssh_interface(vm_) == 'private_ips':
        ip_address = data[0]['instancesSet']['item']['privateIpAddress']
        log.info('Salt node data. Private_ip: {0}'.format(ip_address))
    else:
        ip_address = data[0]['instancesSet']['item']['ipAddress']
        log.info('Salt node data. Public_ip: {0}'.format(ip_address))

    display_ssh_output = config.get_cloud_config_value(
        'display_ssh_output', vm_, __opts__, default=True
    )

    salt.utils.cloud.fire_event(
        'event',
        'waiting for ssh',
        'salt/cloud/{0}/waiting_for_ssh'.format(vm_['name']),
        {'ip_address': ip_address},
    )

    ssh_connect_timeout = config.get_cloud_config_value(
        'ssh_connect_timeout', vm_, __opts__, 900   # 15 minutes
    )

    if config.get_cloud_config_value('win_installer', vm_, __opts__):
        username = config.get_cloud_config_value(
                'win_username', vm_, __opts__, default='Administrator'
            )
        win_passwd = config.get_cloud_config_value(
                'win_password', vm_, __opts__, default=''
            )
        if not salt.utils.cloud.wait_for_port(ip_address,
                                              port=445,
                                              timeout=ssh_connect_timeout):
            raise SaltCloudSystemExit(
                'Failed to connect to remote windows host'
            )
        if not salt.utils.cloud.validate_windows_cred(ip_address,
                                                      username,
                                                      win_passwd):
            raise SaltCloudSystemExit(
                'Failed to authenticate against remote windows host'
            )
    elif salt.utils.cloud.wait_for_port(ip_address,
                                        timeout=ssh_connect_timeout):
        for user in usernames:
            if salt.utils.cloud.wait_for_passwd(
                host=ip_address,
                username=user,
                ssh_timeout=config.get_cloud_config_value(
                    'wait_for_passwd_timeout', vm_, __opts__, default=1 * 60),
                key_filename=key_filename,
                display_ssh_output=display_ssh_output
            ):
                username = user
                break
        else:
            raise SaltCloudSystemExit(
                'Failed to authenticate against remote ssh'
            )
    else:
        raise SaltCloudSystemExit(
            'Failed to connect to remote ssh'
        )

    ret = {}
    if config.get_cloud_config_value('deploy', vm_, __opts__) is True:
        deploy_script = script(vm_)
        deploy_kwargs = {
            'host': ip_address,
            'username': username,
            'key_filename': key_filename,
            'tmp_dir': config.get_cloud_config_value(
                'tmp_dir', vm_, __opts__, default='/tmp/.saltcloud'
            ),
            'deploy_command': config.get_cloud_config_value(
                'deploy_command', vm_, __opts__,
                default='/tmp/.saltcloud/deploy.sh',
            ),
            'tty': config.get_cloud_config_value(
                'tty', vm_, __opts__, default=True
            ),
            'script': deploy_script,
            'name': vm_['name'],
            'sudo': config.get_cloud_config_value(
                'sudo', vm_, __opts__, default=(username != 'root')
            ),
            'sudo_password': config.get_cloud_config_value(
                'sudo_password', vm_, __opts__, default=None
            ),
            'start_action': __opts__['start_action'],
            'parallel': __opts__['parallel'],
            'conf_file': __opts__['conf_file'],
            'sock_dir': __opts__['sock_dir'],
            'minion_pem': vm_['priv_key'],
            'minion_pub': vm_['pub_key'],
            'keep_tmp': __opts__['keep_tmp'],
            'preseed_minion_keys': vm_.get('preseed_minion_keys', None),
            'display_ssh_output': display_ssh_output,
            'minion_conf': salt.utils.cloud.minion_config(__opts__, vm_),
            'script_args': config.get_cloud_config_value(
                'script_args', vm_, __opts__
            ),
            'script_env': config.get_cloud_config_value(
                'script_env', vm_, __opts__
            )
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
        win_installer = config.get_cloud_config_value('win_installer',
                                                      vm_,
                                                      __opts__)
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
        )

        deployed = False
        if win_installer:
            deployed = salt.utils.cloud.deploy_windows(**deploy_kwargs)
        else:
            deployed = salt.utils.cloud.deploy_script(**deploy_kwargs)

        if deployed:
            log.info('Salt installed on {name}'.format(**vm_))
        else:
            log.error('Failed to start Salt on Cloud VM {name}'.format(**vm_))

    log.info('Created Cloud VM {0[name]!r}'.format(vm_))
    log.debug(
        '{0[name]!r} VM creation details:\n{1}'.format(
            vm_, pprint.pformat(data[0]['instancesSet']['item'])
        )
    )

    ret.update(data[0]['instancesSet']['item'])

    # Get ANY defined volumes settings, merging data, in the following order
    # 1. VM config
    # 2. Profile config
    # 3. Global configuration
    volumes = config.get_cloud_config_value(
        'volumes', vm_, __opts__, search_global=True
    )
    if volumes:
        salt.utils.cloud.fire_event(
            'event',
            'attaching volumes',
            'salt/cloud/{0}/attaching_volumes'.format(vm_['name']),
            {'volumes': volumes},
        )

        log.info('Create and attach volumes to node {0}'.format(vm_['name']))
        created = create_attach_volumes(
            vm_['name'],
            {
                'volumes': volumes,
                'zone': ret['placement']['availabilityZone'],
                'instance_id': ret['instanceId'],
                'del_all_vols_on_destroy': set_del_all_vols_on_destroy
            },
            call='action'
        )
        ret['Attached Volumes'] = created

    salt.utils.cloud.fire_event(
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
            'instance_id': instance_id,
        },
    )

    return ret


def create_attach_volumes(name, kwargs, call=None):
    '''
    Create and attach volumes to created node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The create_attach_volumes action must be called with '
            '-a or --action.'
        )

    if not 'instance_id' in kwargs:
        kwargs['instance_id'] = _get_node(name)['instanceId']

    if type(kwargs['volumes']) is str:
        volumes = yaml.safe_load(kwargs['volumes'])
    else:
        volumes = kwargs['volumes']

    ret = []
    for volume in volumes:
        created = False
        volume_name = '{0} on {1}'.format(volume['device'], name)

        volume_dict = {
            'volume_name': volume_name,
            'zone': kwargs['zone']
        }
        if 'volume_id' in volume:
            volume_dict['volume_id'] = volume['volume_id']
        elif 'snapshot' in volume:
            volume_dict['snapshot'] = volume['snapshot']
        else:
            volume_dict['size'] = volume['size']

            if 'type' in volume:
                volume_dict['type'] = volume['type']
            if 'iops' in volume:
                volume_dict['iops'] = volume['iops']

        if 'volume_id' not in volume_dict:
            created_volume = create_volume(volume_dict, call='function')
            created = True
            for item in created_volume:
                if 'volumeId' in item:
                    volume_dict['volume_id'] = item['volumeId']

        attach = attach_volume(
            name,
            {'volume_id': volume_dict['volume_id'], 'device': volume['device']},
            instance_id=kwargs['instance_id'],
            call='action'
        )

        # Update the delvol parameter for this volume
        delvols_on_destroy = kwargs.get('del_all_vols_on_destroy', None)

        if attach and created and delvols_on_destroy is not None:
            _toggle_delvol(instance_id=kwargs['instance_id'],
                           device=volume['device'],
                           value=delvols_on_destroy)

        if attach:
            msg = (
                '{0} attached to {1} (aka {2}) as device {3}'.format(
                    volume_dict['volume_id'],
                    kwargs['instance_id'],
                    name,
                    volume['device']
                )
            )
            log.info(msg)
            ret.append(msg)
    return ret


def stop(name, call=None):
    '''
    Stop a node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The stop action must be called with -a or --action.'
        )

    log.info('Stopping node {0}'.format(name))

    instance_id = _get_node(name)['instanceId']

    params = {'Action': 'StopInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    return result


def start(name, call=None):
    '''
    Start a node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The start action must be called with -a or --action.'
        )

    log.info('Starting node {0}'.format(name))

    instance_id = _get_node(name)['instanceId']

    params = {'Action': 'StartInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    return result


def set_tags(name, tags, call=None, location=None, instance_id=None):
    '''
    Set tags for a node

    CLI Example::

        salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The set_tags action must be called with -a or --action.'
        )

    if instance_id is None:
        instance_id = _get_node(name, location)['instanceId']

    params = {'Action': 'CreateTags',
              'ResourceId.1': instance_id}

    log.debug('Tags to set for {0}: {1}'.format(name, tags))

    for idx, (tag_k, tag_v) in enumerate(tags.iteritems()):
        params['Tag.{0}.Key'.format(idx)] = tag_k
        params['Tag.{0}.Value'.format(idx)] = tag_v

    attempts = 5
    while attempts >= 0:
        query(params, setname='tagSet', location=location)

        settags = get_tags(
            instance_id=instance_id, call='action', location=location
        )

        log.debug('Setting the tags returned: {0}'.format(settags))

        failed_to_set_tags = False
        for tag in settags:
            if tag['key'] not in tags:
                # We were not setting this tag
                continue

            if str(tags.get(tag['key'])) != str(tag['value']):
                # Not set to the proper value!?
                failed_to_set_tags = True
                break

        if failed_to_set_tags:
            log.warn(
                'Failed to set tags. Remaining attempts {0}'.format(
                    attempts
                )
            )
            attempts -= 1
            continue

        return settags

    raise SaltCloudSystemExit(
        'Failed to set tags on {0}!'.format(name)
    )


def get_tags(name=None, instance_id=None, call=None, location=None):
    '''
    Retrieve tags for a node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The get_tags action must be called with -a or --action.'
        )

    if instance_id is None:
        if location is None:
            location = get_location()

        instances = list_nodes_full(location)
        if name in instances:
            instance_id = instances[name]['instanceId']

    params = {'Action': 'DescribeTags',
              'Filter.1.Name': 'resource-id',
              'Filter.1.Value': instance_id}
    return query(params, setname='tagSet', location=location)


def del_tags(name, kwargs, call=None):
    '''
    Delete tags for a node

    CLI Example::

        salt-cloud -a del_tags mymachine tag1,tag2,tag3
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The del_tags action must be called with -a or --action.'
        )

    if not 'tags' in kwargs:
        raise SaltCloudSystemExit(
            'A tag or tags must be specified using tags=list,of,tags'
        )

    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'DeleteTags',
              'ResourceId.1': instance_id}

    for idx, tag in enumerate(kwargs['tags'].split(',')):
        params['Tag.{0}.Key'.format(idx)] = tag

    query(params, setname='tagSet')

    return get_tags(name, call='action')


def rename(name, kwargs, call=None):
    '''
    Properly rename a node. Pass in the new name as "new name".

    CLI Example::

        salt-cloud -a rename mymachine newname=yourmachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The rename action must be called with -a or --action.'
        )

    log.info('Renaming {0} to {1}'.format(name, kwargs['newname']))

    set_tags(name, {'Name': kwargs['newname']}, call='action')

    salt.utils.cloud.rename_key(
        __opts__['pki_dir'], name, kwargs['newname']
    )


def destroy(name, call=None):
    '''
    Destroy a node. Will check termination protection and warn if enabled.

    CLI Example::

        salt-cloud --destroy mymachine
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    node_metadata = _get_node(name)
    instance_id = node_metadata['instanceId']
    sir_id = node_metadata.get('spotInstanceRequestId')
    protected = show_term_protect(
        name=name,
        instance_id=instance_id,
        call='action',
        quiet=True
    )

    salt.utils.cloud.fire_event(
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        {'name': name, 'instance_id': instance_id},
    )

    if protected == 'true':
        raise SaltCloudSystemExit(
            'This instance has been protected from being destroyed. '
            'Use the following command to disable protection:\n\n'
            'salt-cloud -a disable_term_protect {0}'.format(
                name
            )
        )

    ret = {}

    if config.get_cloud_config_value('rename_on_destroy',
                               get_configured_provider(),
                               __opts__, search_global=False) is True:
        newname = '{0}-DEL{1}'.format(name, uuid.uuid4().hex)
        rename(name, kwargs={'newname': newname}, call='action')
        log.info(
            'Machine will be identified as {0} until it has been '
            'cleaned up.'.format(
                newname
            )
        )
        ret['newname'] = newname

    params = {'Action': 'TerminateInstances',
              'InstanceId.1': instance_id}
    result = query(params)
    log.info(result)
    ret.update(result[0])

    # If this instance is part of a spot instance request, we
    # need to cancel it as well
    if sir_id is not None:
        params = {'Action': 'CancelSpotInstanceRequests',
                  'SpotInstanceRequestId.1': sir_id}
        result = query(params)
        ret['spotInstance'] = result[0]

    salt.utils.cloud.fire_event(
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        {'name': name, 'instance_id': instance_id},
    )

    return ret


def reboot(name, call=None):
    '''
    Reboot a node.

    CLI Example::

        salt-cloud -a reboot mymachine
    '''
    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'RebootInstances',
              'InstanceId.1': instance_id}
    result = query(params)
    if result == []:
        log.info("Complete")

    return {'Reboot': 'Complete'}


def show_image(kwargs, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The show_image action must be called with -f or --function.'
        )

    params = {'ImageId.1': kwargs['image'],
              'Action': 'DescribeImages'}
    result = query(params)
    log.info(result)

    return result


def show_instance(name, call=None):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_instance action must be called with -a or --action.'
        )

    return _get_node(name)


def _get_node(name, location=None):
    if location is None:
        location = get_location()

    attempts = 10
    while attempts >= 0:
        try:
            return list_nodes_full(location)[name]
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


def list_nodes_full(location=None, call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes_full function must be called with -f or --function.'
        )

    if not location:
        ret = {}
        locations = set(
            get_location(vm_) for vm_ in __opts__['profiles'].values()
            if _vm_provider_driver(vm_)
        )
        for loc in locations:
            ret.update(_list_nodes_full(loc))
        return ret

    return _list_nodes_full(location)


def _vm_provider_driver(vm_):
    alias, driver = vm_['provider'].split(':')
    if alias not in __opts__['providers']:
        return None

    if driver not in __opts__['providers'][alias]:
        return None

    return driver == 'ec2'


def _extract_name_tag(item):
    if 'tagSet' in item:
        tagset = item['tagSet']
        if type(tagset['item']) is list:
            for tag in tagset['item']:
                if tag['key'] == 'Name':
                    return tag['value']
            return item['instanceId']
        return item['tagSet']['item']['value']
    return item['instanceId']


def _list_nodes_full(location=None):
    '''
    Return a list of the VMs that in this location
    '''

    ret = {}
    params = {'Action': 'DescribeInstances'}
    instances = query(params, location=location)
    if 'error' in instances:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                instances['error']['Errors']['Error']['Message']
            )
        )

    for instance in instances:
        # items could be type dict or list (for stopped EC2 instances)
        if isinstance(instance['instancesSet']['item'], list):
            for item in instance['instancesSet']['item']:
                name = _extract_name_tag(item)
                ret[name] = item
                ret[name].update(
                    dict(
                        id=item['instanceId'],
                        image=item['imageId'],
                        size=item['instanceType'],
                        state=item['instanceState']['name'],
                        private_ips=item.get('privateIpAddress', []),
                        public_ips=item.get('ipAddress', [])
                    )
                )
        else:
            item = instance['instancesSet']['item']
            name = _extract_name_tag(item)
            ret[name] = item
            ret[name].update(
                dict(
                    id=item['instanceId'],
                    image=item['imageId'],
                    size=item['instanceType'],
                    state=item['instanceState']['name'],
                    private_ips=item.get('privateIpAddress', []),
                    public_ips=item.get('ipAddress', [])
                )
            )
    return ret


def list_nodes(call=None):
    '''
    Return a list of the VMs that are on the provider
    '''
    if call == 'action':
        raise SaltCloudSystemExit(
            'The list_nodes function must be called with -f or --function.'
        )

    ret = {}
    nodes = list_nodes_full(get_location())
    if 'error' in nodes:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                nodes['error']['Errors']['Error']['Message']
            )
        )
    for node in nodes:
        ret[node] = {
            'id': nodes[node]['id'],
            'image': nodes[node]['image'],
            'size': nodes[node]['size'],
            'state': nodes[node]['state'],
            'private_ips': nodes[node]['private_ips'],
            'public_ips': nodes[node]['public_ips'],
        }
    return ret


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(get_location()), __opts__['query.selection'], call,
    )


def show_term_protect(name=None, instance_id=None, call=None, quiet=False):
    '''
    Show the details from EC2 concerning an AMI
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_term_protect action must be called with -a or --action.'
        )

    if not instance_id:
        instances = list_nodes_full(get_location())
        instance_id = instances[name]['instanceId']
    params = {'Action': 'DescribeInstanceAttribute',
              'InstanceId': instance_id,
              'Attribute': 'disableApiTermination'}
    result = query(params, return_root=True)

    disable_protect = False
    for item in result:
        if 'value' in item:
            disable_protect = item['value']
            break

    log.log(
        logging.DEBUG if quiet is True else logging.INFO,
        'Termination Protection is {0} for {1}'.format(
            disable_protect == 'true' and 'enabled' or 'disabled',
            name
        )
    )

    return disable_protect


def enable_term_protect(name, call=None):
    '''
    Enable termination protection on a node

    CLI Example::

        salt-cloud -a enable_term_protect mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The enable_term_protect action must be called with '
            '-a or --action.'
        )

    return _toggle_term_protect(name, 'true')


def disable_term_protect(name, call=None):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The disable_term_protect action must be called with '
            '-a or --action.'
        )

    return _toggle_term_protect(name, 'false')


def _toggle_term_protect(name, value):
    '''
    Disable termination protection on a node

    CLI Example::

        salt-cloud -a disable_term_protect mymachine
    '''
    instances = list_nodes_full(get_location())
    instance_id = instances[name]['instanceId']
    params = {'Action': 'ModifyInstanceAttribute',
              'InstanceId': instance_id,
              'DisableApiTermination.Value': value}

    query(params, return_root=True)

    return show_term_protect(name=name, instance_id=instance_id, call='action')


def show_delvol_on_destroy(name, kwargs=None, call=None):
    '''
    Do not delete all/specified EBS volumes upon instance termination

    CLI Example::

        salt-cloud -a show_delvol_on_destroy mymachine
    '''

    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_delvol_on_destroy action must be called '
            'with -a or --action.'
        )

    if not kwargs:
        kwargs = {}

    instance_id = kwargs.get('instance_id', None)
    device = kwargs.get('device', None)
    volume_id = kwargs.get('volume_id', None)

    if instance_id is None:
        instances = list_nodes_full()
        instance_id = instances[name]['instanceId']

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}

    data, requesturl = query(params, return_url=True)

    blockmap = data[0]['instancesSet']['item']['blockDeviceMapping']

    if type(blockmap['item']) != list:
        blockmap['item'] = [blockmap['item']]

    items = []

    for idx, item in enumerate(blockmap['item']):
        device_name = item['deviceName']

        if device is not None and device != device_name:
            continue

        if volume_id is not None and volume_id != item['ebs']['volumeId']:
            continue

        info = {
            'device_name': device_name,
            'volume_id': item['ebs']['volumeId'],
            'deleteOnTermination': item['ebs']['deleteOnTermination']
        }

        items.append(info)

    return items


def keepvol_on_destroy(name, kwargs=None, call=None):
    '''
    Do not delete all/specified EBS volumes upon instance termination

    CLI Example::

        salt-cloud -a keepvol_on_destroy mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The keepvol_on_destroy action must be called with -a or --action.'
        )

    if not kwargs:
        kwargs = {}

    device = kwargs.get('device', None)
    volume_id = kwargs.get('volume_id', None)

    return _toggle_delvol(name=name, device=device,
                          volume_id=volume_id, value='false')


def delvol_on_destroy(name, kwargs=None, call=None):
    '''
    Delete all/specified EBS volumes upon instance termination

    CLI Example::

        salt-cloud -a delvol_on_destroy mymachine
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The delvol_on_destroy action must be called with -a or --action.'
        )

    if not kwargs:
        kwargs = {}

    device = kwargs.get('device', None)
    volume_id = kwargs.get('volume_id', None)

    return _toggle_delvol(name=name, device=device,
                          volume_id=volume_id, value='true')


def _toggle_delvol(name=None, instance_id=None, device=None, volume_id=None,
                   value=None, requesturl=None):

    if not instance_id:
        instances = list_nodes_full(get_location())
        instance_id = instances[name]['instanceId']

    if requesturl:
        data = query(requesturl=requesturl)
    else:
        params = {'Action': 'DescribeInstances',
                  'InstanceId.1': instance_id}
        data, requesturl = query(params, return_url=True)

    blockmap = data[0]['instancesSet']['item']['blockDeviceMapping']

    params = {'Action': 'ModifyInstanceAttribute',
              'InstanceId': instance_id}

    if type(blockmap['item']) != list:
        blockmap['item'] = [blockmap['item']]

    for idx, item in enumerate(blockmap['item']):
        device_name = item['deviceName']

        if device is not None and device != device_name:
            continue
        if volume_id is not None and volume_id != item['ebs']['volumeId']:
            continue

        params['BlockDeviceMapping.%d.DeviceName' % (idx)] = device_name
        params['BlockDeviceMapping.%d.Ebs.DeleteOnTermination' % (idx)] = value

    query(params, return_root=True)

    return query(requesturl=requesturl)


def create_volume(kwargs=None, call=None):
    '''
    Create a volume
    '''
    if call != 'function':
        log.error(
            'The create_volume function must be called with -f or --function.'
        )
        return False

    if 'zone' not in kwargs:
        log.error('An availability zone must be specified to create a volume.')
        return False

    if 'size' not in kwargs and 'snapshot' not in kwargs:
        # This number represents GiB
        kwargs['size'] = '10'

    params = {'Action': 'CreateVolume',
              'AvailabilityZone': kwargs['zone']}

    if 'size' in kwargs:
        params['Size'] = kwargs['size']

    if 'snapshot' in kwargs:
        params['SnapshotId'] = kwargs['snapshot']

    if 'type' in kwargs:
        params['VolumeType'] = kwargs['type']

    if 'iops' in kwargs and kwargs.get('type', 'standard') == 'io1':
        params['Iops'] = kwargs['iops']

    log.debug(params)

    data = query(params, return_root=True)

    # Wait a few seconds to make sure the volume
    # has had a chance to shift to available state
    # TODO: Should probably create a util method to
    # wait for available status and fail on others
    time.sleep(5)

    return data


def attach_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Attach a volume to an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The attach_volume action must be called with -a or --action.'
        )

    if not kwargs:
        kwargs = {}

    if 'instance_id' in kwargs:
        instance_id = kwargs['instance_id']

    if name and not instance_id:
        instances = list_nodes_full(get_location())
        instance_id = instances[name]['instanceId']

    if not name and not instance_id:
        log.error('Either a name or an instance_id is required.')
        return False

    if 'volume_id' not in kwargs:
        log.error('A volume_id is required.')
        return False

    if 'device' not in kwargs:
        log.error('A device is required (ex. /dev/sdb1).')
        return False

    params = {'Action': 'AttachVolume',
              'VolumeId': kwargs['volume_id'],
              'InstanceId': instance_id,
              'Device': kwargs['device']}

    log.debug(params)

    data = query(params, return_root=True)
    return data


def show_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Show volume details
    '''
    if not kwargs:
        kwargs = {}

    if 'volume_id' not in kwargs:
        log.error('A volume_id is required.')
        return False

    params = {'Action': 'DescribeVolumes',
              'VolumeId.1': kwargs['volume_id']}

    data = query(params, return_root=True)
    return data


def detach_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Detach a volume from an instance
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The detach_volume action must be called with -a or --action.'
        )

    if not kwargs:
        kwargs = {}

    if 'volume_id' not in kwargs:
        log.error('A volume_id is required.')
        return False

    params = {'Action': 'DetachVolume',
              'VolumeId': kwargs['volume_id']}

    data = query(params, return_root=True)
    return data


def delete_volume(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Delete a volume
    '''
    if not kwargs:
        kwargs = {}

    if 'volume_id' not in kwargs:
        log.error('A volume_id is required.')
        return False

    params = {'Action': 'DeleteVolume',
              'VolumeId': kwargs['volume_id']}

    data = query(params, return_root=True)
    return data


def create_keypair(kwargs=None, call=None):
    '''
    Create an SSH keypair
    '''
    if call != 'function':
        log.error(
            'The create_keypair function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    params = {'Action': 'CreateKeyPair',
              'KeyName': kwargs['keyname']}

    data = query(params, return_root=True)
    return data


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

    params = {'Action': 'DescribeKeyPairs',
              'KeyName.1': kwargs['keyname']}

    data = query(params, return_root=True)
    return data


def delete_keypair(kwargs=None, call=None):
    '''
    Delete an SSH keypair
    '''
    if call != 'function':
        log.error(
            'The delete_keypair function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    params = {'Action': 'DeleteKeyPair',
              'KeyName.1': kwargs['keyname']}

    data = query(params, return_root=True)
    return data
