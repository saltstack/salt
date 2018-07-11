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
