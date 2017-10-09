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
from __future__ import absolute_import

# Import salt libs
import salt.utils.color

# Import 3rd-party libs
from salt.ext import six


class NestDisplay(object):
    '''
    Create generator for nested output
    '''
    def __init__(self):
        self.colors = salt.utils.color.get_colors(
                __opts__.get(u'color'),
                __opts__.get(u'color_theme'))

    def display(self, ret, indent, prefix, out):
        '''
        Recursively iterate down through data structures to determine output
        '''
        if isinstance(ret, six.string_types):
            lines = ret.split(u'\n')
            for line in lines:
                out += u'{0}{1}{2}{3}{4}\n'.format(
                        self.colors[u'RED'],
                        u' ' * indent,
                        prefix,
                        line,
                        self.colors[u'ENDC'])
        elif isinstance(ret, dict):
            for key in sorted(ret):
                val = ret[key]
                out += u'{0}{1}{2}{3}{4}:\n'.format(
                        self.colors[u'CYAN'],
                        ' ' * indent,
                        prefix,
                        key,
                        self.colors[u'ENDC'])
                out = self.display(val, indent + 4, u'', out)
        return out


def output(ret, **kwargs):  # pylint: disable=unused-argument
    '''
    Display ret data
    '''
    nest = NestDisplay()
    return nest.display(ret, 0, u'', u'')
