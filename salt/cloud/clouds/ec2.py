# -*- coding: utf-8 -*-
'''
The EC2 Cloud Module
====================

The EC2 cloud module is used to interact with the Amazon Elastic Compute Cloud.

To use the EC2 cloud module, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/ec2.conf``:

.. code-block:: yaml

    my-ec2-config:
      # EC2 API credentials: Access Key ID and Secret Access Key.
      # Alternatively, to use IAM Instance Role credentials available via
      # EC2 metadata set both id and key to 'use-instance-role-credentials'
      id: GKTADJGHEIQSXMKKRBJ08H
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

      driver: ec2

      # Pass userdata to the instance to be created
      userdata_file: /etc/salt/my-userdata-file

:depends: requests
'''
# pylint: disable=invalid-name,function-redefined

# Import python libs
from __future__ import absolute_import
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
import base64
import msgpack
import json
import re
import decimal

# Import Salt Libs
import salt.utils
from salt._compat import ElementTree as ET
import salt.utils.http as http
import salt.utils.aws as aws

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

# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves import map, range, zip
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse, urlencode as _urlencode

# Import 3rd-Party Libs
# Try to import PyCrypto, which may not be installed on a RAET-based system
try:
    import Crypto
    # PKCS1_v1_5 was added in PyCrypto 2.5
    from Crypto.Cipher import PKCS1_v1_5  # pylint: disable=E0611
    from Crypto.Hash import SHA  # pylint: disable=E0611,W0611
    HAS_PYCRYPTO = True
except ImportError:
    HAS_PYCRYPTO = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Get logging started
log = logging.getLogger(__name__)


EC2_LOCATIONS = {
    'ap-northeast-1': 'ec2_ap_northeast',
    'ap-northeast-2': 'ec2_ap_northeast_2',
    'ap-southeast-1': 'ec2_ap_southeast',
    'ap-southeast-2': 'ec2_ap_southeast_2',
    'eu-west-1': 'ec2_eu_west',
    'eu-central-1': 'ec2_eu_central',
    'sa-east-1': 'ec2_sa_east',
    'us-east-1': 'ec2_us_east',
    'us-gov-west-1': 'ec2_us_gov_west_1',
    'us-west-1': 'ec2_us_west',
    'us-west-2': 'ec2_us_west_oregon',
}
DEFAULT_LOCATION = 'us-east-1'

DEFAULT_EC2_API_VERSION = '2014-10-01'

EC2_RETRY_CODES = [
    'RequestLimitExceeded',
    'InsufficientInstanceCapacity',
    'InternalError',
    'Unavailable',
    'InsufficientAddressCapacity',
    'InsufficientReservedInstanceCapacity',
]

JS_COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)

__virtualname__ = 'ec2'


