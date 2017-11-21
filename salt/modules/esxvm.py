# -*- coding: utf-8 -*-
'''
Module used to access the esx proxy connection methods
'''
from __future__ import absolute_import

# Import python libs
import logging
import salt.utils


log = logging.getLogger(__name__)

__proxyenabled__ = ['esxvm']
# Define the module's virtual name
__virtualname__ = 'esxvm'


def __virtual__():
    '''
    Only work on proxy
    '''
    if salt.utils.platform.is_proxy():
        return __virtualname__
    return False


def get_details():
    return __proxy__['esxvm.get_details']()
