# coding=utf-8
'''
Collection of tools to report messages to console.
This is subject to be moved to utils.
'''

from __future__ import absolute_import, print_function, unicode_literals

import sys
import os
import salt.utils.color


class IndentOutput(object):
    '''
    Paint different indends in different output.
    '''
    def __init__(self, conf=None, device=sys.stdout):
        if conf is None:
            conf = {0: 'CYAN', 2: 'GREEN', 4: 'LIGHT_CYAN', 6: 'CYAN'}
        self._colors_conf = conf
        self._device = device
        self._colors = salt.utils.color.get_colors()
        self._default_color = 'GREEN'
        self._default_hl_color = 'LIGHT_GREEN'

    def put(self, message, indent=0):
        '''
        Print message with an indent.

        :param message:
        :param indent:
        :return:
        '''
        color = self._colors_conf.get(indent + indent % 2, self._colors_conf.get(0, self._default_color))

        for chunk in [' ' * indent, self._colors[color], message, self._colors['ENDC']]:
            self._device.write(str(chunk))
        self._device.write(os.linesep)
        self._device.flush()


class MessagesOutput(IndentOutput):
    '''
    Messages output to the CLI.
    '''

    def error(self, message):
        '''
        Print an error to the screen.

        :param message:
        :return:
        '''
        for chunk in [self._colors['RED'], 'Error:', ' ', self._colors['LIGHT_RED'], message, self._colors['ENDC']]:
            self._device.write(str(chunk))
        self._device.write(os.linesep)
        self._device.flush()

    def highlight(self, message, *values, **colors):
        '''
        Highlighter works the way that message parameter is a template,
        the "values" is a list of arguments going one after another as values there.
        And so the "colors" should designate either highlight color or alternate for each.

        Example:

           highlight('Hello {}, there! It is {}.', 'user', 'daytime', _main='GREEN', _highlight='RED')
           highlight('Hello {}, there! It is {}.', 'user', 'daytime', _main='GREEN', _highlight='RED', 'daytime'='YELLOW')

        First example will highlight all the values in the template with the red color.
        Second example will highlight the second value with the yellow color.

        Usage:

            colors:
              _main: Sets the main color (or default is used)
              _highlight: Sets the alternative color for everything
              'any phrase' that is the same in the "values" can override color.

        :param message:
        :param formatted:
        :param colors:
        :return:
        '''

        m_color = colors.get('_main', self._default_color)
        h_color = colors.get('_highlight', self._default_hl_color)

        _values = []
        for value in values:
            _values.append('{p}{c}{r}'.format(p=self._colors[colors.get(value, h_color)],
                                              c=value, r=self._colors[m_color]))
        self._device.write('{s}{m}{e}'.format(s=self._colors[m_color],
                                              m=message.format(*_values), e=self._colors['ENDC']))
        self._device.write(os.linesep)
        self._device.flush()
