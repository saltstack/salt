# -*- coding: utf-8 -*-
'''
Management of languages/locales
===============================

Manage the available locales and the system default:

.. code-block:: yaml

    us_locale:
      locale.present:
        - name: en_US.UTF-8

    default_locale:
      locale.system:
        - name: en_US.UTF-8
        - require:
          - locale: us_locale
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
from salt.exceptions import CommandExecutionError


def __virtual__():
    '''
    Only load if the locale module is available in __salt__
    '''
    if 'locale.get_locale' in __salt__:
        return True
    else:
        return (False, __salt__.missing_fun_string('locale.get_locale'))


def system(name):
    '''
    Set the locale for the system

    name
        The name of the locale to use
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    try:
        if __salt__['locale.get_locale']() == name:
            ret['result'] = True
            ret['comment'] = 'System locale {0} already set'.format(name)
            return ret
        if __opts__['test']:
            ret['comment'] = 'System locale {0} needs to be set'.format(name)
            return ret
        if __salt__['locale.set_locale'](name):
            ret['changes'] = {'locale': name}
            ret['result'] = True
            ret['comment'] = 'Set system locale {0}'.format(name)
            return ret
        else:
            ret['result'] = False
            ret['comment'] = 'Failed to set system locale to {0}'.format(name)
            return ret
    except CommandExecutionError as err:
        ret['result'] = False
        ret['comment'] = 'Failed to set system locale: {0}'.format(err)
        return ret


def present(name):
    '''
    Generate a locale if it is not present

    .. versionadded:: 2014.7.0

    name
        The name of the locale to be present. Some distributions require the
        charmap to be specified as part of the locale at this point.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if __salt__['locale.avail'](name):
        ret['result'] = True
        ret['comment'] = 'Locale {0} is already present'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Locale {0} needs to be generated'.format(name)
        return ret
    if __salt__['locale.gen_locale'](name):
        ret['changes'] = {'locale': name}
        ret['result'] = True
        ret['comment'] = 'Generated locale {0}'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to generate locale {0}'.format(name)
        return ret
