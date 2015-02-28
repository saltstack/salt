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

      # SSH Gateways can be used with this provider. Gateways can be used
      # when a salt-master is not on the same private network as the instance
      # that is being deployed.

      # Defaults to None
      # Required
      ssh_gateway: gateway.example.com

      # Defaults to port 22
      # Optional
      ssh_gateway_port: 22

      # Defaults to root
      # Optional
      ssh_gateway_username: root

      # One authentication method is required. If both
      # are specified, Private key wins.

      # Private key defaults to None
      ssh_gateway_private_key: /path/to/key.pem

      # Password defaults to None
      ssh_gateway_password: ExamplePasswordHere

      provider: ec2

:depends: requests
'''
# pylint: disable=E0102

# Import python libs
import os
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
import urlparse
import requests

# Import salt libs
import salt.utils
from salt._compat import ElementTree as ET

# Import salt.cloud libs
import salt.utils.cloud
import salt.config as config
from salt.exceptions import (
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
    'ap-northeast-1': 'ec2_ap_northeast',
    'ap-southeast-1': 'ec2_ap_southeast',
    'ap-southeast-2': 'ec2_ap_southeast_2',
    'eu-west-1': 'ec2_eu_west',
    'sa-east-1': 'ec2_sa_east',
    'us-east-1': 'ec2_us_east',
    'us-west-1': 'ec2_us_west',
    'us-west-2': 'ec2_us_west_oregon',
}
DEFAULT_LOCATION = 'us-east-1'

DEFAULT_EC2_API_VERSION = '2013-10-01'

EC2_RETRY_CODES = [
    'RequestLimitExceeded',
    'InsufficientInstanceCapacity',
    'InternalError',
    'Unavailable',
    'InsufficientAddressCapacity',
    'InsufficientReservedInstanceCapacity',
]


# Only load in this module if the EC2 configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for EC2 configurations
    '''
    if get_configured_provider() is False:
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
        if name not in xmldict:
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


def optimize_providers(providers):
    '''
    Return an optimized list of providers.

    We want to reduce the duplication of querying
    the same region.

    If a provider is using the same credentials for the same region
    the same data will be returned for each provider, thus causing
    un-wanted duplicate data and API calls to EC2.

    '''
    tmp_providers = {}
    optimized_providers = {}

    for name, data in providers.iteritems():
        if 'location' not in data:
            data['location'] = DEFAULT_LOCATION

        if data['location'] not in tmp_providers:
            tmp_providers[data['location']] = {}

        creds = (data['id'], data['key'])
        if creds not in tmp_providers[data['location']]:
            tmp_providers[data['location']][creds] = {'name': name,
                                                      'data': data,
                                                      }

    for location, tmp_data in tmp_providers.iteritems():
        for creds, data in tmp_data.iteritems():
            _id, _key = creds
            _name = data['name']
            _data = data['data']
            if _name not in optimized_providers:
                optimized_providers[_name] = _data

    return optimized_providers


def query(params=None, setname=None, requesturl=None, location=None,
          return_url=False, return_root=False):

    provider = get_configured_provider()
    service_url = provider.get('service_url', 'amazonaws.com')

    attempts = 5
    while attempts > 0:
        params_with_headers = params.copy()
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        if not location:
            location = get_location()

        if not requesturl:
            endpoint = provider.get(
                'endpoint',
                'ec2.{0}.{1}'.format(location, service_url)
            )

            requesturl = 'https://{0}/'.format(endpoint)
        else:
            endpoint = urlparse.urlparse(requesturl).netloc
            if endpoint == '':
                endpoint_err = 'Could not find a valid endpoint in the requesturl: {0}. Looking for something like https://some.ec2.endpoint/?args'.format(
                    requesturl
                )
                log.error(endpoint_err)
                if return_url is True:
                    return {'error': endpoint_err}, requesturl
                return {'error': endpoint_err}

        log.debug('Using EC2 endpoint: {0}'.format(endpoint))
        method = 'GET'

        ec2_api_version = provider.get(
            'ec2_api_version',
            DEFAULT_EC2_API_VERSION
        )

        params_with_headers['AWSAccessKeyId'] = provider['id']
        params_with_headers['SignatureVersion'] = '2'
        params_with_headers['SignatureMethod'] = 'HmacSHA256'
        params_with_headers['Timestamp'] = '{0}'.format(timestamp)
        params_with_headers['Version'] = ec2_api_version
        keys = sorted(params_with_headers)
        values = map(params_with_headers.get, keys)
        querystring = urllib.urlencode(list(zip(keys, values)))

        # AWS signature version 2 requires that spaces be encoded as
        # %20, however urlencode uses '+'. So replace pluses with %20.
        querystring = querystring.replace('+', '%20')

        uri = '{0}\n{1}\n/\n{2}'.format(method.encode('utf-8'),
                                        endpoint.encode('utf-8'),
                                        querystring.encode('utf-8'))

        hashed = hmac.new(provider['key'], uri, hashlib.sha256)
        sig = binascii.b2a_base64(hashed.digest())
        params_with_headers['Signature'] = sig.strip()

        log.debug('EC2 Request: {0}'.format(requesturl))
        log.trace('EC2 Request Parameters: {0}'.format(params_with_headers))
        try:
            result = requests.get(requesturl, params=params_with_headers)
            log.debug(
                'EC2 Response Status Code: {0}'.format(
                    # result.getcode()
                    result.status_code
                )
            )
            log.trace(
                'EC2 Response Text: {0}'.format(
                    result.text
                )
            )
            result.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            root = ET.fromstring(exc.response.content)
            data = _xml_to_dict(root)

            # check to see if we should retry the query
            err_code = data.get('Errors', {}).get('Error', {}).get('Code', '')
            if attempts > 0 and err_code and err_code in EC2_RETRY_CODES:
                attempts -= 1
                log.error(
                    'EC2 Response Status Code and Error: [{0} {1}] {2}; '
                    'Attempts remaining: {3}'.format(
                        exc.response.status_code, exc, data, attempts
                    )
                )
                # Wait a bit before continuing to prevent throttling
                time.sleep(2)
                continue

            log.error(
                'EC2 Response Status Code and Error: [{0} {1}] {2}'.format(
                    exc.response.status_code, exc, data
                )
            )
            if return_url is True:
                return {'error': data}, requesturl
            return {'error': data}
    else:
        log.error(
            'EC2 Response Status Code and Error: [{0} {1}] {2}'.format(
                exc.response.status_code, exc, data
            )
        )
        if return_url is True:
            return {'error': data}, requesturl
        return {'error': data}

    response = result.text

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
                            for spot instance request. It must return None if
                            the required data, running instance included, is
                            not available yet.
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
            'c3.large': {
                'id': 'c3.large',
                'cores': '2 (with 3.5 ECUs each)',
                'disk': '32 GiB (2 x 16 GiB SSD)',
                'ram': '3.75 GiB'
            },
            'c3.xlarge': {
                'id': 'c3.xlarge',
                'cores': '4 (with 3.5 ECUs each)',
                'disk': '80 GiB (2 x 40 GiB SSD)',
                'ram': '7.5 GiB'
            },
            'c3.2xlarge': {
                'id': 'c3.2xlarge',
                'cores': '8 (with 3.5 ECUs each)',
                'disk': '160 GiB (2 x 80 GiB SSD)',
                'ram': '15 GiB'
            },
            'c3.4xlarge': {
                'id': 'c3.4xlarge',
                'cores': '16 (with 3.5 ECUs each)',
                'disk': '320 GiB (2 x 80 GiB SSD)',
                'ram': '30 GiB'
            },
            'c3.8xlarge': {
                'id': 'c3.8xlarge',
                'cores': '32 (with 3.5 ECUs each)',
                'disk': '320 GiB (2 x 160 GiB SSD)',
                'ram': '60 GiB'
            }
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
            'r3.large': {
                'id': 'r3.large',
                'cores': '2 (with 3.25 ECUs each)',
                'disk': '32 GiB (1 x 32 GiB SSD)',
                'ram': '15 GiB'
            },
            'r3.xlarge': {
                'id': 'r3.xlarge',
                'cores': '4 (with 3.25 ECUs each)',
                'disk': '80 GiB (1 x 80 GiB SSD)',
                'ram': '30.5 GiB'
            },
            'r3.2xlarge': {
                'id': 'r3.2xlarge',
                'cores': '8 (with 3.25 ECUs each)',
                'disk': '160 GiB (1 x 160 GiB SSD)',
                'ram': '61 GiB'
            },
            'r3.4xlarge': {
                'id': 'r3.4xlarge',
                'cores': '16 (with 3.25 ECUs each)',
                'disk': '320 GiB (1 x 320 GiB SSD)',
                'ram': '122 GiB'
            },
            'r3.8xlarge': {
                'id': 'r3.8xlarge',
                'cores': '32 (with 3.25 ECUs each)',
                'disk': '640 GiB (2 x 320 GiB SSD)',
                'ram': '244 GiB'
            }
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


