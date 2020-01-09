# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os
import pipes
import logging

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ShellCase
from tests.support.mixins import ShellCaseCommonTestsMixin

# Import salt libs
import salt.utils.platform
import salt.utils.files
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six


log = logging.getLogger(__name__)


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

        def quote(arg):
            if salt.utils.platform.is_windows():
                return arg
            return pipes.quote(arg)

        for idx, minion in enumerate(minions):
            if 'localhost' in minion:
                continue
            ret = self.run_salt(
                '--out yaml {0} file.directory_exists {1}'.format(
                    quote(minion), RUNTIME_VARS.TMP
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            if data[minion] is False:
                ret = self.run_salt(
                    '--out yaml {0} file.makedirs {1}'.format(
                        quote(minion),
                        RUNTIME_VARS.TMP
                    )
                )

                data = salt.utils.yaml.safe_load('\n'.join(ret))
                self.assertTrue(data[minion])

            minion_testfile = os.path.join(
                RUNTIME_VARS.TMP, 'cp_{0}_testfile'.format(idx)
            )

            ret = self.run_cp('--out pprint {0} {1} {2}'.format(
                quote(minion),
                quote(testfile),
                quote(minion_testfile),
            ))

            data = eval('\n'.join(ret), {}, {})  # pylint: disable=eval-used
            for part in six.itervalues(data):
                key = minion_testfile
                self.assertTrue(part[key])

            ret = self.run_salt(
                '--out yaml {0} file.file_exists {1}'.format(
                    quote(minion),
                    quote(minion_testfile)
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            self.assertTrue(data[minion])

            ret = self.run_salt(
                '--out yaml {0} file.contains {1} {2}'.format(
                    quote(minion),
                    quote(minion_testfile),
                    quote(testfile_contents)
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            self.assertTrue(data[minion])
            ret = self.run_salt(
                '--out yaml {0} file.remove {1}'.format(
                    quote(minion),
                    quote(minion_testfile)
                )
            )
            data = salt.utils.yaml.safe_load('\n'.join(ret))
            self.assertTrue(data[minion])
