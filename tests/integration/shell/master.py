# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.integration.shell.master
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import yaml
import signal
import shutil

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class MasterTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-master'

    def test_issue_7754(self):
        old_cwd = os.getcwd()
        config_dir = os.path.join(integration.TMP, 'issue-7754')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir)

        os.chdir(config_dir)

        config_file_name = 'master'
        pid_path = os.path.join(config_dir, '{0}.pid'.format(config_file_name))
        config = yaml.load(
            open(self.get_config_file_path(config_file_name), 'r').read()
        )
        config['root_dir'] = config_dir
        config['log_file'] = 'file:///dev/log/LOG_LOCAL3'
        config['ret_port'] = config['ret_port'] + 10
        config['publish_port'] = config['publish_port'] + 10

        open(os.path.join(config_dir, config_file_name), 'w').write(
            yaml.dump(config, default_flow_style=False)
        )

        self.run_script(
            self._call_binary_,
            '--config-dir {0} --pid-file {1} -l debug'.format(
                config_dir,
                pid_path
            ),
            timeout=5,
            catch_stderr=True
        )

        # Now kill it if still running
        if os.path.exists(pid_path):
            try:
                os.kill(int(open(pid_path).read()), signal.SIGKILL)
            except OSError:
                pass
        try:
            self.assertFalse(os.path.isdir(os.path.join(config_dir, 'file:')))
        finally:
            os.chdir(old_cwd)
            if os.path.isdir(config_dir):
                shutil.rmtree(config_dir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MasterTest)
