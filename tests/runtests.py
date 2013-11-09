#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
import os
import resource
import tempfile

# Import salt libs
from integration import TestDaemon, TMP

# Import Salt Testing libs
from salttesting.parser import PNUM, print_header
from salttesting.parser.cover import SaltCoverageTestingParser

TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))
SALT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
XML_OUTPUT_DIR = os.environ.get(
    'SALT_XML_TEST_REPORTS_DIR',
    os.path.join(TMP, 'xml-test-reports')
)
HTML_OUTPUT_DIR = os.environ.get(
    'SALT_HTML_TEST_REPORTS_DIR',
    os.path.join(TMP, 'html-test-reports')
)


try:
    if SALT_ROOT:
        os.chdir(SALT_ROOT)
except OSError as err:
    print 'Failed to change directory to salt\'s source: {0}'.format(err)

REQUIRED_OPEN_FILES = 3072


class SaltTestsuiteParser(SaltCoverageTestingParser):
    support_docker_execution = True
    support_destructive_tests_selection = True
    source_code_basedir = SALT_ROOT

    def setup_additional_options(self):
        self.add_option(
            '--sysinfo',
            default=False,
            action='store_true',
            help='Print some system information.'
        )

        self.test_selection_group.add_option(
            '-m',
            '--module',
            '--module-tests',
            dest='module',
            default=False,
            action='store_true',
            help='Run tests for modules'
        )
        self.test_selection_group.add_option(
            '-S',
            '--state',
            '--state-tests',
            dest='state',
            default=False,
            action='store_true',
            help='Run tests for states'
        )
        self.test_selection_group.add_option(
            '-c',
            '--client',
            '--client-tests',
            dest='client',
            default=False,
            action='store_true',
            help='Run tests for client'
        )
        self.test_selection_group.add_option(
            '-s',
            '--shell',
            dest='shell',
            default=False,
            action='store_true',
            help='Run shell tests'
        )
        self.test_selection_group.add_option(
            '-r',
            '--runner',
            dest='runner',
            default=False,
            action='store_true',
            help='Run runner tests'
        )
        self.test_selection_group.add_option(
            '-u',
            '--unit',
            '--unit-tests',
            dest='unit',
            default=False,
            action='store_true',
            help='Run unit tests'
        )

        self.output_options_group.add_option(
            '--no-colors',
            '--no-colours',
            default=False,
            action='store_true',
            help='Disable colour printing.'
        )

    def validate_options(self):
        if self.options.coverage and any((
                self.options.module, self.options.client, self.options.shell,
                self.options.unit, self.options.state, self.options.runner,
                self.options.name, os.geteuid() != 0,
                not self.options.run_destructive)):
            self.error(
                'No sense in generating the tests coverage report when '
                'not running the full test suite, including the '
                'destructive tests, as \'root\'. It would only produce '
                'incorrect results.'
            )

        # Set test suite defaults if no specific suite options are provided
        if not any((self.options.module, self.options.client,
                    self.options.shell, self.options.unit, self.options.state,
                    self.options.runner, self.options.name)):
            self.options.module = True
            self.options.client = True
            self.options.shell = True
            self.options.unit = True
            self.options.runner = True
            self.options.state = True

        self.start_coverage(
            branch=True,
            source=[os.path.join(SALT_ROOT, 'salt')],
        )

    def run_integration_suite(self, suite_folder, display_name):
        '''
        Run an integration test suite
        '''
        path = os.path.join(TEST_DIR, 'integration', suite_folder)
        return self.run_suite(path, display_name)

    def run_integration_tests(self):
        '''
        Execute the integration tests suite
        '''
        named_tests = []
        named_unit_test = []

        if self.options.name:
            for test in self.options.name:
                if test.startswith('unit.'):
                    named_unit_test.append(test)
                    continue
                named_tests.append(test)

        if (self.options.unit or named_unit_test) and not \
                (self.options.runner or
                 self.options.state or
                 self.options.module or
                 self.options.client or
                 named_tests):
            # We're either not running any of runner, state, module and client
            # tests, or, we're only running unittests by passing --unit or by
            # passing only `unit.<whatever>` to --name.
            # We don't need the tests daemon running
            return [True]

        smax_open_files, hmax_open_files = resource.getrlimit(
            resource.RLIMIT_NOFILE
        )
        if smax_open_files < REQUIRED_OPEN_FILES:
            print('~' * PNUM)
            print(
                'Max open files setting is too low({0}) for running the '
                'tests'.format(smax_open_files)
            )
            print(
                'Trying to raise the limit to {0}'.format(REQUIRED_OPEN_FILES)
            )
            if hmax_open_files < 4096:
                hmax_open_files = 4096  # Decent default?
            try:
                resource.setrlimit(
                    resource.RLIMIT_NOFILE,
                    (REQUIRED_OPEN_FILES, hmax_open_files)
                )
            except Exception as err:
                print(
                    'ERROR: Failed to raise the max open files setting -> '
                    '{0}'.format(err)
                )
                print('Please issue the following command on your console:')
                print('  ulimit -n {0}'.format(REQUIRED_OPEN_FILES))
                self.exit()
            finally:
                print('~' * PNUM)

        print_header('Setting up Salt daemons to execute tests', top=False)
        status = []
        if not any([self.options.client, self.options.module,
                    self.options.runner, self.options.shell,
                    self.options.state, self.options.name]):
            return status

        with TestDaemon(self):
            if self.options.name:
                for name in self.options.name:
                    if name.startswith('unit.'):
                        continue
                    results = self.run_suite('', name, load_from_name=True)
                    status.append(results)
            if self.options.runner:
                status.append(self.run_integration_suite('runners', 'Runner'))
            if self.options.module:
                status.append(self.run_integration_suite('modules', 'Module'))
            if self.options.state:
                status.append(self.run_integration_suite('states', 'State'))
            if self.options.client:
                status.append(self.run_integration_suite('client', 'Client'))
            if self.options.shell:
                status.append(self.run_integration_suite('shell', 'Shell'))
        return status

    def run_unit_tests(self):
        '''
        Execute the unit tests
        '''
        named_unit_test = []
        if self.options.name:
            for test in self.options.name:
                if not test.startswith('unit.'):
                    continue
                named_unit_test.append(test)

        if not self.options.unit and not named_unit_test:
            # We are not explicitly running the unit tests and none of the
            # names passed to --name is a unit test.
            return [True]

        status = []
        if self.options.unit:
            results = self.run_suite(
                os.path.join(TEST_DIR, 'unit'), 'Unit', '*_test.py'
            )
            status.append(results)
            # We executed ALL unittests, we can skip running unittests by name
            # bellow
            return status

        for name in named_unit_test:
            results = self.run_suite(
                os.path.join(TEST_DIR, 'unit'), name, load_from_name=True
            )
            status.append(results)
        return status


def main():
    '''
    Parse command line options for running specific tests
    '''
    parser = SaltTestsuiteParser(
        TEST_DIR,
        xml_output_dir=XML_OUTPUT_DIR,
        html_output_dir=HTML_OUTPUT_DIR,
        tests_logfile=os.path.join(tempfile.gettempdir(), 'salt-runtests.log')
    )
    parser.parse_args()

    overall_status = []
    status = parser.run_integration_tests()
    overall_status.extend(status)
    status = parser.run_unit_tests()
    overall_status.extend(status)
    false_count = overall_status.count(False)

    if false_count > 0:
        parser.finalize(1)
    parser.finalize(0)


if __name__ == '__main__':
    main()
