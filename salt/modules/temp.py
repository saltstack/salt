# -*- coding: utf-8 -*-
'''
Simple module for creating tmps
'''
from __future__ import absolute_import

import logging
import tempfile

log = logging.getLogger(__name__)


def dir(suffix='', prefix='tmp', dir=None):
    '''
    Create a temporary directory
    see tempfile.mkdtemp function
    '''
    return tempfile.mkdtemp(suffix, prefix, dir)


def file(suffix='', prefix='tmp', dir=None):
    '''
    Create a temporary file
    see tempfile.mkstemp function
    '''
    return tempfile.mkstemp(suffix, prefix, dir)[1]
