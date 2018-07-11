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
        self.__colors_conf = conf
        self.__device = device
        self.__colors = salt.utils.color.get_colors()

    def put(self, message, indent=0):
        '''
        Print message with an indent.

        :param message:
        :param indent:
        :return:
        '''
        color = self.__colors_conf.get(indent + indent % 2, self.__colors_conf.get(0, 'LIGHT_GREEN'))

        for chunk in [' ' * indent, self.__colors[color], message, self.__colors['ENDC']]:
            self.__device.write(str(chunk))
        self.__device.write(os.linesep)
        self.__device.flush()


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
        for chunk in [self.__colors['LIGHT_RED'], 'Error:', self.__colors['RED'], message, self.__colors['ENDC']]:
            self.__device.write(str(chunk))
        self.__device.write(os.linesep)
        self.__device.flush()

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

