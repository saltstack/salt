# -*- coding: utf-8 -*-
'''
NAPALM Probes
=============

Manages RPM/SLA probes on the network device.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

- :mod:`napalm proxy minion <salt.proxy.napalm>`
- :mod:`NET basic features <salt.modules.napalm_network>`

.. seealso::
    :mod:`Probes configuration management state <salt.states.probes>`

.. versionadded:: 2016.11.0
'''

from __future__ import absolute_import, unicode_literals, print_function

# Import python lib
import logging
log = logging.getLogger(__file__)

# import NAPALM utils
import salt.utils.napalm
from salt.utils.napalm import proxy_napalm_wrap

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
def config(**kwargs):  # pylint: disable=unused-argument

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

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_probes_config',
        **{
        }
    )


@proxy_napalm_wrap
def results(**kwargs):  # pylint: disable=unused-argument

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
                    'source'                : '192.168.0.2',
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
                    'source'                : '172.17.17.2',
                    'probe_count'           : 15,
                    'current_test_min_delay': 176.402
                }
            }
        }
    '''

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        'get_probes_results',
        **{
        }
    )


@proxy_napalm_wrap
def set_probes(probes, test=False, commit=True, **kwargs):  # pylint: disable=unused-argument
    '''
    Configures RPM/SLA probes on the device.
    Calls the configuration template 'set_probes' from the NAPALM library,
    providing as input a rich formatted dictionary with the configuration details of the probes to be configured.

    :param probes: Dictionary formatted as the output of the function config()

    :param test: Dry run? If set as True, will apply the config, discard and return the changes. Default: False

    :param commit: Commit? (default: True) Sometimes it is not needed to commit
        the config immediately after loading the changes. E.g.: a state loads a
        couple of parts (add / remove / update) and would not be optimal to
        commit after each operation.  Also, from the CLI when the user needs to
        apply the similar changes before committing, can specify commit=False
        and will not discard the config.

    :raise MergeConfigException: If there is an error on the configuration sent.
    :return a dictionary having the following keys:

        * result (bool): if the config was applied successfully. It is `False`
          only in case of failure. In case there are no changes to be applied
          and successfully performs all operations it is still `True` and so
          will be the `already_configured` flag (example below)
        * comment (str): a message for the user
        * already_configured (bool): flag to check if there were no changes applied
        * diff (str): returns the config changes applied

    Input example - via state/script:

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

    CLI Example - to push cahnges on the fly (not recommended):

    .. code-block:: bash

        salt 'junos_minion' probes.set_probes "{'new_probe':{'new_test1':{'probe_type':'icmp-ping',\
            'target':'192.168.0.1','source':'192.168.0.2','probe_count':13,'test_interval':3}}}" test=True

    Output example - for the CLI example above:

    .. code-block:: yaml

        junos_minion:
            ----------
            already_configured:
                False
            comment:
                Configuration discarded.
            diff:
                [edit services rpm]
                     probe transit { ... }
                +    probe new_probe {
                +        test new_test1 {
                +            probe-type icmp-ping;
                +            target address 192.168.0.1;
                +            probe-count 13;
                +            test-interval 3;
                +            source-address 192.168.0.2;
                +        }
                +    }
            result:
                True
    '''

    return __salt__['net.load_template']('set_probes',
                                         probes=probes,
                                         test=test,
                                         commit=commit,
                                         inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable


@proxy_napalm_wrap
def delete_probes(probes, test=False, commit=True, **kwargs):  # pylint: disable=unused-argument

    '''
    Removes RPM/SLA probes from the network device.
    Calls the configuration template 'delete_probes' from the NAPALM library,
    providing as input a rich formatted dictionary with the configuration details of the probes to be removed
    from the configuration of the device.

    :param probes: Dictionary with a similar format as the output dictionary of
        the function config(), where the details are not necessary.
    :param test: Dry run? If set as True, will apply the config, discard and
        return the changes. Default: False
    :param commit: Commit? (default: True) Sometimes it is not needed to commit
        the config immediately after loading the changes. E.g.: a state loads a
        couple of parts (add / remove / update) and would not be optimal to
        commit after each operation.  Also, from the CLI when the user needs to
        apply the similar changes before committing, can specify commit=False
        and will not discard the config.

    :raise MergeConfigException: If there is an error on the configuration sent.
    :return: A dictionary having the following keys:

    - result (bool): if the config was applied successfully. It is `False` only
      in case of failure. In case there are no changes to be applied and
      successfully performs all operations it is still `True` and so will be
      the `already_configured` flag (example below)
    - comment (str): a message for the user
    - already_configured (bool): flag to check if there were no changes applied
    - diff (str): returns the config changes applied

    Input example:

    .. code-block:: python

        probes = {
            'existing_probe':{
                'existing_test1': {},
                'existing_test2': {}
            }
        }

    '''

    return __salt__['net.load_template']('delete_probes',
                                         probes=probes,
                                         test=test,
                                         commit=commit,
                                         inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable


@proxy_napalm_wrap
def schedule_probes(probes, test=False, commit=True, **kwargs):  # pylint: disable=unused-argument

    '''
    Will schedule the probes. On Cisco devices, it is not enough to define the
    probes, it is also necessary to schedule them.

    This function calls the configuration template ``schedule_probes`` from the
    NAPALM library, providing as input a rich formatted dictionary with the
    names of the probes and the tests to be scheduled.

    :param probes: Dictionary with a similar format as the output dictionary of
        the function config(), where the details are not necessary.
    :param test: Dry run? If set as True, will apply the config, discard and
        return the changes. Default: False
    :param commit: Commit? (default: True) Sometimes it is not needed to commit
        the config immediately after loading the changes. E.g.: a state loads a
        couple of parts (add / remove / update) and would not be optimal to
        commit after each operation.  Also, from the CLI when the user needs to
        apply the similar changes before committing, can specify commit=False
        and will not discard the config.

    :raise MergeConfigException: If there is an error on the configuration sent.
    :return: a dictionary having the following keys:

    - result (bool): if the config was applied successfully. It is `False` only
      in case of failure. In case there are no changes to be applied and
      successfully performs all operations it is still `True` and so will be
      the `already_configured` flag (example below)
    - comment (str): a message for the user
    - already_configured (bool): flag to check if there were no changes applied
    - diff (str): returns the config changes applied

    Input example:

    .. code-block:: python

        probes = {
            'new_probe':{
                'new_test1': {},
                'new_test2': {}
            }
        }
    '''

    return __salt__['net.load_template']('schedule_probes',
                                         probes=probes,
                                         test=test,
                                         commit=commit,
                                         inherit_napalm_device=napalm_device)  # pylint: disable=undefined-variable
