# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import hg

# Globals
hg.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HgTestCase(TestCase):
    '''
    Test cases for salt.modules.hg
    '''
    def test_revision(self):
        '''
        Test for Returns the long hash of a given identifier
        '''
        with patch.object(hg, '_check_hg', return_value=None):
            mock = MagicMock(side_effect=[{'retcode': 0, 'stdout': 'A'},
                                          {'retcode': 1, 'stdout': 'A'}])
            with patch.dict(hg.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(hg.revision('cwd'), 'A')

                self.assertEqual(hg.revision('cwd'), '')

    def test_describe(self):
        '''
        Test for Mimic git describe.
        '''
        with patch.object(hg, '_check_hg', return_value=None):
            with patch.dict(hg.__salt__, {'cmd.run_stdout':
                                          MagicMock(return_value='A')}):
                with patch.object(hg, 'revision', return_value=False):
                    self.assertEqual(hg.describe('cwd'), 'A')

    def test_archive(self):
        '''
        Test for Export a tarball from the repository
        '''
        with patch.object(hg, '_check_hg', return_value=None):
            with patch.dict(hg.__salt__, {'cmd.run':
                                          MagicMock(return_value='A')}):
                self.assertEqual(hg.archive('cwd', 'output'), 'A')

    def test_pull(self):
        '''
        Test for Perform a pull on the given repository
        '''
        with patch.object(hg, '_check_hg', return_value=None):
            with patch.dict(hg.__salt__, {'cmd.run':
                                          MagicMock(return_value='A')}):
                self.assertEqual(hg.pull('cwd'), 'A')

    def test_update(self):
        '''
        Test for Update to a given revision
        '''
        with patch.object(hg, '_check_hg', return_value=None):
            with patch.dict(hg.__salt__, {'cmd.run':
                                          MagicMock(return_value='A')}):
                self.assertEqual(hg.update('cwd', 'rev'), 'A')

    def test_clone(self):
        '''
        Test for Clone a new repository
        '''
        with patch.object(hg, '_check_hg', return_value=None):
            with patch.dict(hg.__salt__, {'cmd.run':
                                          MagicMock(return_value='A')}):
                self.assertEqual(hg.clone('cwd', 'repository'), 'A')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HgTestCase, needs_daemon=False)
