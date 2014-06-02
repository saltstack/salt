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

# Define the module's virtual name
__virtualname__ = 'varnish'


def __virtual__():
    '''
    Only load the module if varnish is installed
    '''
    if salt.utils.which('varnishd'):
        return __virtualname__
    return False


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
