# -*- coding: utf-8 -*-
"""
Module for editing ini files through saltstack

use section as DEFAULT_IMPLICIT if your ini file does not have any section
for example /etc/sysctl.conf

@author: akilesh
"""
try:
    import re
    HAS_RE = True
except ImportError:
    HAS_RE = False


def __virtual__():
    if HAS_RE:
        return 'ini_manage'
    return False

comment_regexp = re.compile(r'^\s*#\s*(.*)')
section_regexp = re.compile(r'\s*\[(.+)\]\s*')
option_regexp1 = re.compile(r'\s*(.+)\s*(=)\s*(.+)\s*')
option_regexp2 = re.compile(r'\s*(.+)\s*(:)\s*(.+)\s*')


def ini_option_set(file_name, sections={}):
    """
    edit ini files

    returns a dictionary containing the changes made

    from cli:
    salt 'target' ini_manage.ini_option_set path_to_ini_file \
        '{"section_to_change": {"key": "value"}}'
    if value is an empty dict just the section will be added

    from api:
    import salt
    sc = salt.client.LocalClient()
    sc.cmd('target', 'ini_manage.ini_option_set',
           ['path_to_ini_file', '{"section_to_change": {"key": "value"}}'])
    """
    ret = {'file_name': file_name}
    inifile = ini.get_ini_file(file_name)
    if not inifile:
        ret.update({'error': 'ini file not found'})
        return ret
    changes = {}
    err_flag = False
    for section in sections:
        changes.update({section: {}})
        for option in sections[section]:
            try:
                current_value = ini_option_get(file_name, section, option)
                if not current_value == sections[section][option]:
                    inifile.update_section(section,
                                           option,
                                           sections[section][option])
            except:
                changes[section].update({option: 'error encountered'})
                err_flag = True
                break
            else:
                changes[section].update({option:
                                         {'before': current_value,
                                          'after': sections[section][option]}})
    if not err_flag:
        inifile.flush()
    ret.update({'changes': changes})
    return ret


def ini_option_get(file_name, section, option):
    """
    get value of a key from a section in a ini file

    from cli
    salt 'target' ini_manage.ini_option_get path_to_ini_file section_name \
        option_name

    from api:
    import salt
    sc = salt.client.LocalClient()
    sc.cmd('target', 'ini_manage.ini_option_get',
           [path_to_ini_file, section_name, option])
    """
    inifile = ini.get_ini_file(file_name)
    if inifile:
        opt = inifile.get_option(section, option)
        if opt:
            return opt.value


def ini_option_remove(file_name, section, option):
    """
    remove a key,value pair from a section in a ini file
    returns the value of the removed key

    from cli
    salt 'target' ini_manage.ini_option_remove path_to_ini_file section_name \
        option_name

    from api:
    import salt
    sc = salt.client.LocalClient()
    sc.cmd('target', 'ini_manage.ini_option_remove',
           [path_to_ini_file, section_name, option])
    """
    inifile = ini.get_ini_file(file_name)
    if inifile:
        opt = inifile.remove_option(section, option)
        if opt:
            inifile.flush()
            return opt.value


def ini_section_get(file_name, section):
    """
    get a section in a ini file
    returns the section as dictionary

    from cli
    salt 'target' ini_manage.ini_section_get path_to_ini_file section_name

    from api:
    import salt
    sc = salt.client.LocalClient()
    sc.cmd('target', 'ini_manage.ini_section_get',
           [path_to_ini_file, section_name])
    """
    inifile = ini.get_ini_file(file_name)
    if inifile:
        sect = inifile.get_section(section)
        if sect:
            return sect.contents()


def ini_section_remove(file_name, section):
    """
    remove a section in a ini file
    returns the removed section as dictionary

    from cli
    salt 'target' ini_manage.ini_section_remove path_to_ini_file section_name

    from api:
    import salt
    sc = salt.client.LocalClient()
    sc.cmd('target', 'ini_manage.ini_section_remove',
           [path_to_ini_file, section_name])
    """
    inifile = ini.get_ini_file(file_name)
    if inifile:
        sect = inifile.remove_section(section)
        if sect:
            inifile.flush()
            return sect.contents()


