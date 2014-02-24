# -*- coding: utf-8 -*-
'''
znc - An advanced IRC bouncer
'''

# Import python libs
import hashlib
import logging
import os.path
import random
import signal

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if znc is installed
    '''
    if salt.utils.which('znc'):
        return 'znc'
    return False


def _makepass(password, hasher='sha256'):
    '''
    Create a znc compatible hashed password
    '''
    # Setup the hasher
    if hasher == 'sha256':
        h = hashlib.sha256(password)
    elif hasher == 'md5':
        h = hashlib.md5(password)
    else:
        return NotImplemented

    c = "abcdefghijklmnopqrstuvwxyz" \
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
        "0123456789!?.,:;/*-+_()"
    r = {
        'Method': h.name,
        'Salt': ''.join(random.choice(c) for x in xrange(20)),
    }

    # Salt the password hash
    h.update(r['Salt'])
    r['Hash'] = h.hexdigest()

    return r


def buildmod(*moules):
    '''
    Build module using znc-buildmod

    CLI Example:

    .. code-block:: bash

        salt '*' znc.buildmod module.cpp [...]
    '''
    cmd = 'znc-buildmod {0}'.format(' '.join(args))
    out = __salt__['cmd.run'](cmd).splitlines()
    return out[-1]


def dumpconf():
    '''
    Wite the active configuration state to config file

    CLI Example:

    .. code-block:: bash

        salt '*' znc.dumpconf
    '''
    return __salt__['ps.pkill']('znc', signal=signal.SIGUSR1)


def rehashconf():
    '''
    Rehash the active configuration state from config file

    CLI Example:

    .. code-block:: bash

        salt '*' znc.rehashconf
    '''
    return __salt__['ps.pkill']('znc', signal=signal.SIGHUP)


def version():
    '''
    Return server version from znc --version

    CLI Example:

    .. code-block:: bash

        salt '*' znc.version
    '''
    cmd = 'znc --version'
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = out[0].split(' - ')
    return ret[0]
