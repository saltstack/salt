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

    if 'profile_attr' in kwargs:
        profile_attr = kwargs['profile_attr']
    else:
        profile_attr = None

    if 'profile_attrs' in kwargs:
        profile_attrs = kwargs['profile_attrs']
    else:
        profile_attrs = None

    if 'defaults' in kwargs:
        defaults = kwargs['defaults']
    else:
        defaults = None

    if '__salt__' in kwargs:
        __salt__ = kwargs['__salt__']
    else:
        __salt__ = {}

    if '__opts__' in kwargs:
        __opts__ = kwargs['__opts__']
    else:
        __opts__ = {}

    _options = {}
    for attr in attrs:
        if 'config.option' in __salt__:
            cfg = __salt__['config.option']
            c_cfg = cfg('{0}'.format(virtualname), {})
            if ret_config:
                ret_cfg = cfg('{0}.{1}'.format(ret_config, virtualname), {})
                if ret_cfg.get(attrs[attr], cfg('{0}.{1}.{2}'.format(ret_config, virtualname, attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr], cfg('{0}.{1}.{2}'.format(ret_config, virtualname, attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr], cfg('{0}.{1}'.format(virtualname, attrs[attr])))
            else:
                _attr = c_cfg.get(attrs[attr], cfg('{0}.{1}'.format(virtualname, attrs[attr])))
        else:
            cfg = __opts__
            c_cfg = cfg.get('{0}'.format(virtualname), {})
            if ret_config:
                ret_cfg = cfg.get('{0}.{1}'.format(ret_config, virtualname), {})
                if ret_cfg.get(attrs[attr], cfg.get('{0}.{1}.{2}'.format(ret_config, virtualname, attrs[attr]))):
                    _attr = ret_cfg.get(attrs[attr], cfg.get('{0}.{1}.{2}'.format(ret_config, virtualname, attrs[attr])))
                else:
                    _attr = c_cfg.get(attrs[attr], cfg.get('{0}.{1}'.format(virtualname, attrs[attr])))
            else:
                _attr = c_cfg.get(attrs[attr], cfg.get('{0}.{1}'.format(virtualname, attrs[attr])))
        if not _attr:
            if defaults:
                if attr in defaults:
                    log.info('Using default for {0} {1}'.format(virtualname, attr))
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
        if profile_attr in _options:
            log.info('Using profile {0}'.format(_options[profile_attr]))
            if 'config.option' in __salt__:
                creds = cfg(_options[profile_attr])
            else:
                creds = cfg.get(_options[profile_attr])
            if creds:
                for pattr in profile_attrs:
                    _options[pattr] = creds.get('{0}.{1}'.format(virtualname, profile_attrs[pattr]))
    return _options
