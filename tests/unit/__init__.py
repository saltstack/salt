# -*- coding: utf-8 -*-
'''
A lightweight version of tests.integration for testing of unit tests

This test class will not import the salt minion, runner and config modules.
'''
from salttesting.case import TestCase
from salttesting.parser import SaltTestcaseParser

__all__ = ['run_tests', 'ModuleTestCase']


def run_tests(*test_cases, **kwargs):
    '''
    Run unit tests for the chosen test cases.

    :param test_cases: The list of test cases to execute
    :type  test_cases: ``list`` of :class:`TestCase`
    '''
    parser = SaltTestcaseParser()
    parser.parse_args()
    for case in test_cases:
        if parser.run_testcase(case) is False:
            parser.finalize(1)
    parser.finalize(0)


def hasDependency(module, fake_module=None):
    '''
    Use this function in your test class setUp to
    mock modules into your namespace

    :param module: The module name
    :type  module: ``str``

    :param fake_module: The module to inject into sys.modules
        if not provided, a mock will be injected
    :type  fake_module: ``object``

    ..
        hasDependency('super_module')
    '''
    import mock
    import sys
    if fake_module is None:
        fake_module = mock.MagicMock()
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
