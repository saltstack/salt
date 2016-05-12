# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
import re
import shutil
import yaml
from datetime import datetime
import logging

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
from salttesting.helpers import (
    destructiveTest
)

log = logging.getLogger(__name__)

_PKG_TARGETS = {
    'Arch': ['python2-django', 'libpng'],
    'Debian': ['python-plist', 'apg'],
    'RedHat': ['xz-devel', 'zsh-html'],
    'FreeBSD': ['aalib', 'pth'],
    'Suse': ['aalib', 'python-pssh']
}


class CallTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

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
        expect = ['{"local": true}']
        self.assertEqual(expect, out)

        out = self.run_call('test.ping -l quiet --out=json --out-indent=0')
        expect = ['{', '"local": true', '}']
        self.assertEqual(expect, out)

        out = self.run_call('test.ping -l quiet --out=json --out-indent=1')
        expect = ['{', ' "local": true', '}']
        self.assertEqual(expect, out)

    def test_local_sls_call(self):
        fileroot = os.path.join(integration.FILES, 'file', 'base')
        out = self.run_call('--file-root {0} --local state.sls saltcalllocal'.format(fileroot))
        self.assertIn('Name: test.echo', ''.join(out))
        self.assertIn('Result: True', ''.join(out))
        self.assertIn('hello', ''.join(out))
        self.assertIn('Succeeded: 1', ''.join(out))

    @destructiveTest
    @skipIf(True, 'Skipping due to off the wall failures and hangs on most os\'s. Will re-enable when fixed.')
    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_local_pkg_install(self):
        '''
        Test to ensure correct output when installing package
        '''
        get_os_family = self.run_call('--local grains.get os_family')
        pkg_targets = _PKG_TARGETS.get(get_os_family[1].strip(), [])
        check_pkg = self.run_call('--local pkg.list_pkgs')
        for pkg in pkg_targets:
            if pkg not in str(check_pkg):
                out = self.run_call('--local pkg.install {0}'.format(pkg))
                self.assertIn('local:    ----------', ''.join(out))
                self.assertIn('{0}:        ----------'.format(pkg), ''.join(out))
                self.assertIn('new:', ''.join(out))
                self.assertIn('old:', ''.join(out))
            else:
                log.debug('The pkg: {0} is already installed on the machine'.format(pkg))

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_user_delete_kw_output(self):
        ret = self.run_call('-l quiet -d user.delete')
        self.assertIn(
            'salt \'*\' user.delete name remove=True force=True',
            ''.join(ret)
        )

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
        src = os.path.join(integration.FILES, 'file/base/top.sls')
        dst = os.path.join(integration.FILES, 'file/base/top.sls.bak')
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
    @skipIf(True, 'to be reenabled when #23623 is merged')
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

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_issue_2731_masterless(self):
        root_dir = os.path.join(integration.TMP, 'issue-2731')
        config_dir = os.path.join(root_dir, 'conf')
        minion_config_file = os.path.join(config_dir, 'minion')
        logfile = os.path.join(root_dir, 'minion_test_issue_2731')

        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        with salt.utils.fopen(self.get_config_file_path('master')) as fhr:
            master_config = yaml.load(fhr.read())

        master_root_dir = master_config['root_dir']
        this_minion_key = os.path.join(
            master_root_dir, 'pki', 'minions', 'minion_test_issue_2731'
        )

        minion_config = {
            'id': 'minion_test_issue_2731',
            'master': 'localhost',
            'master_port': 64506,
            'root_dir': master_root_dir,
            'pki_dir': 'pki',
            'cachedir': 'cachedir',
            'sock_dir': 'minion_sock',
            'open_mode': True,
            'log_file': logfile,
            'log_level': 'quiet',
            'log_level_logfile': 'info',
            'transport': self.master_opts['transport'],
        }

        # Remove existing logfile
        if os.path.isfile(logfile):
            os.unlink(logfile)

        start = datetime.now()
        # Let's first test with a master running
        with salt.utils.fopen(minion_config_file, 'w') as fh_:
            fh_.write(
                yaml.dump(minion_config, default_flow_style=False)
            )
        ret = self.run_script(
            'salt-call',
            '--config-dir {0} cmd.run "echo foo"'.format(
                config_dir
            )
        )
        try:
            self.assertIn('local:', ret)
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
        with salt.utils.fopen(minion_config_file, 'w') as fh_:
            fh_.write(
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
            self.assertIn('local:', ret)
        except AssertionError:
            if os.path.isfile(minion_config_file):
                os.unlink(minion_config_file)
            # Let's remove our key from the master
            if os.path.isfile(this_minion_key):
                os.unlink(this_minion_key)
            raise

        # Should work with local file client
        minion_config['file_client'] = 'local'
        with salt.utils.fopen(minion_config_file, 'w') as fh_:
            fh_.write(
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
            self.assertIn('local:', ret)
        finally:
            if os.path.isfile(minion_config_file):
                os.unlink(minion_config_file)
            # Let's remove our key from the master
            if os.path.isfile(this_minion_key):
                os.unlink(this_minion_key)

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(integration.TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        with salt.utils.fopen(self.get_config_file_path('minion'), 'r') as fh_:
            minion_config = yaml.load(fh_.read())
            minion_config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
            with salt.utils.fopen(os.path.join(config_dir, 'minion'), 'w') as fh_:
                fh_.write(
                    yaml.dump(minion_config, default_flow_style=False)
                )
        ret = self.run_script(
            'salt-call',
            '--config-dir {0} cmd.run "echo foo"'.format(
                config_dir
            ),
            timeout=15,
            catch_stderr=True,
            with_retcode=True
        )
        try:
            self.assertIn('local:', ret[0])
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        except AssertionError:
            # We now fail when we're unable to properly set the syslog logger
            self.assertIn(
                'Failed to setup the Syslog logging handler', '\n'.join(ret[1])
            )
            self.assertEqual(ret[2], 2)
        finally:
            self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)

    def test_issue_15074_output_file_append(self):
        output_file_append = os.path.join(integration.TMP, 'issue-15074')
        try:
            # Let's create an initial output file with some data
            ret = self.run_script(
                'salt-call',
                '-c {0} --output-file={1} test.versions'.format(
                    self.get_config_dir(),
                    output_file_append
                ),
                catch_stderr=True,
                with_retcode=True
            )

            with salt.utils.fopen(output_file_append) as ofa:
                output = ofa.read()

            self.run_script(
                'salt-call',
                '-c {0} --output-file={1} --output-file-append test.versions'.format(
                    self.get_config_dir(),
                    output_file_append
                ),
                catch_stderr=True,
                with_retcode=True
            )
            with salt.utils.fopen(output_file_append) as ofa:
                self.assertEqual(ofa.read(), output + output)
        finally:
            if os.path.exists(output_file_append):
                os.unlink(output_file_append)

    def test_issue_14979_output_file_permissions(self):
        output_file = os.path.join(integration.TMP, 'issue-14979')
        current_umask = os.umask(0o077)
        try:
            # Let's create an initial output file with some data
            self.run_script(
                'salt-call',
                '-c {0} --output-file={1} -g'.format(
                    self.get_config_dir(),
                    output_file
                ),
                catch_stderr=True,
                with_retcode=True
            )
            stat1 = os.stat(output_file)

            # Let's change umask
            os.umask(0o777)

            self.run_script(
                'salt-call',
                '-c {0} --output-file={1} --output-file-append -g'.format(
                    self.get_config_dir(),
                    output_file
                ),
                catch_stderr=True,
                with_retcode=True
            )
            stat2 = os.stat(output_file)
            self.assertEqual(stat1.st_mode, stat2.st_mode)
            # Data was appeneded to file
            self.assertTrue(stat1.st_size < stat2.st_size)

            # Let's remove the output file
            os.unlink(output_file)

            # Not appending data
            self.run_script(
                'salt-call',
                '-c {0} --output-file={1} -g'.format(
                    self.get_config_dir(),
                    output_file
                ),
                catch_stderr=True,
                with_retcode=True
            )
            stat3 = os.stat(output_file)
            # Mode must have changed since we're creating a new log file
            self.assertNotEqual(stat1.st_mode, stat3.st_mode)
            # Data was appended to file
            self.assertEqual(stat1.st_size, stat3.st_size)
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
            # Restore umask
            os.umask(current_umask)

    def tearDown(self):
        '''
        Teardown method to remove installed packages
        '''
        check_pkg = self.run_call('--local pkg.list_pkgs')
        get_os_family = self.run_call('--local grains.get os_family')
        pkg_targets = _PKG_TARGETS.get(get_os_family[1].strip(), [])
        check_pkg = self.run_call('--local pkg.list_pkgs')
        for pkg in pkg_targets:
            if pkg in str(check_pkg):
                out = self.run_call('--local pkg.remove {0}'.format(pkg))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(CallTest)