def ssh_interface(vm_):
    '''
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    '''
    return config.get_cloud_config_value(
        'ssh_interface', vm_, __opts__, default='public_ips',
        search_global=False
    )


def get_ssh_gateway_config(vm_):
    '''
    Return the ssh_gateway configuration.
    '''
    ssh_gateway = config.get_cloud_config_value(
        'ssh_gateway', vm_, __opts__, default=None,
        search_global=False
    )

    # Check to see if a SSH Gateway will be used.
    if not isinstance(ssh_gateway, str):
        return None

    # Create dictionary of configuration items

    # ssh_gateway
    ssh_gateway_config = {'ssh_gateway': ssh_gateway}

    # ssh_gateway_port
    ssh_gateway_config['ssh_gateway_port'] = config.get_cloud_config_value(
        'ssh_gateway_port', vm_, __opts__, default=None,
        search_global=False
    )

    # ssh_gateway_username
    ssh_gateway_config['ssh_gateway_user'] = config.get_cloud_config_value(
        'ssh_gateway_username', vm_, __opts__, default=None,
        search_global=False
    )

    # ssh_gateway_private_key
    ssh_gateway_config['ssh_gateway_key'] = config.get_cloud_config_value(
        'ssh_gateway_private_key', vm_, __opts__, default=None,
        search_global=False
    )

    # ssh_gateway_password
    ssh_gateway_config['ssh_gateway_password'] = config.get_cloud_config_value(
        'ssh_gateway_password', vm_, __opts__, default=None,
        search_global=False
    )

    # Check if private key exists
    key_filename = ssh_gateway_config['ssh_gateway_key']
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            'The defined ssh_gateway_private_key {0!r} does not exist'.format(
                key_filename
            )
        )
    elif (
        key_filename is None and
        not ssh_gateway_config['ssh_gateway_password']
    ):
        raise SaltCloudConfigError(
            'No authentication method. Please define: '
            ' ssh_gateway_password or ssh_gateway_private_key'
        )

    return ssh_gateway_config


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
    if avz not in zones:
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


