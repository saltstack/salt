#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
from __future__ import print_function
import os
import resource
import tempfile

# Import salt libs
from integration import TestDaemon, TMP  # pylint: disable=W0403

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
    print('Failed to change directory to salt\'s source: {0}'.format(err))

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
        self.add_option(
            '--transport',
            default='zeromq',
            choices=('zeromq', 'raet'),
            help='Set to raet to run integration tests with raet transport. Default: %default')

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
            '-C',
            '--cli',
            '--cli-tests',
            dest='cli',
            default=False,
            action='store_true',
            help='Run tests for cli'
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
            '-R',
            '--runner',
            dest='runner',
            default=False,
            action='store_true',
            help='Run salt/runner.py tests'
        )
        self.test_selection_group.add_option(
            '-r',
            '--runners',
            dest='runners',
            default=False,
            action='store_true',
            help='Run salt/runners/*.py tests'
        )
        self.test_selection_group.add_option(
            '-l',
            '--loader',
            default=False,
            action='store_true',
            help='Run loader tests'
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
            '--fileserver-tests',
            dest='fileserver',
            default=False,
            action='store_true',
            help='Run Fileserver tests'
        )
        self.test_selection_group.add_option(
            '-w',
            '--wheel',
            action='store_true',
            default=False,
            help='Run wheel tests'
        )
        self.test_selection_group.add_option(
            '-o',
            '--outputter',
            action='store_true',
            default=False,
            help='Run outputter tests'
        )
        self.test_selection_group.add_option(
            '--cloud-provider-tests',
            action='store_true',
            default=False,
            help=('Run cloud provider tests. These tests create and delete '
                  'instances on cloud providers. Must provide valid credentials '
                  'in salt/tests/integration/files/conf/cloud.*.d to run tests.')
        )
        self.test_selection_group.add_option(
            '--ssh',
            action='store_true',
            default=False,
            help='Run salt-ssh tests. These tests will spin up a temporary '
                 'SSH server on your machine. In certain environments, this '
                 'may be insecure! Default: False'
        )
        self.test_selection_group.add_option(
            '-A',
            '--api-tests',
            dest='api',
            action='store_true',
            default=False,
            help='Run salt-api tests'
        )
        self.output_options_group.add_option(
            '--no-colors',
            '--no-colours',
            default=False,
            action='store_true',
            help='Disable colour printing.'
        )

    def validate_options(self):
        if self.options.cloud_provider_tests:
            # Turn on expensive tests execution
            os.environ['EXPENSIVE_TESTS'] = 'True'

        if self.options.coverage and any((
                self.options.module, self.options.cli, self.options.client,
                self.options.shell, self.options.unit, self.options.state,
                self.options.runner, self.options.runners, self.options.loader,
                self.options.name, self.options.outputter, self.options.fileserver,
                self.options.wheel, os.geteuid() != 0,
                not self.options.run_destructive)):
            self.error(
                'No sense in generating the tests coverage report when '
                'not running the full test suite, including the '
                'destructive tests, as \'root\'. It would only produce '
                'incorrect results.'
            )

        # Set test suite defaults if no specific suite options are provided
        if not any((self.options.module, self.options.client, self.options.cli,
                    self.options.shell, self.options.unit, self.options.state,
                    self.options.runner, self.options.runners, self.options.loader,
                    self.options.name, self.options.outputter,
                    self.options.cloud_provider_tests, self.options.fileserver,
                    self.options.wheel, self.options.api)):
            self.options.module = True
            self.options.cli = True
            self.options.client = True
            self.options.shell = True
            self.options.unit = True
            self.options.runner = True
            self.options.runners = True
            self.options.state = True
            self.options.loader = True
            self.options.outputter = True
            self.options.fileserver = True
            self.options.wheel = True
            self.options.api = True

        self.start_coverage(
            branch=True,
            source=[os.path.join(SALT_ROOT, 'salt')],
        )

        # Transplant configuration
        TestDaemon.transplant_configs(transport=self.options.transport)

    def post_execution_cleanup(self):
        SaltCoverageTestingParser.post_execution_cleanup(self)
        if self.options.clean:
            TestDaemon.clean()

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
                 self.options.runners or
                 self.options.state or
                 self.options.module or
                 self.options.cli or
                 self.options.client or
                 self.options.loader or
                 self.options.outputter or
                 self.options.fileserver or
                 self.options.wheel or
                 self.options.cloud_provider_tests or
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
            print(
                ' * Max open files setting is too low({0}) for running the '
                'tests'.format(smax_open_files)
            )
            print(
                ' * Trying to raise the limit to {0}'.format(REQUIRED_OPEN_FILES)
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
                print('~' * getattr(self.options, 'output_columns', PNUM))

        try:
            print_header(
                ' * Setting up Salt daemons to execute tests',
                top=False, width=getattr(self.options, 'output_columns', PNUM)
            )
        except TypeError:
            print_header(' * Setting up Salt daemons to execute tests', top=False)

        status = []
        if not any([self.options.cli, self.options.client, self.options.module,
                    self.options.runner, self.options.runners, self.options.shell,
                    self.options.state, self.options.loader,
                    self.options.outputter, self.options.name,
                    self.options.cloud_provider_tests,
                    self.options.api, self.options.fileserver,
                    self.options.wheel]):
            return status

        with TestDaemon(self):
            if self.options.name:
                for name in self.options.name:
                    if name.startswith('unit.'):
                        continue
                    results = self.run_suite('', name, load_from_name=True)
                    status.append(results)
            if self.options.loader:
                status.append(self.run_integration_suite('loader', 'Loader'))
            if self.options.runner:
                status.append(self.run_integration_suite('runner', 'Runner'))
            if self.options.runners:
                status.append(self.run_integration_suite('runners', 'Runners'))
            if self.options.module:
                status.append(self.run_integration_suite('modules', 'Module'))
            if self.options.state:
                status.append(self.run_integration_suite('states', 'State'))
            if self.options.cli:
                status.append(self.run_integration_suite('cli', 'CLI'))
            if self.options.client:
                status.append(self.run_integration_suite('client', 'Client'))
            if self.options.shell:
                status.append(self.run_integration_suite('shell', 'Shell'))
            if self.options.outputter:
                status.append(self.run_integration_suite('output', 'Outputter'))
            if self.options.fileserver:
                status.append(self.run_integration_suite('fileserver', 'Fileserver'))
            if self.options.wheel:
                status.append(self.run_integration_suite('wheel', 'Wheel'))
            if self.options.cloud_provider_tests:
                status.append(self.run_integration_suite('cloud/providers', 'Cloud Provider'))
            if self.options.api:
                status.append(self.run_integration_suite('netapi', 'NetAPI'))
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
    try:
        parser = SaltTestsuiteParser(
            TEST_DIR,
            xml_output_dir=XML_OUTPUT_DIR,
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
    except KeyboardInterrupt:
        print('\nCaught keyboard interrupt. Exiting.\n')
        exit(0)


if __name__ == '__main__':
    main()
