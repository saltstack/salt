# -*- coding: utf-8 -*-

from salttesting import TestCase
from salttesting.parser import SaltTestcaseParser

def run_tests(*test_cases, **kwargs):
    '''
    Run integration tests for the chosen test cases.

    Function uses optparse to set up test environment
    '''
    parser = SaltTestcaseParser()
    parser.parse_args()
    for case in test_cases:
        if parser.run_testcase(case) is False:
            parser.finalize(1)
    parser.finalize(0)