def get_placementgroup(vm_):
    '''
    Returns the PlacementGroup to use
    '''
    return config.get_cloud_config_value(
        'placementgroup', vm_, __opts__, search_global=False
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


def _request_eip(interface):
    '''
    Request and return Elastic IP
    '''
    params = {'Action': 'AllocateAddress'}
    params['Domain'] = interface.setdefault('domain', 'vpc')
    eip = query(params, return_root=True)
    for e in eip:
        if 'allocationId' in e:
            return e['allocationId']
    return None


def _create_eni(interface, eip=None):
    '''
    Create and return an Elastic Interface
    '''
    params = {'Action': 'DescribeSubnets'}
    subnet_query = query(params, return_root=True)
    found = False

    for subnet_query_result in subnet_query:
        if 'item' in subnet_query_result:
            for subnet in subnet_query_result['item']:
                if subnet['subnetId'] == interface['SubnetId']:
                    found = True
                    break

    if not found:
        raise SaltCloudConfigError(
            'No such subnet <{0}>'.format(interface['SubnetId'])
        )

    params = {'Action': 'CreateNetworkInterface',
              'SubnetId': interface['SubnetId']}

    for k in ('Description', 'PrivateIpAddress',
              'SecondaryPrivateIpAddressCount'):
        if k in interface:
            params[k] = interface[k]

    for k in ('PrivateIpAddresses', 'SecurityGroupId'):
        if k in interface:
            params.update(_param_from_config(k, interface[k]))

    result = query(params, return_root=True)
    eni_desc = result[1]
    if not eni_desc or not eni_desc.get('networkInterfaceId'):
        raise SaltCloudException('Failed to create interface: {0}'.format(result))

    eni_id = eni_desc.get('networkInterfaceId')
    log.debug(
        'Created network interface {0} inst {1}'.format(
            eni_id, interface['DeviceIndex']
        )
    )

    if interface.get('associate_eip'):
        _associate_eip_with_interface(eni_id, interface.get('associate_eip'))
    elif interface.get('allocate_new_eip'):
        _new_eip = _request_eip(interface)
        _associate_eip_with_interface(eni_id, _new_eip)
    elif interface.get('allocate_new_eips'):
        addr_list = _list_interface_private_addresses(eni_desc)
        eip_list = []
        for idx, addr in enumerate(addr_list):
            eip_list.append(_request_eip(interface))
        for idx, addr in enumerate(addr_list):
            _associate_eip_with_interface(eni_id, eip_list[idx], addr)

    return {'DeviceIndex': interface['DeviceIndex'],
            'NetworkInterfaceId': eni_id}


def _list_interface_private_addresses(eni_desc):
    '''
    Returns a list of all of the private IP addresses attached to a
    network interface. The 'primary' address will be listed first.
    '''
    primary = eni_desc.get('privateIpAddress')
    if not primary:
        return None

    addresses = [primary]

    lst = eni_desc.get('privateIpAddressesSet', {}).get('item', [])
    if not isinstance(lst, list):
        return addresses

    for entry in lst:
        if entry.get('primary') == 'true':
            continue
        if entry.get('privateIpAddress'):
            addresses.append(entry.get('privateIpAddress'))

    return addresses


def _associate_eip_with_interface(eni_id, eip_id, private_ip=None):
    '''
    Accept the id of a network interface, and the id of an elastic ip
    address, and associate the two of them, such that traffic sent to the
    elastic ip address will be forwarded (NATted) to this network interface.

    Optionally specify the private (10.x.x.x) IP address that traffic should
    be NATted to - useful if you have multiple IP addresses assigned to an
    interface.
    '''
    retries = 5
    while retries > 0:
        params = {'Action': 'AssociateAddress',
                  'NetworkInterfaceId': eni_id,
                  'AllocationId': eip_id}

        if private_ip:
            params['PrivateIpAddress'] = private_ip

        retries = retries - 1
        result = query(params, return_root=True)

        if isinstance(result, dict) and result.get('error'):
            time.sleep(1)
            continue

        if not result[2].get('associationId'):
            break

        log.debug(
            'Associated ElasticIP address {0} with interface {1}'.format(
                eip_id, eni_id
            )
        )

        return result[2].get('associationId')

    raise SaltCloudException(
        'Could not associate elastic ip address '
        '<{0}> with network interface <{1}>'.format(
            eip_id, eni_id
        )
    )


def _update_enis(interfaces, instance):
    config_enis = {}
    instance_enis = []
    for interface in interfaces:
        if 'DeviceIndex' in interface:
            if interface['DeviceIndex'] in config_enis:
                log.error(
                    'Duplicate DeviceIndex in profile. Cannot update ENIs.'
                )
                return None
            config_enis[str(interface['DeviceIndex'])] = interface
    query_enis = instance[0]['instancesSet']['item']['networkInterfaceSet']['item']
    if isinstance(query_enis, list):
        for query_eni in query_enis:
            instance_enis.append((query_eni['networkInterfaceId'], query_eni['attachment']))
    else:
        instance_enis.append((query_enis['networkInterfaceId'], query_enis['attachment']))

    for eni_id, eni_data in instance_enis:
        params = {'Action': 'ModifyNetworkInterfaceAttribute',
                  'NetworkInterfaceId': eni_id,
                  'Attachment.AttachmentId': eni_data['attachmentId'],
                  'Attachment.DeleteOnTermination': config_enis[eni_data['deviceIndex']].setdefault('delete_interface_on_terminate', True)}
        set_eni_attributes = query(params, return_root=True)

    return None


def _param_from_config(key, data):
    '''
    Return EC2 API parameters based on the given config data.

    Examples:
    1. List of dictionaries
    >>> data = [
    ...     {'DeviceIndex': 0, 'SubnetId': 'subid0',
    ...      'AssociatePublicIpAddress': True},
    ...     {'DeviceIndex': 1,
    ...      'SubnetId': 'subid1',
    ...      'PrivateIpAddress': '192.168.1.128'}
    ... ]
    >>> _param_from_config('NetworkInterface', data)
    ... {'NetworkInterface.0.SubnetId': 'subid0',
    ...  'NetworkInterface.0.DeviceIndex': 0,
    ...  'NetworkInterface.1.SubnetId': 'subid1',
    ...  'NetworkInterface.1.PrivateIpAddress': '192.168.1.128',
    ...  'NetworkInterface.0.AssociatePublicIpAddress': 'true',
    ...  'NetworkInterface.1.DeviceIndex': 1}

    2. List of nested dictionaries
    >>> data = [
    ...     {'DeviceName': '/dev/sdf',
    ...      'Ebs': {
    ...      'SnapshotId': 'dummy0',
    ...      'VolumeSize': 200,
    ...      'VolumeType': 'standard'}},
    ...     {'DeviceName': '/dev/sdg',
    ...      'Ebs': {
    ...          'SnapshotId': 'dummy1',
    ...          'VolumeSize': 100,
    ...          'VolumeType': 'standard'}}
    ... ]
    >>> _param_from_config('BlockDeviceMapping', data)
    ... {'BlockDeviceMapping.0.Ebs.VolumeType': 'standard',
    ...  'BlockDeviceMapping.1.Ebs.SnapshotId': 'dummy1',
    ...  'BlockDeviceMapping.0.Ebs.VolumeSize': 200,
    ...  'BlockDeviceMapping.0.Ebs.SnapshotId': 'dummy0',
    ...  'BlockDeviceMapping.1.Ebs.VolumeType': 'standard',
    ...  'BlockDeviceMapping.1.DeviceName': '/dev/sdg',
    ...  'BlockDeviceMapping.1.Ebs.VolumeSize': 100,
    ...  'BlockDeviceMapping.0.DeviceName': '/dev/sdf'}

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


def request_instance(vm_=None, call=None):
    '''
    Put together all of the information necessary to request an instance on EC2,
    and then fire off the request the instance.

    Returns data about the instance
    '''
    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The request_instance action must be called with -a or --action.'
        )

    location = vm_.get('location', get_location(vm_))

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
                  'Type': spot_config['type']
                  if 'type' in spot_config else 'one-time',
                  'SpotPrice': spot_config['spot_price']}

        # All of the necessary launch parameters for a VM when using
        # spot instances are the same except for the prefix below
        # being tacked on.
        spot_prefix = 'LaunchSpecification.'

    # regular EC2 instance
    else:
        # WARNING! EXPERIMENTAL!
        # This allows more than one instance to be spun up in a single call.
        # The first instance will be called by the name provided, but all other
        # instances will be nameless (or more specifically, they will use the
        # InstanceId as the name). This interface is expected to change, so
        # use at your own risk.
        min_instance = config.get_cloud_config_value(
            'min_instance', vm_, __opts__, search_global=False, default=1
        )
        max_instance = config.get_cloud_config_value(
            'max_instance', vm_, __opts__, search_global=False, default=1
        )
        params = {'Action': 'RunInstances',
                  'MinCount': min_instance,
                  'MaxCount': max_instance}

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
                params[
                    spot_prefix + 'IamInstanceProfile.Arn'
                ] = ex_iam_profile
            else:
                params[
                    spot_prefix + 'IamInstanceProfile.Name'
                ] = ex_iam_profile
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
                params[
                    spot_prefix + 'SecurityGroupId.{0}'.format(counter)
                ] = sg_

    placementgroup_ = get_placementgroup(vm_)
    if placementgroup_ is not None:
        params[spot_prefix + 'Placement.GroupName'] = placementgroup_

    ex_blockdevicemappings = block_device_mappings(vm_)
    if ex_blockdevicemappings:
        params.update(_param_from_config(spot_prefix + 'BlockDeviceMapping',
                      ex_blockdevicemappings))

    network_interfaces = config.get_cloud_config_value(
        'network_interfaces',
        vm_,
        __opts__,
        search_global=False
    )

    if network_interfaces:
        eni_devices = []
        for interface in network_interfaces:
            log.debug('Create network interface: {0}'.format(interface))
            _new_eni = _create_eni(interface)
            eni_devices.append(_new_eni)
        params.update(_param_from_config(spot_prefix + 'NetworkInterface',
                                         eni_devices))

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

    vm_['set_del_root_vol_on_destroy'] = set_del_root_vol_on_destroy

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
                exc_info_on_loglevel=logging.DEBUG
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
                dev_list = [
                    dev['DeviceName'] for dev in ex_blockdevicemappings
                ]
            else:
                dev_list = []

            if rd_name in dev_list:
                dev_index = dev_list.index(rd_name)
                termination_key = '{0}BlockDeviceMapping.{1}.Ebs.DeleteOnTermination'.format(spot_prefix, dev_index)
                params[termination_key] = str(set_del_root_vol_on_destroy).lower()
            else:
                dev_index = len(dev_list)
                params[
                    '{0}BlockDeviceMapping.{1}.DeviceName'.format(
                        spot_prefix, dev_index
                    )
                ] = rd_name
                params[
                    '{0}BlockDeviceMapping.{1}.Ebs.DeleteOnTermination'.format(
                        spot_prefix, dev_index
                    )
                ] = str(set_del_root_vol_on_destroy).lower()

    set_del_all_vols_on_destroy = config.get_cloud_config_value(
        'del_all_vols_on_destroy', vm_, __opts__, search_global=False, default=False
    )

    if set_del_all_vols_on_destroy is not None:
        if not isinstance(set_del_all_vols_on_destroy, bool):
            raise SaltCloudConfigError(
                '\'del_all_vols_on_destroy\' should be a boolean value.'
            )

    salt.utils.cloud.fire_event(
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        {'kwargs': params, 'location': location},
        transport=__opts__['transport']
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
            exc_info_on_loglevel=logging.DEBUG
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
                    'There was an error in the query. {0}'
                    .format(data['error'])
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
            transport=__opts__['transport']
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
                    'wait_for_spot_interval_multiplier',
                    vm_,
                    __opts__,
                    default=1),
                max_failures=config.get_cloud_config_value(
                    'wait_for_spot_max_failures',
                    vm_,
                    __opts__,
                    default=10),
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
                raise SaltCloudSystemExit(str(exc))

    return data, vm_


def query_instance(vm_=None, call=None):
    '''
    Query an instance upon creation from the EC2 API
    '''
    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The query_instance action must be called with -a or --action.'
        )

    instance_id = vm_['instance_id']
    location = vm_.get('location', get_location(vm_))
    salt.utils.cloud.fire_event(
        'event',
        'querying instance',
        'salt/cloud/{0}/querying'.format(vm_['name']),
        {'instance_id': instance_id},
        transport=__opts__['transport']
    )

    log.debug('The new VM instance_id is {0}'.format(instance_id))

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}

    attempts = 5
    while attempts > 0:
        data, requesturl = query(                       # pylint: disable=W0632
            params, location=location, return_url=True
        )
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
            raise SaltCloudSystemExit(str(exc))

    if 'reactor' in vm_ and vm_['reactor'] is True:
        salt.utils.cloud.fire_event(
            'event',
            'instance queried',
            'salt/cloud/{0}/query_reactor'.format(vm_['name']),
            {'data': data},
            transport=__opts__['transport']
        )

    return data


def wait_for_instance(
        vm_=None,
        data=None,
        ip_address=None,
        display_ssh_output=True,
        call=None,
    ):
    '''
    Wait for an instance upon creation from the EC2 API, to become available
    '''
    if call == 'function':
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            'The wait_for_instance action must be called with -a or --action.'
        )

    if vm_ is None:
        vm_ = {}

    if data is None:
        data = {}

    ssh_gateway_config = vm_.get(
        'gateway', get_ssh_gateway_config(vm_)
    )

    salt.utils.cloud.fire_event(
        'event',
        'waiting for ssh',
        'salt/cloud/{0}/waiting_for_ssh'.format(vm_['name']),
        {'ip_address': ip_address},
        transport=__opts__['transport']
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
                                        timeout=ssh_connect_timeout,
                                        gateway=ssh_gateway_config
                                        ):
        # If a known_hosts_file is configured, this instance will not be
        # accessible until it has a host key. Since this is provided on
        # supported instances by cloud-init, and viewable to us only from the
        # console output (which may take several minutes to become available,
        # we have some more waiting to do here.
        known_hosts_file = config.get_cloud_config_value(
            'known_hosts_file', vm_, __opts__, default=None
        )
        if known_hosts_file:
            console = {}
            while 'output_decoded' not in console:
                console = get_console_output(
                    instance_id=vm_['instance_id'],
                    call='action',
                )
                pprint.pprint(console)
                time.sleep(5)
            output = console['output_decoded']
            comps = output.split('-----BEGIN SSH HOST KEY KEYS-----')
            if len(comps) < 2:
                # Fail; there are no host keys
                return False

            comps = comps[1].split('-----END SSH HOST KEY KEYS-----')
            keys = ''
            for line in comps[0].splitlines():
                if not line:
                    continue
                keys += '\n{0} {1}'.format(ip_address, line)

            with salt.utils.fopen(known_hosts_file, 'a') as fp_:
                fp_.write(keys)
            fp_.close()

        for user in vm_['usernames']:
            if salt.utils.cloud.wait_for_passwd(
                host=ip_address,
                username=user,
                ssh_timeout=config.get_cloud_config_value(
                    'wait_for_passwd_timeout', vm_, __opts__, default=1 * 60
                ),
                key_filename=vm_['key_filename'],
                display_ssh_output=display_ssh_output,
                gateway=ssh_gateway_config,
                maxtries=config.get_cloud_config_value(
                    'wait_for_passwd_maxtries', vm_, __opts__, default=15
                ),
                known_hosts_file=config.get_cloud_config_value(
                    'known_hosts_file', vm_, __opts__,
                    default='/dev/null'
                ),
            ):
                __opts__['ssh_username'] = user
                vm_['ssh_username'] = user
                break
        else:
            raise SaltCloudSystemExit(
                'Failed to authenticate against remote ssh'
            )
    else:
        raise SaltCloudSystemExit(
            'Failed to connect to remote ssh'
        )

    if 'reactor' in vm_ and vm_['reactor'] is True:
        salt.utils.cloud.fire_event(
            'event',
            'ssh is available',
            'salt/cloud/{0}/ssh_ready_reactor'.format(vm_['name']),
            {'ip_address': ip_address},
            transport=__opts__['transport']
        )

    return vm_


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
        transport=__opts__['transport']
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
    vm_['key_filename'] = key_filename

    # Get SSH Gateway config early to verify the private_key,
    # if used, exists or not. We don't want to deploy an instance
    # and not be able to access it via the gateway.
    vm_['gateway'] = get_ssh_gateway_config(vm_)

    location = get_location(vm_)
    vm_['location'] = location

    log.info('Creating Cloud VM {0} in {1}'.format(vm_['name'], location))
    vm_['usernames'] = salt.utils.cloud.ssh_usernames(
        vm_,
        __opts__,
        default_users=(
            'ec2-user', 'ubuntu', 'fedora', 'admin', 'bitnami', 'root'
        )
    )

    if 'instance_id' in vm_:
        # This was probably created via another process, and doesn't have
        # things like salt keys created yet, so let's create them now.
        if 'pub_key' not in vm_ and 'priv_key' not in vm_:
            log.debug('Generating minion keys for {0[name]!r}'.format(vm_))
            vm_['priv_key'], vm_['pub_key'] = salt.utils.cloud.gen_keys(
                salt.config.get_cloud_config_value(
                    'keysize',
                    vm_,
                    __opts__
                )
            )
    else:
        # Put together all of the information required to request the instance,
        # and then fire off the request for it
        data, vm_ = request_instance(vm_, location)

        # Pull the instance ID, valid for both spot and normal instances

        # Multiple instances may have been spun up, get all their IDs
        vm_['instance_id_list'] = []
        for instance in data:
            vm_['instance_id_list'].append(instance['instanceId'])

        vm_['instance_id'] = vm_['instance_id_list'].pop()
        if len(vm_['instance_id_list']) > 0:
            # Multiple instances were spun up, get one now, and queue the rest
            queue_instances(vm_['instance_id_list'])

    # Wait for vital information, such as IP addresses, to be available
    # for the new instance
    data = query_instance(vm_)

    # Now that the instance is available, tag it appropriately. Should
    # mitigate race conditions with tags
    tags = config.get_cloud_config_value('tag',
                                         vm_,
                                         __opts__,
                                         {},
                                         search_global=False)
    if not isinstance(tags, dict):
        raise SaltCloudConfigError(
            '\'tag\' should be a dict.'
        )

    for value in tags.itervalues():
        if not isinstance(value, str):
            raise SaltCloudConfigError(
                '\'tag\' values must be strings. Try quoting the values. '
                'e.g. "2013-09-19T20:09:46Z".'
            )

    tags['Name'] = vm_['name']

    salt.utils.cloud.fire_event(
        'event',
        'setting tags',
        'salt/cloud/{0}/tagging'.format(vm_['name']),
        {'tags': tags},
        transport=__opts__['transport']
    )

    set_tags(
        vm_['name'],
        tags,
        instance_id=vm_['instance_id'],
        call='action',
        location=location
    )

    network_interfaces = config.get_cloud_config_value(
        'network_interfaces',
        vm_,
        __opts__,
        search_global=False
    )

    if network_interfaces:
        _update_enis(network_interfaces, data)

    # At this point, the node is created and tagged, and now needs to be
    # bootstrapped, once the necessary port is available.
    log.info('Created node {0}'.format(vm_['name']))

    # Wait for the necessary port to become available to bootstrap
    if ssh_interface(vm_) == 'private_ips':
        ip_address = data[0]['instancesSet']['item']['privateIpAddress']
        log.info('Salt node data. Private_ip: {0}'.format(ip_address))
    else:
        ip_address = data[0]['instancesSet']['item']['ipAddress']
        log.info('Salt node data. Public_ip: {0}'.format(ip_address))
    vm_['ssh_host'] = ip_address

    display_ssh_output = config.get_cloud_config_value(
        'display_ssh_output', vm_, __opts__, default=True
    )

    vm_ = wait_for_instance(
        vm_, data, ip_address, display_ssh_output
    )

    # The instance is booted and accessible, let's Salt it!
    ret = salt.utils.cloud.bootstrap(vm_, __opts__)

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
            transport=__opts__['transport']
        )

        log.info('Create and attach volumes to node {0}'.format(vm_['name']))
        created = create_attach_volumes(
            vm_['name'],
            {
                'volumes': volumes,
                'zone': ret['placement']['availabilityZone'],
                'instance_id': ret['instanceId'],
                'del_all_vols_on_destroy': vm_.get('set_del_all_vols_on_destroy', False)
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
            'instance_id': vm_['instance_id'],
        },
        transport=__opts__['transport']
    )

    return ret


def queue_instances(instances):
    '''
    Queue a set of instances to be provisioned later. Expects a list.

    Currently this only queries node data, and then places it in the cloud
    cache (if configured). If the salt-cloud-reactor is being used, these
    instances will be automatically provisioned using that.

    For more information about the salt-cloud-reactor, see:

    https://github.com/saltstack-formulas/salt-cloud-reactor
    '''
    for instance_id in instances:
        node = _get_node(instance_id=instance_id)
        salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)


def create_attach_volumes(name, kwargs, call=None, wait_to_finish=True):
    '''
    Create and attach volumes to created node
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The create_attach_volumes action must be called with '
            '-a or --action.'
        )

    if 'instance_id' not in kwargs:
        kwargs['instance_id'] = _get_node(name)[name]['instanceId']

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
            created_volume = create_volume(volume_dict, call='function', wait_to_finish=wait_to_finish)
            created = True
            for item in created_volume:
                if 'volumeId' in item:
                    volume_dict['volume_id'] = item['volumeId']

        attach = attach_volume(
            name,
            {'volume_id': volume_dict['volume_id'],
             'device': volume['device']},
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

    instance_id = _get_node(name)[name]['instanceId']

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

    instance_id = _get_node(name)[name]['instanceId']

    params = {'Action': 'StartInstances',
              'InstanceId.1': instance_id}
    result = query(params)

    return result


def set_tags(name=None,
             tags=None,
             call=None,
             location=None,
             instance_id=None,
             resource_id=None,
             kwargs=None):  # pylint: disable=W0613
    '''
    Set tags for a resource. Normally a VM name or instance_id is passed in,
    but a resource_id may be passed instead. If both are passed in, the
    instance_id will be used.

    CLI Examples::

        salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
        salt-cloud -a set_tags resource_id=vol-3267ab32 tag=somestuff
    '''
    if kwargs is None:
        kwargs = {}

    if instance_id is None:
        if 'resource_id' in kwargs:
            resource_id = kwargs['resource_id']
            del kwargs['resource_id']

        if 'instance_id' in kwargs:
            instance_id = kwargs['instance_id']
            del kwargs['instance_id']

        if resource_id is None:
            if instance_id is None:
                instance_id = _get_node(name, location)[name]['instanceId']
        else:
            instance_id = resource_id

    # This second check is a safety, in case the above still failed to produce
    # a usable ID
    if instance_id is None:
        return {
            'Error': 'A valid instance_id or resource_id was not specified.'
        }

    params = {'Action': 'CreateTags',
              'ResourceId.1': instance_id}

    log.debug('Tags to set for {0}: {1}'.format(name, tags))

    if kwargs and not tags:
        tags = kwargs

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


def get_tags(name=None,
             instance_id=None,
             call=None,
             location=None,
             kwargs=None,
             resource_id=None):  # pylint: disable=W0613
    '''
    Retrieve tags for a resource. Normally a VM name or instance_id is passed
    in, but a resource_id may be passed instead. If both are passed in, the
    instance_id will be used.

    CLI Examples::

        salt-cloud -a get_tags mymachine
        salt-cloud -a get_tags resource_id=vol-3267ab32
    '''
    if location is None:
        location = get_location()

    if instance_id is None:
        if resource_id is None:
            if name:
                instances = list_nodes_full(location)
                if name in instances:
                    instance_id = instances[name]['instanceId']
            elif 'instance_id' in kwargs:
                instance_id = kwargs['instance_id']
            elif 'resource_id' in kwargs:
                instance_id = kwargs['resource_id']
        else:
            instance_id = resource_id

    params = {'Action': 'DescribeTags',
              'Filter.1.Name': 'resource-id',
              'Filter.1.Value': instance_id}

    return query(params, setname='tagSet', location=location)


def del_tags(name=None,
             kwargs=None,
             call=None,
             instance_id=None,
             resource_id=None):  # pylint: disable=W0613
    '''
    Delete tags for a resource. Normally a VM name or instance_id is passed in,
    but a resource_id may be passed instead. If both are passed in, the
    instance_id will be used.

    CLI Examples::

        salt-cloud -a del_tags mymachine tags=tag1,tag2,tag3
        salt-cloud -a del_tags resource_id=vol-3267ab32 tags=tag1,tag2,tag3
    '''
    if kwargs is None:
        kwargs = {}

    if 'tags' not in kwargs:
        raise SaltCloudSystemExit(
            'A tag or tags must be specified using tags=list,of,tags'
        )

    if not name and 'resource_id' in kwargs:
        instance_id = kwargs['resource_id']
        del kwargs['resource_id']

    if not instance_id:
        instance_id = _get_node(name)[name]['instanceId']

    params = {'Action': 'DeleteTags',
              'ResourceId.1': instance_id}

    for idx, tag in enumerate(kwargs['tags'].split(',')):
        params['Tag.{0}.Key'.format(idx)] = tag

    query(params, setname='tagSet')

    if resource_id:
        return get_tags(resource_id=resource_id)
    else:
        return get_tags(instance_id=instance_id)


def rename(name, kwargs, call=None):
    '''
    Properly rename a node. Pass in the new name as "new name".

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
    '''
    if call == 'function':
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )

    node_metadata = _get_node(name)
    instance_id = node_metadata[name]['instanceId']
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
        transport=__opts__['transport']
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
                                     __opts__,
                                     search_global=False) is True:
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
        transport=__opts__['transport']
    )

    if __opts__.get('update_cachedir', False) is True:
        salt.utils.cloud.delete_minion_cachedir(name, __active_provider_name__.split(':')[0], __opts__)

    return ret