class section(list):
    def __init__(self, name):
        super(section, self).__init__()
        self.section_name = name

    def get_option(self, option_name):
        for item in self:
            if isinstance(item, option) and (item.name == option_name):
                return item

    def update_option(self, option_name, option_value=None, separator="="):
        option_to_update = self.get_option(option_name)
        if not option_to_update:
            option_to_update = option(option_name)
            self.append(option_to_update)
        option_to_update.value = option_value
        option_to_update.separator = separator

    def remove_option(self, option_name):
        option_to_remove = self.get_option(option_name)
        if option_to_remove:
            return self.pop(self.index(option_to_remove))

    def contents(self):
        contents = {}
        for item in self:
            try:
                contents.update({item.name: item.value})
            except:
                pass  # item was a comment
        return contents

    def __nonzero__(self):
        return True

    def __eq__(self, item):
        return (isinstance(item, self.__class__) and
                self.section_name == item.section_name)

    def __ne__(self, item):
        return not (isinstance(item, self.__class__) and
                    self.section_name == item.section_name)


class option(object):
    def __init__(self, name, value=None, separator="="):
        super(option, self).__init__()
        self.name = name
        self.value = value
        self.separator = separator

    def __eq__(self, item):
        return (isinstance(item, self.__class__) and
                self.name == item.name)

    def __ne__(self, item):
        return not (isinstance(item, self.__class__) and
                    self.name == item.name)


class ini(object):
    def __init__(self, file_name):
        super(ini, self).__init__()
        self.file_name = file_name

    def refresh(self):
        self.sections = []
        current_section = section('DEFAULT_IMPLICIT')
        self.sections.append(current_section)
        with open(self.file_name, 'r') as inifile:
            for line in inifile.readlines():
                if ini.iscomment(line):
                    current_section.append(ini.decrypt_comment(line))
                elif ini.isnewsection(line):
                    self.sections.append(ini.decrypt_section(line))
                    current_section = self.sections[-1]
                elif ini.isoption(line):
                    current_section.append(ini.decrypt_option(line))
        return self

    def flush(self):
        with open(self.file_name, 'w') as outfile:
            outfile.write(self.current_contents())

    def dump(self):
        print self.current_contents()

    def current_contents(self):
        file_contents = ''
        for section in self.sections:
            if not section.section_name == 'DEFAULT_IMPLICIT':
                file_contents += '[%s]\n' % section.section_name
            for item in section:
                if isinstance(item, option):
                    file_contents += '%s %s %s\n' % (item.name, item.separator,
                                                     item.value)
                else:
                    file_contents += '# %s\n' % item
            file_contents += '\n'
        return file_contents

    def get_section(self, section_name):
        for section in self.sections:
            if section.section_name == section_name:
                return section

    def get_option(self, section_name, option):
        section_to_get = self.get_section(section_name)
        if section_to_get:
            return section_to_get.get_option(option)

    def update_section(self, section_name, option_name=None,
                       option_value=None, separator="="):
        section_to_update = self.get_section(section_name)
        if not section_to_update:
            section_to_update = section(section_name)
            self.sections.append(section_to_update)
        if option_name:
            section_to_update.update_option(option_name, option_value,
                                            separator)

    def remove_section(self, section_name):
        section_to_remove = self.get_section(section_name)
        if section_to_remove:
            return self.sections.pop(self.sections.index(section_to_remove))

    def remove_option(self, section_name, option_name):
        section_to_update = self.get_section(section_name)
        if section_to_update:
            return section_to_update.remove_option(option_name)

    @staticmethod
    def decrypt_comment(line):
        ma = re.match(comment_regexp, line)
        return ma.group(1).strip()

    @staticmethod
    def decrypt_section(line):
        ma = re.match(section_regexp, line)
        return section(ma.group(1).strip())

    @staticmethod
    def decrypt_option(line):
        ma = re.match(option_regexp1, line)
        if not ma:
            ma = re.match(option_regexp2, line)
        return option(ma.group(1).strip(), ma.group(3).strip(),
                      ma.group(2).strip())

    @staticmethod
    def iscomment(line):
        return re.match(comment_regexp, line)

    @staticmethod
    def isnewsection(line):
        return re.match(section_regexp, line)

    @staticmethod
    def isoption(line):
        return re.match(option_regexp1, line) or re.match(option_regexp2, line)

    @staticmethod
    def get_ini_file(file_name):
        try:
            return ini(file_name).refresh()
        except:
            return
