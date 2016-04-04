# -*- coding: utf-8 -*-
'''
Beacon to fire events at login of users as registered in the wtmp file

.. code-block:: yaml

    beacons:
      wtmp: {}
'''

# Import Python libs
from __future__ import absolute_import
import os
import struct

# Import 3rd-party libs
from salt.ext.six.moves import range

# Import salt libs
import salt.utils

__virtualname__ = 'wtmp'
WTMP = '/var/log/wtmp'
FMT = '<hI32s4s32s256siili4l20s'
FIELDS = [
          'type',
          'PID',
          'line',
          'inittab',
          'user',
          'hostname',
          'exit_status',
          'session',
          'time',
          'addr'
]
SIZE = struct.calcsize(FMT)
LOC_KEY = 'wtmp.loc'

import logging
log = logging.getLogger(__name__)


def __virtual__():
    if os.path.isfile(WTMP):
        return __virtualname__
    return False


def _get_loc():
    '''
    return the active file location
    '''
    if LOC_KEY in __context__:
        return __context__[LOC_KEY]


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for wtmp beacon should be a list of dicts
    if not isinstance(config, dict):
        return False, ('Configuration for wtmp beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


# TODO: add support for only firing events for specific users and login times
def beacon(config):
    '''
    Read the last wtmp file and return information on the logins

    .. code-block:: yaml

        beacons:
          wtmp: {}
    '''
    ret = []
    with salt.utils.fopen(WTMP, 'rb') as fp_:
        loc = __context__.get(LOC_KEY, 0)
        if loc == 0:
            fp_.seek(0, 2)
            __context__[LOC_KEY] = fp_.tell()
            return ret
        else:
            fp_.seek(loc)
        while True:
            raw = fp_.read(SIZE)
            if len(raw) != SIZE:
                return ret
            __context__[LOC_KEY] = fp_.tell()
            pack = struct.unpack(FMT, raw)
            event = {}
            for ind in range(len(FIELDS)):
                event[FIELDS[ind]] = pack[ind]
                if isinstance(event[FIELDS[ind]], str):
                    event[FIELDS[ind]] = event[FIELDS[ind]].strip('\x00')
            ret.append(event)
    return ret
