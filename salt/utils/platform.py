# -*- coding: utf-8 -*-
'''
Functions for identifying which platform a machine is
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import subprocess
import sys

# Import Salt libs
from salt.utils.decorators import memoize as real_memoize


@real_memoize
def is_windows():
    '''
    Simple function to return if a host is Windows or not
    '''
    return sys.platform.startswith('win')


@real_memoize
def is_proxy():
    '''
    Return True if this minion is a proxy minion.
    Leverages the fact that is_linux() and is_windows
    both return False for proxies.
    TODO: Need to extend this for proxies that might run on
    other Unices
    '''
    import __main__ as main
    # This is a hack.  If a proxy minion is started by other
    # means, e.g. a custom script that creates the minion objects
    # then this will fail.
    ret = False
    try:
        # Changed this from 'salt-proxy in main...' to 'proxy in main...'
        # to support the testsuite's temp script that is called 'cli_salt_proxy'
        if 'proxy' in main.__file__:
            ret = True
    except AttributeError:
        pass
    return ret


@real_memoize
def is_linux():
    '''
    Simple function to return if a host is Linux or not.
    Note for a proxy minion, we need to return something else
    '''
    return sys.platform.startswith('linux')


@real_memoize
def is_darwin():
    '''
    Simple function to return if a host is Darwin (macOS) or not
    '''
    return sys.platform.startswith('darwin')


@real_memoize
def is_sunos():
    '''
    Simple function to return if host is SunOS or not
    '''
    return sys.platform.startswith('sunos')


@real_memoize
def is_smartos():
    '''
    Simple function to return if host is SmartOS (Illumos) or not
    '''
    if not is_sunos():
        return False
    else:
        return os.uname()[3].startswith('joyent_')


@real_memoize
def is_smartos_globalzone():
    '''
    Function to return if host is SmartOS (Illumos) global zone or not
    '''
    if not is_smartos():
        return False
    else:
        cmd = ['zonename']
        try:
            zonename = subprocess.Popen(
                cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            return False
        if zonename.returncode:
            return False
        if zonename.stdout.read().strip() == 'global':
            return True

        return False


@real_memoize
def is_smartos_zone():
    '''
    Function to return if host is SmartOS (Illumos) and not the gz
    '''
    if not is_smartos():
        return False
    else:
        cmd = ['zonename']
        try:
            zonename = subprocess.Popen(
                cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            return False
        if zonename.returncode:
            return False
        if zonename.stdout.read().strip() == 'global':
            return False

        return True


@real_memoize
def is_freebsd():
    '''
    Simple function to return if host is FreeBSD or not
    '''
    return sys.platform.startswith('freebsd')


@real_memoize
def is_netbsd():
    '''
    Simple function to return if host is NetBSD or not
    '''
    return sys.platform.startswith('netbsd')


@real_memoize
def is_openbsd():
    '''
    Simple function to return if host is OpenBSD or not
    '''
    return sys.platform.startswith('openbsd')


@real_memoize
def is_aix():
    '''
    Simple function to return if host is AIX or not
    '''
    return sys.platform.startswith('aix')
