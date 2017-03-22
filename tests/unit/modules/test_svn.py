# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.svn as svn


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SvnTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.svn
    '''
    def setup_loader_modules(self):
        return {svn: {}}

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
