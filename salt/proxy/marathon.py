# -*- coding: utf-8 -*-
'''
Marathon
========

Proxy minion for managing a Marathon cluster.

Dependencies
------------

- :mod:`marathon execution module (salt.modules.marathon) <salt.modules.marathon>`

Pillar
------

The marathon proxy configuration requires a 'base_url' property that points to
the marathon endpoint:

.. code-block:: yaml

    proxy:
      proxytype: marathon
      base_url: http://my-marathon-master.mydomain.com:8080

.. versionadded:: 2015.8.2
'''
from __future__ import absolute_import

import logging
import salt.utils.http


__proxyenabled__ = ['marathon']
CONFIG = {}
CONFIG_BASE_URL = 'base_url'
log = logging.getLogger(__file__)


def __virtual__():
    return True


def init(opts):
    '''
    Perform any needed setup.
    '''
    if CONFIG_BASE_URL in opts['proxy']:
        CONFIG[CONFIG_BASE_URL] = opts['proxy'][CONFIG_BASE_URL]
    else:
        log.error('missing proxy property %s', CONFIG_BASE_URL)
    log.debug('CONFIG: %s', CONFIG)


def ping():
    '''
    Is the marathon api responding?
    '''
    try:
        response = salt.utils.http.query(
            "{0}/ping".format(CONFIG[CONFIG_BASE_URL]),
            decode_type='plain',
            decode=True,
        )
        log.debug(
            'marathon.info returned succesfully: %s',
            response,
        )
        if 'text' in response and response['text'].strip() == 'pong':
            return True
    except Exception as ex:
        log.error(
            'error calling marathon.info with base_url %s: %s',
            CONFIG[CONFIG_BASE_URL],
            ex,
        )
    return False


def shutdown(opts):
    '''
    For this proxy shutdown is a no-op
    '''
    log.debug('marathon proxy shutdown() called...')
