# -*- coding: utf-8 -*-
'''
Connection library for Amazon IAM

:depends: requests
'''
from __future__ import absolute_import, unicode_literals

# Import Python libs
import logging
import time
import pprint
import salt.utils.data
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
        except Exception as exc:  # pylint: disable=broad-except
            pass

        log.warning(
            'Caught exception reading from URL. Retry no. %s', i
        )
        log.warning(pprint.pformat(exc))
        time.sleep(2 ** i)
    log.error(
        'Failed to read from URL for %s times. Giving up.', num_retries
    )
    return ''


def _convert_key_to_str(key):
    '''
    Stolen completely from boto.providers
    '''
    # IMPORTANT: on PY2, the secret key must be str and not unicode to work
    # properly with hmac.new (see http://bugs.python.org/issue5285)
    #
    # pylint: disable=incompatible-py3-code,undefined-variable
    return salt.utils.data.encode(key) \
        if six.PY2 and isinstance(key, unicode) \
        else key
    # pylint: enable=incompatible-py3-code,undefined-variable
