# -*- coding: utf-8 -*-
'''
Wheel functions for integration tests
'''

# Import python libs
from __future__ import absolute_import, unicode_literals


def failure():
    __context__['retcode'] = 1
    return False


def success():
    return True
