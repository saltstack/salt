# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import errno
import os
import pipes
import shutil
import tempfile

# Import Salt Testing libs
from tests.support.case import ShellCase
from tests.support.paths import TMP
from tests.support.mixins import ShellCaseCommonTestsMixin

# Import salt libs
import salt.utils.files
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six


class CopyTest(ShellCase, ShellCaseCommonTestsMixin):

    _call_binary_ = 'salt-cp'

    def test_cp_testfile(self):
        '''
        test salt-cp
        '''
        minions = []
        for line in self.run_salt('--out yaml "*" test.ping'):
            if not line:
                continue
            data = salt.utils.yaml.safe_load(line)
            minions.extend(data.keys())

        self.assertNotEqual(minions, [])

        testfile = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'files', 'file', 'base', 'testfile'
            )
        )
        with salt.utils.files.fopen(testfile, 'r') as fh_:
            testfile_contents = fh_.read()

        for idx, minion in enumerate(minions):
            if 'localhost' in minion:
                continue
            ret = self.run_salt(
                '--out yaml {0} file.directory_exists {1}'.format(
                    pipes.quote(minion), TMP
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            if data[minion] is False:
                ret = self.run_salt(
                    '--out yaml {0} file.makedirs {1}'.format(
                        pipes.quote(minion),
                        TMP
                    )
                )

                data = salt.utils.yaml.safe_load('\n'.join(ret))
                self.assertTrue(data[minion])

            minion_testfile = os.path.join(
                TMP, 'cp_{0}_testfile'.format(idx)
            )

            ret = self.run_cp('--out pprint {0} {1} {2}'.format(
                pipes.quote(minion),
                pipes.quote(testfile),
                pipes.quote(minion_testfile)
            ))

            data = salt.utils.yaml.safe_load('\n'.join(ret))
            for part in six.itervalues(data):
                self.assertTrue(part[minion_testfile])

            ret = self.run_salt(
                '--out yaml {0} file.file_exists {1}'.format(
                    pipes.quote(minion),
                    pipes.quote(minion_testfile)
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            self.assertTrue(data[minion])

            ret = self.run_salt(
                '--out yaml {0} file.contains {1} {2}'.format(
                    pipes.quote(minion),
                    pipes.quote(minion_testfile),
                    pipes.quote(testfile_contents)
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            self.assertTrue(data[minion])
            ret = self.run_salt(
                '--out yaml {0} file.remove {1}'.format(
                    pipes.quote(minion),
                    pipes.quote(minion_testfile)
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            self.assertTrue(data[minion])

    def test_issue_7754(self):
        config_dir = os.path.join(TMP, 'issue-7754')

        try:
            os.makedirs(config_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

        config_file_name = 'master'
        with salt.utils.files.fopen(self.get_config_file_path(config_file_name), 'r') as fhr:
            config = salt.utils.yaml.safe_load(fhr)
            config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
            with salt.utils.files.fopen(os.path.join(config_dir, config_file_name), 'w') as fhw:
                salt.utils.yaml.safe_dump(config, fhw, default_flow_style=False)

        try:
            fd_, fn_ = tempfile.mkstemp()
            os.close(fd_)

            with salt.utils.files.fopen(fn_, 'w') as fp_:
                fp_.write('Hello world!\n')

            ret = self.run_script(
                self._call_binary_,
                '--out pprint --config-dir {0} \'*minion\' {1} {0}/{2}'.format(
                    config_dir,
                    fn_,
                    os.path.basename(fn_),
                ),
                catch_stderr=True,
                with_retcode=True
            )

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
            try:
                os.remove(fn_)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)
