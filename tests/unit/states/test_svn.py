# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Libs
import salt.states.svn as svn

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SvnTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the svn state
    '''
    def setup_loader_modules(self):
        return {svn: {}}

    def test_latest(self):
        '''
            Checkout or update the working directory to
            the latest revision from the remote repository.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(svn, '_fail', mock):
            self.assertTrue(svn.latest("salt"))

        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.object(os.path, 'exists', mock):
            mock = MagicMock(return_value=False)
            with patch.object(os.path, 'isdir', mock):
                with patch.object(svn, '_fail', mock):
                    self.assertFalse(svn.latest("salt", "c://salt"))

            with patch.dict(svn.__opts__, {'test': True}):
                mock = MagicMock(return_value=["salt"])
                with patch.object(svn, '_neutral_test', mock):
                    self.assertListEqual(svn.latest("salt", "c://salt"),
                                         ['salt'])

                mock = MagicMock(side_effect=[False, True])
                with patch.object(os.path, 'exists', mock):
                    mock = MagicMock(return_value=True)
                    with patch.dict(svn.__salt__, {'svn.diff': mock}):
                        mock = MagicMock(return_value=["Dude"])
                        with patch.object(svn, '_neutral_test', mock):
                            self.assertListEqual(svn.latest("salt",
                                                            "c://salt"),
                                                 ['Dude'])

            with patch.dict(svn.__opts__, {'test': False}):
                mock = MagicMock(return_value=[{'Revision': 'a'}])
                with patch.dict(svn.__salt__, {'svn.info': mock}):
                    mock = MagicMock(return_value=True)
                    with patch.dict(svn.__salt__, {'svn.update': mock}):
                        self.assertDictEqual(svn.latest("salt", "c://salt"),
                                             {'changes': {}, 'comment': True,
                                              'name': 'salt', 'result': True})

    def test_export(self):
        '''
            Test to export a file or directory from an SVN repository
        '''
        mock = MagicMock(return_value=True)
        with patch.object(svn, '_fail', mock):
            self.assertTrue(svn.export("salt"))

        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.object(os.path, 'exists', mock):
            mock = MagicMock(return_value=False)
            with patch.object(os.path, 'isdir', mock):
                with patch.object(svn, '_fail', mock):
                    self.assertFalse(svn.export("salt", "c://salt"))

            with patch.dict(svn.__opts__, {'test': True}):
                mock = MagicMock(return_value=["salt"])
                with patch.object(svn, '_neutral_test', mock):
                    self.assertListEqual(svn.export("salt", "c://salt"),
                                         ['salt'])

                mock = MagicMock(side_effect=[False, True])
                with patch.object(os.path, 'exists', mock):
                    mock = MagicMock(return_value=True)
                    with patch.dict(svn.__salt__, {'svn.list': mock}):
                        mock = MagicMock(return_value=["Dude"])
                        with patch.object(svn, '_neutral_test', mock):
                            self.assertListEqual(svn.export("salt",
                                                            "c://salt"),
                                                 ['Dude'])

            with patch.dict(svn.__opts__, {'test': False}):
                mock = MagicMock(return_value=True)
                with patch.dict(svn.__salt__, {'svn.export': mock}):
                    self.assertDictEqual(svn.export("salt",
                                                    "c://salt"),
                                         {'changes': 'salt was Exported'
                                          ' to c://salt', 'comment': '',
                                          'name': 'salt', 'result': True
                                          }
                                         )

    def test_dirty(self):
        '''
            Test to determine if the working directory has been changed.
        '''
        mock = MagicMock(return_value=True)
        with patch.object(svn, '_fail', mock):
            self.assertTrue(svn.dirty("salt", "c://salt"))
