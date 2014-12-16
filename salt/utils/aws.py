# -*- coding: utf-8 -*-
'''
Connection library for AWS

.. versionadded:: Lithium

This is a base library used by a number of AWS services.

:depends: requests
'''
from __future__ import absolute_import

# Import Python libs
import sys
import time
import binascii
import datetime
import hashlib
import hmac
import logging

# Import Salt libs
import salt.utils.xmlutil as xml
from salt._compat import ElementTree as ET

# Import 3rd-party libs
import requests
# pylint: disable=import-error,redefined-builtin,no-name-in-module
from salt.ext.six.moves import map, range, zip
from salt.ext.six.moves.urllib.parse import urlencode, urlparse
# pylint: enable=import-error,redefined-builtin,no-name-in-module

LOG = logging.getLogger(__name__)
DEFAULT_LOCATION = 'us-east-1'
DEFAULT_AWS_API_VERSION = '2014-10-01'
AWS_RETRY_CODES = [
    'RequestLimitExceeded',
    'InsufficientInstanceCapacity',
    'InternalError',
    'Unavailable',
    'InsufficientAddressCapacity',
    'InsufficientReservedInstanceCapacity',
]


def sig2(method, endpoint, params, provider, aws_api_version):
    '''
    Sign a query against AWS services using Signature Version 2 Signing
    Process. This is documented at:

    http://docs.aws.amazon.com/general/latest/gr/signature-version-2.html
    '''
    timenow = datetime.datetime.utcnow()
    timestamp = timenow.strftime('%Y-%m-%dT%H:%M:%SZ')

    params_with_headers = params.copy()
    params_with_headers['AWSAccessKeyId'] = provider.get('id', '')
    params_with_headers['SignatureVersion'] = '2'
    params_with_headers['SignatureMethod'] = 'HmacSHA256'
    params_with_headers['Timestamp'] = '{0}'.format(timestamp)
    params_with_headers['Version'] = aws_api_version
    keys = sorted(params_with_headers.keys())
    values = list(list(map(params_with_headers.get, keys)))
    querystring = urlencode(list(zip(keys, values)))

    canonical = '{0}\n{1}\n/\n{2}'.format(
        method.encode('utf-8'),
        endpoint.encode('utf-8'),
        querystring.encode('utf-8'),
    )

    hashed = hmac.new(provider['key'], canonical, hashlib.sha256)
    sig = binascii.b2a_base64(hashed.digest())
    params_with_headers['Signature'] = sig.strip()
    return params_with_headers


def sig4(method, endpoint, params, prov_dict, aws_api_version, location,
         product='ec2', uri='/', requesturl=None):
    '''
    Sign a query against AWS services using Signature Version 4 Signing
    Process. This is documented at:

    http://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html
    http://docs.aws.amazon.com/general/latest/gr/sigv4-signed-request-examples.html
    http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html
    '''
    timenow = datetime.datetime.utcnow()
    timestamp = timenow.strftime('%Y-%m-%dT%H:%M:%SZ')

    params_with_headers = params.copy()
    params_with_headers['Version'] = aws_api_version
    keys = sorted(params_with_headers.keys())
    values = list(map(params_with_headers.get, keys))
    querystring = urlencode(list(zip(keys, values)))

    amzdate = timenow.strftime('%Y%m%dT%H%M%SZ')
    datestamp = timenow.strftime('%Y%m%d')
    payload_hash = hashlib.sha256('').hexdigest()

    canonical_headers = 'host:{0}\nx-amz-date:{1}\n'.format(
        endpoint,
        amzdate,
    )
    signed_headers = 'host;x-amz-date'

    request = '\n'.join((
        method, endpoint, querystring, canonical_headers,
        signed_headers, payload_hash
    ))

    algorithm = 'AWS4-HMAC-SHA256'

    # Create payload hash (hash of the request body content). For GET
    # requests, the payload is an empty string ('').
    payload_hash = hashlib.sha256('').hexdigest()

    # Combine elements to create create canonical request
    canonical_request = '\n'.join((
        method,
        uri,
        querystring,
        canonical_headers,
        signed_headers,
        payload_hash
    ))

    # Create the string to sign
    credential_scope = '/'.join((
        datestamp, location, product, 'aws4_request'
    ))
    string_to_sign = '\n'.join((
        algorithm,
        amzdate,
        credential_scope,
        hashlib.sha256(canonical_request).hexdigest()
    ))

    # Create the signing key using the function defined above.
    signing_key = _sig_key(
        prov_dict.get('key', ''),
        datestamp,
        location,
        product
    )

    # Sign the string_to_sign using the signing_key
    signature = hmac.new(
        signing_key,
        string_to_sign.encode('utf-8'),
        hashlib.sha256).hexdigest()

    # Add signing information to the request
    authorization_header = (
            '{0} Credential={1}/{2}, SignedHeaders={3}, Signature={4}'
        ).format(
            algorithm,
            prov_dict.get('id', ''),
            credential_scope,
            signed_headers,
            signature,
        )

    headers = {
        'x-amz-date': amzdate,
        'Authorization': authorization_header
    }

    requesturl = '{0}?{1}'.format(requesturl, querystring)
    return headers, requesturl


