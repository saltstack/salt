#!/usr/bin/env python
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
import sys
import os
import optparse

# Import salt libs
import saltunittest
from integration import TestDaemon

try:
    import xmlrunner
except ImportError:
    pass

TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))

PNUM = 50


def run_integration_tests(opts):
    '''
    Execute the integration tests suite
    '''
    print('~' * PNUM)
    print('Setting up Salt daemons to execute tests')
    print('~' * PNUM)
    status = []
    with TestDaemon():
        if opts.module:
            moduleloader = saltunittest.TestLoader()
            moduletests = moduleloader.discover(
                    os.path.join(TEST_DIR, 'integration', 'modules'),
                    '*.py'
                    )
            print('~' * PNUM)
            print('Starting Module Tests')
            print('~' * PNUM)
            if opts.xmlout:
                runner = xmlrunner.XMLTestRunner(output='test-reports').run(moduletests)
            else:
                runner = saltunittest.TextTestRunner(verbosity=opts.verbosity).run(moduletests)
            status.append(runner.wasSuccessful())
        if opts.state:
            stateloader = saltunittest.TestLoader()
            statetests = stateloader.discover(
                    os.path.join(TEST_DIR, 'integration', 'states'),
                    '*.py'
                    )
            print('~' * PNUM)
            print('Starting State Tests')
            print('~' * PNUM)
            if opts.xmlout:
                runner = xmlrunner.XMLTestRunner(output='test-reports').run(statetests)
            else:
                runner = saltunittest.TextTestRunner(verbosity=opts.verbosity).run(statetests)
            status.append(runner.wasSuccessful())
        if opts.client:
            clientloader = saltunittest.TestLoader()
            clienttests = clientloader.discover(
                    os.path.join(TEST_DIR, 'integration', 'client'),
                    '*.py'
                    )
            print('~' * PNUM)
            print('Starting Client Tests')
            print('~' * PNUM)
            if opts.xmlout:
                runner = xmlrunner.XMLTestRunner(output='test-reports').run(clienttests)
            else:
                runner = saltunittest.TextTestRunner(verbosity=opts.verbosity).run(clienttests)
            status.append(runner.wasSuccessful())
        if opts.shell:
            shellloader = saltunittest.TestLoader()
            shelltests = shellloader.discover(
                    os.path.join(TEST_DIR, 'integration', 'shell'),
                    '*.py'
                    )
            print('~' * PNUM)
            print('Starting Shell Tests')
            print('~' * PNUM)
            if opts.xmlout:
                runner = xmlrunner.XMLTestRunner(output='test-reports').run(shelltests)
            else:
                runner = saltunittest.TextTestRunner(verbosity=opts.verbosity).run(shelltests)
            status.append(runner.wasSuccessful())

    return status


def run_unit_tests(opts):
    '''
    Execute the unit tests
    '''
    if not opts.unit:
        return [True]
    status = []
    loader = saltunittest.TestLoader()
    tests = loader.discover(os.path.join(TEST_DIR, 'unit'), '*_test.py')
    print('~' * PNUM)
    print('Starting Unit Tests')
    print('~' * PNUM)
    if opts.xmlout:
        runner = xmlrunner.XMLTestRunner(output='test-reports').run(tests)
    else:
        runner = saltunittest.TextTestRunner(verbosity=opts.verbosity).run(tests)
    status.append(runner.wasSuccessful())
    return status


def parse_opts():
    '''
    Parse command line options for running specific tests
    '''
    parser = optparse.OptionParser()
    parser.add_option('-m',
            '--module',
            '--module-tests',
            dest='module',
            default=False,
            action='store_true',
            help='Run tests for modules')
    parser.add_option('-S',
            '--state',
            '--state-tests',
            dest='state',
            default=False,
            action='store_true',
            help='Run tests for states')
    parser.add_option('-c',
            '--client',
            '--client-tests',
            dest='client',
            default=False,
            action='store_true',
            help='Run tests for client')
    parser.add_option('-s',
            '--shell',
            dest='shell',
            default=False,
            action='store_true',
            help='Run shell tests')
    parser.add_option('-u',
            '--unit',
            '--unit-tests',
            dest='unit',
            default=False,
            action='store_true',
            help='Run unit tests')
    parser.add_option('-v',
            '--verbose',
            dest='verbosity',
            default=1,
            action='count',
            help='Verbose test runner output')

    parser.add_option('-x',
            '--xml',
            dest='xmlout',
            default=False,
            action='store_true',
            help='Verbose test runner output')

    options, args = parser.parse_args()
    if all((not options.module, not options.client,
            not options.shell, not options.unit,
            not options.state)):
        options.module = True
        options.client = True
        options.shell = True
        options.unit = True
    return options


if __name__ == "__main__":
    opts = parse_opts()
    overall_status = []
    status = run_integration_tests(opts)
    overall_status.extend(status)
    status = run_unit_tests(opts)
    overall_status.extend(status)
    false_count = overall_status.count(False)
    if false_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
