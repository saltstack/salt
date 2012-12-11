# -*- coding: utf-8 -*-
'''
    tests.integration.shell.call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import yaml
from datetime import datetime

# Import salt libs
from salt import version

# Import salt test libs
import integration
from saltunittest import (
    TestLoader,
    TextTestRunner,
    skipIf,
)


class CallTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-call'

    def test_default_output(self):
        out = self.run_call('-l quiet test.fib 3')

        expect = ['local: !!python/tuple',
                  '- - 0',
                  '  - 1',
                  '  - 1',
                  '  - 2']
        self.assertEqual(expect, out[:-1])

    def test_text_output(self):
        out = self.run_call('-l quiet --text-out test.fib 3')
        if version.__version_info__ < (0, 10, 8):
            expect = [
                "WARNING: The option --text-out is deprecated. Please "
                "consider using '--out text' instead."
            ]
        else:
            expect = []

        expect += [
            'local: ([0, 1, 1, 2]'
        ]

        self.assertEqual(''.join(expect), ''.join(out).rsplit(",", 1)[0])

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_user_delete_kw_output(self):
        ret = self.run_call('-l quiet -d user.delete')
        self.assertIn(
            'salt \'*\' user.delete name remove=True force=True',
            ''.join(ret)
        )

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_issue_2731_masterless(self):
        config_dir = '/tmp/salttest'
        minion_config_file = os.path.join(config_dir, 'minion')
        this_minion_key = os.path.join(
            config_dir, 'pki', 'minions', 'minion_test_issue_2731'
        )

        minion_config = {
            'id': 'minion_test_issue_2731',
            'master': 'localhost',
            'master_port': 64506,
            'root_dir': '/tmp/salttest',
            'pki_dir': 'pki',
            'cachedir': 'cachedir',
            'sock_dir': 'minion_sock',
            'open_mode': True,
            'log_file': '/tmp/salttest/minion_test_issue_2731',
            'log_level': 'quiet',
            'log_level_logfile': 'info'
        }

        # Remove existing logfile
        if os.path.isfile('/tmp/salttest/minion_test_issue_2731'):
            os.unlink('/tmp/salttest/minion_test_issue_2731')

        start = datetime.now()
        # Let's first test with a master running
        open(minion_config_file, 'w').write(
            yaml.dump(minion_config, default_flow_style=False)
        )
        ret = self.run_script(
            'salt-call',
            '--config-dir {0} cmd.run "echo foo"'.format(
                config_dir
            )
        )
        try:
            self.assertIn('local: foo', ret)
        except AssertionError:
            if os.path.isfile(minion_config_file):
                os.unlink(minion_config_file)
            # Let's remove our key from the master
            if os.path.isfile(this_minion_key):
                os.unlink(this_minion_key)

            raise

        # Calculate the required timeout, since next will fail.
        # I needed this because after many attempts, I was unable to catch:
        #   WARNING: Master hostname: salt not found. Retrying in 30 seconds
        ellapsed = datetime.now() - start
        timeout = ellapsed.seconds + 3

        # Now let's remove the master configuration
        minion_config.pop('master')
        minion_config.pop('master_port')
        open(minion_config_file, 'w').write(
            yaml.dump(minion_config, default_flow_style=False)
        )

        out = self.run_script(
            'salt-call',
            '--config-dir {0} cmd.run "echo foo"'.format(
                config_dir
            ),
            timeout=timeout,
        )

        try:
            self.assertIn(
                'Process took more than {0} seconds to complete. '
                'Process Killed!'.format(timeout),
                out
            )
        except AssertionError:
            if os.path.isfile(minion_config_file):
                os.unlink(minion_config_file)
            # Let's remove our key from the master
            if os.path.isfile(this_minion_key):
                os.unlink(this_minion_key)

            raise

        # Should work with --local
        ret = self.run_script(
            'salt-call',
            '--config-dir {0} --local cmd.run "echo foo"'.format(
                config_dir
            ),
            timeout=15
        )
        try:
            self.assertIn('local: foo', ret)
        except AssertionError:
            if os.path.isfile(minion_config_file):
                os.unlink(minion_config_file)
            # Let's remove our key from the master
            if os.path.isfile(this_minion_key):
                os.unlink(this_minion_key)
            raise

        # Should work with local file client
        minion_config['file_client'] = 'local'
        open(minion_config_file, 'w').write(
            yaml.dump(minion_config, default_flow_style=False)
        )
        ret = self.run_script(
            'salt-call',
            '--config-dir {0} cmd.run "echo foo"'.format(
                config_dir
            ),
            timeout=15
        )
        try:
            self.assertIn('local: foo', ret)
        finally:
            if os.path.isfile(minion_config_file):
                os.unlink(minion_config_file)
            # Let's remove our key from the master
            if os.path.isfile(this_minion_key):
                os.unlink(this_minion_key)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(CallTest)
    print('Setting up Salt daemons to execute tests')
    with integration.TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
