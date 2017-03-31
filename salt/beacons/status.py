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
import salt.exceptions

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __validate__(config):
    '''
    Validate the the config is a dict
    '''
    if not isinstance(config, dict):
        return False, ('Configuration for status beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


def __virtual__():
    # TODO Find a way to check the existence of the module itself, not just a single func
    if 'status.w' not in __salt__:
        return (False, 'The \'status\' execution module is not available on this system')
    else:
        return True


def beacon(config):
    '''
    Return status for requested information
    '''
    log.debug(config)
    ctime = datetime.datetime.utcnow().isoformat()
    ret = {}
    if salt.utils.is_windows():
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
                log.debug('Status beacon attempted to process function {0} '
                          'but encountered error: {1}'.format(func, exc))
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
