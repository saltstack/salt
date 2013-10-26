# -*- coding: utf-8 -*-
'''
Module for running arbitrary tests
'''

# Import Python libs
import os
import sys
import time
import random

# Import Salt libs
import salt
import salt.version
import salt.loader


__virtualname__ = 'test'

def __virtual__():
    return __virtualname__


def recho(text):
    '''
    Return a reversed string

    CLI Example:

    .. code-block:: bash

        salt '*' test.recho 'foo bar baz quo qux'
    '''
    return text[::-1]
