# -*- coding: utf-8 -*-
'''
Connection library for Amazon IAM

:depends: requests
'''
from __future__ import absolute_import

# Import Python libs
import logging
import time
import pprint
from salt.ext.six.moves import range
from salt.ext import six

try:
    import requests
    HAS_REQUESTS = True  # pylint: disable=W0612
except ImportError:
    HAS_REQUESTS = False  # pylint: disable=W0612

log = logging.getLogger(__name__)


def _retry_get_url(url, num_retries=10, timeout=5):
    '''
    Retry grabbing a URL.
    Based heavily on boto.utils.retry_url
    '''
    for i in range(0, num_retries):
        try:
            result = requests.get(url, timeout=timeout, proxies={'http': ''})
            if hasattr(result, 'text'):
                return result.text
            elif hasattr(result, 'content'):
                return result.content
            else:
                return ''
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
    if isinstance(key, six.text_type):
        # the secret key must be bytes and not unicode to work
        #  properly with hmac.new (see http://bugs.python.org/issue5285)
        return str(key)
    return key
