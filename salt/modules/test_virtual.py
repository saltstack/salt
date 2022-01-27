# -*- coding: utf-8 -*-
'''
Module for testing that a __virtual__ function returning False will not be
available via the Salt Loader.
'''
from __future__ import absolute_import, unicode_literals, print_function


def __virtual__():
    return (False, 'The test_virtual execution module failed to load.')


def ping():
    return True
