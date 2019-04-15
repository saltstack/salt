# -*- coding: utf-8 -*-
'''
Jinja-specific decorators
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging

log = logging.getLogger(__name__)


class JinjaFilter(object):
    '''
    This decorator is used to specify that a function is to be loaded as a
    Jinja filter.
    '''
    salt_jinja_filters = {}

    def __init__(self, name=None):
        '''
        '''
        self.name = name

    def __call__(self, function):
        '''
        '''
        name = self.name or function.__name__
        if name not in self.salt_jinja_filters:
            log.debug('Marking \'%s\' as a jinja filter', name)
            self.salt_jinja_filters[name] = function
        return function


jinja_filter = JinjaFilter


class JinjaTest(object):
    '''
    This decorator is used to specify that a function is to be loaded as a
    Jinja test.
    '''
    salt_jinja_tests = {}

    def __init__(self, name=None):
        '''
        '''
        self.name = name

    def __call__(self, function):
        '''
        '''
        name = self.name or function.__name__
        if name not in self.salt_jinja_tests:
            log.debug('Marking \'%s\' as a jinja test', name)
            self.salt_jinja_tests[name] = function
        return function


jinja_test = JinjaTest


class JinjaGlobal(object):
    '''
    This decorator is used to specify that a function is to be loaded as a
    Jinja global.
    '''
    salt_jinja_globals = {}

    def __init__(self, name=None):
        '''
        '''
        self.name = name

    def __call__(self, function):
        '''
        '''
        name = self.name or function.__name__
        if name not in self.salt_jinja_globals:
            log.debug('Marking \'%s\' as a jinja global', name)
            self.salt_jinja_globals[name] = function
        return function


jinja_global = JinjaGlobal
