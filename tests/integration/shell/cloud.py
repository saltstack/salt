# -*- coding: utf-8 -*-
'''
    integration.cli_test
    ~~~~~~~~~~~~~~~~~~~~

    CLI related unit testing

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''


# Import salt testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt libs
import integration


class SaltCloudCliTest(integration.ShellCase,
                       integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-cloud'

    def test_function_arguments(self):
        self.assertIn(
            'salt-cloud: error: --function expects two arguments: '
            '<function-name> <provider>',
            self.run_cloud('--function show_image -h', catch_stderr=True)[1]
        )

    def test_list_providers_accepts_no_arguments(self):
        self.assertIn(
            'salt-cloud: error: \'--list-providers\' does not accept any '
            'arguments',
            self.run_cloud('--list-providers ec2', catch_stderr=True)[1]
        )

    def test_mutually_exclusive_query_options(self):
        test_options = [
            '--query', '--full-query', '--select-query', '--list-providers'
        ]
        while True:
            for idx in range(1, len(test_options)):
                self.assertIn(
                    'salt-cloud: error: The options {0}/{1} are mutually '
                    'exclusive. Please only choose one of them'.format(
                        test_options[0], test_options[idx]
                    ),
                    self.run_cloud(
                        '{0} {1}'.format(test_options[0], test_options[idx]),
                        catch_stderr=True)[1]
                )
            # Remove the first option from the list
            test_options.pop(0)
            if len(test_options) <= 1:
                # Only one left? Stop iterating
                break

    def test_mutually_exclusive_list_options(self):
        test_options = ['--list-locations', '--list-images', '--list-sizes']
        while True:
            for idx in range(1, len(test_options)):
                output = self.run_cloud(
                    '{0} ec2 {1} ec2'.format(
                        test_options[0], test_options[idx]
                    ), catch_stderr=True
                )
                try:
                    self.assertIn(
                        'salt-cloud: error: The options {0}/{1} are mutually '
                        'exclusive. Please only choose one of them'.format(
                            test_options[0], test_options[idx]
                        ),
                        output[1]
                    )
                except AssertionError:
                    print output
                    raise
            # Remove the first option from the list
            test_options.pop(0)
            if len(test_options) <= 1:
                # Only one left? Stop iterating
                break


if __name__ == '__main__':
    integration.run_testcase(SaltCloudCliTest)
