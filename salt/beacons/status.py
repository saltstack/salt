# -*- coding: utf-8 -*-
'''
The status beacon is intended to send a basic health check event up to the
master, this allows for event driven routines based on presence to be set up.

The intention of this beacon is to add the config options to add monitoring
stats to the health beacon making it a one stop shop for gathering systems
health and status data

.. versionadded:: Carbon

To configure this beacon to use the defaults, set up an empty dict for it in
the minion config:

.. code-block:: yaml

    beacons:
      status: {}

By default, all of the information from the following execution module
functions will be returned:

    - loadavg
    - cpustats
    - meminfo
    - vmstats
    - time

You can also configure your own set of functions to be returned:

.. code-block:: yaml

    beacons:
      status:
        - time:
          - all
        - loadavg:
          - all

You may also configure only certain fields from each function to be returned.
For instance, the ``loadavg`` function returns the following fields:

    - 1-min
    - 5-min
    - 15-min

If you wanted to return only the ``1-min`` and ``5-min`` fields for ``loadavg``
then you would configure:

.. code-block:: yaml

    beacons:
      status:
        - loadavg:
          - 1-min
          - 5-min

Other functions only return a single value instead of a dictionary. With these,
you may specify ``all`` or ``0``. The following are both valid:

.. code-block:: yaml

    beacons:
      status:
        - time:
          - all

    beacons:
      status:
        - time:
          - 0

If a ``status`` function returns a list, you may return the index marker or
markers for specific list items:

.. code-block:: yaml

    beacons:
      status:
        - w:
          - 0
          - 1
          - 2
'''

# Import python libs
from __future__ import absolute_import
import logging
import datetime

log = logging.getLogger(__name__)


def __validate__(config):
    '''
    Validate the the config is a dict
    '''
    if not isinstance(config, dict):
        return False, ('Configuration for status beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Return status for requested information
    '''
    log.debug(config)
    ctime = datetime.datetime.utcnow().isoformat()

    if len(config) < 1:
        config = {
            'loadavg': 'all',
            'cpustats': 'all',
            'meminfo': 'all',
            'vmstats': 'all',
            'time': 'all',
        }

    ret = {}
    for func in config:
        data = __salt__['status.{0}'.format(func)]()
        ret[func] = {}
        for item in config[func]:
            if item == 'all':
                ret[func] = data
            else:
                try:
                    try:
                        ret[func][item] = data[item]
                    except TypeError:
                        ret[func][item] = data[int(item)]
                except KeyError as exc:
                    ret[func] = 'Status beacon is incorrectly configured: {0}'.format(exc)

    return [{
        'tag': ctime,
        'data': ret,
    }]
