# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import yaml
import pipes
import shutil

# Import Salt Testing libs
import tests.integration as integration

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


class CopyTest(integration.ShellCase, integration.ShellCaseCommonTestsMixin):

    _call_binary_ = 'salt-cp'

    def test_cp_testfile(self):
        '''
        test salt-cp
        '''
        minions = []
        for line in self.run_salt('--out yaml "*" test.ping'):
            if not line:
                continue
            data = yaml.load(line)
            minions.extend(data.keys())

        self.assertNotEqual(minions, [])

        testfile = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'files', 'file', 'base', 'testfile'
            )
        )
        with salt.utils.fopen(testfile, 'r') as fh_:
            testfile_contents = fh_.read()

        for idx, minion in enumerate(minions):
            ret = self.run_salt(
                '--out yaml {0} file.directory_exists {1}'.format(
                    pipes.quote(minion), integration.TMP
                )
            )
            data = yaml.load('\n'.join(ret))
            if data[minion] is False:
                ret = self.run_salt(
                    '--out yaml {0} file.makedirs {1}'.format(
                        pipes.quote(minion),
                        integration.TMP
                    )
                )

                data = yaml.load('\n'.join(ret))
                self.assertTrue(data[minion])

            minion_testfile = os.path.join(
                integration.TMP, 'cp_{0}_testfile'.format(idx)
            )

            ret = self.run_cp('--out pprint {0} {1} {2}'.format(
                pipes.quote(minion),
                pipes.quote(testfile),
                pipes.quote(minion_testfile)
            ))

            data = yaml.load('\n'.join(ret))
            for part in six.itervalues(data):
                self.assertTrue(part[minion_testfile])

            ret = self.run_salt(
                '--out yaml {0} file.file_exists {1}'.format(
                    pipes.quote(minion),
                    pipes.quote(minion_testfile)
                )
            )
            data = yaml.load('\n'.join(ret))
            self.assertTrue(data[minion])

            ret = self.run_salt(
                '--out yaml {0} file.contains {1} {2}'.format(
                    pipes.quote(minion),
                    pipes.quote(minion_testfile),
                    pipes.quote(testfile_contents)
                )
            )
            data = yaml.load('\n'.join(ret))
            self.assertTrue(data[minion])
            ret = self.run_salt(
                '--out yaml {0} file.remove {1}'.format(
                    pipes.quote(minion),
                    pipes.quote(minion_testfile)
                )
            )
            data = yaml.load('\n'.join(ret))
            self.assertTrue(data[minion])

    def test_issue_7754(self):
        try:
            old_cwd = os.getcwd()
        except OSError:
            # Jenkins throws an OSError from os.getcwd()??? Let's not worry
            # about it
            old_cwd = None

        config_dir = os.path.join(integration.TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'master'
        with salt.utils.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = yaml.load(fhr.read())
            config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
            with salt.utils.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                fhw.write(
                    yaml.dump(config, default_flow_style=False)
                )

        ret = self.run_script(
            self._call_binary_,
            '--out pprint --config-dir {0} \'*\' foo {0}/foo'.format(
                config_dir
            ),
            catch_stderr=True,
            with_retcode=True
        )
        try:
            self.assertIn('minion', '\n'.join(ret[0]))
            self.assertIn('sub_minion', '\n'.join(ret[0]))
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        except AssertionError:
            if os.path.exists('/dev/log') and ret[2] != 2:
                # If there's a syslog device and the exit code was not 2, 'No
                # such file or directory', raise the error
                raise
            self.assertIn(
                'Failed to setup the Syslog logging handler', '\n'.join(ret[1])
            )
            self.assertEqual(ret[2], 2)
        finally:
            if old_cwd is not None:
                self.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)
