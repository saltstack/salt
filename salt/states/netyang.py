# -*- coding: utf-8 -*-
'''
NAPALM YANG state
=================

Manage the configuration of network devices according to
the YANG models (OpenConfig/IETF).

.. versionadded:: 2017.7.0

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
from __future__ import absolute_import, print_function, unicode_literals
import logging

log = logging.getLogger(__file__)

# Import third party libs
try:
    # pylint: disable=unused-import
    import napalm_yang
    HAS_NAPALM_YANG = True
    # pylint: enable=unused-import
except ImportError:
    HAS_NAPALM_YANG = False

# Import salt modules
import salt.utils.files
import salt.utils.json
import salt.utils.napalm
import salt.utils.stringutils
import salt.utils.yaml

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

    compliance_report: ``False``
        Return the compliance report in the comment.
        The compliance report structured object can be found however
        in the ``pchanges`` field of the output (not displayed on the CLI).

        .. versionadded:: 2017.7.3

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

        {%- set expected_config =  pillar.get('openconfig_interfaces_cfg') -%}
        interfaces_config:
          napalm_yang.managed:
            - data: {{ expected_config | json }}
            - models:
              - models.openconfig_interfaces
            - debug: true

    Pillar example:

    .. code-block:: yaml

        openconfig_interfaces_cfg:
          _kwargs:
            filter: true
          interfaces:
            interface:
              Et1:
                config:
                  mtu: 9000
              Et2:
                config:
                  description: "description example"
    '''
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]
    ret = salt.utils.napalm.default_ret(name)
    test = kwargs.get('test', False) or __opts__.get('test', False)
    debug = kwargs.get('debug', False) or __opts__.get('debug', False)
    commit = kwargs.get('commit', True) or __opts__.get('commit', True)
    replace = kwargs.get('replace', False) or __opts__.get('replace', False)
    return_compliance_report = kwargs.get('compliance_report', False) or __opts__.get('compliance_report', False)
    profiles = kwargs.get('profiles', [])
    temp_file = __salt__['temp.file']()
    log.debug('Creating temp file: %s', temp_file)
    if 'to_dict' not in data:
        data = {'to_dict': data}
    data = [data]
    with salt.utils.files.fopen(temp_file, 'w') as file_handle:
        salt.utils.yaml.safe_dump(
            salt.utils.json.loads(salt.utils.json.dumps(data)),
            file_handle,
            encoding='utf-8'
        )
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
            'comment': 'Already configured as required.'
        })
        log.debug('All good here.')
        return ret
    log.debug('Does not comply, trying to generate and load config')
    data = data[0]['to_dict']
    if '_kwargs' in data:
        data.pop('_kwargs')
    loaded_changes = __salt__['napalm_yang.load_config'](data,
                                                         *models,
                                                         profiles=profiles,
                                                         test=test,
                                                         debug=debug,
                                                         commit=commit,
                                                         replace=replace)
    log.debug('Loaded config result:')
    log.debug(loaded_changes)
    __salt__['file.remove'](temp_file)
    loaded_changes['compliance_report'] = compliance_report
    return salt.utils.napalm.loaded_ret(ret,
                                        loaded_changes,
                                        test,
                                        debug,
                                        opts=__opts__,
                                        compliance_report=return_compliance_report)


def configured(name,
               data,
               *models,
               **kwargs):
    '''
    Configure the network device, given the input data strucuted
    according to the YANG models.

    .. note::
        The main difference between this function and ``managed``
        is that the later generates and loads the configuration
        only when there are differences between the existing
        configuration on the device and the expected
        configuration. Depending on the platform and hardware
        capabilities, one could be more optimal than the other.
        Additionally, the output of the ``managed`` is diferent,
        in such a way that the ``pchange`` field in the output
        contains structured data, rather than text.

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

        {%- set expected_config =  pillar.get('openconfig_interfaces_cfg') -%}
        interfaces_config:
          napalm_yang.configured:
            - data: {{ expected_config | json }}
            - models:
              - models.openconfig_interfaces
            - debug: true

    Pillar example:

    .. code-block:: yaml

        openconfig_interfaces_cfg:
          _kwargs:
            filter: true
          interfaces:
            interface:
              Et1:
                config:
                  mtu: 9000
              Et2:
                config:
                  description: "description example"
    '''
    if isinstance(models, tuple) and isinstance(models[0], list):
        models = models[0]
    ret = salt.utils.napalm.default_ret(name)
    test = kwargs.get('test', False) or __opts__.get('test', False)
    debug = kwargs.get('debug', False) or __opts__.get('debug', False)
    commit = kwargs.get('commit', True) or __opts__.get('commit', True)
    replace = kwargs.get('replace', False) or __opts__.get('replace', False)
    profiles = kwargs.get('profiles', [])
    if '_kwargs' in data:
        data.pop('_kwargs')
    loaded_changes = __salt__['napalm_yang.load_config'](data,
                                                         *models,
                                                         profiles=profiles,
                                                         test=test,
                                                         debug=debug,
                                                         commit=commit,
                                                         replace=replace)
    return salt.utils.napalm.loaded_ret(ret, loaded_changes, test, debug)
