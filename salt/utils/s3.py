'''
Connection library for Amazon S3
'''

# Import Python libs
import binascii
import datetime
import hashlib
import hmac
import json
import logging
import time
import urllib
import urllib2
import xml.etree.ElementTree as ET

# Import Salt libs
import salt.utils
import salt.utils.xmlutil as xml

log = logging.getLogger(__name__)

def _retry_get_url(url, num_retries=10, timeout=5):
    '''
    Retry grabbing a URL.
    Based heavily on boto.utils.retry_url
    '''
    for i in range(0, num_retries):
        try:
            # disable any environmental proxy settings
            proxy_handler = urllib2.ProxyHandler({})
            opener = urllib2.build_opener(proxy_handler)

            req = urllib2.Request(url)

            # timeout only in > 2.6
            r = opener.open(req, timeout=timeout)
            return r.read()
        except urllib2.HTTPError:
            return ''
        except urllib2.URLError:
            pass
        except Exception:
            pass

        log.warning('Caught exception reading from URL. Retry no. {0}'.format(i))
        time.sleep(2 ** i)
    log.error('Failed to read from URL for {0} times. Giving up.'.format(num_retries))
    return ''

def _convert_key_to_str(key):
    '''
    Stolen completely from boto.providers
    '''
    if isinstance(key, unicode):
        # the secret key must be bytes and not unicode to work
        #  properly with hmac.new (see http://bugs.python.org/issue5285)
        return str(key)
    return key

def get_iam_metadata(version='latest', url='http://169.254.169.254',
        timeout=None, num_retries=5):
    '''
    Grabs the first IAM role from this instances metadata if it exists.
    '''
    iam_url = '{0}/{1}/meta-data/iam/security-credentials/'.format(url, version)
    roles = _retry_get_url(iam_url, num_retries, timeout).splitlines()

    credentials = {
                'access_key': None,
                'secret_key': None,
                'expires_at': None,
                'security_token': None
            }

    try:
        data = _retry_get_url(iam_url + roles[0], num_retries, timeout)
        meta = json.loads(data)

    except (ValueError, TypeError, IndexError):
        # JSON failed to decode, so just pass no credentials back
        log.error('Failed to read metadata. Giving up on IAM credentials.')

    else:
        credentials['access_key'] = meta['AccessKeyId']
        credentials['secret_key'] = _convert_key_to_str(meta['SecretAccessKey'])
        credentials['expires_at'] = meta['Expiration']
        credentials['security_token'] = meta['Token']

    return credentials

def query(key, keyid, method='GET', params=None, headers=None,
          requesturl=None, return_url=False, bucket=None, service_url=None,
          path=None, return_bin=False, action=None, local_file=None):
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
        iam_creds = get_iam_metadata()
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
        for header in sorted(headers.keys()):
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

    req = urllib2.Request(url=requesturl)
    if method == 'PUT':
        if local_file:
            with salt.utils.fopen(local_file, 'r') as ifile:
                data = ifile.read()
            req = urllib2.Request(url=requesturl, data=data)
        req.get_method = lambda: 'PUT'
    elif method == 'HEAD':
        req.get_method = lambda: 'HEAD'
    elif method == 'DELETE':
        req.get_method = lambda: 'DELETE'

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

    if method == 'PUT':
        if result.getcode() == 200:
            if local_file:
                log.debug('Uploaded from {0} to {1}'.format(local_file, path))
            else:
                log.debug('Created bucket {0}'.format(bucket))
        else:
            if local_file:
                log.debug('Failed to upload from {0} to {1}: {2}'.format(
                                                    local_file,
                                                    path,
                                                    result.getcode(),
                                                    ))
            else:
                log.debug('Failed to create bucket {0}'.format(bucket))
        return

    if method == 'DELETE':
        if str(result.getcode()).startswith('2'):
            if path:
                log.debug('Deleted {0} from bucket {1}'.format(path, bucket))
            else:
                log.debug('Deleted bucket {0}'.format(bucket))
        else:
            if path:
                log.debug('Failed to delete {0} from bucket {1}: {2}'.format(
                                                    path,
                                                    bucket,
                                                    result.getcode(),
                                                    ))
            else:
                log.debug('Failed to delete bucket {0}'.format(bucket))
        return

    # This can be used to save a binary object to disk
    if local_file and method == 'GET':
        log.debug('Saving to local file: {0}'.format(local_file))
        out = open(local_file, 'w')
        out.write(response)
        out.close()
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
        ret = {'headers': []}
        for header in result.headers.headers:
            ret['headers'].append(header.strip())

    return ret
