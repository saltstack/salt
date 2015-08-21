# -*- coding: utf-8 -*-
'''
Manage ini files
================

:maintainer: <akilesh1597@gmail.com>
:maturity: new
:depends: re
:platform: all

'''


__virtualname__ = 'ini'


def __virtual__():
    '''
    Only load if the ini module is available
    '''
    return __virtualname__ if 'ini.set_option' in __salt__ else False


def options_present(name, sections=None):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_present:
            - sections:
                test:
                  testkey: 'testval'
                  secondoption: 'secondvalue'
                test1:
                  testkey1: 'testval121'

    options present in file and not specified in sections
    dict will be untouched

    changes dict will contain the list of changes made
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'No anomaly detected'
           }
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('ini file {0} shall be validated for presence of '
                          'given options under their respective '
                          'sections').format(name)
        return ret
    changes = __salt__['ini.set_option'](name, sections)
    if 'error' in changes:
        ret['result'] = False
        ret['comment'] = 'Errors encountered. {0}'.format(changes['error'])
        ret['changes'] = {}
    else:
        ret['comment'] = 'Changes take effect'
        ret['changes'] = changes
    return ret


def options_absent(name, sections=None):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_absent:
            - sections:
                test:
                  - testkey
                  - secondoption
                test1:
                  - testkey1

    options present in file and not specified in sections
    dict will be untouched

    changes dict will contain the list of changes made
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'No anomaly detected'
           }
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('ini file {0} shall be validated for absence of '
                          'given options under their respective '
                          'sections').format(name)
        return ret
    sections = sections or {}
    for section, key in sections.iteritems():
        current_value = __salt__['ini.remove_option'](name, section, key)
        if not current_value:
            continue
        if section not in ret['changes']:
            ret['changes'].update({section: {}})
        ret['changes'][section].update({key: current_value})
        ret['comment'] = 'Changes take effect'
    return ret


def sections_present(name, sections=None):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_present:
            - sections:
                - section_one
                - section_two

    This will only create empty sections. To also create options, use
    options_present state

    options present in file and not specified in sections will be deleted
    changes dict will contain the sections that changed
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'No anomaly detected'
           }
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('ini file {0} shall be validated for presence of '
                          'given sections').format(name)
        return ret
    sections = {section_name: {} for section_name in sections or []}
    changes = __salt__['ini.set_option'](name, sections)
    if 'error' in changes:
        ret['result'] = False
        ret['changes'] = 'Errors encountered {0}'.format(changes['error'])
        return ret
    ret['changes'] = changes
    ret['comment'] = 'Changes take effect'
    return ret


def sections_absent(name, sections=None):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_absent:
            - sections:
                - test
                - test1

    options present in file and not specified in sections will be deleted
    changes dict will contain the sections that changed
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'No anomaly detected'
           }
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = ('ini file {0} shall be validated for absence of '
                          'given sections').format(name)
        return ret
    for section in sections or []:
        cur_section = __salt__['ini.remove_section'](name, section)
        if not cur_section:
            continue
        ret['changes'][section] = cur_section
        ret['comment'] = 'Changes take effect'
    return ret
