# -*- coding: utf-8 -*-
'''
Support for Varnish

.. versionadded:: Helium

.. note::

    These functions are generic, and are designed to work with all
    implementations of Varnish.
'''

# Import python libs
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'varnish'


def __virtual__():
    '''
    Only load the module if varnish is installed
    '''
    if salt.utils.which(_get_varnish_bin()):
        return __virtualname__
    return False


def _get_varnish_bin():
    '''
    Helper module to resolve the platform to the correct name of the varnish
    binary. Currently just returns 'varnishd' but this will allow future
    revisions of this module to integrate nicely with the rest of the module.
    '''
    return 'varnishd'


def version():
    '''
    Return server version from varnishd -V

    CLI Example:

    .. code-block:: bash

        salt '*' varnish.version
    '''
    cmd = '{0} -V'.format(_get_varnish_bin())
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
    log.debug('Purging varnish cache')
    if ver.startswith('4'):
        purge_cmd = 'ban .'
    elif ver.startswith('3'):
        purge_cmd = 'ban.url .'
    elif ver.startswith('2'):
        purge_cmd = 'url.purge .'
    cmd = 'varnishadm {0}'.format(purge_cmd)
    return __salt__['cmd.retcode'](cmd) == 0
