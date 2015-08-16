# -*- coding: utf-8 -*-
'''
Module for running arbitrary tests with a __virtual__ function
'''
from __future__ import absolute_import


def __virtual__():
    return False


def ping():
    return True
