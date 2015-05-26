# -*- coding: utf-8 -*-
'''
A simple beacon to watch journald for specific entries
'''
# Import salt libs
import salt.utils
import salt.utils.cloud
import salt.ext.six

# Import third party libs
try:
    import systemd.journal
    HAS_SYSTEMD = True
except ImportError:
    HAS_SYSTEMD = False

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


def beacon(config):
    '''
    The journald beacon allows for the systemd jornal to be parsed and linked
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
                    key = salt.utils.sdecode(key)
                if key in cur:
                    if config[name][key] == cur[key]:
                        n_flag += 1
            if n_flag == len(config[name]):
                # Match!
                ret.append(salt.utils.cloud.simple_types_filter(cur))
    return ret
