# -*- coding: utf-8 -*-
'''
Example beacon to use with salt-proxy

.. code-block:: yaml

    beacons:
      proxy_example:
        foo: bar
'''

# Import Python libs
from __future__ import absolute_import

# Important: Required for the beacon to load!!!
__proxyenabled__ = ['*']

__virtualname__ = 'proxy_example'

import logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Trivially let the beacon load for the test example.
    For a production beacon we should probably have some expression here.
    '''
    return True


def validate(config):
    '''
    Validate the beacon configuration
    '''
    if not isinstance(config, dict):
        log.info('Configuration for rest_example beacon must be a dictionary.')
        return False
    return True


def beacon(config):
    '''
    Called several times each second
    https://docs.saltstack.com/en/latest/topics/beacons/#the-beacon-function

    .. code-block:: yaml

        beacons:
          proxy_example:
            foo: bar
    '''
    # TBD
    # Call rest.py and return the result
    ret = [{'foo': config['foo']}]
    log.info('Called the beacon function for proxy_test beacon')

    return ret
