# -*- coding: utf-8 -*-
'''
Contains systemd related help files
'''
# import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import subprocess

# Import Salt libs
from salt.exceptions import SaltInvocationError
import salt.utils.stringutils

log = logging.getLogger(__name__)


def booted(context=None):
    '''
    Return True if the system was booted with systemd, False otherwise.  If the
    loader context dict ``__context__`` is passed, this function will set the
    ``salt.utils.systemd.booted`` key to represent if systemd is running and
    keep the logic below from needing to be run again during the same salt run.
    '''
    contextkey = 'salt.utils.systemd.booted'
    if isinstance(context, dict):
        # Can't put this if block on the same line as the above if block,
        # because it willl break the elif below.
        if contextkey in context:
            return context[contextkey]
    elif context is not None:
        raise SaltInvocationError('context must be a dictionary if passed')

    try:
        # This check does the same as sd_booted() from libsystemd-daemon:
        # http://www.freedesktop.org/software/systemd/man/sd_booted.html
        ret = bool(os.stat('/run/systemd/system'))
    except OSError:
        ret = False

    try:
        context[contextkey] = ret
    except TypeError:
        pass

    return ret


def version(context=None):
    '''
    Attempts to run systemctl --version. Returns None if unable to determine
    version.
    '''
    contextkey = 'salt.utils.systemd.version'
    if isinstance(context, dict):
        # Can't put this if block on the same line as the above if block,
        # because it will break the elif below.
        if contextkey in context:
            return context[contextkey]
    elif context is not None:
        raise SaltInvocationError('context must be a dictionary if passed')
    stdout = subprocess.Popen(
        ['systemctl', '--version'],
        close_fds=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0]
    outstr = salt.utils.stringutils.to_str(stdout)
    try:
        ret = int(outstr.splitlines()[0].split()[-1])
    except (IndexError, ValueError):
        log.error(
            'Unable to determine systemd version from systemctl '
            '--version, output follows:\n%s', outstr
        )
        return None
    else:
        try:
            context[contextkey] = ret
        except TypeError:
            pass
        return ret


def has_scope(context=None):
    '''
    Scopes were introduced in systemd 205, this function returns a boolean
    which is true when the minion is systemd-booted and running systemd>=205.
    '''
    if not booted(context):
        return False
    _sd_version = version(context)
    if _sd_version is None:
        return False
    return _sd_version >= 205
