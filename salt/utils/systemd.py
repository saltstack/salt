# -*- coding: utf-8 -*-
'''
Contains systemd related help files
'''
# import python libs
from __future__ import absolute_import
import logging
import os
import subprocess

# Import Salt libs
from salt.exceptions import SaltInvocationError
import salt.utils

log = logging.getLogger(__name__)


def booted(context):
    '''
    Return True if the system was booted with systemd, False otherwise.
    Pass in the loader context "__context__", this function will set the
    systemd.sd_booted key to represent if systemd is running
    '''
    # We can cache this for as long as the minion runs.
    if 'systemd.sd_booted' not in context:
        try:
            # This check does the same as sd_booted() from libsystemd-daemon:
            # http://www.freedesktop.org/software/systemd/man/sd_booted.html
            if os.stat('/run/systemd/system'):
                context['systemd.sd_booted'] = True
        except OSError:
            context['systemd.sd_booted'] = False
    return context['systemd.sd_booted']


def version(context=None):
    '''
    Attempts to run systemctl --version. Returns None if unable to determine
    version.
    '''
    if isinstance(context, dict):
        if 'systemd.version' in context:
            return context['systemd.version']
    elif context is not None:
        raise SaltInvocationError('context must be a dictionary or None')
    stdout = subprocess.Popen(
        ['systemctl', '--version'],
        close_fds=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
    outstr = salt.utils.to_str(stdout)
    try:
        ret = int(outstr.splitlines()[0].split()[-1])
    except (IndexError, ValueError):
        log.error(
            'Unable to determine systemd version from systemctl '
            '--version, output follows:\n{0}'.format(outstr)
        )
        return None
    else:
        try:
            context['systemd.version'] = ret
        except TypeError:
            pass
        return ret
