# -*- coding: utf-8 -*-
'''
Support for Varnish

Please note: The functions in here are generic functions designed to work with
all implementations of Varnish.
'''

# Import salt libs
import salt.utils
import logging
import re

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if varnish is installed
    '''
    cmd = _detect_os()
    if salt.utils.which(cmd):
        return True
    return False


def _detect_os():
    '''
    Varnish commands and paths differ depending on packaging
    '''
    if __grains__['os_family'] == 'Debian':
        return 'varnishd'
    else:
        return 'varnishd'


def version():
    '''
    Return server version from varnishd -V

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.version
    '''
    cmd = '{0} -V'.format(_detect_os())
    out = __salt__['cmd.run'](cmd)
    ret = out.split(' ')
    ret = re.findall(r'\d+', ret[1])
    return ret[0]


def purge():
    '''
    Purge the varnish cache
    CLI Example:
    .. code-block:: bash

        salt '*' varnish.purge
    '''
    ver = version()
    msg = "Purging varnish cache."
    log.debug(msg)
    if ver.startswith("4"):
        purge = "ban ."
    elif ver.startswith("3"):
        purge = "ban.url ."
    elif ver.startswith("2"):
        purge = "url.purge ."
    cmd = 'varnishadm {0}'.format(purge)
    return msg
