'''
Connection library for Amazon S3

:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

        s3.keyid: GKTADJGHEIQSXMKKRBJ08H
        s3.key: askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs
        s3.region: us-east-1
        s3.bucket: salttest
        s3.service_url: s3.amazonaws.com
'''

# Import python libs
import xml.etree.ElementTree as ET
import salt.utils.xmlutil as xml
import hmac
import hashlib
import binascii
import datetime
import urllib
import urllib2
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Should work on any modern Python installation

    TODO: Check configuration for S3 params before continuing
    '''
    return 's3'


def get(bucket, path=None, return_bin=False):
    '''
    List the contents of a bucket, or return an object from a bucket. Set
    return_bin to True in order to retreive an object wholesale. Otherwise,
    Salt will attempt to parse an XML response.

    CLI Examples::

        salt myminion s3.get mybucket
        salt myminion s3.get mybucket myfile.png return_bin=True
    '''
    return _query(bucket=bucket, path=path, return_bin=return_bin)


def _query(params=None, headers=None, requesturl=None, return_url=False,
           bucket=None, key=None, keyid=None, region=None, service_url=None,
           path=None, return_bin=False):
    '''
    Perform a query against an S3-like API
    '''
    if not headers:
        headers = {}

    if not params:
        params = {}

    if path is None:
        path = ''

    bucket = __salt__['config.option']('s3.bucket')
    key = __salt__['config.option']('s3.key')
    keyid = __salt__['config.option']('s3.keyid')
    region = __salt__['config.option']('s3.region')
    service_url = __salt__['config.option']('s3.service_url')
    endpoint = '{0}.{1}'.format(bucket, service_url)

    if not requesturl:
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        x_amz_date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        method = 'GET'
        content_type = 'text/plain'
        content_md5 = ''
        date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        can_resource = '/{0}/{1}'.format(bucket, path)
        log.debug('CanonicalizedResource: {0}'.format(can_resource))

        headers['Host'] = endpoint
        headers['Content-type'] = content_type
        headers['Date'] = x_amz_date

        string_to_sign = '{0}\n'.format(method)

        new_headers = []
        for header in sorted(headers.keys()):
            if header.lower().startswith('x-amz'):
                log.debug(header.lower())
                new_headers.append('{0}:{1}'.format(header.lower(),
                                                    headers[header]))
                string_to_sign += '{0}\n'.format(headers[header])
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
        requesturl = 'https://{0}/'.format(endpoint)
        if path:
            requesturl += path
        if querystring:
            requesturl += '?{1}'.format(querystring)

    req = urllib2.Request(url=requesturl)

    log.debug('S3 Request: {0}'.format(requesturl))
    log.debug('S3 Headers::')
    for header in sorted(headers.keys()):
        if header == 'Authorization':
            continue
        req.add_header(header, headers[header])
        log.debug('    {0}: {1}'.format(header, headers[header]))
    log.debug('    Authorization: {0}'.format(headers['Authorization']))
    req.add_header('Authorization', headers['Authorization'])

    try:
        result = urllib2.urlopen(req)
        response = result.read()
    except Exception as exc:
        log.error('There was an error::')
        log.error('    Code: {0}: {1}'.format(exc.code, exc.msg))
        log.error('    Content: \n{0}'.format(exc.read()))
        return False

    log.debug('S3 Response Status Code: {0}'.format(result.getcode()))
    result.close()

    # This can be used to return a binary object wholesale
    if return_bin:
        return response

    items = ET.fromstring(response)

    ret = []
    for item in items:
        ret.append(xml.to_dict(item))

    if return_url is True:
        return ret, requesturl

    return ret


