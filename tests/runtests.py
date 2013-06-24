#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
import sys
import os
import re
import resource
import tempfile

# Import salt libs
from integration import TestDaemon, TMP

# Import Salt Testing libs
from salttesting import *
from salttesting.parser import PNUM, print_header, SaltTestingParser

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

try:
    import coverage
    # Cover any subprocess
    coverage.process_startup()
    # Setup coverage
    code_coverage = coverage.coverage(
        branch=True,
        source=[os.path.join(os.getcwd(), 'salt')],
    )
except ImportError:
    code_coverage = None


REQUIRED_OPEN_FILES = 3072


class SaltTestsuiteParser(SaltTestingParser):

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
        self.test_selection_group.add_option(
            '--run-destructive',
            action='store_true',
            default=False,
            help=('Run destructive tests. These tests can include adding or '
                  'removing users from your system for example. Default: '
                  '%default')
        )

        self.output_options_group.add_option(
            '--coverage',
            default=False,
            action='store_true',
            help='Run tests and report code coverage'
        )
        self.output_options_group.add_option(
            '--no-coverage-report',
            default=False,
            action='store_true',
            help='Don\'t build the coverage HTML report'
        )
        self.output_options_group.add_option(
            '--no-colors',
            '--no-colours',
            default=False,
            action='store_true',
            help='Disable colour printing.'
        )

    def validate_options(self):
        if self.options.coverage and code_coverage is None:
            self.error(
                'Cannot run tests with coverage report. '
                'Please install coverage>=3.5.3'
            )
        elif self.options.coverage:
            coverage_version = tuple([
                int(part) for part in re.search(
                    r'([0-9.]+)', coverage.__version__).group(0).split('.')
            ])
            if coverage_version < (3, 5, 3):
                # Should we just print the error instead of exiting?
                self.error(
                    'Versions lower than 3.5.3 of the coverage library are '
                    'know to produce incorrect results. Please consider '
                    'upgrading...'
                )
            # Update environ so that any subprocess started on test are also
            # included in the report
            os.environ['COVERAGE_PROCESS_START'] = '1'

            if any((self.options.module, self.options.client,
                    self.options.shell, self.options.unit, self.options.state,
                    self.options.runner, self.options.name, os.geteuid() != 0,
                    not self.options.run_destructive)):
                self.error(
                    'No sense in generating the tests coverage report when '
                    'not running the full test suite, including the '
                    'destructive tests, as \'root\'. It would only produce '
                    'incorrect results.'
                )

        # Set the required environment variable in order to know if destructive
        # tests should be executed or not.
        os.environ['DESTRUCTIVE_TESTS'] = str(self.options.run_destructive)

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

        if self.options.coverage:
            code_coverage.start()

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
        if self.options.unit and not (self.options.runner or
                                      self.options.state or
                                      self.options.module or
                                      self.options.client):
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
                    results = self.run_suite('', name)
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
        if not self.options.unit:
            return [True]
        status = []
        if self.options.name:
            for name in self.options.name:
                results = self.run_suite(os.path.join(TEST_DIR, 'unit'), name)
                status.append(results)
        else:
            results = self.run_suite(
                os.path.join(TEST_DIR, 'unit'), 'Unit', '*_test.py'
            )
            status.append(results)
        return status

    def print_overall_testsuite_report(self):
        SaltTestingParser.print_overall_testsuite_report(self)
        if not self.options.coverage:
            return

        print('Stopping and saving coverage info')
        code_coverage.stop()
        code_coverage.save()
        print('Current Directory: {0}'.format(os.getcwd()))
        print(
            'Coverage data file exists? {0}'.format(
                os.path.isfile('.coverage')
            )
        )

        if self.options.no_coverage_report is False:
            report_dir = os.path.join(
                os.path.dirname(__file__),
                'coverage-report'
            )
            print(
                '\nGenerating Coverage HTML Report Under {0!r} ...'.format(
                    report_dir
                )
            ),
            sys.stdout.flush()

            if os.path.isdir(report_dir):
                import shutil
                shutil.rmtree(report_dir)
            code_coverage.html_report(directory=report_dir)
            print('Done.\n')

    def finalize(self, exit_code):
        if self.options.no_report:
            if self.options.coverage:
                code_coverage.stop()
                code_coverage.save()
        SaltTestingParser.finalize(self, exit_code)


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
