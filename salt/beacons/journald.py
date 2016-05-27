# -*- coding: utf-8 -*-
'''
A simple beacon to watch journald for specific entries
'''

# Import Python libs
from __future__ import absolute_import

# Import salt libs
import salt.utils
import salt.utils.locales
import salt.utils.cloud
import salt.ext.six

# Import third party libs
try:
    import systemd.journal
    HAS_SYSTEMD = True
except ImportError:
    HAS_SYSTEMD = False

import logging
log = logging.getLogger(__name__)

__virtualname__ = 'journald'


def __virtual__():
    if HAS_SYSTEMD:
        return __virtualname__
    return False


def _get_journal():
    '''
    Return the active running journal object
    '''
    if 'systemd.journald' in __context__:
        return __context__['systemd.journald']
    __context__['systemd.journald'] = systemd.journal.Reader()
    # get to the end of the journal
    __context__['systemd.journald'].seek_tail()
    __context__['systemd.journald'].get_previous()
    return __context__['systemd.journald']


def validate(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for journald beacon should be a list of dicts
    if not isinstance(config, dict):
        return False
    else:
        for item in config:
            if not isinstance(config[item], dict):
                return False, ('Configuration for journald beacon must '
                               'be a dictionary of dictionaries.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    The journald beacon allows for the systemd journal to be parsed and linked
    objects to be turned into events.

    This beacons config will return all sshd jornal entries

    .. code-block:: yaml

        beacons:
          journald:
            sshd:
              SYSLOG_IDENTIFIER: sshd
              PRIORITY: 6
    '''
    ret = []
    journal = _get_journal()
    while True:
        cur = journal.get_next()
        if not cur:
            break
        for name in config:
            n_flag = 0
            for key in config[name]:
                if isinstance(key, salt.ext.six.string_types):
                    key = salt.utils.locales.sdecode(key)
                if key in cur:
                    if config[name][key] == cur[key]:
                        n_flag += 1
            if n_flag == len(config[name]):
                # Match!
                sub = salt.utils.cloud.simple_types_filter(cur)
                sub.update({'tag': name})
                ret.append(sub)
    return ret
