# -*- coding: utf-8 -*-
'''
Returners Directory
'''

import logging
log = logging.getLogger(__name__)


def get_returner_options(virtualname=None,
                         ret=None,
                         attrs=None,
                         **kwargs):
    '''
    Get the returner options from salt.
    '''

    if ret:
        ret_config = '{0}'.format(ret['ret_config']) if 'ret_config' in ret else ''
    else:
        ret_config = None

    profile_attr = kwargs.get('profile_attr', None)
    profile_attrs = kwargs.get('profile_attrs', None)
    defaults = kwargs.get('defaults', None)
    __salt__ = kwargs.get('__salt__', {})
    __opts__ = kwargs.get('__opts__', {})

    _options = {}

    for attr in attrs:
        if 'config.option' in __salt__:
            # Look for the configuration options in __salt__
            # most likely returner is being called from a state or module run

            # cfg is a copy of the config.option function
            cfg = __salt__['config.option']

            # c_cfg is a dictionary returned from config.option for
            # any options configured for this returner.
            c_cfg = cfg('{0}'.format(virtualname), {})
            if ret_config:
                # Using ret_config to override the default configuration key
                ret_cfg = cfg('{0}.{1}'.format(ret_config, virtualname), {})

                # Look for the configuration item in the override location
                # if not found, fall back to the default location.
                if ret_cfg.get(attrs[attr],
                               cfg('{0}.{1}.{2}'.format(ret_config,
                                                        virtualname,
                                                        attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr],
                                        cfg('{0}.{1}.{2}'.format(ret_config,
                                                                 virtualname,
                                                                 attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr],
                                      cfg('{0}.{1}'.format(virtualname,
                                                           attrs[attr])))
            else:
                # Using the default configuration key
                _attr = c_cfg.get(attrs[attr],
                                  cfg('{0}.{1}'.format(virtualname,
                                                       attrs[attr])))
        else:
            # __salt__ is unavailable, most likely the returner
            # is being called from the Salt scheduler so
            # look for the configuration options in __opts__

            # cfg is a copy for the __opts_ dictionary
            cfg = __opts__

            # c_cfg is a dictionary found in the cfg dictionary
            # otherwise an empty dict.
            c_cfg = cfg.get('{0}'.format(virtualname), {})

            if ret_config:
                # Using ret_config to override the default configuration key
                ret_cfg = cfg.get('{0}.{1}'.format(ret_config, virtualname), {})

                # Look for the configuration item in the override location
                # if not found, fall back to the default location.
                if ret_cfg.get(attrs[attr],
                               cfg.get('{0}.{1}.{2}'.format(ret_config,
                                                            virtualname,
                                                            attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr],
                                        cfg.get('{0}.{1}.{2}'.format(ret_config,
                                                                     virtualname,
                                                                     attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr],
                                      cfg.get('{0}.{1}'.format(virtualname,
                                                               attrs[attr])))
            else:
                # Using the default configuration key.
                _attr = c_cfg.get(attrs[attr],
                                  cfg.get('{0}.{1}'.format(virtualname,
                                                           attrs[attr])))
        if not _attr:
            # Attribute not found, check for a default value
            if defaults:
                if attr in defaults:
                    log.info('Using default for {0} {1}'.format(virtualname,
                                                                attr))
                    _options[attr] = defaults[attr]
                    continue
                else:
                    _options[attr] = ''
                    continue
            else:
                _options[attr] = ''
                continue
        _options[attr] = _attr

    if profile_attr:
        # Using a profile
        if profile_attr in _options:
            log.info('Using profile {0}'.format(_options[profile_attr]))
            if 'config.option' in __salt__:
                creds = cfg(_options[profile_attr])
            else:
                creds = cfg.get(_options[profile_attr])
            if creds:
                for pattr in profile_attrs:
                    _options[pattr] = creds.get('{0}.{1}'.format(virtualname,
                                                                 profile_attrs[pattr]))
    return _options
