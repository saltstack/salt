# coding=utf-8
'''
Module to run salt-support within Salt
'''
from __future__ import unicode_literals, print_function, absolute_import

from salt.cli.support.collector import SaltSupport, SupportDataCollector
import tempfile
import os
import time
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

    def _get_default_archive_name(self):
    def run(self):
        '''
        Create default archive name.

        :return:
        '''
        host = None
        for grain in ['fqdn', 'host', 'localhost', 'nodename']:
            host = __grains__.get(grain)
            if host:
                break
        if not host:
            host = 'localhost'

        return os.path.join(tempfile.gettempdir(),
                            '{hostname}-support-{date}-{time}.bz2'.format(
                                hostname=host, date=time.strftime('%Y%m%d'), time=time.strftime('%H%M%S')))


def __virtual__():
    return True


def run():
    '''

    :return:
    '''
    support = SaltSupportModule()
    return support.run()
