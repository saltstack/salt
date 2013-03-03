'''
Connection module for Amazon S3

:configuration: This module is not usable until the following are specified
    either in a pillar or in the minion's config file::

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

    This module should be usable to query other S3-like services, such as
    OpenStack Swift.
'''

# Import Python libs
import xml.etree.ElementTree as ET
import hmac
import hashlib
import binascii
import datetime
import urllib
import urllib2
import logging

# Import Salt libs
import salt.utils.xmlutil as xml

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Should work on any modern Python installation

    TODO: Check configuration for S3 params before continuing
    '''
    return 's3'


def get(bucket=None, path=None, return_bin=False, action=None,
        local_file=None):
    '''
    List the contents of a bucket, or return an object from a bucket. Set
    return_bin to True in order to retreive an object wholesale. Otherwise,
    Salt will attempt to parse an XML response.

    To list buckets::

        salt myminion s3.get

    To list the contents of a bucket::

        salt myminion s3.get mybucket

    To return the binary contents of an object::

        salt myminion s3.get mybucket myfile.png return_bin=True

    To save the binary contents of an object to a local file::

        salt myminion s3.get mybucket myfile.png local_file=/tmp/myfile.png

    It is also possible to perform an action on a bucket. Currently, S3
    supports the following actions::

        acl
        cors
        lifecycle
        policy
        location
        logging
        notification
        tagging
        versions
        requestPayment
        versioning
        website

    To perform an action on a bucket::

        salt myminion s3.get mybucket myfile.png action=acl
    '''
    return _query(method='GET',
                  bucket=bucket,
                  path=path,
                  return_bin=return_bin,
                  local_file=local_file,
                  action=action)


def _query(method='GET', params=None, headers=None, requesturl=None,
           return_url=False, bucket=None, key=None, keyid=None, region=None,
           service_url=None, path=None, return_bin=False, action=None,
           local_file=None):
    '''
    Perform a query against an S3-like API
    '''
    if not headers:
        headers = {}

    if not params:
        params = {}

    if path is None:
        path = ''

    key = __salt__['config.option']('s3.key')
    keyid = __salt__['config.option']('s3.keyid')

    if not service_url and __salt__['config.option']('s3.service_url'):
        service_url = __salt__['config.option']('s3.service_url')

    if not service_url:
        service_url = 's3.amazonaws.com'

    if bucket:
        endpoint = '{0}.{1}'.format(bucket, service_url)
    else:
        endpoint = service_url

    if not requesturl:
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        x_amz_date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        content_type = 'text/plain'
        content_md5 = ''
        date = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        if bucket:
            can_resource = '/{0}/{1}'.format(bucket, path)
        else:
            can_resource = '/'

        if action:
            can_resource += '?{0}'.format(action)

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
    if local_file and method == 'GET':
        out = open(local_file, 'w')
        out.write(response)
        out.close()
        return 'Saved to local file: {0}'.format(local_file)

    if return_bin:
        return response

    items = ET.fromstring(response)

    ret = []
    for item in items:
        ret.append(xml.to_dict(item))

    if return_url is True:
        return ret, requesturl

    return ret


