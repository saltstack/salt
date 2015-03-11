# -*- coding: utf-8 -*-
'''
Connection library for Amazon S3

:depends: requests
'''

# Import Python libs
import binascii
import datetime
import hashlib
import hmac
import logging
import urllib
import requests

# Import Salt libs
import salt.utils
import salt.utils.xmlutil as xml
import salt.utils.iam as iam
from salt._compat import ElementTree as ET

log = logging.getLogger(__name__)


def query(key, keyid, method='GET', params=None, headers=None,
          requesturl=None, return_url=False, bucket=None, service_url=None,
          path=None, return_bin=False, action=None, local_file=None,
          verify_ssl=True):
    '''
    Perform a query against an S3-like API. This function requires that a
    secret key and the id for that key are passed in. For instance:

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    A service_url may also be specified in the configuration::

        s3.service_url: s3.amazonaws.com

    If a service_url is not specified, the default is s3.amazonaws.com. This
    may appear in various documentation as an "endpoint". A comprehensive list
    for Amazon S3 may be found at::

        http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region

    The service_url will form the basis for the final endpoint that is used to
    query the service.

    SSL verification may also be turned off in the configuration:

    s3.verify_ssl: False

    This is required if using S3 bucket names that contain a period, as
    these will not match Amazon's S3 wildcard certificates. Certificate
    verification is enabled by default.
    '''
    if not headers:
        headers = {}

    if not params:
        params = {}

    if path is None:
        path = ''

    if not service_url:
        service_url = 's3.amazonaws.com'

    if bucket:
        endpoint = '{0}.{1}'.format(bucket, service_url)
    else:
        endpoint = service_url

    # Try grabbing the credentials from the EC2 instance IAM metadata if available
    token = None
    if not key or not keyid:
        iam_creds = iam.get_iam_metadata()
        key = iam_creds['secret_key']
        keyid = iam_creds['access_key']
        token = iam_creds['security_token']

    if not requesturl:
        x_amz_date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        content_type = 'text/plain'
        if method == 'GET':
            if bucket:
                can_resource = '/{0}/{1}'.format(bucket, path)
            else:
                can_resource = '/'
        elif method == 'PUT' or method == 'HEAD' or method == 'DELETE':
            if path:
                can_resource = '/{0}/{1}'.format(bucket, path)
            else:
                can_resource = '/{0}/'.format(bucket)

        if action:
            can_resource += '?{0}'.format(action)

        log.debug('CanonicalizedResource: {0}'.format(can_resource))

        headers['Host'] = endpoint
        headers['Content-type'] = content_type
        headers['Date'] = x_amz_date
        if token:
            headers['x-amz-security-token'] = token

        string_to_sign = '{0}\n'.format(method)

        new_headers = []
        for header in sorted(headers):
            if header.lower().startswith('x-amz'):
                log.debug(header.lower())
                new_headers.append('{0}:{1}'.format(header.lower(),
                                                    headers[header]))
        can_headers = '\n'.join(new_headers)
        log.debug('CanonicalizedAmzHeaders: {0}'.format(can_headers))

        string_to_sign += '\n{0}'.format(content_type)
        string_to_sign += '\n{0}'.format(x_amz_date)
        if can_headers:
            string_to_sign += '\n{0}'.format(can_headers)
        string_to_sign += '\n{0}'.format(can_resource)
        log.debug('String To Sign:: \n{0}'.format(string_to_sign))

        hashed = hmac.new(key, string_to_sign, hashlib.sha1)
        sig = binascii.b2a_base64(hashed.digest())
        headers['Authorization'] = 'AWS {0}:{1}'.format(keyid, sig.strip())

        querystring = urllib.urlencode(params)
        if action:
            if querystring:
                querystring = '{0}&{1}'.format(action, querystring)
            else:
                querystring = action
        requesturl = 'https://{0}/'.format(endpoint)
        if path:
            requesturl += path
        if querystring:
            requesturl += '?{0}'.format(querystring)

    data = None
    if method == 'PUT':
        if local_file:
            with salt.utils.fopen(local_file, 'r') as ifile:
                data = ifile.read()

    log.debug('S3 Request: {0}'.format(requesturl))
    log.debug('S3 Headers::')
    log.debug('    Authorization: {0}'.format(headers['Authorization']))

    try:
        result = requests.request(method, requesturl, headers=headers,
                                  data=data,
                                  verify=verify_ssl)
        response = result.content
    except requests.exceptions.HTTPError as exc:
        log.error('There was an error::')
        if hasattr(exc, 'code') and hasattr(exc, 'msg'):
            log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
        log.error('    Content: \n{0}'.format(exc.read()))
        return False

    log.debug('S3 Response Status Code: {0}'.format(result.status_code))

    if method == 'PUT':
        if result.status_code == 200:
            if local_file:
                log.debug('Uploaded from {0} to {1}'.format(local_file, path))
            else:
                log.debug('Created bucket {0}'.format(bucket))
        else:
            if local_file:
                log.debug('Failed to upload from {0} to {1}: {2}'.format(
                                                    local_file,
                                                    path,
                                                    result.status_code,
                                                    ))
            else:
                log.debug('Failed to create bucket {0}'.format(bucket))
        return

    if method == 'DELETE':
        if str(result.status_code).startswith('2'):
            if path:
                log.debug('Deleted {0} from bucket {1}'.format(path, bucket))
            else:
                log.debug('Deleted bucket {0}'.format(bucket))
        else:
            if path:
                log.debug('Failed to delete {0} from bucket {1}: {2}'.format(
                                                    path,
                                                    bucket,
                                                    result.status_code,
                                                    ))
            else:
                log.debug('Failed to delete bucket {0}'.format(bucket))
        return

    # This can be used to save a binary object to disk
    if local_file and method == 'GET':
        log.debug('Saving to local file: {0}'.format(local_file))
        with salt.utils.fopen(local_file, 'w') as out:
            out.write(response)
        return 'Saved to local file: {0}'.format(local_file)

    # This can be used to return a binary object wholesale
    if return_bin:
        return response

    if response:
        items = ET.fromstring(response)

        ret = []
        for item in items:
            ret.append(xml.to_dict(item))

        if return_url is True:
            return ret, requesturl
    else:
        if result.status_code != requests.codes.ok:
            return
        ret = {'headers': []}
        for header in result.headers:
            ret['headers'].append(header.strip())

    return ret