def reboot(name, call=None):
    '''
    Reboot a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot mymachine
    '''
    instance_id = _get_node(name)[name]['instanceId']
    params = {'Action': 'RebootInstances',
              'InstanceId.1': instance_id}
    result = query(params)
    if result == []:
        log.info('Complete')

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


def show_instance(name=None, instance_id=None, call=None, kwargs=None):
    '''
    Show the details from EC2 concerning an AMI.

    Can be called as an action (which requires a name):

        salt-cloud -a show_instance myinstance

    ...or as a function (which requires either a name or instance_id):

        salt-cloud -f show_instance my-ec2 name=myinstance
        salt-cloud -f show_instance my-ec2 instance_id=i-d34db33f
    '''
    if not name and call == 'action':
        raise SaltCloudSystemExit(
            'The show_instance action requires a name.'
        )

    if call == 'function':
        name = kwargs.get('name', None)
        instance_id = kwargs.get('instance_id', None)

    if not name and not instance_id:
        raise SaltCloudSystemExit(
            'The show_instance function requires '
            'either a name or an instance_id'
        )

    node = _get_node(name=name, instance_id=instance_id)
    salt.utils.cloud.cache_node(node, __active_provider_name__, __opts__)
    return node


def _get_node(name=None, instance_id=None, location=None):
    if location is None:
        location = get_location()

    params = {'Action': 'DescribeInstances'}
    if instance_id:
        params['InstanceId.1'] = instance_id
    else:
        params['Filter.1.Name'] = 'tag:Name'
        params['Filter.1.Value.1'] = name

    log.trace(params)

    attempts = 10
    while attempts >= 0:
        try:
            instances = query(params, location=location)
            return _extract_instance_info(instances)
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
            'The list_nodes_full function must be called with -f '
            'or --function.'
        )

    if not location:
        ret = {}
        locations = set(
            get_location(vm_) for vm_ in __opts__['profiles'].itervalues()
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


def _extract_instance_info(instances):
    '''
    Given an instance query, return a dict of all instance data
    '''
    ret = {}
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


def _list_nodes_full(location=None):
    '''
    Return a list of the VMs that in this location
    '''

    params = {'Action': 'DescribeInstances'}
    instances = query(params, location=location)
    if 'error' in instances:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                instances['error']['Errors']['Error']['Message']
            )
        )

    ret = _extract_instance_info(instances)

    provider = __active_provider_name__ or 'ec2'
    if ':' in provider:
        comps = provider.split(':')
        provider = comps[0]
    salt.utils.cloud.cache_node_list(ret, provider, __opts__)
    return ret


