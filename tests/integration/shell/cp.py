# -*- coding: utf-8 -*-
'''
    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import yaml
import pipes

# Import salt libs
import salt.utils
import integration
from saltunittest import TestLoader, TextTestRunner


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

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(CopyTest)
    print('Setting up Salt daemons to execute tests')
    with integration.TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
