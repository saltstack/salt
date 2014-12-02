# -*- coding: utf-8 -*-
'''
Edit ini files

:maintainer: <akilesh1597@gmail.com>
:maturity: new
:depends: re
:platform: all

Use section as DEFAULT_IMPLICIT if your ini file does not have any section
(for example /etc/sysctl.conf)
'''

# Import Python libs
from __future__ import print_function
from __future__ import absolute_import
import re

# Import Salt libs
import salt.utils

__virtualname__ = 'ini'


def __virtual__():
    '''
    Rename to ini
    '''
    return __virtualname__

comment_regexp = re.compile(r'^\s*#\s*(.*)')
section_regexp = re.compile(r'\s*\[(.+)\]\s*')
option_regexp1 = re.compile(r'\s*(.+?)\s*(=)(.*)')
option_regexp2 = re.compile(r'\s*(.+?)\s*(:)(.*)')


def set_option(file_name, sections=None, summary=True):
    '''
    Edit an ini file, replacing one or more sections. Returns a dictionary
    containing the changes made.

    file_name
        path of ini_file

    sections : None
        A dictionary representing the sections to be edited ini file

    Set ``summary=False`` if return data need not have previous option value

    API Example:

    .. code-block:: python

        import salt
        sc = salt.client.get_local_client()
        sc.cmd('target', 'ini.set_option',
               ['path_to_ini_file', '{"section_to_change": {"key": "value"}}'])

    CLI Example:

    .. code-block:: bash

        salt '*' ini.set_option /path/to/ini '{section_foo: {key: value}}'
    '''
    if sections is None:
        sections = {}
    ret = {'file_name': file_name}
    inifile = _Ini.get_ini_file(file_name)
    if not inifile:
        ret.update({'error': 'ini file not found'})
        return ret
    changes = {}
    err_flag = False
    for section in sections:
        changes.update({section: {}})
        for option in sections[section]:
            try:
                current_value = get_option(file_name, section, option)
                if not current_value == sections[section][option]:
                    inifile.update_section(section,
                                           option,
                                           sections[section][option])
                    changes[section].update(
                        {
                            option: {
                                'before': current_value,
                                'after': sections[section][option]
                            }
                        })
                    if not summary:
                        changes[section].update({option:
                                                 sections[section][option]})
            except Exception:
                ret.update({'error':
                            'while setting option {0} in section {1}'.
                            format(option, section)})
                err_flag = True
                break
    if not err_flag:
        inifile.flush()
    ret.update({'changes': changes})
    return ret


def get_option(file_name, section, option):
    '''
    Get value of a key from a section in an ini file. Returns ``None`` if
    no matching key was found.

    API Example:

    .. code-block:: python

        import salt
        sc = salt.client.get_local_client()
        sc.cmd('target', 'ini.get_option',
               [path_to_ini_file, section_name, option])

    CLI Example:

    .. code-block:: bash

        salt '*' ini.get_option /path/to/ini section_name option_name
    '''
    inifile = _Ini.get_ini_file(file_name)
    if inifile:
        opt = inifile.get_option(section, option)
        if opt:
            return opt.value


def remove_option(file_name, section, option):
    '''
    Remove a key/value pair from a section in an ini file. Returns the value of
    the removed key, or ``None`` if nothing was removed.

    API Example:

    .. code-block:: python

        import salt
        sc = salt.client.get_local_client()
        sc.cmd('target', 'ini.remove_option',
               [path_to_ini_file, section_name, option])

    CLI Example:

    .. code-block:: bash

        salt '*' ini.remove_option /path/to/ini section_name option_name
    '''
    inifile = _Ini.get_ini_file(file_name)
    if inifile:
        opt = inifile.remove_option(section, option)
        if opt:
            inifile.flush()
            return opt.value


def get_section(file_name, section):
    '''
    Retrieve a section from an ini file. Returns the section as dictionary. If
    the section is not found, an empty dictionary is returned.

    API Example:

    .. code-block:: python

        import salt
        sc = salt.client.get_local_client()
        sc.cmd('target', 'ini.get_section',
               [path_to_ini_file, section_name])

    CLI Example:

    .. code-block:: bash

        salt '*' ini.get_section /path/to/ini section_name
    '''
    inifile = _Ini.get_ini_file(file_name)
    if inifile:
        sect = inifile.get_section(section)
        if sect:
            return sect.contents()
    return {}


