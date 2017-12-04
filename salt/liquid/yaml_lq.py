# -*- coding: utf-8 -*-
'''
'''
from __future__ import absolute_import
import logging

# Import salt libs
__virtualname__ = 'yaml'

log = logging.getLogger(__name__)

def __virtual__():
    return True


def fetch(**kwargs):
    '''
    '''
    return {
        'some_test_data_from_the_liquid_yaml': True
    }
