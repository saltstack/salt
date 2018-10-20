# coding=utf-8
'''
Module to run salt-support within Salt
'''
from __future__ import unicode_literals, print_function, absolute_import

from salt.cli.support.collector import SaltSupport
import logging


log = logging.getLogger(__name__)


class LogCollector(object):
    '''
    Output collector.
    '''
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'

    def __init__(self):
        self.messages = []

    def msg(self, message, *args, **kwargs):
        self.messages.append({self.INFO: message})

    def info(self, message, *args, **kwargs):
        self.msg(message)

    def warning(self, message, *args, **kwargs):
        self.messages.append({self.WARNING: message})

    def error(self, message, *args, **kwargs):
        self.messages.append({self.ERROR: message})

    def put(self, message, *args, **kwargs):
        self.messages.append({self.INFO: message})

    def highlight(self, message, *args, **kwargs):
        self.msg(message)


class SaltSupportModule(SaltSupport):
    '''
    Salt Support module class.
    '''
    def setup_config(self):
        '''
        Return current configuration
        :return:
        '''
        return __opts__

    def run(self):
        '''

        :return:
        '''
        return 'stub'


def __virtual__():
    return True


def run():
    '''

    :return:
    '''
    support = SaltSupportModule()
    return support.run()
