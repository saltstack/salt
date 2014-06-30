# -*- coding: utf-8 -*-
'''
Recursively display nested data
===============================

This is the default outputter for most execution functions.

Example output::

    myminion:
        ----------
        foo:
            ----------
            bar:
                baz
            dictionary:
                ----------
                abc:
                    123
                def:
                    456
            list:
                - Hello
                - World
'''
# Import python libs
from numbers import Number
import re

# Import salt libs
import salt.utils
import salt.output
from salt._compat import string_types


class NestDisplay(object):
    '''
    Manage the nested display contents
    '''
    def __init__(self):
        self.colors = salt.utils.get_colors(__opts__.get('color'))

    def display(self, ret, indent, prefix, out):
        '''
        Recursively iterate down through data structures to determine output
        '''
        strip_colors = __opts__.get('strip_colors', True)
        if ret is None or ret is True or ret is False:
            out += '{0}{1}{2}{3}{4}\n'.format(
                    ' ' * indent,
                    self.colors['YELLOW'],
                    prefix,
                    ret,
                    self.colors['ENDC'])
        # Number includes all python numbers types (float, int, long, complex, ...)
        elif isinstance(ret, Number):
            out += '{0}{1}{2}{3}{4}\n'.format(
                    ' ' * indent,
                    self.colors['YELLOW'],
                    prefix,
                    ret,
                    self.colors['ENDC'])
        elif isinstance(ret, string_types):
            lines = re.split(r'\r?\n', ret)
            for line in lines:
                if strip_colors:
                    line = salt.output.strip_esc_sequence(line)
                out += '{0}{1}{2}{3}{4}\n'.format(
                        ' ' * indent,
                        self.colors['GREEN'],
                        prefix,
                        line,
                        self.colors['ENDC'])
        elif isinstance(ret, list) or isinstance(ret, tuple):
            for ind in ret:
                if isinstance(ind, (list, tuple, dict)):
                    out += '{0}{1}|_{2}\n'.format(
                            ' ' * indent,
                            self.colors['GREEN'],
                            self.colors['ENDC'])
                    prefix = '' if isinstance(ind, dict) else '- '
                    out = self.display(ind, indent + 2, prefix, out)
                else:
                    out = self.display(ind, indent, '- ', out)
        elif isinstance(ret, dict):
            if indent:
                out += '{0}{1}{2}{3}\n'.format(
                        ' ' * indent,
                        self.colors['CYAN'],
                        '-' * 10,
                        self.colors['ENDC'])
            for key in sorted(ret):
                val = ret[key]
                out += '{0}{1}{2}{3}{4}:\n'.format(
                        ' ' * indent,
                        self.colors['CYAN'],
                        prefix,
                        key,
                        self.colors['ENDC'])
                out = self.display(val, indent + 4, '', out)
        return out


def output(ret):
    '''
    Display ret data
    '''
    nest = NestDisplay()
    return nest.display(ret, __opts__.get('nested_indent', 0), '', '')
