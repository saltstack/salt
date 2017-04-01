# -*- coding: utf-8 -*-
'''
NAPALM YANG state
=================

Manage the configuration of network devices according to
the YANG models (OpenConfig/IETF).

.. versionadded:: Nitrogen

Dependencies
------------

- napalm-yang
- pyangbing > 0.5.11

To be able to load configuration on network devices,
it requires NAPALM_ library to be installed:  ``pip install napalm``.
Please check Installation_ for complete details.

.. _NAPALM: https://napalm.readthedocs.io
.. _Installation: https://napalm.readthedocs.io/en/latest/installation.html
'''
from __future__ import absolute_import

import logging
log = logging.getLogger(__file__)

# Import third party libs
try:
    import yaml
    # pylint: disable=W0611
    import napalm_yang
    HAS_NAPALM_YANG = True
    # pylint: enable=W0611
except ImportError:
    HAS_NAPALM_YANG = False

import salt.utils.napalm

# ------------------------------------------------------------------------------
# state properties
# ------------------------------------------------------------------------------

__virtualname__ = 'napalm_yang'

# ------------------------------------------------------------------------------
# global variables
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# property functions
# ------------------------------------------------------------------------------


def __virtual__():
    '''
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    This module in particular requires also napalm-yang.
    '''
    if not HAS_NAPALM_YANG:
        return (False, 'Unable to load napalm_yang execution module: please install napalm-yang!')
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)

# ------------------------------------------------------------------------------
# helper functions -- will not be exported
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# callable functions
# ------------------------------------------------------------------------------


def managed(name,
            data,
            *models,
            **kwargs):
    '''
    Manage the device configuration given the input data strucuted
    according to the YANG models.

    data
        YANG structured data.

    models
         A list of models to be used when generating the config.

    profiles: ``None``
        Use certain profiles to generate the config.
        If not specified, will use the platform default profile(s).

    test: ``False``
        Dry run? If set as ``True``, will apply the config, discard
        and return the changes. Default: ``False`` and will commit
        the changes on the device.

    commit: ``True``
        Commit? Default: ``True``.

    debug: ``False``
        Debug mode. Will insert a new key under the output dictionary,
        as ``loaded_config`` contaning the raw configuration loaded on the device.

    replace: ``False``
        Should replace the config with the new generate one?

    State SLS example:

    .. code-block:: jinja

        {%- set expected_config =  pillar.get('interfaces') -%}
        interfaces_config:
          napalm_yang.managed:
            data: {{ expected_config | json }}
            models:
              - models.openconfig_interfaces
            debug: true
    '''
    ret = salt.utils.napalm.default_ret(name)
    test = kwargs.get('test', False) or __opts__.get('test', False)
    debug = kwargs.get('debug', False) or __opts__.get('debug', False)
    commit = kwargs.get('commit', True) or __opts__.get('commit', True)
    replace = kwargs.get('replace', False) or __opts__.get('replace', False)
    profiles = kwargs.get('profiles', [])
    temp_file = __salt__['temp.file']()
    log.debug('Creating temp file: {0}'.format(temp_file))
    if 'to_dict' not in data:
        data = {'to_dict': data}
    with salt.utils.fopen(temp_file, 'w') as file_handle:
        yaml.dump(data, file_handle)
    device_config = __salt__['napalm_yang.parse'](*models,
                                                  config=True,
                                                  profiles=profiles)
    log.debug('Parsed the config from the device:')
    log.debug(device_config)
    compliance_report = __salt__['napalm_yang.compliance_report'](device_config,
                                                                  *models,
                                                                  filepath=temp_file)
    log.debug('Compliance report:')
    log.debug(compliance_report)
    complies = compliance_report.get('complies', False)
    if complies:
        ret.update({
            'result': True,
            'comment': 'Already configured as required.',
            'changes': {},
            'pchanges': {}
        })
        log.debug('All good here.')
        return ret
    loaded_changes = __salt__['napalm_yang.load_config'](data,
                                                         **models,
                                                         profiles=profiles,
                                                         test=test,
                                                         debug=debug,
                                                         commit=commit,
                                                         replace=replace)
    log.debug('Loaded config result:')
    log.debug(loaded_changes)
    __salt__['file.remove'](temp_file)
    return salt.utils.napalm.loaded_ret(ret, loaded_changes, test, debug)
