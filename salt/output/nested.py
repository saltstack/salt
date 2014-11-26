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
from __future__ import absolute_import
# Import python libs
from numbers import Number
import re

# Import salt libs
import salt.utils
import salt.output
from salt.ext.six import string_types


class NestDisplay(object):
    '''
    Manage the nested display contents
    '''
    def __init__(self):
        self.colors = salt.utils.get_colors(__opts__.get('color'))

    def ustring(self,
                indent,
                color,
                msg,
                prefix='',
                suffix='',
                endc=None):
        if endc is None:
            endc = self.colors['ENDC']
        try:
            return u'{0}{1}{2}{3}{4}{5}\n'.format(
                indent, color, prefix, msg, endc, suffix)
        except UnicodeDecodeError:
            return u'{0}{1}{2}{3}{4}{5}\n'.format(
                indent, color, prefix, salt.utils.sdecode(msg), endc, suffix)

    def display(self, ret, indent, prefix, out):
        '''
        Recursively iterate down through data structures to determine output
        '''
        strip_colors = __opts__.get('strip_colors', True)

        if ret is None or ret is True or ret is False:
            out += self.ustring(
                ' ' * indent,
                self.colors['YELLOW'],
                ret,
                prefix=prefix)
        # Number includes all python numbers types
        #  (float, int, long, complex, ...)
        elif isinstance(ret, Number):
            out += self.ustring(
                ' ' * indent,
                self.colors['YELLOW'],
                ret,
                prefix=prefix)
        elif isinstance(ret, string_types):
            lines = re.split(r'\r?\n', ret)
            for line in lines:
                if strip_colors:
                    line = salt.output.strip_esc_sequence(line)
                out += self.ustring(
                    ' ' * indent,
                    self.colors['GREEN'],
                    line,
                    prefix=prefix)
        elif isinstance(ret, list) or isinstance(ret, tuple):
            for ind in ret:
                if isinstance(ind, (list, tuple, dict)):
                    out += self.ustring(' ' * indent,
                                        self.colors['GREEN'],
                                        '|_')
                    prefix = '' if isinstance(ind, dict) else '- '
                    out = self.display(ind, indent + 2, prefix, out)
                else:
                    out = self.display(ind, indent, '- ', out)
        elif isinstance(ret, dict):
            if indent:
                out += self.ustring(
                    ' ' * indent,
                    self.colors['CYAN'],
                    '-' * 10)
            for key in sorted(ret):
                val = ret[key]
                out += self.ustring(
                    ' ' * indent,
                    self.colors['CYAN'],
                    key,
                    suffix=":",
                    prefix=prefix)
                out = self.display(val, indent + 4, '', out)
        return out


def output(ret):
    '''
    Display ret data
    '''
    nest = NestDisplay()
    return nest.display(ret, __opts__.get('nested_indent', 0), '', '')
