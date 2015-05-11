# -*- coding: utf-8 -*-
'''
Returners Directory

:func:`get_returner_options` is a general purpose function that returners may
use to fetch their configuration options.
'''
from __future__ import absolute_import

import logging

log = logging.getLogger(__name__)


def get_returner_options(virtualname=None,
                         ret=None,
                         attrs=None,
                         **kwargs):
    '''
    Get the returner options from salt.

    :param str virtualname: The returner virtualname (as returned
        by __virtual__()
    :param ret: result of the module that ran. dit-like object

        May contain a `ret_config` key pointing to a string
        If a `ret_config` is specified, config options are read from::

            value.virtualname.option

        If not, config options are read from::

            value.virtualname.option

    :param attrs: options the returner wants to read
    :param __opts__: Optional dict-like object that contains a fallback config
        in case the param `__salt__` is not supplied.

        Defaults to empty dict.
    :param __salt__: Optional dict-like object that exposes the salt API.

        Defaults to empty dict.

        a) if __salt__ contains a 'config.option' configuration options,
            we infer the returner is being called from a state or module run ->
            config is a copy of the `config.option` function

        b) if __salt__ was not available, we infer that the returner is being
        called from the Salt scheduler, so we look for the
        configuration options in the param `__opts__`
        -> cfg is a copy for the __opts__ dictionary
    :param str profile_attr: Optional.

        If supplied, an overriding config profile is read from
        the corresponding key of `__salt__`.

    :param dict profile_attrs: Optional

        .. fixme:: only keys are read

        For each key in profile_attr, a value is read in the are
        used to fetch a value pointed by 'virtualname.%key' in
        the dict found thanks to the param `profile_attr`
    '''

    ret_config = _fetch_ret_config(ret)

    attrs = attrs or {}
    profile_attr = kwargs.get('profile_attr', None)
    profile_attrs = kwargs.get('profile_attrs', None)
    defaults = kwargs.get('defaults', None)
    __salt__ = kwargs.get('__salt__', {})
    __opts__ = kwargs.get('__opts__', {})

    # select the config source
    cfg = __salt__.get('config.option', __opts__)

    # browse the config for relevant options, store them in a dict
    _options = dict(
        _options_browser(
            cfg,
            ret_config,
            defaults,
            virtualname,
            attrs,
        )
    )

    # override some values with relevant profile options
    _options.update(
        _fetch_profile_opts(
            cfg,
            __salt__,
            virtualname,
            _options,
            profile_attr,
            profile_attrs
        )
    )

    return _options


def _fetch_ret_config(ret):
    """
    Fetches 'ret_config' if available.

    @see :func:`get_returner_options`
    """
    if not ret:
        return None
    if 'ret_config' not in ret:
        return ''
    return str(ret['ret_config'])


def _fetch_option(cfg, ret_config, virtualname, attr_name):
    """
    Fetch a given option value from the config.

    @see :func:`get_returner_options`
    """
    # c_cfg is a dictionary returned from config.option for
    # any options configured for this returner.
    if isinstance(cfg, dict):
        c_cfg = cfg
    else:
        c_cfg = cfg('{0}'.format(virtualname), {})

    default_cfg_key = '{0}.{1}'.format(virtualname, attr_name)
    if not ret_config:
        # Using the default configuration key
        if isinstance(cfg, dict):
            return c_cfg.get(default_cfg_key, cfg.get(default_cfg_key))
        else:
            return c_cfg.get(default_cfg_key, cfg(default_cfg_key))

    # Using ret_config to override the default configuration key
    ret_cfg = cfg('{0}.{1}'.format(ret_config, virtualname), {})

    override_default_cfg_key = '{0}.{1}.{2}'.format(
        ret_config,
        virtualname,
        attr_name,
    )
    override_cfg_default = cfg(override_default_cfg_key)

    # Look for the configuration item in the override location
    ret_override_cfg = ret_cfg.get(
        attr_name,
        override_cfg_default
    )
    if ret_override_cfg:
        return ret_override_cfg

    # if not configuration item found, fall back to the default location.
    return c_cfg.get(attr_name, cfg(default_cfg_key))


def _options_browser(cfg, ret_config, defaults, virtualname, options):
    """
    Iterator generating all duples ```option name -> value```

    @see :func:`get_returner_options`
    """

    for option in options:

        # default place for the option in the config
        value = _fetch_option(cfg, ret_config, virtualname, options[option])

        if value:
            yield option, value
            continue

        # Attribute not found, check for a default value
        if defaults:
            if option in defaults:
                log.info('Using default for %s %s', virtualname, option)
                yield option, defaults[option]
                continue

        # fallback (implicit else for all ifs)
        yield option, ''


def _fetch_profile_opts(
        cfg, virtualname,
        __salt__,
        _options,
        profile_attr,
        profile_attrs
    ):
    """
    Fetches profile specific options if applicable

    @see :func:`get_returner_options`

    :return: a options dict
    """

    if (not profile_attr) or (profile_attr not in _options):
        return {}

    # Using a profile and it is in _options

    creds = {}
    profile = _options[profile_attr]
    if profile:
        log.info('Using profile %s', profile)

        if 'config.option' in __salt__:
            creds = cfg.get(profile)
        else:
            creds = cfg(profile)

    if not creds:
        return {}

    return dict(
        (
            pattr,
            creds.get('{0}.{1}'.format(virtualname, profile_attrs[pattr]))
        )
        for pattr in profile_attrs
        )
