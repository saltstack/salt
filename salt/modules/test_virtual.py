# -*- coding: utf-8 -*-
'''
Module for running arbitrary tests
'''
from __future__ import absolute_import

# expose all of the same functions as test
from salt.modules.test import *

def __virtual__():
    return False

