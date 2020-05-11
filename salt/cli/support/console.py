# coding=utf-8
'''
Collection of tools to report messages to console.

NOTE: This is subject to incorporate other formatting bits
      from all around everywhere and then to be moved to utils.
'''

from __future__ import absolute_import, print_function, unicode_literals

import sys
import os
import salt.utils.color
import textwrap


class IndentOutput(object):
    '''
    Paint different indends in different output.
    '''
    def __init__(self, conf=None, device=sys.stdout):
        if conf is None:
            conf = {0: 'CYAN', 2: 'GREEN', 4: 'LIGHT_BLUE', 6: 'BLUE'}
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
    def msg(self, message, title=None, title_color=None, color='BLUE', ident=0):
        '''
        Hint message.

        :param message:
        :param title:
        :param title_color:
        :param color:
        :param ident:
        :return:
        '''
        if title and not title_color:
            title_color = color
        if title_color and not title:
            title_color = None

        self.__colored_output(title, message, title_color, color, ident=ident)

    def info(self, message, ident=0):
        '''
        Write an info message to the CLI.

        :param message:
        :param ident:
        :return:
        '''
        self.__colored_output('Info', message, 'GREEN', 'LIGHT_GREEN', ident=ident)

    def warning(self, message, ident=0):
        '''
        Write a warning message to the CLI.

        :param message:
        :param ident:
        :return:
        '''
        self.__colored_output('Warning', message, 'YELLOW', 'LIGHT_YELLOW', ident=ident)

    def error(self, message, ident=0):
        '''
        Write an error message to the CLI.

        :param message:
        :param ident
        :return:
        '''
        self.__colored_output('Error', message, 'RED', 'LIGHT_RED', ident=ident)

    def __colored_output(self, title, message, title_color, message_color, ident=0):
        if title and not title.endswith(':'):
            _linesep = title.endswith(os.linesep)
            title = '{}:{}'.format(title.strip(), _linesep and os.linesep or ' ')

        for chunk in [title_color and self._colors[title_color] or None, ' ' * ident,
                      title, self._colors[message_color], message, self._colors['ENDC']]:
            if chunk:
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


def wrap(txt, width=80, ident=0):
    '''
    Wrap text to the required dimensions and clean it up, prepare for display.

    :param txt:
    :param width:
    :return:
    '''
    ident = ' ' * ident
    txt = (txt or '').replace(os.linesep, ' ').strip()

    wrapper = textwrap.TextWrapper()
    wrapper.fix_sentence_endings = False
    wrapper.initial_indent = wrapper.subsequent_indent = ident

    return wrapper.wrap(txt)
