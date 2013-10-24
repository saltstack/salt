# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import yaml
import pipes
import shutil

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class CopyTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

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
        testfile_contents = salt.utils.fopen(testfile, 'r').read()

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

            ret = self.run_cp('{0} {1} {2}'.format(
                pipes.quote(minion),
                pipes.quote(testfile),
                pipes.quote(minion_testfile)
            ))

            data = yaml.load('\n'.join(ret))
            for part in data.values():
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
        config = yaml.load(
            open(self.get_config_file_path(config_file_name), 'r').read()
        )
        config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
        open(os.path.join(config_dir, config_file_name), 'w').write(
            yaml.dump(config, default_flow_style=False)
        )

        self.run_script(
            self._call_binary_,
            '--config-dir {0} \'*\' test.ping'.format(
                config_dir
            ),
            timeout=15
        )
        try:
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        finally:
            if old_cwd is not None:
                os.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CopyTest)
