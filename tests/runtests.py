#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
    runtests.py
    ~~~~~~~~~~~

    salt-cloud tests

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import tempfile

# Import salt testing libs
from salttesting.parser.cover import SaltCoverageTestingParser

TEST_DIR = os.path.abspath(os.path.dirname(__file__))
SALTCLOUD_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

XML_OUTPUT_DIR = os.environ.get(
    'XML_TEST_REPORTS', os.path.join(
        tempfile.gettempdir(), 'xml-test-reports'
    )
)
HTML_OUTPUT_DIR = os.environ.get(
    'HTML_OUTPUT_DIR', os.path.join(
        tempfile.gettempdir(), 'html-test-results'
    )
)


try:
    if SALTCLOUD_ROOT:
        os.chdir(SALTCLOUD_ROOT)
except OSError as err:
    print 'Failed to change directory to salt-cloud\'s source: {0}'.format(err)


class SaltCloudTestingParser(SaltCoverageTestingParser):
    def setup_additional_options(self):
        self.test_selection_group.add_option(
            '-u',
            '--unit',
            default=False,
            action='store_true',
            help='Run unit tests'
        )
        self.test_selection_group.add_option(
            '-s',
            '--shell',
            default=False,
            action='store_true',
            help='Run shell tests'
        )

    def validate_options(self):
        if self.options.coverage and any((
                self.options.name, self.options.unit, self.options.shell)):
            self.error(
                'No sense in generating the tests coverage report when not '
                'running the full test suite, it would only produce '
                'incorrect results.'
            )

        # Set test suite defaults if no specific suite options are provided
        if not any((self.options.name, self.options.unit, self.options.shell)):
            self.options.unit = True
            self.options.shell = True

        self.start_coverage(
            branch=True,
            source=[os.path.join(SALTCLOUD_ROOT, 'saltcloud')],
            track_processes=True
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
        status = []
        if not any([self.options.shell, self.options.name]):
            return status

        if self.options.name:
            for name in self.options.name:
                results = self.run_suite('', name)
                status.append(results)
        if self.options.shell:
            status.append(
                self.run_suite(
                    os.path.join(TEST_DIR, 'integration'), 'Shell', 'cli*.py'
                )
            )
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


def main():
    parser = SaltCloudTestingParser(
        TEST_DIR,
        xml_output_dir=XML_OUTPUT_DIR,
        html_output_dir=HTML_OUTPUT_DIR,
        tests_logfile=os.path.join(
            tempfile.gettempdir(), 'salt-cloud-runtests.log'
        )
    )
    parser.parse_args()

    overall_status = []
    overall_status.extend(parser.run_unit_tests())
    overall_status.extend(parser.run_integration_tests())
    false_count = overall_status.count(False)

    if false_count > 0:
        parser.finalize(1)
    parser.finalize(0)


if __name__ == '__main__':
    main()
