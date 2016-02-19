# -*- coding: utf-8 -*-
'''
Edit ini files

:maintainer: <akilesh1597@gmail.com>
:maturity: new
:depends: re
:platform: all

(for example /etc/sysctl.conf)
'''

# Import Python libs
from __future__ import print_function
from __future__ import absolute_import
import re
import json
from salt.utils.odict import OrderedDict
from salt.utils import fopen as _fopen


__virtualname__ = 'ini'


def __virtual__():
    '''
    Rename to ini
    '''
    return __virtualname__


ini_regx = re.compile(r'^\s*\[(.+?)\]\s*$', flags=re.M)
com_regx = re.compile(r'^\s*(#|;)\s*(.*)')
indented_regx = re.compile(r'(\s+)(.*)')


def set_option(file_name, sections=None, separator='='):
    '''
    Edit an ini file, replacing one or more sections. Returns a dictionary
    containing the changes made.

    file_name
        path of ini_file

    sections : None
        A dictionary representing the sections to be edited ini file
        The keys are the section names and the values are the dictionary
        containing the options
        If the Ini does not contain sections the keys and values represent the
        options

    separator : =
        A character used to separate keys and values. Standard ini files use
        the "=" character.

        .. versionadded:: Carbon

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
    sections = sections or {}
    changes = {}
    inifile = _Ini.get_ini_file(file_name, separator=separator)
    if not inifile:
        changes.update({'error': 'ini file not found'})
        return changes
    changes = inifile.update(sections)
    inifile.flush()
    return changes


def get_option(file_name, section, option, separator='='):
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
    inifile = _Ini.get_ini_file(file_name, separator=separator)
    return inifile.get(section, {}).get(option, None)


def remove_option(file_name, section, option, separator='='):
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
    inifile = _Ini.get_ini_file(file_name, separator=separator)
    value = inifile.get(section, {}).pop(option, None)
    inifile.flush()
    return value


def get_section(file_name, section, separator='='):
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
    inifile = _Ini.get_ini_file(file_name, separator=separator)
    ret = {}
    for key, value in inifile.get(section, {}).iteritems():
        if key[0] != '#':
            ret.update({key: value})
    return ret


def remove_section(file_name, section, separator='='):
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

    inifile = _Ini.get_ini_file(file_name, separator=separator)
    section = inifile.pop(section, {})
    inifile.flush()
    ret = {}
    for key, value in section.iteritems():
        if key[0] != '#':
            ret.update({key: value})
    return ret


class _Section(OrderedDict):
    def __init__(self, name, inicontents='', separator='=', commenter='#'):
        super(_Section, self).__init__(self)
        self.name = name
        self.inicontents = inicontents
        self.sep = separator
        self.com = commenter

        opt_regx_prefix = r'(\s*)(.+?)\s*'
        opt_regx_suffix = r'\s*(.*)\s*'
        self.opt_regx_str = r'{0}(\{1}){2}'.format(
            opt_regx_prefix, self.sep, opt_regx_suffix
        )
        self.opt_regx = re.compile(self.opt_regx_str)

    def refresh(self, inicontents=None):
        comment_count = 1
        unknown_count = 1
        curr_indent = ''
        inicontents = inicontents or self.inicontents
        inicontents = inicontents.strip('\n')

        if not inicontents:
            return
        for opt in self:
            self.pop(opt)
        for opt_str in inicontents.split('\n'):
            # Match comments
            com_match = com_regx.match(opt_str)
            if com_match:
                name = '#comment{0}'.format(comment_count)
                self.com = com_match.group(1)
                comment_count += 1
                self.update({name: opt_str})
                continue
            # Add indented lines to the value of the previous entry.
            indented_match = indented_regx.match(opt_str)
            if indented_match:
                indent = indented_match.group(1).replace('\t', '    ')
                if indent > curr_indent:
                    options = self.keys()
                    if options:
                        prev_opt = options[-1]
                        value = self.get(prev_opt)
                        self.update({prev_opt: '\n'.join((value, opt_str))})
                    continue
            # Match normal key+value lines.
            opt_match = self.opt_regx.match(opt_str)
            if opt_match:
                curr_indent, name, self.sep, value = opt_match.groups()
                curr_indent = curr_indent.replace('\t', '    ')
                self.update({name: value})
                continue
            # Anything remaining is a mystery.
            name = '#unknown{0}'.format(unknown_count)
            self.update({name: opt_str})
            unknown_count += 1

    def _uncomment_if_commented(self, opt_key):
        # should be called only if opt_key is not already present
        # will uncomment the key if commented and create a place holder
        # for the key where the correct value can be update later
        # used to preserve the ordering of comments and commented options
        # and to make sure options without sectons go above any section
        options_backup = OrderedDict()
        comment_index = None
        for key, value in self.iteritems():
            if comment_index is not None:
                options_backup.update({key: value})
                continue
            if '#comment' not in key:
                continue
            opt_match = self.opt_regx.match(value.lstrip('#'))
            if opt_match and opt_match.group(2) == opt_key:
                comment_index = key
        for key in options_backup:
            self.pop(key)
        self.pop(comment_index, None)
        super(_Section, self).update({opt_key: None})
        for key, value in options_backup.iteritems():
            super(_Section, self).update({key: value})

    def update(self, update_dict):
        changes = {}
        for key, value in update_dict.iteritems():
            if key not in self:
                changes.update({key: {'before': None,
                                      'after': value}})
                if hasattr(value, 'iteritems'):
                    sect = _Section(
                        name=key, inicontents='',
                        separator=self.sep, commenter=self.com
                    )
                    sect.update(value)
                    super(_Section, self).update({key: sect})
                else:
                    self._uncomment_if_commented(key)
                    super(_Section, self).update({key: value})
            else:
                curr_value = self.get(key, None)
                if isinstance(curr_value, _Section):
                    sub_changes = curr_value.update(value)
                    if sub_changes:
                        changes.update({key: sub_changes})
                else:
                    if not curr_value == value:
                        changes.update({key: {'before': curr_value,
                                              'after': value}})
                        super(_Section, self).update({key: value})
        return changes

    def gen_ini(self):
        yield '\n[{0}]\n'.format(self.name)
        sections_dict = OrderedDict()
        for name, value in self.iteritems():
            if com_regx.match(name):
                yield '{0}\n'.format(value)
            elif isinstance(value, _Section):
                sections_dict.update({name: value})
            else:
                yield '{0}{1}{2}\n'.format(
                    name,
                    (
                        ' {0} '.format(self.sep) if self.sep != ' '
                        else self.sep
                    ),
                    value
                )
        for name, value in sections_dict.iteritems():
            for line in value.gen_ini():
                yield line

    def as_ini(self):
        return ''.join(self.gen_ini())

    def as_dict(self):
        return dict(self)

    def dump(self):
        print(str(self))

    def __repr__(self, _repr_running=None):
        _repr_running = _repr_running or {}
        super_repr = super(_Section, self).__repr__(_repr_running)
        return '\n'.join((super_repr, json.dumps(self, indent=4)))

    def __str__(self):
        return json.dumps(self, indent=4)

    def __eq__(self, item):
        return (isinstance(item, self.__class__) and
                self.name == item.name)

    def __ne__(self, item):
        return not (isinstance(item, self.__class__) and
                    self.name == item.name)


class _Ini(_Section):
    def __init__(self, name, inicontents='', separator='=', commenter='#'):
        super(_Ini, self).__init__(name, inicontents, separator, commenter)

    def refresh(self, inicontents=None):
        inicontents = inicontents or _fopen(self.name).read()
        if not inicontents:
            return
        # Remove anything left behind from a previous run.
        for opt in self:
            self.pop(opt)
        inicontents = ini_regx.split(inicontents)
        inicontents.reverse()
        # Pop anything defined outside of a section (ie. at the top of
        # the ini file).
        super(_Ini, self).refresh(inicontents.pop())
        for section_name, sect_ini in self._gen_tuples(inicontents):
            sect_obj = _Section(
                section_name, sect_ini, separator=self.sep
            )
            sect_obj.refresh()
            self.update({sect_obj.name: sect_obj})

    def flush(self):
        with _fopen(self.name, 'w') as outfile:
            ini_gen = self.gen_ini()
            next(ini_gen)
            outfile.writelines(ini_gen)

    @staticmethod
    def get_ini_file(file_name, separator='='):
        inifile = _Ini(file_name, separator=separator)
        inifile.refresh()
        return inifile

    @staticmethod
    def _gen_tuples(list_object):
        while True:
            try:
                key = list_object.pop()
                value = list_object.pop()
            except IndexError:
                raise StopIteration
            else:
                yield key, value
