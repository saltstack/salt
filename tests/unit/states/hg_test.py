# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Libs
from salt.states import hg

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

ensure_in_syspath('../../')

hg.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HgTestCase(TestCase):
    '''
        Validate the svn state
    '''
    def test_latest(self):
        '''
            Test to Make sure the repository is cloned to
            the given directory and is up to date
        '''
        ret = {'changes': {}, 'comment': '', 'name': 'salt', 'result': True}
        mock = MagicMock(return_value=True)
        with patch.object(hg, '_fail', mock):
            self.assertTrue(hg.latest("salt"))

        mock = MagicMock(side_effect=[False, True, False, False, False, False])
        with patch.object(os.path, 'isdir', mock):
            mock = MagicMock(return_value=True)
            with patch.object(hg, '_handle_existing', mock):
                self.assertTrue(hg.latest("salt", target="c:\\salt"))

            with patch.dict(hg.__opts__, {'test': True}):
                mock = MagicMock(return_value=True)
                with patch.object(hg, '_neutral_test', mock):
                    self.assertTrue(hg.latest("salt", target="c:\\salt"))

            with patch.dict(hg.__opts__, {'test': False}):
                mock = MagicMock(return_value=True)
                with patch.object(hg, '_clone_repo', mock):
                    self.assertDictEqual(hg.latest("salt", target="c:\\salt"),
                                         ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HgTestCase, needs_daemon=False)
