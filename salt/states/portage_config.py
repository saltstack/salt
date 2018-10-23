# -*- coding: utf-8 -*-
'''
Management of Portage package configuration on Gentoo
=====================================================

A state module to manage Portage configuration on Gentoo

.. code-block:: yaml

    salt:
        portage_config.flags:
            - use:
                - openssl
'''
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    '''
    Only load if the portage_config module is available in __salt__
    '''
    return 'portage_config' if 'portage_config.get_missing_flags' in __salt__ else False


def mod_init(low):
    '''
    Enforce a nice structure on the configuration files.
    '''
    try:
        __salt__['portage_config.enforce_nice_config']()
    except Exception:
        return False
    return True


def _flags_helper(conf, atom, new_flags, test=False):
    try:
        new_flags = __salt__['portage_config.get_missing_flags'](conf, atom, new_flags)
    except Exception:
        import traceback
        return {'result': False, 'comment': traceback.format_exc()}
    if new_flags:
        old_flags = __salt__['portage_config.get_flags_from_package_conf'](conf, atom)
        if not test:
            __salt__['portage_config.append_to_package_conf'](conf, atom, new_flags)
        return {'result': True, 'changes': {'old': old_flags, 'new': new_flags}}
    return {'result': None}


def _mask_helper(conf, atom, test=False):
    try:
        is_present = __salt__['portage_config.is_present'](conf, atom)
    except Exception:
        import traceback
        return {'result': False, 'comment': traceback.format_exc()}
    if not is_present:
        if not test:
            __salt__['portage_config.append_to_package_conf'](conf, string=atom)
        return {'result': True}
    return {'result': None}


def flags(name,
          use=None,
          accept_keywords=None,
          env=None,
          license=None,
          properties=None,
          unmask=False,
          mask=False):
    '''
    Enforce the given flags on the given package or ``DEPEND`` atom.

    .. warning::

        In most cases, the affected package(s) need to be rebuilt in
        order to apply the changes.

    name
        The name of the package or its DEPEND atom
    use
        A list of ``USE`` flags
    accept_keywords
        A list of keywords to accept. ``~ARCH`` means current host arch, and will
        be translated into a line without keywords
    env
        A list of environment files
    license
        A list of accepted licenses
    properties
        A list of additional properties
    unmask
        A boolean to unmask the package
    mask
        A boolean to mask the package
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': True}

    if use:
        result = _flags_helper('use', name, use, __opts__['test'])
        if result['result']:
            ret['changes']['use'] = result['changes']
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if accept_keywords:
        result = _flags_helper('accept_keywords', name, accept_keywords, __opts__['test'])
        if result['result']:
            ret['changes']['accept_keywords'] = result['changes']
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if env:
        result = _flags_helper('env', name, env, __opts__['test'])
        if result['result']:
            ret['changes']['env'] = result['changes']
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if license:
        result = _flags_helper('license', name, license, __opts__['test'])
        if result['result']:
            ret['changes']['license'] = result['changes']
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if properties:
        result = _flags_helper('properties', name, properties, __opts__['test'])
        if result['result']:
            ret['changes']['properties'] = result['changes']
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if mask:
        result = _mask_helper('mask', name, __opts__['test'])
        if result['result']:
            ret['changes']['mask'] = 'masked'
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if unmask:
        result = _mask_helper('unmask', name, __opts__['test'])
        if result['result']:
            ret['changes']['unmask'] = 'unmasked'
        elif result['result'] is False:
            ret['result'] = False
            ret['comment'] = result['comment']
            return ret

    if __opts__['test'] and not ret['result']:
        ret['result'] = None

    return ret
