# -*- coding: utf-8 -*-
'''
Manage ini files
================

:maintainer: <akilesh1597@gmail.com>
:maturity: new
:depends: re
:platform: all

use section as DEFAULT_IMPLICIT if your ini file does not have any section
for example /etc/sysctl.conf
'''


__virtualname__ = 'ini'


def __virtual__():
    '''
    Only load if the mysql module is available
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
    for section in sections or {}:
        for key in sections[section]:
            current_value = __salt__['ini.get_option'](name,
                                                       section,
                                                       key)
            # Test if the change is necessary
            if current_value == str(sections[section][key]):
                continue

            ret['changes'] = __salt__['ini.set_option'](name,
                                                        sections)
            if 'error' in ret['changes']:
                ret['result'] = False
                ret['comment'] = 'Errors encountered. {0}'.\
                    format(ret['changes'])
                ret['changes'] = {}
            else:
                ret['comment'] = 'Changes take effect'
    return ret


def options_absent(name, sections=None):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.options_present:
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
    for section in sections or {}:
        for key in sections[section]:
            current_value = __salt__['ini.remove_option'](name,
                                                          section,
                                                          key)
            if not current_value:
                continue
            if section not in ret['changes']:
                ret['changes'].update({section: {}})
            ret['changes'][section].update({key: {'before': current_value,
                                                  'after': None}})
            ret['comment'] = 'Changes take effect'
    return ret


def sections_present(name, sections=None):
    '''
    .. code-block:: yaml

        /home/saltminion/api-paste.ini:
          ini.sections_present:
            - sections:
                test:
                  testkey: testval
                  secondoption: secondvalue
                test1:
                  testkey1: 'testval121'

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
        ret['comment'] = ('ini file {0} shall be validated for '
                          'presence of given sections with the '
                          'exact contents').format(name)
        return ret
    for section in sections or {}:
        cur_section = __salt__['ini.get_section'](name, section)
        if _same(cur_section, sections[section]):
            continue
        __salt__['ini.remove_section'](name, section)
        changes = __salt__['ini.set_option'](name, {section:
                                                    sections[section]},
                                                    summary=False)
        if 'error' in changes:
            ret['result'] = False
            ret['changes'] = 'Errors encountered'
            return ret
        ret['changes'][section] = {'before': {section: cur_section},
                                   'after': changes['changes']}
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
        ret['changes'][section] = {'before': cur_section,
                                   'after': None}
        ret['comment'] = 'Changes take effect'
    return ret


def _same(dict1, dict2):
    diff = _DictDiffer(dict1, dict2)
    return not (diff.added() or diff.removed() or diff.changed())


class _DictDiffer(object):
    def __init__(self, current_dict, past_dict):
        self.current_dict = current_dict
        self.past_dict = past_dict
        self.set_current = set(current_dict)
        self.set_past = set(past_dict)
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(o for o in self.intersect if
                   self.past_dict[o] != self.current_dict[o])
