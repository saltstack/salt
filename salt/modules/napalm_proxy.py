# -*- coding: utf-8 -*-
'''
NAPALM Proxy functions
======================

Proxy-related features for the NAPALM modules.

.. versionadded:: 2016.11.3
'''

from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)

try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm_base import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'napalm_proxy'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work.
    Also, the key proxymodule must be set in the __opts___ dictionary.
    '''
    if HAS_NAPALM and 'proxy' in __opts__:
        return __virtualname__
    else:
        return (False, 'The NAPALM keepalive modules cannot be loaded: \
                NAPALM or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def alive():
    '''
    Returns the alive status of the connection layer.
    The output is a dictionary under the usual dictionary
    output of the NAPALM modules.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_proxy.alive

    Output Example:

    .. code-block:: yaml

        result: True
        out:
            is_alive: False
        comment: ''
    '''
    return __proxy__['napalm.call'](
        'is_alive',
        **{
        }
    )


def reconnect(force=False):
    '''
    Reconnect the NAPALM proxy when the connection
    is dropped by the network device.
    The connection can be forced to be restarted
    using the ``force`` argument

    CLI Example:

    .. code-block:: bash

        salt '*' napalm_proxy.reconnect
        salt '*' napalm_proxy.reconnect force=True
    '''
    is_alive = alive()
    log.debug('Is alive fetch:')
    log.debug(is_alive)
    if not is_alive.get('result', False) or\
       not is_alive.get('out', False) or\
       not is_alive.get('out', {}).get('is_alive', False) or\
       force:  # even if alive, but the user wants to force a restart
        proxyid = __opts__.get('proxyid') or __opts__.get('id')
        # close the connection
        log.info('Closing the NAPALM proxy connection with {proxyid}'.format(proxyid=proxyid))
        __proxy__['napalm.call'](
            'close',
            **{
            }
        )
        # and re-open
        log.info('Re-opening the NAPALM proxy connection with {proxyid}'.format(proxyid=proxyid))
        __proxy__['napalm.call'](
            'open',
            **{
            }
        )
    # otherwise, I have nothing to do here:
    return {
        'out': None,
        'result': True,
        'comment': 'Already alive.'
    }
