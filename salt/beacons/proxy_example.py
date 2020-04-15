# -*- coding: utf-8 -*-
"""
Example beacon to use with salt-proxy

.. code-block:: yaml

    beacons:
      proxy_example:
        endpoint: beacon
"""

# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging

# Import salt libs
import salt.utils.http
from salt.ext.six.moves import map

# Important: If used with salt-proxy
# this is required for the beacon to load!!!
__proxyenabled__ = ["*"]

__virtualname__ = "proxy_example"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Trivially let the beacon load for the test example.
    For a production beacon we should probably have some expression here.
    """
    return True


def validate(config):
    """
    Validate the beacon configuration
    """
    if not isinstance(config, list):
        return False, ("Configuration for proxy_example beacon must be a list.")
    return True, "Valid beacon configuration"


def beacon(config):
    """
    Called several times each second
    https://docs.saltstack.com/en/latest/topics/beacons/#the-beacon-function

    .. code-block:: yaml

        beacons:
          proxy_example:
            - endpoint: beacon
    """
    # Important!!!
    # Although this toy example makes an HTTP call
    # to get beacon information
    # please be advised that doing CPU or IO intensive
    # operations in this method will cause the beacon loop
    # to block.
    _config = {}
    list(map(_config.update, config))

    beacon_url = "{0}{1}".format(__opts__["proxy"]["url"], _config["endpoint"])
    ret = salt.utils.http.query(beacon_url, decode_type="json", decode=True)
    return [ret["dict"]]
