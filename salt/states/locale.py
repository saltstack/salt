# -*- coding: utf-8 -*-
'''
Management of languages/locales
==============================+

The locale can be managed for the system:

.. code-block:: yaml

    en_US.UTF-8:
      locale.system
'''


def __virtual__():
    '''
    Only load if the locale module is available in __salt__
    '''
    return 'locale' if 'locale.get_locale' in __salt__ else False


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
        ret['comment'] = 'Failed to set system locale'
        return ret
