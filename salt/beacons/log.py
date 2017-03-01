# -*- coding: utf-8 -*-
'''
Beacon to fire events at specific log messages.

.. versionadded:: Nitrogen

'''

# Import Python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils


try:
    import re
    HAS_REGEX = True
except ImportError:
    HAS_REGEX = False

__virtualname__ = 'log'
LOC_KEY = 'log.loc'

SKEL = {}
SKEL['tag'] = ''
SKEL['match'] = 'no'
SKEL['raw'] = ''
SKEL['error'] = ''


log = logging.getLogger(__name__)


def __virtual__():
    if not salt.utils.is_windows() and HAS_REGEX:
        return __virtualname__
    return False


def _get_loc():
    '''
    return the active file location
    '''
    if LOC_KEY in __context__:
        return __context__[LOC_KEY]


def __validate__(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for log beacon should be a list of dicts
    if not isinstance(config, dict):
        return False, ('Configuration for log beacon must be a dictionary.')
    return True, 'Valid beacon configuration'


# TODO: match values should be returned in the event
def beacon(config):
    '''
    Read the log file and return match whole string

    .. code-block:: yaml

        beacons:
            log:
              file: <path>
              <tag>:
                regex: <pattern>
    '''
    ret = []

    if 'file' not in config:
        event = SKEL.copy()
        event['tag'] = 'global'
        event['error'] = 'file not defined in config'
        ret.append(event)
        return ret

    with salt.utils.fopen(config['file'], 'r') as fp_:
        loc = __context__.get(LOC_KEY, 0)
        if loc == 0:
            fp_.seek(0, 2)
            __context__[LOC_KEY] = fp_.tell()
            return ret

        fp_.seek(0, 2)
        __context__[LOC_KEY] = fp_.tell()
        fp_.seek(loc)

        txt = fp_.read()

        d = {}
        for tag in config:
            if 'regex' not in config[tag]:
                continue
            if len(config[tag]['regex']) < 1:
                continue
            try:
                d[tag] = re.compile(r'{0}'.format(config[tag]['regex']))
            except Exception:
                event = SKEL.copy()
                event['tag'] = tag
                event['error'] = 'bad regex'
                ret.append(event)

        for line in txt.splitlines():
            for tag, reg in d.items():
                try:
                    m = reg.match(line)
                    if m:
                        event = SKEL.copy()
                        event['tag'] = tag
                        event['raw'] = line
                        event['match'] = 'yes'
                        ret.append(event)
                except Exception:
                    event = SKEL.copy()
                    event['tag'] = tag
                    event['error'] = 'bad match'
                    ret.append(event)
    return ret
