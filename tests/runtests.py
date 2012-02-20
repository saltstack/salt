#!/usr/bin/env python
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
import os
# Import salt libs
import saltunittest
from integration import TestDaemon

TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))

def run_integration_tests():
    with TestDaemon():
        loader = saltunittest.TestLoader()
        tests = loader.discover(os.path.join(TEST_DIR, 'integration', 'modules'), '*.py')
        saltunittest.TextTestRunner(verbosity=1).run(tests)

def run_unit_tests():
    loader = saltunittest.TestLoader()
    tests = loader.discover(os.path.join(TEST_DIR, 'unit', 'templates'), '*.py')
    saltunittest.TextTestRunner(verbosity=1).run(tests)


if __name__ == "__main__":
    run_integration_tests()
    run_unit_tests()
