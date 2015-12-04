# -*- coding: utf-8 -*-
'''
Manage Apache Sites

.. versionadded:: Boron

Enable and disable apache sites.

.. code-block:: yaml

    Enable default site:
        apache_site.enable:
            - name: default

    Disable default site:
        apache_site.disable:
            - name: default
'''
from __future__ import absolute_import
from salt.ext.six import string_types


def __virtual__():
    '''
    Only load if a2ensite is available.
    '''
    return 'apache_site' if 'apache.a2ensite' in __salt__ else False


def enable(name):
    '''
    Ensure an Apache site is enabled.

    name
        Name of the Apache site
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_enabled = __salt__['apache.check_site_enabled']('{0}.load'.format(name))
    if not is_enabled:
        if __opts__['test']:
            msg = 'Apache site {0} is set to be enabled.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = None
            ret['changes']['new'] = name
            ret['result'] = None
            return ret
        status = __salt__['apache.a2ensite'](name)['Status']
        if isinstance(status, string_types) and 'enabled' in status:
            ret['result'] = True
            ret['changes']['old'] = None
            ret['changes']['new'] = name
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to enable {0} Apache site'.format(name)
            if isinstance(status, string_types):
                ret['comment'] = ret['comment'] + ' ({0})'.format(status)
            return ret
    else:
        ret['comment'] = '{0} already enabled.'.format(name)
    return ret


def disable(name):
    '''
    Ensure an Apache site is disabled.

    name
        Name of the Apache site
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    is_enabled = __salt__['apache.check_site_enabled']('{0}.load'.format(name))
    if is_enabled:
        if __opts__['test']:
            msg = 'Apache site {0} is set to be disabled.'.format(name)
            ret['comment'] = msg
            ret['changes']['old'] = name
            ret['changes']['new'] = None
            ret['result'] = None
            return ret
        status = __salt__['apache.a2dissite'](name)['Status']
        if isinstance(status, string_types) and 'disabled' in status:
            ret['result'] = True
            ret['changes']['old'] = name
            ret['changes']['new'] = None
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to disable {0} Apache site'.format(name)
            if isinstance(status, string_types):
                ret['comment'] = ret['comment'] + ' ({0})'.format(status)
            return ret
    else:
        ret['comment'] = '{0} already disabled.'.format(name)
    return ret
