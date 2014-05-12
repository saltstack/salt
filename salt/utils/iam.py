# -*- coding: utf-8 -*-
'''
Connection library for Amazon IAM

:depends: requests
'''

# Import Python libs
import json
import logging
import time
import requests
import pprint

log = logging.getLogger(__name__)


def _retry_get_url(url, num_retries=10, timeout=5):
    '''
    Retry grabbing a URL.
    Based heavily on boto.utils.retry_url
    '''
    for i in range(0, num_retries):
        try:
            result = requests.get(url, timeout=timeout)
            return result.text
        except requests.exceptions.HTTPError as exc:
            return ''
        except Exception as exc:
            pass

        log.warning(
            'Caught exception reading from URL. Retry no. {0}'.format(i)
        )
        log.warning(pprint.pformat(exc))
        time.sleep(2 ** i)
    log.error(
        'Failed to read from URL for {0} times. Giving up.'.format(num_retries)
    )
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
