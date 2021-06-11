# -*- coding: utf-8 -*-
"""
Module for running arbitrary tests with a __virtual__ function
"""
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    return (False, "The test_virtual execution module failed to load.")


def ping():
    return True
