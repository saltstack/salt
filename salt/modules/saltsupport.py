# coding=utf-8
'''
Module to run salt-support within Salt
'''
from __future__ import unicode_literals, print_function, absolute_import

from salt.cli.support.collector import SaltSupport
import logging


log = logging.getLogger(__name__)


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
