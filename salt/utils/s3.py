# -*- coding: utf-8 -*-
'''
Connection library for Amazon S3

:depends: requests
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import 3rd-party libs
try:
    import requests
    HAS_REQUESTS = True  # pylint: disable=W0612
except ImportError:
    HAS_REQUESTS = False  # pylint: disable=W0612

# Import Salt libs
import salt.utils
import salt.utils.aws
import salt.utils.xmlutil as xml
from salt._compat import ElementTree as ET

log = logging.getLogger(__name__)


def query(key, keyid, method='GET', params=None, headers=None,
          requesturl=None, return_url=False, bucket=None, service_url=None,
          path='', return_bin=False, action=None, local_file=None,
          verify_ssl=True, location=None, full_headers=False):
    '''
    Perform a query against an S3-like API. This function requires that a
    secret key and the id for that key are passed in. For instance:

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs

    If keyid or key is not specified, an attempt to fetch them from EC2 IAM
    metadata service will be made.

    A service_url may also be specified in the configuration:

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

    A region may be specified:

        s3.location: eu-central-1

    If region is not specified, an attempt to fetch the region from EC2 IAM
    metadata service will be made. Failing that, default is us-east-1
    '''
    if not HAS_REQUESTS:
        log.error('There was an error: requests is required for s3 access')

    if not headers:
        headers = {}

    if not params:
        params = {}

    if not service_url:
        service_url = 's3.amazonaws.com'

    if bucket:
        endpoint = '{0}.{1}'.format(bucket, service_url)
    else:
        endpoint = service_url

    # Try grabbing the credentials from the EC2 instance IAM metadata if available
    if not key or not keyid:
        key = salt.utils.aws.IROLE_CODE
        keyid = salt.utils.aws.IROLE_CODE

    data = ''
    if method == 'PUT':
        if local_file:
            with salt.utils.fopen(local_file, 'r') as ifile:
                data = ifile.read()

    if not requesturl:
        requesturl = 'https://{0}/{1}'.format(endpoint, path)
        headers, requesturl = salt.utils.aws.sig4(
            method,
            endpoint,
            params,
            data=data,
            uri='/{0}'.format(path),
            prov_dict={'id': keyid, 'key': key},
            location=location,
            product='s3',
            requesturl=requesturl,
        )

    log.debug('S3 Request: {0}'.format(requesturl))
    log.debug('S3 Headers::')
    log.debug('    Authorization: {0}'.format(headers['Authorization']))

    if not data:
        data = None

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
        if full_headers:
            ret['headers'] = dict(result.headers)
        else:
            for header in result.headers:
                ret['headers'].append(header.strip())

    return ret