def _sign(key, msg):
    '''
    Key derivation functions. See:

    http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
    '''
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()


def _sig_key(key, date_stamp, regionName, serviceName):
    '''
    Get a signature key. See:

    http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
    '''
    kDate = _sign(('AWS4' + key).encode('utf-8'), date_stamp)
    kRegion = _sign(kDate, regionName)
    kService = _sign(kRegion, serviceName)
    kSigning = _sign(kService, 'aws4_request')
    return kSigning


def query(params=None, setname=None, requesturl=None, location=None,
          return_url=False, return_root=False, opts=None, provider=None,
          endpoint=None, product='ec2', sigver='2'):
    '''
    Perform a query against AWS services using Signature Version 2 Signing
    Process. This is documented at:

    http://docs.aws.amazon.com/general/latest/gr/signature-version-2.html

    Regions and endpoints are documented at:

    http://docs.aws.amazon.com/general/latest/gr/rande.html

    Default ``product`` is ``ec2``. Valid ``product`` names are:

    .. code-block: yaml

        - autoscaling (Auto Scaling)
        - cloudformation (CloudFormation)
        - ec2 (Elastic Compute Cloud)
        - elasticache (ElastiCache)
        - elasticbeanstalk (Elastic BeanStalk)
        - elasticloadbalancing (Elastic Load Balancing)
        - elasticmapreduce (Elastic MapReduce)
        - iam (Identity and Access Management)
        - importexport (Import/Export)
        - monitoring (CloudWatch)
        - rds (Relational Database Service)
        - simpledb (SimpleDB)
        - sns (Simple Notification Service)
        - sqs (Simple Queue Service)
    '''
    if params is None:
        params = {}

    if opts is None:
        opts = {}

    function = opts.get('function', (None, product))
    providers = opts.get('providers', {})

    if provider is None:
        prov_dict = providers.get(function[1], {}).get(product, {})
        if prov_dict:
            driver = list(list(prov_dict.keys()))[0]
            provider = providers.get(driver, product)
    else:
        prov_dict = providers.get(provider, {}).get(product, {})

    service_url = prov_dict.get('service_url', 'amazonaws.com')

    if not location:
        location = get_location(opts, provider)

    if endpoint is None:
        if not requesturl:
            endpoint = prov_dict.get(
                'endpoint',
                '{0}.{1}.{2}'.format(product, location, service_url)
            )

            requesturl = 'https://{0}/'.format(endpoint)
        else:
            endpoint = urlparse(requesturl).netloc
            if endpoint == '':
                endpoint_err = ('Could not find a valid endpoint in the '
                                'requesturl: {0}. Looking for something '
                                'like https://some.aws.endpoint/?args').format(
                                    requesturl
                                )
                LOG.error(endpoint_err)
                if return_url is True:
                    return {'error': endpoint_err}, requesturl
                return {'error': endpoint_err}

    LOG.debug('Using AWS endpoint: {0}'.format(endpoint))
    method = 'GET'

    aws_api_version = prov_dict.get(
        'aws_api_version', prov_dict.get(
            '{0}_api_version'.format(product),
            DEFAULT_AWS_API_VERSION
        )
    )

    if sigver == '4':
        headers, requesturl = sig4(
            method, endpoint, params, prov_dict, aws_api_version, location, product, requesturl=requesturl
        )
        params_with_headers = {}
    else:
        params_with_headers = sig2(
            method, endpoint, params, prov_dict, aws_api_version
        )
        headers = {}

    attempts = 5
    while attempts > 0:
        LOG.debug('AWS Request: {0}'.format(requesturl))
        LOG.trace('AWS Request Parameters: {0}'.format(params_with_headers))
        try:
            result = requests.get(requesturl, headers=headers, params=params_with_headers)
            LOG.debug(
                'AWS Response Status Code: {0}'.format(
                    result.status_code
                )
            )
            LOG.trace(
                'AWS Response Text: {0}'.format(
                    result.text
                )
            )
            result.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            root = ET.fromstring(exc.response.content)
            data = xml.to_dict(root)

            # check to see if we should retry the query
            err_code = data.get('Errors', {}).get('Error', {}).get('Code', '')
            if attempts > 0 and err_code and err_code in AWS_RETRY_CODES:
                attempts -= 1
                LOG.error(
                    'AWS Response Status Code and Error: [{0} {1}] {2}; '
                    'Attempts remaining: {3}'.format(
                        exc.response.status_code, exc, data, attempts
                    )
                )
                # Wait a bit before continuing to prevent throttling
                time.sleep(2)
                continue

            LOG.error(
                'AWS Response Status Code and Error: [{0} {1}] {2}'.format(
                    exc.response.status_code, exc, data
                )
            )
            if return_url is True:
                return {'error': data}, requesturl
            return {'error': data}
    else:
        LOG.error(
            'AWS Response Status Code and Error: [{0} {1}] {2}'.format(
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
        ret.append(xml.to_dict(item))

    if return_url is True:
        return ret, requesturl

    return ret


def get_location(opts, provider=None):
    '''
    Return the region to use, in this order:
        opts['location']
        provider['location']
        DEFAULT_LOCATION
    '''
    return opts.get(
        'location', provider.get(
            'location', DEFAULT_LOCATION
        )
    )
