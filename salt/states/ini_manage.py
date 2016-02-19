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


def options_present(name, sections=None, separator='='):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_present:
            - separator: '='
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
        ret['result'] = True
        ret['comment'] = ''
        for section in sections or {}:
            section_name = ' in section ' + section if section != 'DEFAULT_IMPLICIT' else ''
            cur_section = __salt__['ini.get_section'](name, section, separator)
            for key in sections[section]:
                cur_value = cur_section.get(key)
                if cur_value == str(sections[section][key]):
                    ret['comment'] += 'Key {0}{1} unchanged.\n'.format(key, section_name)
                    continue
                ret['comment'] += 'Changed key {0}{1}.\n'.format(key, section_name)
                ret['result'] = None
        if ret['comment'] == '':
            ret['comment'] = 'No changes detected.'
        return ret
    changes = __salt__['ini.set_option'](name, sections, separator)
    if 'error' in changes:
        ret['result'] = False
        ret['comment'] = 'Errors encountered. {0}'.format(changes['error'])
        ret['changes'] = {}
    else:
        ret['comment'] = 'Changes take effect'
        ret['changes'] = changes
    return ret


def options_absent(name, sections=None, separator='='):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_absent:
            - separator: '='
            - sections:
                test:
                  testkey
                  secondoption
                test1:
                  testkey1

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
        ret['result'] = True
        ret['comment'] = ''
        for section in sections or {}:
            section_name = ' in section ' + section if section != 'DEFAULT_IMPLICIT' else ''
            cur_section = __salt__['ini.get_section'](name, section, separator)
            for key in sections[section]:
                cur_value = cur_section.get(key)
                if not cur_value:
                    ret['comment'] += 'Key {0}{1} does not exist.\n'.format(key, section_name)
                    continue
                ret['comment'] += 'Deleted key {0}{1}.\n'.format(key, section_name)
                ret['result'] = None
        if ret['comment'] == '':
            ret['comment'] = 'No changes detected.'
        return ret
    sections = sections or {}
    for section, key in sections.iteritems():
        current_value = __salt__['ini.remove_option'](name, section, key, separator)
        if not current_value:
            continue
        if section not in ret['changes']:
            ret['changes'].update({section: {}})
        ret['changes'][section].update({key: current_value})
        ret['comment'] = 'Changes take effect'
    return ret


def sections_present(name, sections=None, separator='='):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_present:
            - separator: '='
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
        ret['result'] = True
        ret['comment'] = ''
        for section in sections or {}:
            cur_section = __salt__['ini.get_section'](name, section, separator)
            if cmp(dict(sections[section]), cur_section) == 0:
                ret['comment'] += 'Section unchanged {0}.\n'.format(section)
                continue
            elif cur_section:
                ret['comment'] += 'Changed existing section {0}.\n'.format(section)
            else:
                ret['comment'] += 'Created new section {0}.\n'.format(section)
            ret['result'] = None
        if ret['comment'] == '':
            ret['comment'] = 'No changes detected.'
        return ret
    section_to_update = {}
    for section_name in sections or []:
        section_to_update.update({section_name: {}})
    changes = __salt__['ini.set_option'](name, section_to_update, separator)
    if 'error' in changes:
        ret['result'] = False
        ret['changes'] = 'Errors encountered {0}'.format(changes['error'])
        return ret
    ret['changes'] = changes
    ret['comment'] = 'Changes take effect'
    return ret


def sections_absent(name, sections=None, separator='='):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_absent:
            - separator: '='
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
        ret['result'] = True
        ret['comment'] = ''
        for section in sections or []:
            cur_section = __salt__['ini.get_section'](name, section, separator)
            if not cur_section:
                ret['comment'] += 'Section {0} does not exist.\n'.format(section)
                continue
            ret['comment'] += 'Deleted section {0}.\n'.format(section)
            ret['result'] = None
        if ret['comment'] == '':
            ret['comment'] = 'No changes detected.'
        return ret
    for section in sections or []:
        cur_section = __salt__['ini.remove_section'](name, section, separator)
        if not cur_section:
            continue
        ret['changes'][section] = cur_section
        ret['comment'] = 'Changes take effect'
    return ret
