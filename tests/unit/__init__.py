# -*- coding: utf-8 -*-
'''
A lightweight version of tests.integration for testing of unit tests

This test class will not import the salt minion, runner and config modules.
'''
from __future__ import absolute_import
from tests.support.case import TestCase
from tests.support.parser import SaltTestcaseParser

__all__ = ['ModuleTestCase']


def hasDependency(module, fake_module=None):
    '''
    Use this function in your test class setUp to
    mock modules into your namespace

    :param module: The module name
    :type  module: ``str``

    :param fake_module: The module to inject into sys.modules
        if not provided, a mock will be injected. If ``False``
        is passed explicitly, the module injection does not
        occur.

    :type  fake_module: ``object``

    ..
        hasDependency('super_module')
    '''
    import sys
    from tests.support.mock import MagicMock
    if fake_module is None:
        fake_module = MagicMock()

    if fake_module:
        sys.modules[module] = fake_module


class MockLoader(object):
    '''
    The default replacement for __salt__'s loader
    class.
    '''
    def set_result(self, module, key, func):
        if module.__salt__ is None:
            module.__salt__ = {}
        module.__salt__[key] = func


class ModuleTestCase(TestCase):
    '''
    A base class for test cases of execution modules

    ..
        class MyModuleTestCase(ModuleTestCase):
            def setUp(self):
                self.setup_loader()
    '''
    # Set this class-level attribute to change
    # the loader behavior
    loaderCls = MockLoader

    def setup_loader(self):
        '''
        Instantiate a loader to your test case
        '''
        self.loader = self.loaderCls()
        self.addCleanup(delattr, self, 'loader')
