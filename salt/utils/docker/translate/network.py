# -*- coding: utf-8 -*-
'''
Functions to translate input for network creation
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six

# Import helpers
from . import helpers

ALIASES = {
    'driver_opt': 'options',
    'driver_opts': 'options',
    'ipv6': 'enable_ipv6',
}
IPAM_ALIASES = {
    'ip_range': 'iprange',
    'aux_address': 'aux_addresses',
}
# ALIASES is a superset of IPAM_ALIASES
ALIASES.update(IPAM_ALIASES)
ALIASES_REVMAP = dict([(y, x) for x, y in six.iteritems(ALIASES)])

DEFAULTS = {'check_duplicate': True}


def _post_processing(kwargs, skip_translate, invalid):  # pylint: disable=unused-argument
    '''
    Additional network-specific post-translation processing
    '''
    # If any defaults were not expicitly passed, add them
    for item in DEFAULTS:
        if item not in kwargs:
            kwargs[item] = DEFAULTS[item]


# Functions below must match names of docker-py arguments
def driver(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_str(val)


def options(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_key_val(val, delimiter='=')


def ipam(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_dict(val)


def check_duplicate(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def internal(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def labels(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_labels(val)


def enable_ipv6(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def attachable(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


def ingress(val, **kwargs):  # pylint: disable=unused-argument
    return helpers.translate_bool(val)


# IPAM args
def ipam_driver(val, **kwargs):  # pylint: disable=unused-argument
    return driver(val, **kwargs)


def ipam_opts(val, **kwargs):  # pylint: disable=unused-argument
    return options(val, **kwargs)


def ipam_pools(val, **kwargs):  # pylint: disable=unused-argument
    if not hasattr(val, '__iter__') \
            or not all(isinstance(x, dict) for x in val):
        # Can't do a simple dictlist check because each dict may have more than
        # one element.
        raise SaltInvocationError('ipam_pools must be a list of dictionaries')
    skip_translate = kwargs.get('skip_translate', ())
    if not (skip_translate is True or 'ipam_pools' in skip_translate):
        _globals = globals()
        for ipam_dict in val:
            for key in list(ipam_dict):
                if skip_translate is not True and key in skip_translate:
                    continue
                if key in IPAM_ALIASES:
                    # Make sure we resolve aliases, since this wouldn't have
                    # been done within the individual IPAM dicts
                    ipam_dict[IPAM_ALIASES[key]] = ipam_dict.pop(key)
                    key = IPAM_ALIASES[key]
                if key in _globals:
                    ipam_dict[key] = _globals[key](ipam_dict[key])
    return val


def subnet(val, **kwargs):  # pylint: disable=unused-argument
    validate_ip_addrs = kwargs.get('validate_ip_addrs', True)
    val = helpers.translate_str(val)
    if validate_ip_addrs:
        helpers.validate_subnet(val)
    return val


def iprange(val, **kwargs):  # pylint: disable=unused-argument
    validate_ip_addrs = kwargs.get('validate_ip_addrs', True)
    val = helpers.translate_str(val)
    if validate_ip_addrs:
        helpers.validate_subnet(val)
    return val


def gateway(val, **kwargs):  # pylint: disable=unused-argument
    validate_ip_addrs = kwargs.get('validate_ip_addrs', True)
    val = helpers.translate_str(val)
    if validate_ip_addrs:
        helpers.validate_ip(val)
    return val


def aux_addresses(val, **kwargs):  # pylint: disable=unused-argument
    validate_ip_addrs = kwargs.get('validate_ip_addrs', True)
    val = helpers.translate_key_val(val, delimiter='=')
    if validate_ip_addrs:
        for address in six.itervalues(val):
            helpers.validate_ip(address)
    return val
