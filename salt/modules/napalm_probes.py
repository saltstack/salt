# -*- coding: utf-8 -*-
'''
NAPALM Probes
=============

Manages RPM/SLA probes on the network device.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   linux

Dependencies
------------

- :doc:`napalm proxy minion (salt.proxy.napalm) </ref/proxy/all/salt.proxy.napalm>`

.. versionadded: Carbon
'''

from __future__ import absolute_import

# Import python lib
import logging
log = logging.getLogger(__file__)


try:
    # will try to import NAPALM
    # https://github.com/napalm-automation/napalm
    # pylint: disable=W0611
    from napalm import get_network_driver
    # pylint: enable=W0611
    HAS_NAPALM = True
except ImportError:
    HAS_NAPALM = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'probes'
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
        return (False, 'The module napalm_probes cannot be loaded: \
                napalm or proxy could not be loaded.')

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def config():

    '''
    Returns the configuration of the RPM probes.

    :return: A dictionary containing the configuration of the RPM/SLA probes.

    CLI Example:

    .. code-block:: bash

        salt '*' probes.config

    Output Example:

    .. code-block:: python

        {
            'probe1':{
                'test1': {
                    'probe_type'   : 'icmp-ping',
                    'target'       : '192.168.0.1',
                    'source'       : '192.168.0.2',
                    'probe_count'  : 13,
                    'test_interval': 3
                },
                'test2': {
                    'probe_type'   : 'http-ping',
                    'target'       : '172.17.17.1',
                    'source'       : '192.17.17.2',
                    'probe_count'  : 5,
                    'test_interval': 60
                }
            }
        }
    '''

    return __proxy__['napalm.call'](
        'get_probes_config',
        **{
        }
    )


def results():

    '''
    Provides the results of the measurements of the RPM/SLA probes.

    :return a dictionary with the results of the probes.


    CLI Example:

    .. code-block:: bash

        salt '*' probes.results


    Output example:

    .. code-block:: python

        {
            'probe1':  {
                'test1': {
                    'last_test_min_delay'   : 63.120,
                    'global_test_min_delay' : 62.912,
                    'current_test_avg_delay': 63.190,
                    'global_test_max_delay' : 177.349,
                    'current_test_max_delay': 63.302,
                    'global_test_avg_delay' : 63.802,
                    'last_test_avg_delay'   : 63.438,
                    'last_test_max_delay'   : 65.356,
                    'probe_type'            : 'icmp-ping',
                    'rtt'                   : 63.138,
                    'last_test_loss'        : 0,
                    'round_trip_jitter'     : -59.0,
                    'target'                : '192.168.0.1',
                    'source'                : '192.168.0.2'
                    'probe_count'           : 15,
                    'current_test_min_delay': 63.138
                },
                'test2': {
                    'last_test_min_delay'   : 176.384,
                    'global_test_min_delay' : 169.226,
                    'current_test_avg_delay': 177.098,
                    'global_test_max_delay' : 292.628,
                    'current_test_max_delay': 180.055,
                    'global_test_avg_delay' : 177.959,
                    'last_test_avg_delay'   : 177.178,
                    'last_test_max_delay'   : 184.671,
                    'probe_type'            : 'icmp-ping',
                    'rtt'                   : 176.449,
                    'last_test_loss'        : 0,
                    'round_trip_jitter'     : -34.0,
                    'target'                : '172.17.17.1',
                    'source'                : '172.17.17.2'
                    'probe_count'           : 15,
                    'current_test_min_delay': 176.402
                }
            }
        }
    '''

    return __proxy__['napalm.call'](
        'get_probes_results',
        **{
        }
    )


def set_probes(probes):

    '''
    Configures RPM/SLA probes on the device.
    Calls the configuration template 'set_probes' from the NAPALM library,
    providing as input a rich formatted dictionary with the configuration details of the probes to be configured.

    :param probes: Dictionary formatted as the output of the function config():
    :return: Will return if the configuration of the device was updated.

    Input example:

    .. code-block:: python

        probes = {
            'new_probe':{
                'new_test1': {
                    'probe_type'   : 'icmp-ping',
                    'target'       : '192.168.0.1',
                    'source'       : '192.168.0.2',
                    'probe_count'  : 13,
                    'test_interval': 3
                },
                'new_test2': {
                    'probe_type'   : 'http-ping',
                    'target'       : '172.17.17.1',
                    'source'       : '192.17.17.2',
                    'probe_count'  : 5,
                    'test_interval': 60
                }
            }
        }
        set_probes(probes)
    '''

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'set_probes',
            'probes': probes
        }
    )


def delete_probes(probes):

    '''
    Removes RPM/SLA probes from the network device.
    Calls the configuration template 'delete_probes' from the NAPALM library,
    providing as input a rich formatted dictionary with the configuration details of the probes to be removed
    from the configuration of the device.

    :param probes: Dictionary with a similar format as the output dictionary of the function config(),
    where the details are not necessary.
    :return: Will return if the configuration of the device was updated.

    Input example:

    .. code-block:: python

        probes = {
            'existing_probe':{
                'existing_test1': {},
                'existing_test2': {}
            }
        }

    '''

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'delete_probes',
            'probes': probes
        }
    )


def schedule_probes(probes):

    '''
    Will schedule the probes. On Cisco devices, it is not enough to define the probes, it is also necessary
    to schedule them.
    This method calls the configuration template 'schedule_probes' from the NAPALM library,
    providing as input a rich formatted dictionary with the names of the probes and the tests to be scheduled.

    :param probes: Dictionary with a similar format as the output dictionary of the function config(),
    where the details are not necessary.
    :return: Will return if the configuration of the device was updated.

    Input example:

    .. code-block:: python

        probes = {
            'new_probe':{
                'new_test1': {},
                'new_test2': {}
            }
        }

    '''

    return __proxy__['napalm.call'](
        'load_template',
        **{
            'template_name': 'schedule_probes',
            'probes': probes
        }
    )
