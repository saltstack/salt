# -*- coding: utf-8 -*-
'''
Display output for minions that did not return
==============================================

This outputter is used to display notices about which minions failed to return
when a salt function is run with ``-v`` or ``--verbose``. It should not be
called directly from the CLI.

Example output::

    virtucentos:
        Minion did not return
'''

# Import salt libs
import salt.utils


class NestDisplay(object):
    '''
    Create generator for nested output
    '''
    def __init__(self):
        self.colors = salt.utils.get_colors(__opts__.get('color'))

    def display(self, ret, indent, prefix, out):
        '''
        Recursively iterate down through data structures to determine output
        '''
        if isinstance(ret, str):
            lines = ret.split('\n')
            for line in lines:
                out += '{0}{1}{2}{3}{4}\n'.format(
                        self.colors['RED'],
                        ' ' * indent,
                        prefix,
                        line,
                        self.colors['ENDC'])
        elif isinstance(ret, dict):
            for key in sorted(ret):
                val = ret[key]
                out += '{0}{1}{2}{3}{4}:\n'.format(
                        self.colors['CYAN'],
                        ' ' * indent,
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
    return nest.display(ret, 0, '', '')
