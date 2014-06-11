# -*- coding: utf-8 -*-
'''
Recursively display nested data, this is the default outputter.
'''
# Import python libs
from numbers import Number

# Import salt libs
import salt.utils


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
        elif isinstance(ret, basestring):
            lines = ret.split('\n')
            for line in lines:
                out += '{0}{1}{2}{3}{4}\n'.format(
                        ' ' * indent,
                        self.colors['GREEN'],
                        prefix,
                        line,
                        self.colors['ENDC'])
        elif isinstance(ret, list) or isinstance(ret, tuple):
            for ind in ret:
                if isinstance(ind, (list, tuple)):
                    out += '{0}{1}|_{2}\n'.format(
                            ' ' * indent,
                            self.colors['GREEN'],
                            self.colors['ENDC'])
                    out = self.display(ind, indent + 2, '- ', out)
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
