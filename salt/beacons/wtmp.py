# -*- coding: utf-8 -*-
'''
Beacon to fire events at login of users as registered in the wtmp file

.. code-block:: yaml

    beacons:
      wtmp: []
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging
import os
import struct
import time

# Import salt libs
import salt.utils.stringutils
import salt.utils.files

# Import 3rd-party libs
import salt.ext.six
# pylint: disable=import-error
from salt.ext.six.moves import map
# pylint: enable=import-error

__virtualname__ = 'wtmp'
WTMP = '/var/log/wtmp'
FMT = b'hi32s4s32s256shhiii4i20x'
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

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    import dateutil.parser as dateutil_parser
    _TIME_SUPPORTED = True
except ImportError:
    _TIME_SUPPORTED = False


def __virtual__():
    if os.path.isfile(WTMP):
        return __virtualname__
    return False


def _check_time_range(time_range, now):
    '''
    Check time range
    '''
    if _TIME_SUPPORTED:
        _start = int(time.mktime(dateutil_parser.parse(time_range['start']).timetuple()))
        _end = int(time.mktime(dateutil_parser.parse(time_range['end']).timetuple()))

        return bool(_start <= now <= _end)
    else:
        log.error('Dateutil is required.')
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
    if not isinstance(config, list):
        return False, ('Configuration for wtmp beacon must be a list.')
    else:
        _config = {}
        list(map(_config.update, config))

        if 'users' in _config:
            if not isinstance(_config['users'], dict):
                return False, ('User configuration for btmp beacon must '
                               'be a dictionary.')
            else:
                for user in _config['users']:
                    if _config['users'][user] and \
                       'time_range' in _config['users'][user]:
                        _time_range = _config['users'][user]['time_range']
                        if not isinstance(_time_range, dict):
                            return False, ('The time_range parameter for '
                                           'btmp beacon must '
                                           'be a dictionary.')
                        else:
                            if not all(k in _time_range for k in ('start', 'end')):
                                return False, ('The time_range parameter for '
                                               'btmp beacon must contain '
                                               'start & end options.')
        if 'defaults' in _config:
            if not isinstance(_config['defaults'], dict):
                return False, ('Defaults configuration for btmp beacon must '
                               'be a dictionary.')
            else:
                if 'time_range' in _config['defaults']:
                    _time_range = _config['defaults']['time_range']
                    if not isinstance(_time_range, dict):
                        return False, ('The time_range parameter for '
                                       'btmp beacon must '
                                       'be a dictionary.')
                    else:
                        if not all(k in _time_range for k in ('start', 'end')):
                            return False, ('The time_range parameter for '
                                           'btmp beacon must contain '
                                           'start & end options.')
    return True, 'Valid beacon configuration'


# TODO: add support for only firing events for specific users and login times
def beacon(config):
    '''
    Read the last wtmp file and return information on the logins

    .. code-block:: yaml

        beacons:
          wtmp: []

        beacons:
          wtmp:
            - users:
                gareth:
            - defaults:
                time_range:
                    start: '8am'
                    end: '4pm'

        beacons:
          wtmp:
            - users:
                gareth:
                    time_range:
                        start: '8am'
                        end: '4pm'
            - defaults:
                time_range:
                    start: '8am'
                    end: '4pm'
'''
    ret = []

    users = None
    defaults = None

    for config_item in config:
        if 'users' in config_item:
            users = config_item['users']

        if 'defaults' in config_item:
            defaults = config_item['defaults']

    with salt.utils.files.fopen(WTMP, 'rb') as fp_:
        loc = __context__.get(LOC_KEY, 0)
        if loc == 0:
            fp_.seek(0, 2)
            __context__[LOC_KEY] = fp_.tell()
            return ret
        else:
            fp_.seek(loc)
        while True:
            now = int(time.time())
            raw = fp_.read(SIZE)
            if len(raw) != SIZE:
                return ret
            __context__[LOC_KEY] = fp_.tell()
            pack = struct.unpack(FMT, raw)
            event = {}
            for ind, field in enumerate(FIELDS):
                event[field] = pack[ind]
                if isinstance(event[field], salt.ext.six.string_types):
                    if isinstance(event[field], bytes):
                        event[field] = salt.utils.stringutils.to_unicode(event[field])
                    event[field] = event[field].strip('\x00')

            if users:
                if event['user'] in users:
                    _user = users[event['user']]
                    if isinstance(_user, dict) and 'time_range' in _user:
                        if _check_time_range(_user['time_range'], now):
                            ret.append(event)
                    else:
                        if defaults and 'time_range' in defaults:
                            if _check_time_range(defaults['time_range'],
                                                 now):
                                ret.append(event)
                        else:
                            ret.append(event)
            else:
                if defaults and 'time_range' in defaults:
                    if _check_time_range(defaults['time_range'], now):
                        ret.append(event)
                else:
                    ret.append(event)
    return ret
