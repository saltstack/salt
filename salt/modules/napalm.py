# -*- coding: utf-8 -*-
'''
NAPALM helpers
==============

Helpers for the NAPALM modules.

.. versionadded:: Nitrogen
'''

from __future__ import absolute_import

# Import python stdlib
import logging
log = logging.getLogger(__file__)

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

# Import Salt modules
from salt.ext import six

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'napalm'
__proxyenabled__ = ['napalm']
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    '''
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@proxy_napalm_wrap
def alive(**kwargs):  # pylint: disable=unused-argument
    '''
    Returns the alive status of the connection layer.
    The output is a dictionary under the usual dictionary
    output of the NAPALM modules.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.alive

    Output Example:

    .. code-block:: yaml

        result: True
        out:
            is_alive: False
        comment: ''
    '''
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'is_alive',
        **{}
    )


@proxy_napalm_wrap
def reconnect(force=False, **kwargs):  # pylint: disable=unused-argument
    '''
    Reconnect the NAPALM proxy when the connection
    is dropped by the network device.
    The connection can be forced to be restarted
    using the ``force`` argument.

    .. note::

        This function can be used only when running proxy minions.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.reconnect
        salt '*' napalm.reconnect force=True
    '''
    default_ret = {
        'out': None,
        'result': True,
        'comment': 'Already alive.'
    }
    if not salt.utils.napalm.is_proxy(__opts__):
        # regular minion is always alive
        # otherwise, the user would not be able to execute this command
        return default_ret
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
        salt.utils.napalm.call(
            napalm_device,  # pylint: disable=undefined-variable
            'close',
            **{}
        )
        # and re-open
        log.info('Re-opening the NAPALM proxy connection with {proxyid}'.format(proxyid=proxyid))
        salt.utils.napalm.call(
            napalm_device,  # pylint: disable=undefined-variable
            'open',
            **{}
        )
        default_ret.update({
            'comment': 'Connection restarted!'
        })
        return default_ret
    # otherwise, I have nothing to do here:
    return default_ret


@proxy_napalm_wrap
def call(method, *args, **kwargs):
    '''
    Execute arbitrary methods from the NAPALM library.
    To see the expected output, please consult the NAPALM documentation.

    .. note::

        This feature is not recommended to be used in production.
        It should be used for testing only!

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.call get_lldp_neighbors
        salt '*' napalm.call get_firewall_policies
        salt '*' napalm.call get_bgp_config group='my-group'
    '''
    clean_kwargs = {}
    for karg, warg in six.iteritems(kwargs):
        # remove the __pub args
        if not karg.startswith('__pub_'):
            clean_kwargs[karg] = warg
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        method,
        *args,
        **clean_kwargs
    )


@proxy_napalm_wrap
def compliance_report(filepath, **kwargs):
    '''
    Return the compliance report.

    filepath
        The absolute path to the validation file.

    CLI Example:

    .. code-block:: bash

        salt '*' napalm.compliance_report ~/validate.yml

    Output Example:

    .. code-block:: json

        {
          "skipped": [],
          "complies": true,
          "get_interfaces_ip": {
            "missing": [],
            "complies": true,
            "present": {
              "ge-0/0/0.0": {
                "complies": true,
                "nested": true
              }
            },
            "extra": []
          }
        }
    '''
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'compliance_report',
        validation_file=filepath
    )