# Only load in this module if the EC2 configurations are in place
def __virtual__():
    '''
    Set up the libcloud functions and check for EC2 configurations
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
    deps = {
        'requests': HAS_REQUESTS,
        'pycrypto': HAS_PYCRYPTO
    }
    return config.check_driver_dependencies(
        __virtualname__,
        deps
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
            if not isinstance(xmldict[name], list):
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

    for name, data in six.iteritems(providers):
        if 'location' not in data:
            data['location'] = DEFAULT_LOCATION

        if data['location'] not in tmp_providers:
            tmp_providers[data['location']] = {}

        creds = (data['id'], data['key'])
        if creds not in tmp_providers[data['location']]:
            tmp_providers[data['location']][creds] = {'name': name,
                                                      'data': data,
                                                      }

    for location, tmp_data in six.iteritems(tmp_providers):
        for creds, data in six.iteritems(tmp_data):
            _id, _key = creds
            _name = data['name']
            _data = data['data']
            if _name not in optimized_providers:
                optimized_providers[_name] = _data

    return optimized_providers


def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()


def query(params=None, setname=None, requesturl=None, location=None,
          return_url=False, return_root=False):

    provider = get_configured_provider()
    service_url = provider.get('service_url', 'amazonaws.com')

    # Retrieve access credentials from meta-data, or use provided
    access_key_id, secret_access_key, token = aws.creds(provider)

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
            endpoint = _urlparse(requesturl).netloc
            endpoint_path = _urlparse(requesturl).path
        else:
            endpoint = _urlparse(requesturl).netloc
            endpoint_path = _urlparse(requesturl).path
            if endpoint == '':
                endpoint_err = (
                        'Could not find a valid endpoint in the '
                        'requesturl: {0}. Looking for something '
                        'like https://some.ec2.endpoint/?args').format(requesturl)
                log.error(endpoint_err)
                if return_url is True:
                    return {'error': endpoint_err}, requesturl
                return {'error': endpoint_err}

        log.debug('Using EC2 endpoint: {0}'.format(endpoint))
        # AWS v4 signature

        method = 'GET'
        region = location
        service = 'ec2'
        canonical_uri = _urlparse(requesturl).path
        host = endpoint.strip()

        # Create a date for headers and the credential string
        t = datetime.datetime.utcnow()
        amz_date = t.strftime('%Y%m%dT%H%M%SZ')  # Format date as YYYYMMDD'T'HHMMSS'Z'
        datestamp = t.strftime('%Y%m%d')  # Date w/o time, used in credential scope

        canonical_headers = 'host:' + host + '\n' + 'x-amz-date:' + amz_date + '\n'
        signed_headers = 'host;x-amz-date'

        payload_hash = hashlib.sha256('').hexdigest()

        ec2_api_version = provider.get(
            'ec2_api_version',
            DEFAULT_EC2_API_VERSION
        )

        params_with_headers['Version'] = ec2_api_version

        keys = sorted(params_with_headers.keys())
        values = map(params_with_headers.get, keys)
        querystring = _urlencode(list(zip(keys, values)))
        querystring = querystring.replace('+', '%20')

        canonical_request = method + '\n' + canonical_uri + '\n' + \
                    querystring + '\n' + canonical_headers + '\n' + \
                    signed_headers + '\n' + payload_hash

        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = datestamp + '/' + region + '/' + service + '/' + 'aws4_request'

        string_to_sign = algorithm + '\n' +  amz_date + '\n' + \
                         credential_scope + '\n' + \
                         hashlib.sha256(canonical_request).hexdigest()

        kDate = sign(('AWS4' + provider['key']).encode('utf-8'), datestamp)
        kRegion = sign(kDate, region)
        kService = sign(kRegion, service)
        signing_key = sign(kService, 'aws4_request')

        signature = hmac.new(signing_key, (string_to_sign).encode('utf-8'),
                             hashlib.sha256).hexdigest()
        #sig = binascii.b2a_base64(hashed)

        authorization_header = algorithm + ' ' + 'Credential=' + \
                               provider['id'] + '/' + credential_scope + \
                               ', ' +  'SignedHeaders=' + signed_headers + \
                               ', ' + 'Signature=' + signature
        headers = {'x-amz-date': amz_date, 'Authorization': authorization_header}

        log.debug('EC2 Request: {0}'.format(requesturl))
        log.trace('EC2 Request Parameters: {0}'.format(params_with_headers))
        try:
            result = requests.get(requesturl, headers=headers, params=params_with_headers)
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
    :param interval: The looping interval, i.e., the amount of time to sleep
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
        'Compute Optimized': {
            'c4.large': {
                'id': 'c4.large',
                'cores': '2',
                'disk': 'EBS - 500 Mbps',
                'ram': '3.75 GiB'
            },
            'c4.xlarge': {
                'id': 'c4.xlarge',
                'cores': '4',
                'disk': 'EBS - 750 Mbps',
                'ram': '7.5 GiB'
            },
            'c4.2xlarge': {
                'id': 'c4.2xlarge',
                'cores': '8',
                'disk': 'EBS - 1000 Mbps',
                'ram': '15 GiB'
            },
            'c4.4xlarge': {
                'id': 'c4.4xlarge',
                'cores': '16',
                'disk': 'EBS - 2000 Mbps',
                'ram': '30 GiB'
            },
            'c4.8xlarge': {
                'id': 'c4.8xlarge',
                'cores': '36',
                'disk': 'EBS - 4000 Mbps',
                'ram': '60 GiB'
            },
            'c3.large': {
                'id': 'c3.large',
                'cores': '2',
                'disk': '32 GiB (2 x 16 GiB SSD)',
                'ram': '3.75 GiB'
            },
            'c3.xlarge': {
                'id': 'c3.xlarge',
                'cores': '4',
                'disk': '80 GiB (2 x 40 GiB SSD)',
                'ram': '7.5 GiB'
            },
            'c3.2xlarge': {
                'id': 'c3.2xlarge',
                'cores': '8',
                'disk': '160 GiB (2 x 80 GiB SSD)',
                'ram': '15 GiB'
            },
            'c3.4xlarge': {
                'id': 'c3.4xlarge',
                'cores': '16',
                'disk': '320 GiB (2 x 160 GiB SSD)',
                'ram': '30 GiB'
            },
            'c3.8xlarge': {
                'id': 'c3.8xlarge',
                'cores': '32',
                'disk': '640 GiB (2 x 320 GiB SSD)',
                'ram': '60 GiB'
            }
        },
        'Dense Storage': {
            'd2.xlarge': {
                'id': 'd2.xlarge',
                'cores': '4',
                'disk': '6 TiB (3 x 2 TiB hard disk drives)',
                'ram': '30.5 GiB'
            },
            'd2.2xlarge': {
                'id': 'd2.2xlarge',
                'cores': '8',
                'disk': '12 TiB (6 x 2 TiB hard disk drives)',
                'ram': '61 GiB'
            },
            'd2.4xlarge': {
                'id': 'd2.4xlarge',
                'cores': '16',
                'disk': '24 TiB (12 x 2 TiB hard disk drives)',
                'ram': '122 GiB'
            },
            'd2.8xlarge': {
                'id': 'd2.8xlarge',
                'cores': '36',
                'disk': '24 TiB (24 x 2 TiB hard disk drives)',
                'ram': '244 GiB'
            },
        },
        'GPU': {
            'g2.2xlarge': {
                'id': 'g2.2xlarge',
                'cores': '8',
                'disk': '60 GiB (1 x 60 GiB SSD)',
                'ram': '15 GiB'
            },
            'g2.8xlarge': {
                'id': 'g2.8xlarge',
                'cores': '32',
                'disk': '240 GiB (2 x 120 GiB SSD)',
                'ram': '60 GiB'
            },
        },
        'GPU Compute': {
            'p2.xlarge': {
                'id': 'p2.xlarge',
                'cores': '4',
                'disk': 'EBS',
                'ram': '61 GiB'
            },
            'p2.8xlarge': {
                'id': 'p2.8xlarge',
                'cores': '32',
                'disk': 'EBS',
                'ram': '488 GiB'
            },
            'p2.16xlarge': {
                'id': 'p2.16xlarge',
                'cores': '64',
                'disk': 'EBS',
                'ram': '732 GiB'
            },
        },
        'High I/O': {
            'i2.xlarge': {
                'id': 'i2.xlarge',
                'cores': '4',
                'disk': 'SSD (1 x 800 GiB)',
                'ram': '30.5 GiB'
            },
            'i2.2xlarge': {
                'id': 'i2.2xlarge',
                'cores': '8',
                'disk': 'SSD (2 x 800 GiB)',
                'ram': '61 GiB'
            },
            'i2.4xlarge': {
                'id': 'i2.4xlarge',
                'cores': '16',
                'disk': 'SSD (4 x 800 GiB)',
                'ram': '122 GiB'
            },
            'i2.8xlarge': {
                'id': 'i2.8xlarge',
                'cores': '32',
                'disk': 'SSD (8 x 800 GiB)',
                'ram': '244 GiB'
            }
        },
        'High Memory': {
            'x1.16xlarge': {
                'id': 'x1.16xlarge',
                'cores': '64 (with 5.45 ECUs each)',
                'disk': '1920 GiB (1 x 1920 GiB)',
                'ram': '976 GiB'
            },
            'x1.32xlarge': {
                'id': 'x1.32xlarge',
                'cores': '128 (with 2.73 ECUs each)',
                'disk': '3840 GiB (2 x 1920 GiB)',
                'ram': '1952 GiB'
            },
            'r4.large': {
                'id': 'r4.large',
                'cores': '2 (with 3.45 ECUs each)',
                'disk': 'EBS',
                'ram': '15.25 GiB'
            },
            'r4.xlarge': {
                'id': 'r4.xlarge',
                'cores': '4 (with 3.35 ECUs each)',
                'disk': 'EBS',
                'ram': '30.5 GiB'
            },
            'r4.2xlarge': {
                'id': 'r4.2xlarge',
                'cores': '8 (with 3.35 ECUs each)',
                'disk': 'EBS',
                'ram': '61 GiB'
            },
            'r4.4xlarge': {
                'id': 'r4.4xlarge',
                'cores': '16 (with 3.3 ECUs each)',
                'disk': 'EBS',
                'ram': '122 GiB'
            },
            'r4.8xlarge': {
                'id': 'r4.8xlarge',
                'cores': '32 (with 3.1 ECUs each)',
                'disk': 'EBS',
                'ram': '244 GiB'
            },
            'r4.16xlarge': {
                'id': 'r4.16xlarge',
                'cores': '64 (with 3.05 ECUs each)',
                'disk': 'EBS',
                'ram': '488 GiB'
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
        'General Purpose': {
            't2.nano': {
                'id': 't2.nano',
                'cores': '1',
                'disk': 'EBS',
                'ram': '512 MiB'
            },
            't2.micro': {
                'id': 't2.micro',
                'cores': '1',
                'disk': 'EBS',
                'ram': '1 GiB'
            },
            't2.small': {
                'id': 't2.small',
                'cores': '1',
                'disk': 'EBS',
                'ram': '2 GiB'
            },
            't2.medium': {
                'id': 't2.medium',
                'cores': '2',
                'disk': 'EBS',
                'ram': '4 GiB'
            },
            't2.large': {
                'id': 't2.large',
                'cores': '2',
                'disk': 'EBS',
                'ram': '8 GiB'
            },
            't2.xlarge': {
                'id': 't2.xlarge',
                'cores': '4',
                'disk': 'EBS',
                'ram': '16 GiB'
            },
            't2.2xlarge': {
                'id': 't2.2xlarge',
                'cores': '8',
                'disk': 'EBS',
                'ram': '32 GiB'
            },
            'm4.large': {
                'id': 'm4.large',
                'cores': '2',
                'disk': 'EBS - 450 Mbps',
                'ram': '8 GiB'
            },
            'm4.xlarge': {
                'id': 'm4.xlarge',
                'cores': '4',
                'disk': 'EBS - 750 Mbps',
                'ram': '16 GiB'
            },
            'm4.2xlarge': {
                'id': 'm4.2xlarge',
                'cores': '8',
                'disk': 'EBS - 1000 Mbps',
                'ram': '32 GiB'
            },
            'm4.4xlarge': {
                'id': 'm4.4xlarge',
                'cores': '16',
                'disk': 'EBS - 2000 Mbps',
                'ram': '64 GiB'
            },
            'm4.10xlarge': {
                'id': 'm4.10xlarge',
                'cores': '40',
                'disk': 'EBS - 4000 Mbps',
                'ram': '160 GiB'
            },
            'm4.16xlarge': {
                'id': 'm4.16xlarge',
                'cores': '64',
                'disk': 'EBS - 10000 Mbps',
                'ram': '256 GiB'
            },
            'm3.medium': {
                'id': 'm3.medium',
                'cores': '1',
                'disk': 'SSD (1 x 4)',
                'ram': '3.75 GiB'
            },
            'm3.large': {
                'id': 'm3.large',
                'cores': '2',
                'disk': 'SSD (1 x 32)',
                'ram': '7.5 GiB'
            },
            'm3.xlarge': {
                'id': 'm3.xlarge',
                'cores': '4',
                'disk': 'SSD (2 x 40)',
                'ram': '15 GiB'
            },
           'm3.2xlarge': {
                'id': 'm3.2xlarge',
                'cores': '8',
                'disk': 'SSD (2 x 80)',
                'ram': '30 GiB'
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

    if not isinstance(kwargs, dict):
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
    images = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

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
            'The defined ssh_gateway_private_key \'{0}\' does not exist'
            .format(key_filename)
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
    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

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

    zones = _list_availability_zones(vm_)

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


def _get_subnetname_id(subnetname):
    '''
    Returns the SubnetId of a SubnetName to use
    '''
    params = {'Action': 'DescribeSubnets'}
    for subnet in aws.query(params, location=get_location(),
               provider=get_provider(), opts=__opts__, sigver='4'):
        tags = subnet.get('tagSet', {}).get('item', {})
        if not isinstance(tags, list):
            tags = [tags]
        for tag in tags:
            if tag['key'] == 'Name' and tag['value'] == subnetname:
                log.debug('AWS Subnet ID of {0} is {1}'.format(
                    subnetname,
                    subnet['subnetId'])
                )
                return subnet['subnetId']
    return None


def get_subnetid(vm_):
    '''
    Returns the SubnetId to use
    '''
    subnetid = config.get_cloud_config_value(
        'subnetid', vm_, __opts__, search_global=False
    )
    if subnetid:
        return subnetid

    subnetname = config.get_cloud_config_value(
        'subnetname', vm_, __opts__, search_global=False
    )
    if subnetname:
        return _get_subnetname_id(subnetname)
    return None


def _get_securitygroupname_id(securitygroupname_list):
    '''
    Returns the SecurityGroupId of a SecurityGroupName to use
    '''
    securitygroupid_set = set()
    if not isinstance(securitygroupname_list, list):
        securitygroupname_list = [securitygroupname_list]
    params = {'Action': 'DescribeSecurityGroups'}
    for sg in aws.query(params, location=get_location(),
                        provider=get_provider(), opts=__opts__, sigver='4'):
        if sg['groupName'] in securitygroupname_list:
            log.debug('AWS SecurityGroup ID of {0} is {1}'.format(
                sg['groupName'],
                sg['groupId'])
            )
            securitygroupid_set.add(sg['groupId'])
    return list(securitygroupid_set)


def securitygroupid(vm_):
    '''
    Returns the SecurityGroupId
    '''
    securitygroupid_set = set()
    securitygroupid_list = config.get_cloud_config_value(
        'securitygroupid',
        vm_,
        __opts__,
        search_global=False
    )
    # If the list is None, then the set will remain empty
    # If the list is already a set then calling 'set' on it is a no-op
    # If the list is a string, then calling 'set' generates a one-element set
    # If the list is anything else, stacktrace
    if securitygroupid_list:
        securitygroupid_set = securitygroupid_set.union(set(securitygroupid_list))

    securitygroupname_list = config.get_cloud_config_value(
        'securitygroupname', vm_, __opts__, search_global=False
    )
    if securitygroupname_list:
        if not isinstance(securitygroupname_list, list):
            securitygroupname_list = [securitygroupname_list]
        params = {'Action': 'DescribeSecurityGroups'}
        for sg in aws.query(params, location=get_location(),
                            provider=get_provider(), opts=__opts__, sigver='4'):
            if sg['groupName'] in securitygroupname_list:
                log.debug('AWS SecurityGroup ID of {0} is {1}'.format(
                    sg['groupName'], sg['groupId'])
                )
                securitygroupid_set.add(sg['groupId'])
    return list(securitygroupid_set)


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


def get_provider(vm_=None):
    '''
    Extract the provider name from vm
    '''
    if vm_ is None:
        provider = __active_provider_name__ or 'ec2'
    else:
        provider = vm_.get('provider', 'ec2')

    if ':' in provider:
        prov_comps = provider.split(':')
        provider = prov_comps[0]
    return provider


def _list_availability_zones(vm_=None):
    '''
    List all availability zones in the current region
    '''
    ret = {}

    params = {'Action': 'DescribeAvailabilityZones',
              'Filter.0.Name': 'region-name',
              'Filter.0.Value.0': get_location(vm_)}
    result = aws.query(params,
                       location=get_location(vm_),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

    for zone in result:
        ret[zone['zoneName']] = zone['zoneState']

    return ret


def block_device_mappings(vm_):
    '''
    Return the block device mapping:

    .. code-block:: python

        [{'DeviceName': '/dev/sdb', 'VirtualName': 'ephemeral0'},
          {'DeviceName': '/dev/sdc', 'VirtualName': 'ephemeral1'}]
    '''
    return config.get_cloud_config_value(
        'block_device_mappings', vm_, __opts__, search_global=True
    )


def _request_eip(interface, vm_):
    '''
    Request and return Elastic IP
    '''
    params = {'Action': 'AllocateAddress'}
    params['Domain'] = interface.setdefault('domain', 'vpc')
    eips = aws.query(params,
                     return_root=True,
                     location=get_location(vm_),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
    for eip in eips:
        if 'allocationId' in eip:
            return eip['allocationId']
    return None


def _create_eni_if_necessary(interface, vm_):
    '''
    Create an Elastic Interface if necessary and return a Network Interface Specification
    '''
    if 'NetworkInterfaceId' in interface and interface['NetworkInterfaceId'] is not None:
        return {'DeviceIndex': interface['DeviceIndex'],
                'NetworkInterfaceId': interface['NetworkInterfaceId']}

    params = {'Action': 'DescribeSubnets'}
    subnet_query = aws.query(params,
                             return_root=True,
                             location=get_location(vm_),
                             provider=get_provider(),
                             opts=__opts__,
                             sigver='4')

    if 'SecurityGroupId' not in interface and 'securitygroupname' in interface:
        interface['SecurityGroupId'] = _get_securitygroupname_id(interface['securitygroupname'])
    if 'SubnetId' not in interface and 'subnetname' in interface:
        interface['SubnetId'] = _get_subnetname_id(interface['subnetname'])

    subnet_id = _get_subnet_id_for_interface(subnet_query, interface)
    if not subnet_id:
        raise SaltCloudConfigError(
            'No such subnet <{0}>'.format(interface.get('SubnetId'))
        )
    params = {'SubnetId': subnet_id}

    for k in 'Description', 'PrivateIpAddress', 'SecondaryPrivateIpAddressCount':
        if k in interface:
            params[k] = interface[k]

    for k in 'PrivateIpAddresses', 'SecurityGroupId':
        if k in interface:
            params.update(_param_from_config(k, interface[k]))

    if 'AssociatePublicIpAddress' in interface:
        # Associating a public address in a VPC only works when the interface is not
        # created beforehand, but as a part of the machine creation request.
        for k in ('DeviceIndex', 'AssociatePublicIpAddress', 'NetworkInterfaceId'):
            if k in interface:
                params[k] = interface[k]
        params['DeleteOnTermination'] = interface.get('delete_interface_on_terminate', True)
        return params

    params['Action'] = 'CreateNetworkInterface'

    result = aws.query(params,
                       return_root=True,
                       location=get_location(vm_),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

    eni_desc = result[1]
    if not eni_desc or not eni_desc.get('networkInterfaceId'):
        raise SaltCloudException('Failed to create interface: {0}'.format(result))

    eni_id = eni_desc.get('networkInterfaceId')
    log.debug(
        'Created network interface {0} inst {1}'.format(
            eni_id, interface['DeviceIndex']
        )
    )

    associate_public_ip = interface.get('AssociatePublicIpAddress', False)
    if isinstance(associate_public_ip, str):
        # Assume id of EIP as value
        _associate_eip_with_interface(eni_id, associate_public_ip, vm_=vm_)

    if interface.get('associate_eip'):
        _associate_eip_with_interface(eni_id, interface.get('associate_eip'), vm_=vm_)
    elif interface.get('allocate_new_eip'):
        _new_eip = _request_eip(interface, vm_)
        _associate_eip_with_interface(eni_id, _new_eip, vm_=vm_)
    elif interface.get('allocate_new_eips'):
        addr_list = _list_interface_private_addrs(eni_desc)
        eip_list = []
        for idx, addr in enumerate(addr_list):
            eip_list.append(_request_eip(interface, vm_))
        for idx, addr in enumerate(addr_list):
            _associate_eip_with_interface(eni_id, eip_list[idx], addr, vm_=vm_)

    if 'Name' in interface:
        tag_params = {'Action': 'CreateTags',
                      'ResourceId.0': eni_id,
                      'Tag.0.Key': 'Name',
                      'Tag.0.Value': interface['Name']}
        tag_response = aws.query(tag_params,
                                 return_root=True,
                                 location=get_location(vm_),
                                 provider=get_provider(),
                                 opts=__opts__,
                                 sigver='4')
        if 'error' in tag_response:
            log.error('Failed to set name of interface {0}')

    return {'DeviceIndex': interface['DeviceIndex'],
            'NetworkInterfaceId': eni_id}


def _get_subnet_id_for_interface(subnet_query, interface):
    for subnet_query_result in subnet_query:
        if 'item' in subnet_query_result:
            if isinstance(subnet_query_result['item'], dict):
                subnet_id = _get_subnet_from_subnet_query(subnet_query_result['item'],
                                                          interface)
                if subnet_id is not None:
                    return subnet_id

            else:
                for subnet in subnet_query_result['item']:
                    subnet_id = _get_subnet_from_subnet_query(subnet, interface)
                    if subnet_id is not None:
                        return subnet_id


def _get_subnet_from_subnet_query(subnet_query, interface):
    if 'subnetId' in subnet_query:
        if interface.get('SubnetId'):
            if subnet_query['subnetId'] == interface['SubnetId']:
                return subnet_query['subnetId']
        else:
            return subnet_query['subnetId']


def _list_interface_private_addrs(eni_desc):
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


def _modify_eni_properties(eni_id, properties=None, vm_=None):
    '''
    Change properties of the interface
    with id eni_id to the values in properties dict
    '''
    if not isinstance(properties, dict):
        raise SaltCloudException(
            'ENI properties must be a dictionary'
        )

    params = {'Action': 'ModifyNetworkInterfaceAttribute',
              'NetworkInterfaceId': eni_id}
    for k, v in six.iteritems(properties):
        params[k] = v

    retries = 5
    while retries > 0:
        retries = retries - 1

        result = aws.query(params,
                           return_root=True,
                           location=get_location(vm_),
                           provider=get_provider(),
                           opts=__opts__,
                           sigver='4')

        if isinstance(result, dict) and result.get('error'):
            time.sleep(1)
            continue

        return result

    raise SaltCloudException(
        'Could not change interface <{0}> attributes '
        '<\'{1}\'> after 5 retries'.format(
            eni_id, properties
        )
    )


def _associate_eip_with_interface(eni_id, eip_id, private_ip=None, vm_=None):
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
        result = aws.query(params,
                           return_root=True,
                           location=get_location(vm_),
                           provider=get_provider(),
                           opts=__opts__,
                           sigver='4')

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


def _update_enis(interfaces, instance, vm_=None):
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
        delete_on_terminate = True
        if 'DeleteOnTermination' in config_enis[eni_data['deviceIndex']]:
            delete_on_terminate = config_enis[eni_data['deviceIndex']]['DeleteOnTermination']
        elif 'delete_interface_on_terminate' in config_enis[eni_data['deviceIndex']]:
            delete_on_terminate = config_enis[eni_data['deviceIndex']]['delete_interface_on_terminate']

        params_attachment = {'Attachment.AttachmentId': eni_data['attachmentId'],
                             'Attachment.DeleteOnTermination': delete_on_terminate}
        set_eni_attachment_attributes = _modify_eni_properties(eni_id, params_attachment, vm_=vm_)

        if 'SourceDestCheck' in config_enis[eni_data['deviceIndex']]:
            params_sourcedest = {'SourceDestCheck.Value': config_enis[eni_data['deviceIndex']]['SourceDestCheck']}
            set_eni_sourcedest_property = _modify_eni_properties(eni_id, params_sourcedest, vm_=vm_)

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
        for k, v in six.iteritems(data):
            param.update(_param_from_config('{0}.{1}'.format(key, k), v))

    elif isinstance(data, list) or isinstance(data, tuple):
        for idx, conf_item in enumerate(data):
            prefix = '{0}.{1}'.format(key, idx)
            param.update(_param_from_config(prefix, conf_item))

    else:
        if isinstance(data, bool):
            # convert boolean True/False to 'true'/'false'
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

    userdata = None
    userdata_file = config.get_cloud_config_value(
        'userdata_file', vm_, __opts__, search_global=False, default=None
    )
    if userdata_file is None:
        userdata = config.get_cloud_config_value(
            'userdata', vm_, __opts__, search_global=False, default=None
        )
    else:
        log.trace('userdata_file: {0}'.format(userdata_file))
        if os.path.exists(userdata_file):
            with salt.utils.fopen(userdata_file, 'r') as fh_:
                userdata = fh_.read()

    userdata = salt.utils.cloud.userdata_template(__opts__, vm_, userdata)

    if userdata is not None:
        try:
            params[spot_prefix + 'UserData'] = base64.b64encode(userdata)
        except Exception as exc:
            log.exception('Failed to encode userdata: %s', exc)

    vm_size = config.get_cloud_config_value(
        'size', vm_, __opts__, search_global=False
    )
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
            for counter, sg_ in enumerate(ex_securitygroupid):
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
            _new_eni = _create_eni_if_necessary(interface, vm_)
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

    if set_del_root_vol_on_destroy and not isinstance(set_del_root_vol_on_destroy, bool):
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
            rd_data = aws.query(rd_params,
                                location=get_location(vm_),
                                provider=get_provider(),
                                opts=__opts__,
                                sigver='4')
            if 'error' in rd_data:
                return rd_data['error']
            log.debug('EC2 Response: \'{0}\''.format(rd_data))
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
        rd_name = None
        rd_type = None
        if 'blockDeviceMapping' in rd_data[0]:
            # Some ami instances do not have a root volume. Ignore such cases
            if rd_data[0]['blockDeviceMapping'] is not None:
                item = rd_data[0]['blockDeviceMapping']['item']
                if isinstance(item, list):
                    item = item[0]
                rd_name = item['deviceName']
                # Grab the volume type
                rd_type = item['ebs'].get('volumeType', None)

            log.info('Found root device name: {0}'.format(rd_name))

        if rd_name is not None:
            if ex_blockdevicemappings:
                dev_list = [
                    dev['DeviceName'] for dev in ex_blockdevicemappings
                ]
            else:
                dev_list = []

            if rd_name in dev_list:
                # Device already listed, just grab the index
                dev_index = dev_list.index(rd_name)
            else:
                dev_index = len(dev_list)
                # Add the device name in since it wasn't already there
                params[
                    '{0}BlockDeviceMapping.{1}.DeviceName'.format(
                        spot_prefix, dev_index
                    )
                ] = rd_name

            # Set the termination value
            termination_key = '{0}BlockDeviceMapping.{1}.Ebs.DeleteOnTermination'.format(spot_prefix, dev_index)
            params[termination_key] = str(set_del_root_vol_on_destroy).lower()

            # Use default volume type if not specified
            if ex_blockdevicemappings and 'Ebs.VolumeType' not in ex_blockdevicemappings[dev_index]:
                type_key = '{0}BlockDeviceMapping.{1}.Ebs.VolumeType'.format(spot_prefix, dev_index)
                params[type_key] = rd_type

    set_del_all_vols_on_destroy = config.get_cloud_config_value(
        'del_all_vols_on_destroy', vm_, __opts__, search_global=False, default=False
    )

    if set_del_all_vols_on_destroy and not isinstance(set_del_all_vols_on_destroy, bool):
        raise SaltCloudConfigError(
            '\'del_all_vols_on_destroy\' should be a boolean value.'
        )

    __utils__['cloud.fire_event'](
        'event',
        'requesting instance',
        'salt/cloud/{0}/requesting'.format(vm_['name']),
        args={
            'kwargs': __utils__['cloud.filter_event'](
                'requesting', params, params.keys()
            ),
            'location': location,
        },
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    provider = get_provider(vm_)

    try:
        data = aws.query(params,
                         'instancesSet',
                         location=location,
                         provider=provider,
                         opts=__opts__,
                         sigver='4')
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
            data = aws.query(params,
                             location=location,
                             provider=provider,
                             opts=__opts__,
                             sigver='4')
            if not data:
                log.error(
                    'There was an error while querying EC2. Empty response'
                )
                # Trigger a failure in the wait for spot instance method
                return False

            if isinstance(data, dict) and 'error' in data:
                log.warning(
                    'There was an error in the query. {0}'
                    .format(data['error'])
                )
                # Trigger a failure in the wait for spot instance method
                return False

            log.debug('Returned query data: {0}'.format(data))

            state = data[0].get('state')

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

        __utils__['cloud.fire_event'](
            'event',
            'waiting for spot instance',
            'salt/cloud/{0}/waiting_for_spot'.format(vm_['name']),
            sock_dir=__opts__['sock_dir'],
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
                data = aws.query(params,
                                 location=location,
                                 provider=provider,
                                 opts=__opts__,
                                 sigver='4')

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
    __utils__['cloud.fire_event'](
        'event',
        'querying instance',
        'salt/cloud/{0}/querying'.format(vm_['name']),
        args={'instance_id': instance_id},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    log.debug('The new VM instance_id is {0}'.format(instance_id))

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}

    provider = get_provider(vm_)

    attempts = 5
    while attempts > 0:
        data, requesturl = aws.query(params,                # pylint: disable=unbalanced-tuple-unpacking
                                     location=location,
                                     provider=provider,
                                     opts=__opts__,
                                     return_url=True,
                                     sigver='4')
        log.debug('The query returned: {0}'.format(data))

        if isinstance(data, dict) and 'error' in data:
            log.warning(
                'There was an error in the query. {0} attempts '
                'remaining: {1}'.format(
                    attempts, data['error']
                )
            )
            attempts -= 1
            # Just a little delay between attempts...
            time.sleep(1)
            continue

        if isinstance(data, list) and not data:
            log.warning(
                'Query returned an empty list. {0} attempts '
                'remaining.'.format(attempts)
            )
            attempts -= 1
            # Just a little delay between attempts...
            time.sleep(1)
            continue

        break
    else:
        raise SaltCloudSystemExit(
            'An error occurred while creating VM: {0}'.format(data['error'])
        )

    def __query_ip_address(params, url):  # pylint: disable=W0613
        data = aws.query(params,
                         #requesturl=url,
                         location=location,
                         provider=provider,
                         opts=__opts__,
                         sigver='4')
        if not data:
            log.error(
                'There was an error while querying EC2. Empty response'
            )
            # Trigger a failure in the wait for IP function
            return False

        if isinstance(data, dict) and 'error' in data:
            log.warning(
                'There was an error in the query. {0}'.format(data['error'])
            )
            # Trigger a failure in the wait for IP function
            return False

        log.debug('Returned query data: {0}'.format(data))

        if ssh_interface(vm_) == 'public_ips':
            if 'ipAddress' in data[0]['instancesSet']['item']:
                return data
            else:
                log.error(
                    'Public IP not detected.'
                )

        if ssh_interface(vm_) == 'private_ips':
            if 'privateIpAddress' in data[0]['instancesSet']['item']:
                return data
            else:
                log.error(
                    'Private IP not detected.'
                )

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
        __utils__['cloud.fire_event'](
            'event',
            'instance queried',
            'salt/cloud/{0}/query_reactor'.format(vm_['name']),
            args={'data': data},
            sock_dir=__opts__['sock_dir'],
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

    __utils__['cloud.fire_event'](
        'event',
        'waiting for ssh',
        'salt/cloud/{0}/waiting_for_ssh'.format(vm_['name']),
        args={'ip_address': ip_address},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    ssh_connect_timeout = config.get_cloud_config_value(
        'ssh_connect_timeout', vm_, __opts__, 900   # 15 minutes
    )
    ssh_port = config.get_cloud_config_value(
        'ssh_port', vm_, __opts__, 22
    )

    if config.get_cloud_config_value('win_installer', vm_, __opts__):
        username = config.get_cloud_config_value(
            'win_username', vm_, __opts__, default='Administrator'
        )
        win_passwd = config.get_cloud_config_value(
            'win_password', vm_, __opts__, default=''
        )
        win_deploy_auth_retries = config.get_cloud_config_value(
            'win_deploy_auth_retries', vm_, __opts__, default=10
        )
        win_deploy_auth_retry_delay = config.get_cloud_config_value(
            'win_deploy_auth_retry_delay', vm_, __opts__, default=1
        )
        use_winrm = config.get_cloud_config_value(
            'use_winrm', vm_, __opts__, default=False
        )

        if win_passwd and win_passwd == 'auto':
            log.debug('Waiting for auto-generated Windows EC2 password')
            while True:
                password_data = get_password_data(
                    name=vm_['name'],
                    kwargs={
                        'key_file': vm_['private_key'],
                    },
                    call='action',
                )
                win_passwd = password_data.get('password', None)
                if win_passwd is None:
                    log.debug(password_data)
                    # This wait is so high, because the password is unlikely to
                    # be generated for at least 4 minutes
                    time.sleep(60)
                else:
                    logging_data = password_data

                    logging_data['password'] = 'XXX-REDACTED-XXX'
                    logging_data['passwordData'] = 'XXX-REDACTED-XXX'
                    log.debug(logging_data)

                    vm_['win_password'] = win_passwd
                    break

        # SMB used whether winexe or winrm
        if not salt.utils.cloud.wait_for_port(ip_address,
                                              port=445,
                                              timeout=ssh_connect_timeout):
            raise SaltCloudSystemExit(
                'Failed to connect to remote windows host'
            )

        # If not using winrm keep same winexe behavior
        if not use_winrm:

            log.debug('Trying to authenticate via SMB using winexe')

            if not salt.utils.cloud.validate_windows_cred(ip_address,
                                                          username,
                                                          win_passwd,
                                                          retries=win_deploy_auth_retries,
                                                          retry_delay=win_deploy_auth_retry_delay):
                raise SaltCloudSystemExit(
                    'Failed to authenticate against remote windows host (smb)'
                )

        # If using winrm
        else:

            # Default HTTPS port can be changed in cloud configuration
            winrm_port = config.get_cloud_config_value(
                'winrm_port', vm_, __opts__, default=5986
            )

            # Wait for winrm port to be available
            if not salt.utils.cloud.wait_for_port(ip_address,
                                                  port=winrm_port,
                                                  timeout=ssh_connect_timeout):
                raise SaltCloudSystemExit(
                    'Failed to connect to remote windows host (winrm)'
                )

            log.debug('Trying to authenticate via Winrm using pywinrm')

            if not salt.utils.cloud.wait_for_winrm(ip_address,
                                                          winrm_port,
                                                          username,
                                                          win_passwd,
                                                          timeout=ssh_connect_timeout):
                raise SaltCloudSystemExit(
                    'Failed to authenticate against remote windows host'
                )

    elif salt.utils.cloud.wait_for_port(ip_address,
                                        port=ssh_port,
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
                    location=get_location(vm_)
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
                port=ssh_port,
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
        __utils__['cloud.fire_event'](
            'event',
            'ssh is available',
            'salt/cloud/{0}/ssh_ready_reactor'.format(vm_['name']),
            args={'ip_address': ip_address},
            sock_dir=__opts__['sock_dir'],
            transport=__opts__['transport']
        )

    return vm_


def _validate_key_path_and_mode(key_filename):
    if key_filename is None:
        raise SaltCloudSystemExit(
            'The required \'private_key\' configuration setting is missing from the '
            '\'ec2\' driver.'
        )

    if not os.path.exists(key_filename):
        raise SaltCloudSystemExit(
            'The EC2 key file \'{0}\' does not exist.\n'.format(
                key_filename
            )
        )

    key_mode = stat.S_IMODE(os.stat(key_filename).st_mode)
    if key_mode not in (0o400, 0o600):
        raise SaltCloudSystemExit(
            'The EC2 key file \'{0}\' needs to be set to mode 0400 or 0600.\n'.format(
                key_filename
            )
        )

    return True


def create(vm_=None, call=None):
    '''
    Create a single VM from a data dict
    '''
    if call:
        raise SaltCloudSystemExit(
            'You cannot create an instance with -a or -f.'
        )

    try:
        # Check for required profile parameters before sending any API calls.
        if vm_['profile'] and config.is_profile_configured(__opts__,
                                                           __active_provider_name__ or 'ec2',
                                                           vm_['profile'],
                                                           vm_=vm_) is False:
            return False
    except AttributeError:
        pass

    # Check for private_key and keyfile name for bootstrapping new instances
    deploy = config.get_cloud_config_value(
        'deploy', vm_, __opts__, default=True
    )
    win_password = config.get_cloud_config_value(
        'win_password', vm_, __opts__, default=''
    )
    key_filename = config.get_cloud_config_value(
        'private_key', vm_, __opts__, search_global=False, default=None
    )
    if deploy:
        # The private_key and keyname settings are only needed for bootstrapping
        # new instances when deploy is True
        _validate_key_path_and_mode(key_filename)

    __utils__['cloud.fire_event'](
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('creating', vm_, ['name', 'profile', 'provider', 'driver']),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )
    __utils__['cloud.cachedir_index_add'](
        vm_['name'], vm_['profile'], 'ec2', vm_['driver']
    )

    vm_['key_filename'] = key_filename
    # wait_for_instance requires private_key
    vm_['private_key'] = key_filename

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
            'ec2-user',  # Amazon Linux, Fedora, RHEL; FreeBSD
            'centos',    # CentOS AMIs from AWS Marketplace
            'ubuntu',    # Ubuntu
            'admin',     # Debian GNU/Linux
            'bitnami',   # BitNami AMIs
            'root'       # Last resort, default user on RHEL 5, SUSE
        )
    )

    if 'instance_id' in vm_:
        # This was probably created via another process, and doesn't have
        # things like salt keys created yet, so let's create them now.
        if 'pub_key' not in vm_ and 'priv_key' not in vm_:
            log.debug('Generating minion keys for \'{0[name]}\''.format(vm_))
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
        if keyname(vm_) is None:
            raise SaltCloudSystemExit(
                'The required \'keyname\' configuration setting is missing from the '
                '\'ec2\' driver.'
            )

        data, vm_ = request_instance(vm_, location)

        # If data is a str, it's an error
        if isinstance(data, str):
            log.error('Error requesting instance: {0}'.format(data))
            return {}

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

    for value in six.itervalues(tags):
        if not isinstance(value, str):
            raise SaltCloudConfigError(
                '\'tag\' values must be strings. Try quoting the values. '
                'e.g. "2013-09-19T20:09:46Z".'
            )

    tags['Name'] = vm_['name']

    __utils__['cloud.fire_event'](
        'event',
        'setting tags',
        'salt/cloud/{0}/tagging'.format(vm_['name']),
        args={'tags': tags},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    salt.utils.cloud.wait_for_fun(
        set_tags,
        timeout=30,
        name=vm_['name'],
        tags=tags,
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
        _update_enis(network_interfaces, data, vm_)

    # At this point, the node is created and tagged, and now needs to be
    # bootstrapped, once the necessary port is available.
    log.info('Created node {0}'.format(vm_['name']))

    instance = data[0]['instancesSet']['item']

    # Wait for the necessary port to become available to bootstrap
    if ssh_interface(vm_) == 'private_ips':
        ip_address = instance['privateIpAddress']
        log.info('Salt node data. Private_ip: {0}'.format(ip_address))
    else:
        ip_address = instance['ipAddress']
        log.info('Salt node data. Public_ip: {0}'.format(ip_address))
    vm_['ssh_host'] = ip_address

    if salt.utils.cloud.get_salt_interface(vm_, __opts__) == 'private_ips':
        salt_ip_address = instance['privateIpAddress']
        log.info('Salt interface set to: {0}'.format(salt_ip_address))
    else:
        salt_ip_address = instance['ipAddress']
        log.debug('Salt interface set to: {0}'.format(salt_ip_address))
    vm_['salt_host'] = salt_ip_address

    if deploy:
        display_ssh_output = config.get_cloud_config_value(
            'display_ssh_output', vm_, __opts__, default=True
        )

        vm_ = wait_for_instance(
            vm_, data, ip_address, display_ssh_output
        )

    # The instance is booted and accessible, let's Salt it!
    ret = instance.copy()

    # Get ANY defined volumes settings, merging data, in the following order
    # 1. VM config
    # 2. Profile config
    # 3. Global configuration
    volumes = config.get_cloud_config_value(
        'volumes', vm_, __opts__, search_global=True
    )
    if volumes:
        __utils__['cloud.fire_event'](
            'event',
            'attaching volumes',
            'salt/cloud/{0}/attaching_volumes'.format(vm_['name']),
            args={'volumes': volumes},
            sock_dir=__opts__['sock_dir'],
            transport=__opts__['transport']
        )

        log.info('Create and attach volumes to node {0}'.format(vm_['name']))
        created = create_attach_volumes(
            vm_['name'],
            {
                'volumes': volumes,
                'zone': ret['placement']['availabilityZone'],
                'instance_id': ret['instanceId'],
                'del_all_vols_on_destroy': vm_.get('del_all_vols_on_destroy', False)
            },
            call='action'
        )
        ret['Attached Volumes'] = created

    # Associate instance with a ssm document, if present
    ssm_document = config.get_cloud_config_value(
        'ssm_document', vm_, __opts__, None, search_global=False
    )
    if ssm_document:
        log.debug('Associating with ssm document: {0}'.format(ssm_document))
        assoc = ssm_create_association(
            vm_['name'],
            {'ssm_document': ssm_document},
            instance_id=vm_['instance_id'],
            call='action'
        )
        if isinstance(assoc, dict) and assoc.get('error', None):
            log.error('Failed to associate instance {0} with ssm document {1}'.format(
                vm_['instance_id'], ssm_document
            ))
            return {}

    for key, value in six.iteritems(__utils__['cloud.bootstrap'](vm_, __opts__)):
        ret.setdefault(key, value)

    log.info('Created Cloud VM \'{0[name]}\''.format(vm_))
    log.debug(
        '\'{0[name]}\' VM creation details:\n{1}'.format(
            vm_, pprint.pformat(instance)
        )
    )

    event_data = {
        'name': vm_['name'],
        'profile': vm_['profile'],
        'provider': vm_['driver'],
        'instance_id': vm_['instance_id'],
    }
    if volumes:
        event_data['volumes'] = volumes
    if ssm_document:
        event_data['ssm_document'] = ssm_document

    __utils__['cloud.fire_event'](
        'event',
        'created instance',
        'salt/cloud/{0}/created'.format(vm_['name']),
        args=__utils__['cloud.filter_event']('created', event_data, event_data.keys()),
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    # Ensure that the latest node data is returned
    node = _get_node(instance_id=vm_['instance_id'])
    ret.update(node)

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
        __utils__['cloud.cache_node'](node, __active_provider_name__, __opts__)


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
        kwargs['instance_id'] = _get_node(name)['instanceId']

    if isinstance(kwargs['volumes'], str):
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
        elif 'size' in volume:
            volume_dict['size'] = volume['size']
        else:
            raise SaltCloudConfigError(
                'Cannot create volume.  Please define one of \'volume_id\', '
                '\'snapshot\', or \'size\''
            )

        if 'tags' in volume:
            volume_dict['tags'] = volume['tags']
        if 'type' in volume:
            volume_dict['type'] = volume['type']
        if 'iops' in volume:
            volume_dict['iops'] = volume['iops']
        if 'encrypted' in volume:
            volume_dict['encrypted'] = volume['encrypted']

        if 'volume_id' not in volume_dict:
            created_volume = create_volume(volume_dict, call='function', wait_to_finish=wait_to_finish)
            created = True
            if 'volumeId' in created_volume:
                volume_dict['volume_id'] = created_volume['volumeId']

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

    instance_id = _get_node(name)['instanceId']

    params = {'Action': 'StopInstances',
              'InstanceId.1': instance_id}
    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

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
    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

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

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a set_tags mymachine tag1=somestuff tag2='Other stuff'
        salt-cloud -a set_tags resource_id=vol-3267ab32 tag=somestuff
    '''
    if kwargs is None:
        kwargs = {}

    if location is None:
        location = get_location()

    if instance_id is None:
        if 'resource_id' in kwargs:
            resource_id = kwargs['resource_id']
            del kwargs['resource_id']

        if 'instance_id' in kwargs:
            instance_id = kwargs['instance_id']
            del kwargs['instance_id']

        if resource_id is None:
            if instance_id is None:
                instance_id = _get_node(name=name, instance_id=None, location=location)['instanceId']
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

    for idx, (tag_k, tag_v) in enumerate(six.iteritems(tags)):
        params['Tag.{0}.Key'.format(idx)] = tag_k
        params['Tag.{0}.Value'.format(idx)] = tag_v

    attempts = 5
    while attempts >= 0:
        result = aws.query(params,
                           setname='tagSet',
                           location=location,
                           provider=get_provider(),
                           opts=__opts__,
                           sigver='4')

        settags = get_tags(
            instance_id=instance_id, call='action', location=location
        )

        log.debug('Setting the tags returned: {0}'.format(settags))

        failed_to_set_tags = False
        for tag in settags:
            if tag['key'] not in tags:
                # We were not setting this tag
                continue

            if tag.get('value') is None and tags.get(tag['key']) == '':
                # This is a correctly set tag with no value
                continue

            if str(tags.get(tag['key'])) != str(tag['value']):
                # Not set to the proper value!?
                log.debug('Setting the tag {0} returned {1} instead of {2}'.format(tag['key'], tags.get(tag['key']), tag['value']))
                failed_to_set_tags = True
                break

        if failed_to_set_tags:
            log.warning(
                'Failed to set tags. Remaining attempts {0}'.format(
                    attempts
                )
            )
            attempts -= 1
            # Just a little delay between attempts...
            time.sleep(1)
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

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a get_tags mymachine
        salt-cloud -a get_tags resource_id=vol-3267ab32
    '''
    if location is None:
        location = get_location()

    if instance_id is None:
        if resource_id is None:
            if name:
                instance_id = _get_node(name)['instanceId']
            elif 'instance_id' in kwargs:
                instance_id = kwargs['instance_id']
            elif 'resource_id' in kwargs:
                instance_id = kwargs['resource_id']
        else:
            instance_id = resource_id

    params = {'Action': 'DescribeTags',
              'Filter.1.Name': 'resource-id',
              'Filter.1.Value': instance_id}

    return aws.query(params,
                     setname='tagSet',
                     location=location,
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')


def del_tags(name=None,
             kwargs=None,
             call=None,
             instance_id=None,
             resource_id=None):  # pylint: disable=W0613
    '''
    Delete tags for a resource. Normally a VM name or instance_id is passed in,
    but a resource_id may be passed instead. If both are passed in, the
    instance_id will be used.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a del_tags mymachine tags=mytag,
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
        instance_id = _get_node(name)['instanceId']

    params = {'Action': 'DeleteTags',
              'ResourceId.1': instance_id}

    for idx, tag in enumerate(kwargs['tags'].split(',')):
        params['Tag.{0}.Key'.format(idx)] = tag

    aws.query(params,
              setname='tagSet',
              location=get_location(),
              provider=get_provider(),
              opts=__opts__,
              sigver='4')

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
    instance_id = node_metadata['instanceId']
    sir_id = node_metadata.get('spotInstanceRequestId')
    protected = show_term_protect(
        name=name,
        instance_id=instance_id,
        call='action',
        quiet=True
    )

    __utils__['cloud.fire_event'](
        'event',
        'destroying instance',
        'salt/cloud/{0}/destroying'.format(name),
        args={'name': name, 'instance_id': instance_id},
        sock_dir=__opts__['sock_dir'],
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

    # Default behavior is to rename EC2 VMs when destroyed
    # via salt-cloud, unless explicitly set to False.
    rename_on_destroy = config.get_cloud_config_value('rename_on_destroy',
                                                      get_configured_provider(),
                                                      __opts__,
                                                      search_global=False)
    if rename_on_destroy is not False:
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

    location = get_location()
    provider = get_provider()
    result = aws.query(params,
                       location=location,
                       provider=provider,
                       opts=__opts__,
                       sigver='4')

    log.info(result)
    ret.update(result[0])

    # If this instance is part of a spot instance request, we
    # need to cancel it as well
    if sir_id is not None:
        params = {'Action': 'CancelSpotInstanceRequests',
                  'SpotInstanceRequestId.1': sir_id}
        result = aws.query(params,
                           location=location,
                           provider=provider,
                           opts=__opts__,
                           sigver='4')
        ret['spotInstance'] = result[0]

    __utils__['cloud.fire_event'](
        'event',
        'destroyed instance',
        'salt/cloud/{0}/destroyed'.format(name),
        args={'name': name, 'instance_id': instance_id},
        sock_dir=__opts__['sock_dir'],
        transport=__opts__['transport']
    )

    __utils__['cloud.cachedir_index_del'](name)

    if __opts__.get('update_cachedir', False) is True:
        __utils__['cloud.delete_minion_cachedir'](name, __active_provider_name__.split(':')[0], __opts__)

    return ret


def reboot(name, call=None):
    '''
    Reboot a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot mymachine
    '''
    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'RebootInstances',
              'InstanceId.1': instance_id}

    result = aws.query(params,
                       setname='tagSet',
                       location=get_location(),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')

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
    result = aws.query(params,
                       setname='tagSet',
                       location=get_location(),
                       provider=get_provider(),
                       opts=__opts__,
                       sigver='4')
    log.info(result)

    return result


def show_instance(name=None, instance_id=None, call=None, kwargs=None):
    '''
    Show the details from EC2 concerning an AMI.

    Can be called as an action (which requires a name):

    .. code-block:: bash

        salt-cloud -a show_instance myinstance

    ...or as a function (which requires either a name or instance_id):

    .. code-block:: bash

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
    __utils__['cloud.cache_node'](node, __active_provider_name__, __opts__)
    return node


def _get_node(name=None, instance_id=None, location=None):
    if location is None:
        location = get_location()

    params = {'Action': 'DescribeInstances'}

    if str(name).startswith('i-') and (len(name) == 10 or len(name) == 19):
        instance_id = name

    if instance_id:
        params['InstanceId.1'] = instance_id
    else:
        params['Filter.1.Name'] = 'tag:Name'
        params['Filter.1.Value.1'] = name

    log.trace(params)

    provider = get_provider()

    attempts = 10
    while attempts >= 0:
        try:
            instances = aws.query(params,
                                  location=location,
                                  provider=provider,
                                  opts=__opts__,
                                  sigver='4')
            return _extract_instance_info(instances).values()[0]
        except IndexError:
            attempts -= 1
            log.debug(
                'Failed to get the data for node \'{0}\'. Remaining '
                'attempts: {1}'.format(
                    instance_id or name, attempts
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
            get_location(vm_) for vm_ in six.itervalues(__opts__['profiles'])
            if _vm_provider_driver(vm_)
        )

        # If there aren't any profiles defined for EC2, check
        # the provider config file, or use the default location.
        if not locations:
            locations = [get_location()]

        for loc in locations:
            ret.update(_list_nodes_full(loc))
        return ret

    return _list_nodes_full(location)


def _vm_provider_driver(vm_):
    alias, driver = vm_['driver'].split(':')
    if alias not in __opts__['providers']:
        return None

    if driver not in __opts__['providers'][alias]:
        return None

    return driver == 'ec2'


def _extract_name_tag(item):
    if 'tagSet' in item and item['tagSet'] is not None:
        tagset = item['tagSet']
        if isinstance(tagset['item'], list):
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
                ret[name]['name'] = name
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
            ret[name]['name'] = name
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
    provider = __active_provider_name__ or 'ec2'
    if ':' in provider:
        comps = provider.split(':')
        provider = comps[0]

    params = {'Action': 'DescribeInstances'}
    instances = aws.query(params,
                          location=location,
                          provider=provider,
                          opts=__opts__,
                          sigver='4')
    if 'error' in instances:
        raise SaltCloudSystemExit(
            'An error occurred while listing nodes: {0}'.format(
                instances['error']['Errors']['Error']['Message']
            )
        )

    ret = _extract_instance_info(instances)

    __utils__['cloud.cache_node_list'](ret, provider, __opts__)
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
    instances = aws.query(params,
                          location=get_location(),
                          provider=get_provider(),
                          opts=__opts__,
                          sigver='4')
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
                id = item['instanceId']
        else:
            item = instance['instancesSet']['item']
            state = item['instanceState']['name']
            name = _extract_name_tag(item)
            id = item['instanceId']
        ret[name] = {'state': state, 'id': id}
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
            'name': nodes[node]['name'],
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
    Show the details from EC2 concerning an instance's termination protection state
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_term_protect action must be called with -a or --action.'
        )

    if not instance_id:
        instance_id = _get_node(name)['instanceId']
    params = {'Action': 'DescribeInstanceAttribute',
              'InstanceId': instance_id,
              'Attribute': 'disableApiTermination'}
    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       return_root=True,
                       opts=__opts__,
                       sigver='4')

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


def show_detailed_monitoring(name=None, instance_id=None, call=None, quiet=False):
    '''
    Show the details from EC2 regarding cloudwatch detailed monitoring.
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The show_detailed_monitoring action must be called with -a or --action.'
        )
    location = get_location()
    if str(name).startswith('i-') and (len(name) == 10 or len(name) == 19):
        instance_id = name

    if not name and not instance_id:
        raise SaltCloudSystemExit(
            'The show_detailed_monitoring action must be provided with a name or instance\
 ID'
        )
    matched = _get_node(name=name, instance_id=instance_id, location=location)
    log.log(
        logging.DEBUG if quiet is True else logging.INFO,
        'Detailed Monitoring is {0} for {1}'.format(matched['monitoring'], name)
    )
    return matched['monitoring']


