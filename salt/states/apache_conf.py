# -*- coding: utf-8 -*-
'''
Manage Apache Confs

.. versionadded:: Boron

Enable and disable apache confs.

.. code-block:: yaml

    Enable security conf:
        apache_conf.enable:
            - name: security

    Disable security conf:
        apache_conf.disable:
            - name: security
'''
from __future__ import absolute_import
from salt.ext.six import string_types

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if a2enconf is available.
    '''
    return 'apache_conf' if 'apache.a2enconf' in __salt__ and salt.utils.which('a2enconf') else False


def enable(name):
    '''
    Ensure an Apache conf is enabled.

    name
        Name of the Apache conf
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_enabled = __salt__['apache.check_conf_enabled']('{0}.load'.format(name))
    if not is_enabled:
        if __opts__['test']:
            msg = 'Apache conf {0} is set to be enabled.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = None
            ret['changes']['new'] = name
            ret['result'] = None
            return ret
        status = __salt__['apache.a2enconf'](name)['Status']
        if isinstance(status, string_types) and 'enabled' in status:
            ret['result'] = True
            ret['changes']['old'] = None
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to enable {0} Apache conf'.format(name)
            if isinstance(status, string_types):
                ret['comment'] = ret['comment'] + ' ({0})'.format(status)
            return ret
    else:
        ret['comment'] = '{0} already enabled.'.format(name)
    return ret


def disable(name):
    '''
    Ensure an Apache conf is disabled.

    name
        Name of the Apache conf
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_enabled = __salt__['apache.check_conf_enabled']('{0}.load'.format(name))
    if is_enabled:
        if __opts__['test']:
            msg = 'Apache conf {0} is set to be disabled.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = name
            ret['changes']['new'] = None
            ret['result'] = None
            return ret
        status = __salt__['apache.a2disconf'](name)['Status']
        if isinstance(status, string_types) and 'disabled' in status:
            ret['result'] = True
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to disable {0} Apache conf'.format(name)
            if isinstance(status, string_types):
                ret['comment'] = ret['comment'] + ' ({0})'.format(status)
            return ret
    else:
        ret['comment'] = '{0} already disabled.'.format(name)
    return ret
