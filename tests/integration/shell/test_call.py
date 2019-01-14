# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import logging
import os
import re
import shutil
import sys

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ShellCase
from tests.support.unit import skipIf
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.helpers import flaky, with_tempfile
from tests.integration.utils import testprogram

# Import salt libs
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.yaml
from salt.ext import six

log = logging.getLogger(__name__)


class CallTest(ShellCase, testprogram.TestProgramCase, ShellCaseCommonTestsMixin):

    _call_binary_ = 'salt-call'

    def test_default_output(self):
        out = self.run_call('-l quiet test.fib 3')

        expect = ['local:',
                  '    - 2']
        self.assertEqual(expect, out[:-1])

    def test_text_output(self):
        out = self.run_call('-l quiet --out txt test.fib 3')

        expect = [
            'local: (2'
        ]

        self.assertEqual(''.join(expect), ''.join(out).rsplit(",", 1)[0])

    def test_json_out_indent(self):
        out = self.run_call('test.ping -l quiet --out=json --out-indent=-1')
        self.assertIn('"local": true', ''.join(out))

        out = self.run_call('test.ping -l quiet --out=json --out-indent=0')
        self.assertIn('"local": true', ''.join(out))

        out = self.run_call('test.ping -l quiet --out=json --out-indent=1')
        self.assertIn('"local": true', ''.join(out))

    def test_local_sls_call(self):
        fileroot = os.path.join(RUNTIME_VARS.FILES, 'file', 'base')
        out = self.run_call('--file-root {0} state.sls saltcalllocal'.format(fileroot), local=True)
        self.assertIn('Name: test.echo', ''.join(out))
        self.assertIn('Result: True', ''.join(out))
        self.assertIn('hello', ''.join(out))
        self.assertIn('Succeeded: 1', ''.join(out))

    @with_tempfile()
    def test_local_salt_call(self, name):
        '''
        This tests to make sure that salt-call does not execute the
        function twice, see https://github.com/saltstack/salt/pull/49552
        '''
        def _run_call(cmd):
            cmd = '--out=json ' + cmd
            return salt.utils.json.loads(''.join(self.run_call(cmd, local=True)))['local']

        ret = _run_call('state.single file.append name={0} text="foo"'.format(name))
        ret = ret[next(iter(ret))]

        # Make sure we made changes
        assert ret['changes']

        # 2nd sanity check: make sure that "foo" only exists once in the file
        with salt.utils.files.fopen(name) as fp_:
            contents = fp_.read()
        assert contents.count('foo') == 1, contents

    @skipIf(salt.utils.platform.is_windows() or salt.utils.platform.is_darwin(), 'This test requires a supported master')
    def test_user_delete_kw_output(self):
        ret = self.run_call('-l quiet -d user.delete')
        assert 'salt \'*\' user.delete name remove=True force=True' in ''.join(ret)

    def test_salt_documentation_too_many_arguments(self):
        '''
        Test to see if passing additional arguments shows an error
        '''
        data = self.run_call('-d virtualenv.create /tmp/ve', catch_stderr=True)
        self.assertIn('You can only get documentation for one method at one time', '\n'.join(data[1]))

    def test_issue_6973_state_highstate_exit_code(self):
        '''
        If there is no tops/master_tops or state file matches
        for this minion, salt-call should exit non-zero if invoked with
        option --retcode-passthrough
        '''
        src = os.path.join(RUNTIME_VARS.BASE_FILES, 'top.sls')
        dst = os.path.join(RUNTIME_VARS.BASE_FILES, 'top.sls.bak')
        shutil.move(src, dst)
        expected_comment = 'No states found for this minion'
        try:
            stdout, retcode = self.run_call(
                '-l quiet --retcode-passthrough state.highstate',
                with_retcode=True
            )
        finally:
            shutil.move(dst, src)
        self.assertIn(expected_comment, ''.join(stdout))
        self.assertNotEqual(0, retcode)

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    @skipIf(True, 'to be re-enabled when #23623 is merged')
    def test_return(self):
        self.run_call('cmd.run "echo returnTOmaster"')
        jobs = [a for a in self.run_run('jobs.list_jobs')]

        self.assertTrue(True in ['returnTOmaster' in j for j in jobs])
        # lookback jid
        first_match = [(i, j)
                       for i, j in enumerate(jobs)
                       if 'returnTOmaster' in j][0]
        jid, idx = None, first_match[0]
        while idx > 0:
            jid = re.match("([0-9]+):", jobs[idx])
            if jid:
                jid = jid.group(1)
                break
            idx -= 1
        assert idx > 0
        assert jid
        master_out = [
            a for a in self.run_run('jobs.lookup_jid {0}'.format(jid))
        ]
        self.assertTrue(True in ['returnTOmaster' in a for a in master_out])

    @skipIf(salt.utils.platform.is_windows(), 'Skip on Windows')
    def test_syslog_file_not_found(self):
        '''
        test when log_file is set to a syslog file that does not exist
        '''
        old_cwd = os.getcwd()
        config_dir = os.path.join(RUNTIME_VARS.TMP, 'log_file_incorrect')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        with salt.utils.files.fopen(self.get_config_file_path('minion'), 'r') as fh_:
            minion_config = salt.utils.yaml.load(fh_.read())
            minion_config['log_file'] = 'file:///dev/doesnotexist'
            with salt.utils.files.fopen(os.path.join(config_dir, 'minion'), 'w') as fh_:
                fh_.write(
                    salt.utils.yaml.dump(minion_config, default_flow_style=False)
                )
        ret = self.run_script(
            'salt-call',
            '--config-dir {0} cmd.run "echo foo"'.format(
                config_dir
            ),
            timeout=120,
            catch_stderr=True,
            with_retcode=True
        )
        try:
            if sys.version_info >= (3, 5, 4):
                self.assertIn('local:', ret[0])
                self.assertIn('[WARNING ] The log_file does not exist. Logging not setup correctly or syslog service not started.', ret[1])
                self.assertEqual(ret[2], 0)
            else:
                self.assertIn(
                    'Failed to setup the Syslog logging handler', '\n'.join(ret[1])
                )
                self.assertEqual(ret[2], 2)
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)

    @skipIf(True, 'This test is unreliable. Need to investigate why more deeply.')
    @flaky
    def test_issue_15074_output_file_append(self):
        output_file_append = os.path.join(RUNTIME_VARS.TMP, 'issue-15074')
        try:
            # Let's create an initial output file with some data
            _ = self.run_script(
                'salt-call',
                '-c {0} --output-file={1} test.versions'.format(
                    self.config_dir,
                    output_file_append
                ),
                catch_stderr=True,
                with_retcode=True
            )

            with salt.utils.files.fopen(output_file_append) as ofa:
                output = ofa.read()

            self.run_script(
                'salt-call',
                '-c {0} --output-file={1} --output-file-append test.versions'.format(
                    self.config_dir,
                    output_file_append
                ),
                catch_stderr=True,
                with_retcode=True
            )
            with salt.utils.files.fopen(output_file_append) as ofa:
                self.assertEqual(ofa.read(), output + output)
        finally:
            if os.path.exists(output_file_append):
                os.unlink(output_file_append)

    @skipIf(True, 'This test is unreliable. Need to investigate why more deeply.')
    @flaky
    def test_issue_14979_output_file_permissions(self):
        output_file = os.path.join(RUNTIME_VARS.TMP, 'issue-14979')
        with salt.utils.files.set_umask(0o077):
            try:
                # Let's create an initial output file with some data
                self.run_script(
                    'salt-call',
                    '-c {0} --output-file={1} -l trace -g'.format(
                        self.config_dir,
                        output_file
                    ),
                    catch_stderr=True,
                    with_retcode=True
                )
                try:
                    stat1 = os.stat(output_file)
                except OSError:
                    self.fail('Failed to generate output file, see log for details')

                # Let's change umask
                os.umask(0o777)  # pylint: disable=blacklisted-function

                self.run_script(
                    'salt-call',
                    '-c {0} --output-file={1} --output-file-append -g'.format(
                        self.config_dir,
                        output_file
                    ),
                    catch_stderr=True,
                    with_retcode=True
                )
                try:
                    stat2 = os.stat(output_file)
                except OSError:
                    self.fail('Failed to generate output file, see log for details')
                self.assertEqual(stat1.st_mode, stat2.st_mode)
                # Data was appeneded to file
                self.assertTrue(stat1.st_size < stat2.st_size)

                # Let's remove the output file
                os.unlink(output_file)

                # Not appending data
                self.run_script(
                    'salt-call',
                    '-c {0} --output-file={1} -g'.format(
                        self.config_dir,
                        output_file
                    ),
                    catch_stderr=True,
                    with_retcode=True
                )
                try:
                    stat3 = os.stat(output_file)
                except OSError:
                    self.fail('Failed to generate output file, see log for details')
                # Mode must have changed since we're creating a new log file
                self.assertNotEqual(stat1.st_mode, stat3.st_mode)
            finally:
                if os.path.exists(output_file):
                    os.unlink(output_file)

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_42116_cli_pillar_override(self):
        ret = self.run_call(
            'state.apply issue-42116-cli-pillar-override '
            'pillar=\'{"myhost": "localhost"}\''
        )
        for line in ret:
            line = line.lstrip()
            if line == 'Comment: Command "ping -c 2 localhost" run':
                # Successful test
                break
        else:
            log.debug('salt-call output:\n\n%s', '\n'.join(ret))
            self.fail('CLI pillar override not found in pillar data')

    def test_pillar_items_masterless(self):
        '''
        Test to ensure we get expected output
        from pillar.items with salt-call
        '''
        get_items = self.run_call('pillar.items', local=True)
        exp_out = ['        - Lancelot', '        - Galahad', '        - Bedevere',
                   '    monty:', '        python']
        for out in exp_out:
            self.assertIn(out, get_items)

    def tearDown(self):
        '''
        Teardown method to remove installed packages
        '''
        user = ''
        user_info = self.run_call(' grains.get username', local=True)
        if user_info and isinstance(user_info, (list, tuple)) and isinstance(user_info[-1], six.string_types):
            user = user_info[-1].strip()
        super(CallTest, self).tearDown()

    # pylint: disable=invalid-name
    def test_exit_status_unknown_argument(self):
        '''
        Ensure correct exit status when an unknown argument is passed to salt-call.
        '''

        call = testprogram.TestProgramSaltCall(
            name='unknown_argument',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        call.setup()
        stdout, stderr, status = call.run(
            args=['--unknown-argument'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_USAGE',
            message='unknown argument',
            stdout=stdout, stderr=stderr
        )

    def test_masterless_highstate(self):
        '''
        test state.highstate in masterless mode
        '''
        ret = self.run_call('state.highstate', local=True)

        destpath = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        exp_out = ['    Function: file.managed', '      Result: True',
                   '          ID: {0}'.format(destpath)]

        for out in exp_out:
            self.assertIn(out, ret)

        self.assertTrue(os.path.exists(destpath))

    def test_exit_status_correct_usage(self):
        '''
        Ensure correct exit status when salt-call starts correctly.
        '''

        call = testprogram.TestProgramSaltCall(
            name='correct_usage',
            parent_dir=self._test_dir,
        )
        # Call setup here to ensure config and script exist
        call.setup()
        stdout, stderr, status = call.run(
            args=['--local', 'test.true'],
            catch_stderr=True,
            with_retcode=True,
        )
        self.assert_exit_status(
            status, 'EX_OK',
            message='correct usage',
            stdout=stdout, stderr=stderr
        )
