# -*- coding: utf-8 -*-
'''
znc - An advanced IRC bouncer
'''

# Import python libs
import logging

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
