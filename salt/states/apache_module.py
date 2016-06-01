# -*- coding: utf-8 -*-
'''
Manage Apache Modules

.. versionadded:: 2014.7.0

Enable and disable apache modules.

.. code-block:: yaml

    Enable cgi module:
        apache_module.enabled:
            - name: cgi

    Disable cgi module:
        apache_module.disabled:
            - name: cgi
'''
from __future__ import absolute_import
from salt.ext.six import string_types

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if a2enmod is available.
    '''
    return 'apache_module' if 'apache.a2enmod' in __salt__ else False


def enabled(name):
    '''
    Ensure an Apache module is enabled.

    name
        Name of the Apache module
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_enabled = __salt__['apache.check_mod_enabled'](name)
    if not is_enabled:
        if __opts__['test']:
            msg = 'Apache module {0} is set to be enabled.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = None
            ret['changes']['new'] = name
            ret['result'] = None
            return ret
        status = __salt__['apache.a2enmod'](name)['Status']
        if isinstance(status, string_types) and 'enabled' in status:
            ret['result'] = True
            ret['changes']['old'] = None
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to enable {0} Apache module'.format(name)
            if isinstance(status, string_types):
                ret['comment'] = ret['comment'] + ' ({0})'.format(status)
            return ret
    else:
        ret['comment'] = '{0} already enabled.'.format(name)
    return ret


def enable(name):
    '''
    Ensure an Apache module is enabled.

    name
        Name of the Apache module
    '''
    salt.utils.warn_until(
        'Carbon',
        'This functionality has been deprecated; use "apache_module.enabled" '
        'instead.'
    )

    return enabled(name)


def disabled(name):
    '''
    Ensure an Apache module is disabled.

    name
        Name of the Apache module
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_enabled = __salt__['apache.check_mod_enabled'](name)
    if is_enabled:
        if __opts__['test']:
            msg = 'Apache module {0} is set to be disabled.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = name
            ret['changes']['new'] = None
            ret['result'] = None
            return ret
        status = __salt__['apache.a2dismod'](name)['Status']
        if isinstance(status, string_types) and 'disabled' in status:
            ret['result'] = True
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to disable {0} Apache module'.format(name)
            if isinstance(status, string_types):
                ret['comment'] = ret['comment'] + ' ({0})'.format(status)
            return ret
    else:
        ret['comment'] = '{0} already disabled.'.format(name)
    return ret


def disable(name):
    '''
    Ensure an Apache module is disabled.

    name
        Name of the Apache module
    '''
    salt.utils.warn_until(
        'Carbon',
        'This functionality has been deprecated; use "apache_module.disabled" '
        'instead.'
    )

    return disabled(name)
