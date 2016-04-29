# -*- coding: utf-8 -*-
'''
Network Probes
===============

Configure RPM (JunOS)/SLA (Cisco) probes on the device via NAPALM proxy.

:codeauthor: Mircea Ulinic <mircea@cloudflare.com> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   linux

Dependencies
------------

- :doc:`napalm probes management module (salt.modules.napalm_probes) </ref/modules/all/salt.modules.napalm_probes>`

.. versionadded: Carbon
'''

from __future__ import absolute_import

# python std lib
import logging
log = logging.getLogger(__name__)

from copy import deepcopy
from json import loads, dumps

# salt modules
from salt.ext import six


# ----------------------------------------------------------------------------------------------------------------------
# state properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'probes'

# ----------------------------------------------------------------------------------------------------------------------
# global variables
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():

    '''
    This is a virtual state module called "probes".
    '''

    return True

# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _default_ret(name):

    '''
    Returns a default structure of the dictionary to be returned as output of the state functions.
    '''

    return {
        'name': name,
        'result': False,
        'changes': {},
        'comment': ''
    }


def _retrieve_rpm_probes():

    '''
    Will retrive the probes from the network device using salt module "probes" throught NAPALM proxy.
    '''

    return __salt__['probes.config']()


def _expand_probes(probes, defaults):

    '''
    Updates the probes dictionary with different levels of default values.
    '''

    expected_probes = dict()

    for probe_name, probe_test in six.iteritems(probes):
        if probe_name not in expected_probes.keys():
            expected_probes[probe_name] = dict()
        probe_defaults = probe_test.pop('defaults', {})
        for test_name, test_details in probe_test.iteritems():
            test_defaults = test_details.pop('defaults', {})
            expected_test_details = deepcopy(defaults)  # copy first the general defaults
            expected_test_details.update(probe_defaults)  # update with more specific defaults if any
            expected_test_details.update(test_defaults)  # update with the most specific defaults if possible
            expected_test_details.update(test_details)  # update with the actual config of the test
            if test_name not in expected_probes[probe_name].keys():
                expected_probes[probe_name][test_name] = expected_test_details

    return expected_probes


def _clean_probes(probes):

    '''
    Will remove empty and useless values from the probes dictionary.
    '''

    probes = _ordered_dict_to_dict(probes)  # make sure we are working only with dict-type
    probes_copy = deepcopy(probes)
    for probe_name, probe_tests in six.iteritems(probes_copy):
        if not probe_tests:
            probes.pop(probe_name)
            continue
        for test_name, test_params in probe_tests.iteritems():
            if not test_params:
                probes[probe_name].pop(test_name)
            if not probes.get(probe_name):
                probes.pop(probe_name)

    return True


def _compare_probes(configured_probes, expected_probes):

    '''
    Compares configured probes on the device with the expected configuration and returns the differences.nap
    '''

    new_probes = dict()
    update_probes = dict()
    remove_probes = dict()

    # noth configured => configure with expected probes
    if not configured_probes:
        return {
            'add': expected_probes
        }

    # noting expected => remove everything
    if not expected_probes:
        return {
            'remove': configured_probes
        }

    configured_probes_keys_set = set(configured_probes.keys())
    expected_probes_keys_set = set(expected_probes.keys())
    new_probes_keys_set = expected_probes_keys_set - configured_probes_keys_set
    remove_probes_keys_set = configured_probes_keys_set - expected_probes_keys_set

    # new probes
    for probe_name in new_probes_keys_set:
        new_probes[probe_name] = expected_probes.pop(probe_name)

    # old probes, to be removed
    for probe_name in remove_probes_keys_set:
        remove_probes[probe_name] = configured_probes.pop(probe_name)

    # common probes
    for probe_name, probe_tests in expected_probes.iteritems():
        configured_probe_tests = configured_probes.get(probe_name, {})
        configured_tests_keys_set = set(configured_probe_tests.keys())
        expected_tests_keys_set = set(probe_tests.keys())
        new_tests_keys_set = expected_tests_keys_set - configured_tests_keys_set
        remove_tests_keys_set = configured_tests_keys_set - expected_tests_keys_set

        # new tests for common probes
        for test_name in new_tests_keys_set:
            if probe_name not in new_probes.keys():
                new_probes[probe_name] = dict()
            new_probes[probe_name].update({
                test_name: probe_tests.pop(test_name)
            })
        # old tests for common probes
        for test_name in remove_tests_keys_set:
            if probe_name not in remove_probes.keys():
                remove_probes[probe_name] = dict()
            remove_probes[probe_name].update({
                test_name: configured_probe_tests.pop(test_name)
            })
        # common tests for common probes
        for test_name, test_params in probe_tests.iteritems():
            configured_test_params = configured_probe_tests.get(test_name, {})
            # if test params are different, probe goes to update probes dict!
            if test_params != configured_test_params:
                if probe_name not in update_probes.keys():
                    update_probes[probe_name] = dict()
                update_probes[probe_name].update({
                    test_name: test_params
                })

    return {
        'add': new_probes,
        'update': update_probes,
        'remove': remove_probes
    }