def _toggle_term_protect(name, value):
    '''
    Enable or Disable termination protection on a node

    '''
    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'ModifyInstanceAttribute',
              'InstanceId': instance_id,
              'DisableApiTermination.Value': value}

    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       return_root=True,
                       opts=__opts__,
                       sigver='4')

    return show_term_protect(name=name, instance_id=instance_id, call='action')


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


def disable_detailed_monitoring(name, call=None):
    '''
    Enable/disable detailed monitoring on a node

    CLI Example:

    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The enable_term_protect action must be called with '
            '-a or --action.'
        )

    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'UnmonitorInstances',
              'InstanceId.1': instance_id}

    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       return_root=True,
                       opts=__opts__,
                       sigver='4')

    return show_detailed_monitoring(name=name, instance_id=instance_id, call='action')

def enable_detailed_monitoring(name, call=None):
    '''
    Enable/disable detailed monitoring on a node

    CLI Example:

    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The enable_term_protect action must be called with '
            '-a or --action.'
        )

    instance_id = _get_node(name)['instanceId']
    params = {'Action': 'MonitorInstances',
              'InstanceId.1': instance_id}

    result = aws.query(params,
                       location=get_location(),
                       provider=get_provider(),
                       return_root=True,
                       opts=__opts__,
                       sigver='4')

    return show_detailed_monitoring(name=name, instance_id=instance_id, call='action')



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
        instance_id = _get_node(name)['instanceId']

    params = {'Action': 'DescribeInstances',
              'InstanceId.1': instance_id}

    data = aws.query(params,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')

    blockmap = data[0]['instancesSet']['item']['blockDeviceMapping']

    if not isinstance(blockmap['item'], list):
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
        instance_id = _get_node(name)['instanceId']

    if requesturl:
        data = aws.query(requesturl=requesturl,
                         location=get_location(),
                         provider=get_provider(),
                         opts=__opts__,
                         sigver='4')
    else:
        params = {'Action': 'DescribeInstances',
                  'InstanceId.1': instance_id}
        data, requesturl = aws.query(params,                    # pylint: disable=unbalanced-tuple-unpacking
                                     return_url=True,
                                     location=get_location(),
                                     provider=get_provider(),
                                     opts=__opts__,
                                     sigver='4')

    blockmap = data[0]['instancesSet']['item']['blockDeviceMapping']

    params = {'Action': 'ModifyInstanceAttribute',
              'InstanceId': instance_id}

    if not isinstance(blockmap['item'], list):
        blockmap['item'] = [blockmap['item']]

    for idx, item in enumerate(blockmap['item']):
        device_name = item['deviceName']

        if device is not None and device != device_name:
            continue
        if volume_id is not None and volume_id != item['ebs']['volumeId']:
            continue

        params['BlockDeviceMapping.{0}.DeviceName'.format(idx)] = device_name
        params['BlockDeviceMapping.{0}.Ebs.DeleteOnTermination'.format(idx)] = value

    aws.query(params,
              return_root=True,
              location=get_location(),
              provider=get_provider(),
              opts=__opts__,
              sigver='4')

    kwargs = {'instance_id': instance_id,
              'device': device,
              'volume_id': volume_id}
    return show_delvol_on_destroy(name, kwargs, call='action')


def register_image(kwargs=None, call=None):
    '''
    Create an ami from a snapshot

    CLI Example:

    .. code-block:: bash

        salt-cloud -f register_image my-ec2-config ami_name=my_ami description="my description" root_device_name=/dev/xvda snapshot_id=snap-xxxxxxxx
    '''

    if call != 'function':
        log.error(
            'The create_volume function must be called with -f or --function.'
        )
        return False

    if 'ami_name' not in kwargs:
        log.error('ami_name must be specified to register an image.')
        return False

    block_device_mapping = kwargs.get('block_device_mapping', None)
    if not block_device_mapping:
        if 'snapshot_id' not in kwargs:
            log.error('snapshot_id or block_device_mapping must be specified to register an image.')
            return False
        if 'root_device_name' not in kwargs:
            log.error('root_device_name or block_device_mapping must be specified to register an image.')
            return False
        block_device_mapping = [{
            'DeviceName': kwargs['root_device_name'],
            'Ebs': {
                'VolumeType': kwargs.get('volume_type', 'gp2'),
                'SnapshotId': kwargs['snapshot_id'],
             }
        }]

    if not isinstance(block_device_mapping, list):
        block_device_mapping = [block_device_mapping]

    params = {'Action': 'RegisterImage',
              'Name': kwargs['ami_name']}

    params.update(_param_from_config('BlockDeviceMapping', block_device_mapping))

    if 'root_device_name' in kwargs:
        params['RootDeviceName'] = kwargs['root_device_name']

    if 'description' in kwargs:
        params['Description'] = kwargs['description']

    if 'virtualization_type' in kwargs:
        params['VirtualizationType'] = kwargs['virtualization_type']

    if 'architecture' in kwargs:
        params['Architecture'] = kwargs['architecture']

    log.debug(params)

    data = aws.query(params,
                     return_url=True,
                     return_root=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')

    r_data = {}
    for d in data[0]:
        for k, v in d.items():
            r_data[k] = v

    return r_data


def volume_create(**kwargs):
    '''
    Wrapper around create_volume.
    Here just to ensure the compatibility with the cloud module.
    '''
    return create_volume(kwargs, 'function')


def create_volume(kwargs=None, call=None, wait_to_finish=False):
    '''
    Create a volume

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f create_volume my-ec2-config zone=us-east-1b
        salt-cloud -f create_volume my-ec2-config zone=us-east-1b tags='{"tag1": "val1", "tag2", "val2"}'
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

    # You can't set `encrypted` if you pass a snapshot
    if 'encrypted' in kwargs and 'snapshot' not in kwargs:
        params['Encrypted'] = kwargs['encrypted']

    log.debug(params)

    data = aws.query(params,
                     return_url=True,
                     return_root=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')

    r_data = {}
    for d in data[0]:
        for k, v in six.iteritems(d):
            r_data[k] = v
    volume_id = r_data['volumeId']

    # Allow tags to be set upon creation
    if 'tags' in kwargs:
        if isinstance(kwargs['tags'], six.string_types):
            tags = yaml.safe_load(kwargs['tags'])
        else:
            tags = kwargs['tags']

        if isinstance(tags, dict):
            new_tags = set_tags(tags=tags,
                                resource_id=volume_id,
                                call='action',
                                location=get_location())
            r_data['tags'] = new_tags

    # Waits till volume is available
    if wait_to_finish:
        salt.utils.cloud.run_func_until_ret_arg(fun=describe_volumes,
                                                kwargs={'volume_id': volume_id},
                                                fun_call=call,
                                                argument_being_watched='status',
                                                required_argument_response='available')

    return r_data


def __attach_vol_to_instance(params, kws, instance_id):
    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
    if data[0]:
        log.warning(
            ('Error attaching volume {0} '
            'to instance {1}. Retrying!').format(kws['volume_id'],
                                                 instance_id))
        return False

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
        instance_id = _get_node(name)['instanceId']

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

    vm_ = get_configured_provider()

    data = salt.utils.cloud.wait_for_ip(
        __attach_vol_to_instance,
        update_args=(params, kwargs, instance_id),
        timeout=config.get_cloud_config_value(
            'wait_for_ip_timeout', vm_, __opts__, default=10 * 60),
        interval=config.get_cloud_config_value(
            'wait_for_ip_interval', vm_, __opts__, default=10),
        interval_multiplier=config.get_cloud_config_value(
            'wait_for_ip_interval_multiplier', vm_, __opts__, default=1),
    )

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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
    return data


def volume_list(**kwargs):
    '''
    Wrapper around describe_volumes.
    Here just to ensure the compatibility with the cloud module.
    '''
    return describe_volumes(kwargs, 'function')


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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
    return data


def import_keypair(kwargs=None, call=None):
    '''
    Import an SSH public key.

    .. versionadded:: 2015.8.3
    '''
    if call != 'function':
        log.error(
            'The import_keypair function must be called with -f or --function.'
        )
        return False

    if not kwargs:
        kwargs = {}

    if 'keyname' not in kwargs:
        log.error('A keyname is required.')
        return False

    if 'file' not in kwargs:
        log.error('A public key file is required.')
        return False

    params = {'Action': 'ImportKeyPair',
              'KeyName': kwargs['keyname']}

    public_key_file = kwargs['file']

    if os.path.exists(public_key_file):
        with salt.utils.fopen(public_key_file, 'r') as fh_:
            public_key = fh_.read()

    if public_key is not None:
        params['PublicKeyMaterial'] = base64.b64encode(public_key)

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
    return data


def create_snapshot(kwargs=None, call=None, wait_to_finish=False):
    '''
    Create a snapshot.

    volume_id
        The ID of the Volume from which to create a snapshot.

    description
        The optional description of the snapshot.

    CLI Exampe:

    .. code-block:: bash

        salt-cloud -f create_snapshot my-ec2-config volume_id=vol-351d8826
        salt-cloud -f create_snapshot my-ec2-config volume_id=vol-351d8826 \\
            description="My Snapshot Description"
    '''
    if call != 'function':
        raise SaltCloudSystemExit(
            'The create_snapshot function must be called with -f '
            'or --function.'
        )

    if kwargs is None:
        kwargs = {}

    volume_id = kwargs.get('volume_id', None)
    description = kwargs.get('description', '')

    if volume_id is None:
        raise SaltCloudSystemExit(
            'A volume_id must be specified to create a snapshot.'
        )

    params = {'Action': 'CreateSnapshot',
              'VolumeId': volume_id,
              'Description': description}

    log.debug(params)

    data = aws.query(params,
                     return_url=True,
                     return_root=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')[0]

    r_data = {}
    for d in data:
        for k, v in six.iteritems(d):
            r_data[k] = v

    if 'snapshotId' in r_data:
        snapshot_id = r_data['snapshotId']

        # Waits till volume is available
        if wait_to_finish:
            salt.utils.cloud.run_func_until_ret_arg(fun=describe_snapshots,
                                                    kwargs={'snapshot_id': snapshot_id},
                                                    fun_call=call,
                                                    argument_being_watched='status',
                                                    required_argument_response='completed')

    return r_data


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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
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

    data = aws.query(params,
                     return_url=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')
    return data


def get_console_output(
        name=None,
        location=None,
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

    if location is None:
        location = get_location()

    if not instance_id:
        instance_id = _get_node(name)['instanceId']

    if kwargs is None:
        kwargs = {}

    if instance_id is None:
        if 'instance_id' in kwargs:
            instance_id = kwargs['instance_id']
            del kwargs['instance_id']

    params = {'Action': 'GetConsoleOutput',
              'InstanceId': instance_id}

    ret = {}
    data = aws.query(params,
                     return_root=True,
                     location=location,
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')

    for item in data:
        if next(six.iterkeys(item)) == 'output':
            ret['output_decoded'] = binascii.a2b_base64(next(six.itervalues(item)))
        else:
            ret[next(six.iterkeys(item))] = next(six.itervalues(item))

    return ret


def get_password_data(
        name=None,
        kwargs=None,
        instance_id=None,
        call=None,
    ):
    '''
    Return password data for a Windows instance.

    By default only the encrypted password data will be returned. However, if a
    key_file is passed in, then a decrypted password will also be returned.

    Note that the key_file references the private key that was used to generate
    the keypair associated with this instance. This private key will _not_ be
    transmitted to Amazon; it is only used internally inside of Salt Cloud to
    decrypt data _after_ it has been received from Amazon.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a get_password_data mymachine
        salt-cloud -a get_password_data mymachine key_file=/root/ec2key.pem

    Note: PKCS1_v1_5 was added in PyCrypto 2.5
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The get_password_data action must be called with '
            '-a or --action.'
        )

    if not instance_id:
        instance_id = _get_node(name)['instanceId']

    if kwargs is None:
        kwargs = {}

    if instance_id is None:
        if 'instance_id' in kwargs:
            instance_id = kwargs['instance_id']
            del kwargs['instance_id']

    params = {'Action': 'GetPasswordData',
              'InstanceId': instance_id}

    ret = {}
    data = aws.query(params,
                     return_root=True,
                     location=get_location(),
                     provider=get_provider(),
                     opts=__opts__,
                     sigver='4')

    for item in data:
        ret[next(six.iterkeys(item))] = next(six.itervalues(item))

    if not HAS_PYCRYPTO:
        return ret

    if 'key' not in kwargs:
        if 'key_file' in kwargs:
            with salt.utils.fopen(kwargs['key_file'], 'r') as kf_:
                kwargs['key'] = kf_.read()

    if 'key' in kwargs:
        pwdata = ret.get('passwordData', None)
        if pwdata is not None:
            rsa_key = kwargs['key']
            pwdata = base64.b64decode(pwdata)
            dsize = Crypto.Hash.SHA.digest_size
            sentinel = Crypto.Random.new().read(15 + dsize)
            key_obj = Crypto.PublicKey.RSA.importKey(rsa_key)
            key_obj = PKCS1_v1_5.new(key_obj)
            ret['password'] = key_obj.decrypt(pwdata, sentinel)

    return ret


def update_pricing(kwargs=None, call=None):
    '''
    Download most recent pricing information from AWS and convert to a local
    JSON file.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f update_pricing my-ec2-config
        salt-cloud -f update_pricing my-ec2-config type=linux

    .. versionadded:: 2015.8.0
    '''
    sources = {
        'linux': 'https://a0.awsstatic.com/pricing/1/ec2/linux-od.min.js',
        'rhel': 'https://a0.awsstatic.com/pricing/1/ec2/rhel-od.min.js',
        'sles': 'https://a0.awsstatic.com/pricing/1/ec2/sles-od.min.js',
        'mswin': 'https://a0.awsstatic.com/pricing/1/ec2/mswin-od.min.js',
        'mswinsql': 'https://a0.awsstatic.com/pricing/1/ec2/mswinSQL-od.min.js',
        'mswinsqlweb': 'https://a0.awsstatic.com/pricing/1/ec2/mswinSQLWeb-od.min.js',
    }

    if kwargs is None:
        kwargs = {}

    if 'type' not in kwargs:
        for source in sources:
            _parse_pricing(sources[source], source)
    else:
        _parse_pricing(sources[kwargs['type']], kwargs['type'])


def _parse_pricing(url, name):
    '''
    Download and parse an individual pricing file from AWS

    .. versionadded:: 2015.8.0
    '''
    price_js = http.query(url, text=True)

    items = []
    current_item = ''

    price_js = re.sub(JS_COMMENT_RE, '', price_js['text'])
    price_js = price_js.strip().rstrip(');').lstrip('callback(')
    for keyword in (
        'vers',
        'config',
        'rate',
        'valueColumns',
        'currencies',
        'instanceTypes',
        'type',
        'ECU',
        'storageGB',
        'name',
        'vCPU',
        'memoryGiB',
        'storageGiB',
        'USD',
    ):
        price_js = price_js.replace(keyword, '"{0}"'.format(keyword))

    for keyword in ('region', 'price', 'size'):
        price_js = price_js.replace(keyword, '"{0}"'.format(keyword))
        price_js = price_js.replace('"{0}"s'.format(keyword), '"{0}s"'.format(keyword))

    price_js = price_js.replace('""', '"')

    # Turn the data into something that's easier/faster to process
    regions = {}
    price_json = json.loads(price_js)
    for region in price_json['config']['regions']:
        sizes = {}
        for itype in region['instanceTypes']:
            for size in itype['sizes']:
                sizes[size['size']] = size
        regions[region['region']] = sizes

    outfile = os.path.join(
        __opts__['cachedir'], 'ec2-pricing-{0}.p'.format(name)
    )
    with salt.utils.fopen(outfile, 'w') as fho:
        msgpack.dump(regions, fho)

    return True


def show_pricing(kwargs=None, call=None):
    '''
    Show pricing for a particular profile. This is only an estimate, based on
    unofficial pricing sources.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f show_pricing my-ec2-config profile=my-profile

    If pricing sources have not been cached, they will be downloaded. Once they
    have been cached, they will not be updated automatically. To manually update
    all prices, use the following command:

    .. code-block:: bash

        salt-cloud -f update_pricing <provider>

    .. versionadded:: 2015.8.0
    '''
    profile = __opts__['profiles'].get(kwargs['profile'], {})
    if not profile:
        return {'Error': 'The requested profile was not found'}

    # Make sure the profile belongs to ec2
    provider = profile.get('provider', '0:0')
    comps = provider.split(':')
    if len(comps) < 2 or comps[1] != 'ec2':
        return {'Error': 'The requested profile does not belong to EC2'}

    image_id = profile.get('image', None)
    image_dict = show_image({'image': image_id}, 'function')
    image_info = image_dict[0]

    # Find out what platform it is
    if image_info.get('imageOwnerAlias', '') == 'amazon':
        if image_info.get('platform', '') == 'windows':
            image_description = image_info.get('description', '')
            if 'sql' in image_description.lower():
                if 'web' in image_description.lower():
                    name = 'mswinsqlweb'
                else:
                    name = 'mswinsql'
            else:
                name = 'mswin'
        elif image_info.get('imageLocation', '').strip().startswith('amazon/suse'):
            name = 'sles'
        else:
            name = 'linux'
    elif image_info.get('imageOwnerId', '') == '309956199498':
        name = 'rhel'
    else:
        name = 'linux'

    pricefile = os.path.join(
        __opts__['cachedir'], 'ec2-pricing-{0}.p'.format(name)
    )

    if not os.path.isfile(pricefile):
        update_pricing({'type': name}, 'function')

    with salt.utils.fopen(pricefile, 'r') as fhi:
        ec2_price = msgpack.load(fhi)

    region = get_location(profile)
    size = profile.get('size', None)
    if size is None:
        return {'Error': 'The requested profile does not contain a size'}

    try:
        raw = ec2_price[region][size]
    except KeyError:
        return {'Error': 'The size ({0}) in the requested profile does not have '
                'a price associated with it for the {1} region'.format(size, region)}

    ret = {}
    if kwargs.get('raw', False):
        ret['_raw'] = raw

    ret['per_hour'] = 0
    for col in raw.get('valueColumns', []):
        ret['per_hour'] += decimal.Decimal(col['prices'].get('USD', 0))

    ret['per_hour'] = decimal.Decimal(ret['per_hour'])
    ret['per_day'] = ret['per_hour'] * 24
    ret['per_week'] = ret['per_day'] * 7
    ret['per_month'] = ret['per_day'] * 30
    ret['per_year'] = ret['per_week'] * 52

    return {profile['profile']: ret}


def ssm_create_association(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Associates the specified SSM document with the specified instance

    http://docs.aws.amazon.com/ssm/latest/APIReference/API_CreateAssociation.html

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a ssm_create_association ec2-instance-name ssm_document=ssm-document-name
    '''

    if call != 'action':
        raise SaltCloudSystemExit(
            'The ssm_create_association action must be called with '
            '-a or --action.'
        )

    if not kwargs:
        kwargs = {}

    if 'instance_id' in kwargs:
        instance_id = kwargs['instance_id']

    if name and not instance_id:
        instance_id = _get_node(name)['instanceId']

    if not name and not instance_id:
        log.error('Either a name or an instance_id is required.')
        return False

    if 'ssm_document' not in kwargs:
        log.error('A ssm_document is required.')
        return False

    params = {'Action': 'CreateAssociation',
              'InstanceId': instance_id,
              'Name': kwargs['ssm_document']}

    result = aws.query(params,
                       return_root=True,
                       location=get_location(),
                       provider=get_provider(),
                       product='ssm',
                       opts=__opts__,
                       sigver='4')
    log.info(result)
    return result


def ssm_describe_association(name=None, kwargs=None, instance_id=None, call=None):
    '''
    Describes the associations for the specified SSM document or instance.

    http://docs.aws.amazon.com/ssm/latest/APIReference/API_DescribeAssociation.html

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a ssm_describe_association ec2-instance-name ssm_document=ssm-document-name
    '''
    if call != 'action':
        raise SaltCloudSystemExit(
            'The ssm_describe_association action must be called with '
            '-a or --action.'
        )

    if not kwargs:
        kwargs = {}

    if 'instance_id' in kwargs:
        instance_id = kwargs['instance_id']

    if name and not instance_id:
        instance_id = _get_node(name)['instanceId']

    if not name and not instance_id:
        log.error('Either a name or an instance_id is required.')
        return False

    if 'ssm_document' not in kwargs:
        log.error('A ssm_document is required.')
        return False

    params = {'Action': 'DescribeAssociation',
              'InstanceId': instance_id,
              'Name': kwargs['ssm_document']}

    result = aws.query(params,
                       return_root=True,
                       location=get_location(),
                       provider=get_provider(),
                       product='ssm',
                       opts=__opts__,
                       sigver='4')
    log.info(result)
    return result
