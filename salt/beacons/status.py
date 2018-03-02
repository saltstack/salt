# -*- coding: utf-8 -*-
'''
The status beacon is intended to send a basic health check event up to the
master, this allows for event driven routines based on presence to be set up.

The intention of this beacon is to add the config options to add monitoring
stats to the health beacon making it a one stop shop for gathering systems
health and status data

.. versionadded:: 2016.11.0

To configure this beacon to use the defaults, set up an empty dict for it in
the minion config:

.. code-block:: yaml

    beacons:
      status: []

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


.. warning::
    Not all status functions are supported for every operating system. Be certain
    to check the minion log for errors after configuring this beacon.

'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import logging
import datetime
import salt.exceptions

# Import salt libs
import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = 'status'


def validate(config):
    '''
    Validate the the config is a dict
    '''
    if not isinstance(config, list):
        return False, ('Configuration for status beacon must be a list.')
    return True, 'Valid beacon configuration'


def __virtual__():
    return __virtualname__


def beacon(config):
    '''
    Return status for requested information
    '''
    log.debug(config)
    ctime = datetime.datetime.utcnow().isoformat()
    ret = {}
    if salt.utils.platform.is_windows():
        return [{
            'tag': ctime,
            'data': ret,
        }]

    if len(config) < 1:
        config = [{
            'loadavg': ['all'],
            'cpustats': ['all'],
            'meminfo': ['all'],
            'vmstats': ['all'],
            'time': ['all'],
        }]

    if not isinstance(config, list):
        # To support the old dictionary config format
        config = [config]

    ret = {}
    for entry in config:
        for func in entry:
            ret[func] = {}
            try:
                data = __salt__['status.{0}'.format(func)]()
            except salt.exceptions.CommandExecutionError as exc:
                log.debug('Status beacon attempted to process function %s '
                          'but encountered error: %s', func, exc)
                continue
            if not isinstance(entry[func], list):
                func_items = [entry[func]]
            else:
                func_items = entry[func]
            for item in func_items:
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