def _ordered_dict_to_dict(probes):

    '''Mandatory to be dict type in order to be used in the NAPALM Jinja template.'''

    return loads(dumps(probes))


def _set_rpm_probes(probes):

    '''
    Calls the Salt module "probes" to configure the probes on the device.
    '''

    return __salt__['probes.set_probes'](
        _ordered_dict_to_dict(probes)  # make sure this does not contain ordered dicts
    )


def _schedule_probes(probes):

    '''
    Calls the Salt module "probes" to schedule the configured probes on the device.
    '''

    return __salt__['probes.schedule_probes'](
        _ordered_dict_to_dict(probes)  # make sure this does not contain ordered dicts
    )


def _delete_rpm_probes(probes):

    '''
    Calls the Salt module "probes" to delete probes from the device.
    '''

    return __salt__['probes.delete_probes'](
        _ordered_dict_to_dict(probes)  # not mandatory, but let's make sure we catch all cases
    )


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def managed(name, probes, defaults=None):

    '''
    Ensure the networks device is configured as specified in the state SLS file.
    Probes not specified will be removed, while probes not confiured as expected will trigger config updates.

    :param probes:      Defines the probes as expected to be configured on the device.
    In order to ease the configuration and avoid repeating the same parameters for each probe,
    the next parameter (defaults) can be used, providing common characteristics.
    :param defaults:    Specifies common parameters for the probes.

    SLS Example:

    .. code-block:: yaml

        rpmprobes:
            probes.managed:
                - probes:
                    probe_name1:
                        probe1_test1:
                            source: 192.168.0.2
                            target: 192.168.0.1
                        probe1_test2:
                            target: 172.17.17.1
                        probe1_test3:
                            target: 8.8.8.8
                            probe_type: http-ping
                    probe_name2:
                        probe2_test1:
                            test_interval: 100
                - defaults:
                    target: 10.10.10.10
                    probe_count: 15
                    test_interval: 3
                    probe_type: icmp-ping

    In the probes configuration, the only mandatory attribute is *target* (specified either in probes configuration,
    either in the defaults dictionary).
    All the other parameters will use the operating system defaults, if not provided:

        * source:           Specifies the source IP Address to be used during the tests.
                            If not specified will use the IP Address of the logical interface loopback0.
        * target:           Destination IP Address.
        * probe_count:      Total number of probes per test (1..15). System defaults: 1 on both JunOS & Cisco.
        * probe_interval:   Delay between tests (0..86400 seconds). System defaults: 3 on JunOS, 5 on Cisco.
        * probe_type:       Probe request type. Available options:

                * icmp-ping
                * tcp-ping
                * udp-ping

    Using the example configuration above, after running the state, on the device will be configured 4 probes,
    with the following properties:

    .. code-block:: yaml

        probe_name1:
            probe1_test1:
                source: 192.168.0.2
                target: 192.168.0.1
                probe_count: 15
                test_interval: 3
                probe_type: icmp-ping
            probe1_test2:
                target: 172.17.17.1
                probe_count: 15
                test_interval: 3
                probe_type: icmp-ping
            probe1_test3:
                target: 8.8.8.8
                probe_count: 15
                test_interval: 3
                probe_type: http-ping
        probe_name2:
            probe2_test1:
                target: 10.10.10.10
                probe_count: 15
                test_interval: 3
                probe_type: icmp-ping
    '''

    ret = _default_ret(name)

    result = True
    comment = ''

    rpm_probes_config = _retrieve_rpm_probes()  # retrieves the RPM config from the device
    if not rpm_probes_config.get('result'):
        ret.update({
            'result': False,
            'comment': 'Cannot retrieve configurtion of the probes from the device: {reason}'.format(
                reason=rpm_probes_config.get('comment')
            )
        })
        return ret

    # build expect probes config dictionary
    # using default values
    configured_probes = rpm_probes_config.get('out', {})
    if not isinstance(defaults, dict):
        defaults = {}
    expected_probes = _expand_probes(probes, defaults)

    _clean_probes(configured_probes)  # let's remove the unnecessary data
    _clean_probes(expected_probes)  # and here

    # ----- Compare expected config with the existing config ---------------------------------------------------------->

    diff = _compare_probes(configured_probes, expected_probes)  # compute the diff

    # <---- Compare expected config with the existing config -----------------------------------------------------------

    # ----- Call set_probes and delete_probes as needed --------------------------------------------------------------->

    add_probes = diff.get('add')
    update_probes = diff.get('update')
    remove_probes = diff.get('remove')

    changes = {
        'added': _ordered_dict_to_dict(add_probes),
        'updated': _ordered_dict_to_dict(update_probes),
        'removed': _ordered_dict_to_dict(remove_probes)
    }

    ret.update({
        'changes': changes
    })

    if __opts__['test'] is True:
        ret.update({
            'result': None,
            'comment': 'Testing mode: the device configuration was not changed!'
        })
        return ret

    config_change_expected = False  # to check if something changed and a commit would be needed
    successfully_changed = True  # if the configuration was successfully changed in all cases (add/update/delete)

    if add_probes:
        added = _set_rpm_probes(add_probes)
        if added.get('result'):
            config_change_expected = True
        else:
            successfully_changed = False
            comment += '\nCannot define new probes: {reason}\n'.format(
                reason=added.get('comment')
            )

    if update_probes:
        updated = _set_rpm_probes(update_probes)
        if updated.get('result'):
            config_change_expected = True
        else:
            successfully_changed = False
            comment += '\nCannot update probes: {reason}\n'.format(
                reason=updated.get('comment')
            )

    if remove_probes:
        removed = _delete_rpm_probes(remove_probes)
        if removed.get('result'):
            config_change_expected = True
        else:
            successfully_changed = False
            comment += '\nCannot remove probes! {reason}\n'.format(
                reason=removed.get('comment')
            )

    # <---- Call set_probes and delete_probes as needed ----------------------------------------------------------------

    # ----- Try to save changes --------------------------------------------------------------------------------------->

    if config_change_expected:
        config_result, config_comment = __salt__['net.config_control']()
        result = config_result and successfully_changed
        # must also be able to commit & make sure we have applied all necessary changes
        comment += ('\n' + config_comment)

    # <---- Try to save changes ----------------------------------------------------------------------------------------

    # ----- Try to schedule the probes -------------------------------------------------------------------------------->

    schedule = _schedule_probes(add_probes)
    if schedule.get('result'):
        schedule_result, schedule_comment = __salt__['net.config_control']()
        result = result and schedule_result
        comment += ('\n' + schedule_comment)

    ret.update({
        'result': result,
        'comment': comment
    })

    return ret
