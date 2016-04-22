# -*- coding: utf-8 -*-
'''
A lightweight version of tests.integration for testing of unit tests

This test class will not import the salt minion, runner and config modules.
'''
from functools import wraps

from salttesting.case import TestCase
from salttesting.parser import SaltTestcaseParser

__all__ = ['run_tests', 'ModuleTestCase']


def run_tests(*test_cases, **kwargs):
    '''
    Run unit tests for the chosen test cases.
    '''
    parser = SaltTestcaseParser()
    parser.parse_args()
    for case in test_cases:
        if parser.run_testcase(case) is False:
            parser.finalize(1)
    parser.finalize(0)

@wraps
def hasDep(func, import_path):
    pass


class MockLoader(object):
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
        self.loader = self.loaderCls()

    @staticmethod
    def loader(self):
        return self.loader