def remove_section(file_name, section):
    '''
    Remove a section in an ini file. Returns the removed section as dictionary,
    or ``None`` if nothing was removed.

    API Example:

    .. code-block:: python

        import salt
        sc = salt.client.get_local_client()
        sc.cmd('target', 'ini.remove_section',
               [path_to_ini_file, section_name])

    CLI Example:

    .. code-block:: bash

        salt '*' ini.remove_section /path/to/ini section_name
    '''
    inifile = _Ini.get_ini_file(file_name)
    if inifile:
        sect = inifile.remove_section(section)
        if sect:
            inifile.flush()
            return sect.contents()


class _Section(list):
    def __init__(self, name):
        super(_Section, self).__init__()
        self.section_name = name

    def get_option(self, option_name):
        for item in self:
            if isinstance(item, _Option) and (item.name == option_name):
                return item

    def update_option(self, option_name, option_value=None, separator="="):
        option_to_update = self.get_option(option_name)
        if not option_to_update:
            option_to_update = _Option(option_name)
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
            except Exception:
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


class _Option(object):
    def __init__(self, name, value=None, separator="="):
        super(_Option, self).__init__()
        self.name = name
        self.value = value
        self.separator = separator

    def __eq__(self, item):
        return (isinstance(item, self.__class__) and
                self.name == item.name)

    def __ne__(self, item):
        return not (isinstance(item, self.__class__) and
                    self.name == item.name)


class _Ini(object):
    def __init__(self, file_name):
        super(_Ini, self).__init__()
        self.file_name = file_name

    def refresh(self):
        self.sections = []
        current_section = _Section('DEFAULT_IMPLICIT')
        self.sections.append(current_section)
        with salt.utils.fopen(self.file_name, 'r') as inifile:
            previous_line = None
            for line in inifile.readlines():
                # Make sure the empty lines between options are preserved
                if _Ini.isempty(previous_line) and not _Ini.isnewsection(line):
                    current_section.append('\n')
                if _Ini.iscomment(line):
                    current_section.append(_Ini.decrypt_comment(line))
                elif _Ini.isnewsection(line):
                    self.sections.append(_Ini.decrypt_section(line))
                    current_section = self.sections[-1]
                elif _Ini.isoption(line):
                    current_section.append(_Ini.decrypt_option(line))
                previous_line = line

    def flush(self):
        with salt.utils.fopen(self.file_name, 'w') as outfile:
            outfile.write(self.current_contents())

    def dump(self):
        print(self.current_contents())

    def current_contents(self):
        file_contents = ''
        for section in self.sections:
            if not section.section_name == 'DEFAULT_IMPLICIT':
                file_contents += '[{0}]\n'.format(section.section_name)
            for item in section:
                if isinstance(item, _Option):
                    file_contents += '{0}{1}{2}\n'.format(
                        item.name, item.separator, item.value
                    )
                elif item == '\n':
                    file_contents += '\n'
                else:
                    file_contents += '# {0}\n'.format(item)
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
            section_to_update = _Section(section_name)
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
        return _Section(ma.group(1).strip())

    @staticmethod
    def decrypt_option(line):
        ma = re.match(option_regexp1, line)
        if not ma:
            ma = re.match(option_regexp2, line)
        return _Option(ma.group(1).strip(), ma.group(3).strip(),
                       ma.group(2).strip())

    @staticmethod
    def iscomment(line):
        return re.match(comment_regexp, line)

    @staticmethod
    def isempty(line):
        return line == '\n'

    @staticmethod
    def isnewsection(line):
        return re.match(section_regexp, line)

    @staticmethod
    def isoption(line):
        return re.match(option_regexp1, line) or re.match(option_regexp2, line)

    @staticmethod
    def get_ini_file(file_name):
        try:
            inifile = _Ini(file_name)
            inifile.refresh()
            return inifile
        except IOError:
            return inifile
        except Exception:
            return
