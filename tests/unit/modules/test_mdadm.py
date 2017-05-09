# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Ted Strzalkowski (tedski@gmail.com)`


    tests.unit.modules.mdadm_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.mdadm as mdadm

# Import 3rd-party libs
import salt.ext.six as six


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MdadmTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {mdadm: {}}

    def test_create(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(mdadm.__salt__, {'cmd.run': mock}), \
                patch('salt.utils.which', lambda exe: exe):
            ret = mdadm.create(
                    '/dev/md0', 5,
                    devices=['/dev/sdb1', '/dev/sdc1', '/dev/sdd1'],
                    test_mode=False,
                    force=True,
                    chunk=256
            )
            self.assertEqual('salt', ret)
            if six.PY2:
                expected_args = [
                    'mdadm',
                    '-C', '/dev/md0',
                    '-R',
                    '-v',
                    '--chunk', '256',
                    '--force',
                     '-l', '5',
                     '-e', 'default',
                     '-n', '3',
                     '/dev/sdb1', '/dev/sdc1', '/dev/sdd1']
            else:
                expected_args = [
                    'mdadm',
                    '-C', '/dev/md0',
                    '-R',
                    '-v',
                    '--force',
                    '--chunk', '256',
                    '-l', '5',
                    '-e', 'default',
                    '-n', '3',
                    '/dev/sdb1', '/dev/sdc1', '/dev/sdd1'
                ]
            mock.assert_called_once_with(expected_args, python_shell=False)

    def test_create_test_mode(self):
        mock = MagicMock()
        with patch.dict(mdadm.__salt__, {'cmd.run': mock}):
            ret = mdadm.create(
                    '/dev/md0', 5,
                    devices=['/dev/sdb1', '/dev/sdc1', '/dev/sdd1'],
                    force=True,
                    chunk=256,
                    test_mode=True
            )
            self.assertEqual(sorted('mdadm -C /dev/md0 -R -v --chunk 256 '
                              '--force -l 5 -e default -n 3 '
                              '/dev/sdb1 /dev/sdc1 /dev/sdd1'.split()), sorted(ret.split()))
            assert not mock.called, 'test mode failed, cmd.run called'