def list_nodes_min(location=None, call=None):
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
    params = {'Action': 'DescribeInstances'}
    instances = query(params)
    if 'error' in instances:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                instances['error']['Errors']['Error']['Message']
            )
        )

    for instance in instances:
        if isinstance(instance['instancesSet']['item'], list):
            for item in instance['instancesSet']['item']:
                state = item['instanceState']['name']
                name = _extract_name_tag(item)
        else:
            item = instance['instancesSet']['item']
            state = item['instanceState']['name']
            name = _extract_name_tag(item)
        ret[name] = {'state': state}
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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    data = query(params)

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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
        data, requesturl = query(                       # pylint: disable=W0632
            params, return_url=True)

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

        params['BlockDeviceMapping.{0}.DeviceName'.format(idx)] = device_name
        params['BlockDeviceMapping.{0}.Ebs.DeleteOnTermination'.format(idx)] = value

    query(params, return_root=True)

    kwargs = {'instance_id': instance_id,
              'device': device,
              'volume_id': volume_id}
    return show_delvol_on_destroy(name, kwargs, call='action')


def create_volume(kwargs=None, call=None, wait_to_finish=False):
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
    r_data = {}
    for d in data:
        for k, v in d.items():
            r_data[k] = v
    volume_id = r_data['volumeId']

    # Waits till volume is available
    if wait_to_finish:
        salt.utils.cloud.run_func_until_ret_arg(fun=describe_volumes,
                                                kwargs={'volume_id': volume_id},
                                                fun_call=call,
                                                argument_being_watched='status',
                                                required_argument_response='available')

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


