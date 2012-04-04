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

PNUM = 50

def run_integration_tests():
    print '~' * PNUM
    print 'Setting up Salt daemons to execute tests'
    print '~' * PNUM
    with TestDaemon():
        moduleloader = saltunittest.TestLoader()
        moduletests = moduleloader.discover(os.path.join(TEST_DIR, 'integration', 'modules'), '*.py')
        print '~' * PNUM
        print 'Starting Module Tets'
        print '~' * PNUM
        saltunittest.TextTestRunner(verbosity=1).run(moduletests)
        clientloader = saltunittest.TestLoader()
        clienttests = clientloader.discover(os.path.join(TEST_DIR, 'integration', 'client'), '*.py')
        print '~' * PNUM
        print 'Starting Client tests'
        print '~' * PNUM
        saltunittest.TextTestRunner(verbosity=1).run(clienttests)

def run_unit_tests():
    loader = saltunittest.TestLoader()
    tests = loader.discover(os.path.join(TEST_DIR, 'unit', 'templates'), '*.py')
    print '~' * PNUM
    print 'Starting Unit Tests'
    print '~' * PNUM
    saltunittest.TextTestRunner(verbosity=1).run(tests)


if __name__ == "__main__":
    run_integration_tests()
    run_unit_tests()
