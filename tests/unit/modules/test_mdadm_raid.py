# -*- coding: utf-8 -*-
'''
    :codeauthor: Ted Strzalkowski (tedski@gmail.com)


    tests.unit.modules.mdadm_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.mdadm_raid as mdadm


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MdadmTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {mdadm: {}}

    def test_create(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(mdadm.__salt__, {'cmd.run': mock}), \
                patch('salt.utils.path.which', lambda exe: exe):
            ret = mdadm.create(
                    '/dev/md0', 5,
                    devices=['/dev/sdb1', '/dev/sdc1', '/dev/sdd1'],
                    test_mode=False,
                    force=True,
                    chunk=256
            )
            self.assertEqual('salt', ret)

            self.assert_called_once(mock)

            args, kwargs = mock.call_args
            # expected cmd is
            # mdadm -C /dev/md0 -R -v --chunk 256 --force -l 5 -e default -n 3 /dev/sdb1 /dev/sdc1 /dev/sdd1
            # where args between -v and -l could be in any order
            self.assertEqual(len(args), 1)
            self.assertEqual(len(args[0]), 17)
            self.assertEqual(args[0][:7], [
                'mdadm',
                '-C', '/dev/md0',
                '-R',
                '-v',
                 '-l', '5',
                ])
            self.assertEqual(args[0][10:], [
                 '-e', 'default',
                 '-n', '3',
                 '/dev/sdb1', '/dev/sdc1', '/dev/sdd1'])
            self.assertEqual(sorted(args[0][7:10]), sorted(['--chunk', '256', '--force']))
            self.assertIn('--chunk 256', ' '.join(args[0][7:10]))
            self.assertEqual(kwargs, {'python_shell': False})

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

    def test_examine(self):
        '''
        Test for mdadm_raid.examine
        '''
        mock = MagicMock(return_value='ARRAY /dev/md/pool metadata=1.2 UUID=567da122:fb8e445e:55b853e0:81bd0a3e name=positron:pool')
        with patch.dict(mdadm.__salt__, {'cmd.run_stdout': mock}):
            self.assertEqual(mdadm.examine('/dev/md0'),
                             {
                                 'ARRAY /dev/md/pool metadata': '1.2 UUID=567da122:fb8e445e:55b853e0:81bd0a3e name=positron:pool'
                             })
            mock.assert_called_with('mdadm -Y -E /dev/md0', ignore_retcode=False,
                                    python_shell=False)

    def test_examine_quiet(self):
        '''
        Test for mdadm_raid.examine
        '''
        mock = MagicMock(return_value='')
        with patch.dict(mdadm.__salt__, {'cmd.run_stdout': mock}):
            self.assertEqual(mdadm.examine('/dev/md0', quiet=True), {})
            mock.assert_called_with('mdadm -Y -E /dev/md0', ignore_retcode=True,
                                    python_shell=False)