def show_volume(kwargs=None, call=None):
    '''
    Wrapper around describe_volumes.
    Here just to keep functionality.
    Might be depreciated later.
    '''
    if not kwargs:
        kwargs = {}

    return describe_volumes(kwargs, call)


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


def describe_volumes(kwargs=None, call=None):
    '''
    Describe a volume (or volumes)

    volume_id
        One or more volume IDs. Multiple IDs must be separated by ",".

    TODO: Add all of the filters.
    '''
    if call != 'function':
        log.error(
            'The describe_volumes function must be called with -f '
            'or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    params = {'Action': 'DescribeVolumes'}

    if 'volume_id' in kwargs:
        volume_id = kwargs['volume_id'].split(',')
        for volume_index, volume_id in enumerate(volume_id):
            params['VolumeId.{0}'.format(volume_index)] = volume_id

    log.debug(params)

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


def create_snapshot(kwargs=None, call=None, wait_to_finish=False):
    '''
    Create a snapshot
    '''
    if call != 'function':
        log.error(
            'The create_snapshot function must be called with -f '
            'or --function.'
        )
        return False

    if 'volume_id' not in kwargs:
        log.error('A volume_id must be specified to create a snapshot.')
        return False

    if 'description' not in kwargs:
        kwargs['description'] = ''

    params = {'Action': 'CreateSnapshot'}

    if 'volume_id' in kwargs:
        params['VolumeId'] = kwargs['volume_id']

    if 'description' in kwargs:
        params['Description'] = kwargs['description']

    log.debug(params)

    data = query(params, return_root=True)
    r_data = {}
    for d in data:
        for k, v in d.items():
            r_data[k] = v
    snapshot_id = r_data['snapshotId']

    # Waits till volume is available
    if wait_to_finish:
        salt.utils.cloud.run_func_until_ret_arg(fun=describe_snapshots,
                                                kwargs={'snapshot_id': snapshot_id},
                                                fun_call=call,
                                                argument_being_watched='status',
                                                required_argument_response='completed')

    return data


def delete_snapshot(kwargs=None, call=None):
    '''
    Delete a snapshot
    '''
    if call != 'function':
        log.error(
            'The delete_snapshot function must be called with -f '
            'or --function.'
        )
        return False

    if 'snapshot_id' not in kwargs:
        log.error('A snapshot_id must be specified to delete a snapshot.')
        return False

    params = {'Action': 'DeleteSnapshot'}

    if 'snapshot_id' in kwargs:
        params['SnapshotId'] = kwargs['snapshot_id']

    log.debug(params)

    data = query(params, return_root=True)
    return data


def copy_snapshot(kwargs=None, call=None):
    '''
    Copy a snapshot
    '''
    if call != 'function':
        log.error(
            'The copy_snapshot function must be called with -f or --function.'
        )
        return False

    if 'source_region' not in kwargs:
        log.error('A source_region must be specified to copy a snapshot.')
        return False

    if 'source_snapshot_id' not in kwargs:
        log.error('A source_snapshot_id must be specified to copy a snapshot.')
        return False

    if 'description' not in kwargs:
        kwargs['description'] = ''

    params = {'Action': 'CopySnapshot'}

    if 'source_region' in kwargs:
        params['SourceRegion'] = kwargs['source_region']

    if 'source_snapshot_id' in kwargs:
        params['SourceSnapshotId'] = kwargs['source_snapshot_id']

    if 'description' in kwargs:
        params['Description'] = kwargs['description']

    log.debug(params)

    data = query(params, return_root=True)
    return data


def describe_snapshots(kwargs=None, call=None):
    '''
    Describe a snapshot (or snapshots)

    snapshot_id
        One or more snapshot IDs. Multiple IDs must be separated by ",".

    owner
        Return the snapshots owned by the specified owner. Valid values
        include: self, amazon, <AWS Account ID>. Multiple values must be
        separated by ",".

    restorable_by
        One or more AWS accounts IDs that can create volumes from the snapshot.
        Multiple aws account IDs must be separated by ",".

    TODO: Add all of the filters.
    '''
    if call != 'function':
        log.error(
            'The describe_snapshot function must be called with -f '
            'or --function.'
        )
        return False

    params = {'Action': 'DescribeSnapshots'}

    # The AWS correct way is to use non-plurals like snapshot_id INSTEAD of snapshot_ids.
    if 'snapshot_ids' in kwargs:
        kwargs['snapshot_id'] = kwargs['snapshot_ids']

    if 'snapshot_id' in kwargs:
        snapshot_ids = kwargs['snapshot_id'].split(',')
        for snapshot_index, snapshot_id in enumerate(snapshot_ids):
            params['SnapshotId.{0}'.format(snapshot_index)] = snapshot_id

    if 'owner' in kwargs:
        owners = kwargs['owner'].split(',')
        for owner_index, owner in enumerate(owners):
            params['Owner.{0}'.format(owner_index)] = owner

    if 'restorable_by' in kwargs:
        restorable_bys = kwargs['restorable_by'].split(',')
        for restorable_by_index, restorable_by in enumerate(restorable_bys):
            params[
                'RestorableBy.{0}'.format(restorable_by_index)
            ] = restorable_by

    log.debug(params)

    data = query(params, return_root=True)
    return data


def get_console_output(
        name=None,
        instance_id=None,
        call=None,
        kwargs=None,
    ):
    '''
    Show the console output from the instance.

    By default, returns decoded data, not the Base64-encoded data that is
    actually returned from the EC2 API.
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The get_console_output action must be called with '
            '-a or --action.'
        )

    if not instance_id:
        instance_id = _get_node(name)[name]['instanceId']

    if kwargs is None:
        kwargs = {}

    if instance_id is None:
        if 'instance_id' in kwargs:
            instance_id = kwargs['instance_id']
            del kwargs['instance_id']

    params = {'Action': 'GetConsoleOutput',
              'InstanceId': instance_id}

    ret = {}
    data = query(params, return_root=True)
    for item in data:
        if item.iterkeys().next() == 'output':
            ret['output_decoded'] = binascii.a2b_base64(item.itervalues().next())
        else:
            ret[item.iterkeys().next()] = item.itervalues().next()

    return ret
