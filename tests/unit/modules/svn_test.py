# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import svn

svn.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SvnTestCase(TestCase):
    '''
    Test cases for salt.modules.svn
    '''
    def test_info(self):
        '''
        Test to display the Subversion information from the checkout.
        '''
        mock = MagicMock(side_effect=[{'retcode': 0, 'stdout': True},
                                      {'retcode': 0, 'stdout': 'A\n\nB'},
                                      {'retcode': 0, 'stdout': 'A\n\nB'}])
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.info('cwd', fmt='xml'))

            self.assertListEqual(svn.info('cwd', fmt='list'), [[], []])

            self.assertListEqual(svn.info('cwd', fmt='dict'), [{}, {}])

    def test_checkout(self):
        '''
        Test to download a working copy of the remote Subversion repository
        directory or file
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.checkout('cwd', 'remote'))

    def test_switch(self):
        '''
        Test to switch a working copy of a remote Subversion repository
        directory
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.switch('cwd', 'remote'))

    def test_update(self):
        '''
        Test to update the current directory, files, or directories from
        the remote Subversion repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.update('cwd'))

    def test_diff(self):
        '''
        Test to return the diff of the current directory, files, or
        directories from the remote Subversion repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.diff('cwd'))

    def test_commit(self):
        '''
        Test to commit the current directory, files, or directories to
        the remote Subversion repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.commit('cwd'))

    def test_add(self):
        '''
        Test to add files to be tracked by the Subversion working-copy
        checkout
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.add('cwd', False))

    def test_remove(self):
        '''
        Test to remove files and directories from the Subversion repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.remove('cwd', False))

    def test_status(self):
        '''
        Test to display the status of the current directory, files, or
        directories in the Subversion repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.status('cwd'))

    def test_export(self):
        '''
        Test to create an unversioned copy of a tree.
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(svn.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(svn.export('cwd', 'remote'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SvnTestCase, needs_daemon=False)
