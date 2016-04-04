# -*- coding: utf-8 -*-
'''
Beacon to fire events at failed login of users

.. code-block:: yaml

    beacons:
      btmp: {}
'''

# Import python libs
from __future__ import absolute_import
import os
import struct

# Import Salt Libs
import salt.utils
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

__virtualname__ = 'btmp'
BTMP = '/var/log/btmp'
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
LOC_KEY = 'btmp.loc'


def __virtual__():
    if os.path.isfile(BTMP):
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
    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, dict):
        return False, ('Configuration for btmp beacon must '
                       'be a list of dictionaries.')
    return True, 'Valid beacon configuration'


# TODO: add support for only firing events for specific users and login times
def beacon(config):
    '''
    Read the last btmp file and return information on the failed logins

    .. code-block:: yaml

        beacons:
          btmp: {}
    '''
    ret = []
    with salt.utils.fopen(BTMP, 'rb') as fp_:
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
