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
import salt.utils.odict
from numbers import Number

# Import salt libs
import salt.output
from salt.ext.six import string_types
from salt.utils import get_colors
import salt.utils.locales


class NestDisplay(object):
    '''
    Manage the nested display contents
    '''
    def __init__(self):
        self.__dict__.update(
            get_colors(
                __opts__.get('color'),
                __opts__.get('color_theme')
            )
        )
        self.strip_colors = __opts__.get('strip_colors', True)

    def ustring(self,
                indent,
                color,
                msg,
                prefix='',
                suffix='',
                endc=None):
        if endc is None:
            endc = self.ENDC

        indent *= ' '
        fmt = u'{0}{1}{2}{3}{4}{5}'

        try:
            return fmt.format(indent, color, prefix, msg, endc, suffix)
        except UnicodeDecodeError:
            return fmt.format(indent, color, prefix, salt.utils.locales.sdecode(msg), endc, suffix)

    def display(self, ret, indent, prefix, out):
        '''
        Recursively iterate down through data structures to determine output
        '''
        if ret is None or ret is True or ret is False:
            out.append(
                self.ustring(
                    indent,
                    self.LIGHT_YELLOW,
                    ret,
                    prefix=prefix
                )
            )
        # Number includes all python numbers types
        #  (float, int, long, complex, ...)
        elif isinstance(ret, Number):
            out.append(
                self.ustring(
                    indent,
                    self.LIGHT_YELLOW,
                    ret,
                    prefix=prefix
                )
            )
        elif isinstance(ret, string_types):
            first_line = True
            for line in ret.splitlines():
                if self.strip_colors:
                    line = salt.output.strip_esc_sequence(line)
                line_prefix = ' ' * len(prefix) if not first_line else prefix
                out.append(
                    self.ustring(
                        indent,
                        self.GREEN,
                        line,
                        prefix=line_prefix
                    )
                )
                first_line = False
        elif isinstance(ret, (list, tuple)):
            for ind in ret:
                if isinstance(ind, (list, tuple, dict)):
                    out.append(
                        self.ustring(
                            indent,
                            self.GREEN,
                            '|_'
                        )
                    )
                    prefix = '' if isinstance(ind, dict) else '- '
                    self.display(ind, indent + 2, prefix, out)
                else:
                    self.display(ind, indent, '- ', out)
        elif isinstance(ret, dict):
            if indent:
                out.append(
                    self.ustring(
                        indent,
                        self.CYAN,
                        '----------'
                    )
                )

            # respect key ordering of ordered dicts
            if isinstance(ret, salt.utils.odict.OrderedDict):
                keys = ret.keys()
            else:
                keys = sorted(ret)

            for key in keys:
                val = ret[key]
                out.append(
                    self.ustring(
                        indent,
                        self.CYAN,
                        key,
                        suffix=':',
                        prefix=prefix
                    )
                )
                self.display(val, indent + 4, '', out)
        return out


def output(ret, **kwargs):
    '''
    Display ret data
    '''
    # Prefer kwargs before opts
    base_indent = kwargs.get('nested_indent', 0) \
        or __opts__.get('nested_indent', 0)
    nest = NestDisplay()
    return '\n'.join(nest.display(ret, base_indent, '', []))
