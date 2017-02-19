# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import hg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.hg
    '''
    loader_module = hg

    def test_revision(self):
        '''
        Test for Returns the long hash of a given identifier
        '''
        mock = MagicMock(side_effect=[{'retcode': 0, 'stdout': 'A'},
                                        {'retcode': 1, 'stdout': 'A'}])
        with patch.dict(hg.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(hg.revision('cwd'), 'A')

            self.assertEqual(hg.revision('cwd'), '')

    def test_describe(self):
        '''
        Test for Mimic git describe.
        '''
        with patch.dict(hg.__salt__, {'cmd.run_stdout':
                                        MagicMock(return_value='A')}):
            with patch.object(hg, 'revision', return_value=False):
                self.assertEqual(hg.describe('cwd'), 'A')

    def test_archive(self):
        '''
        Test for Export a tarball from the repository
        '''
        with patch.dict(hg.__salt__, {'cmd.run':
                                      MagicMock(return_value='A')}):
            self.assertEqual(hg.archive('cwd', 'output'), 'A')

    def test_pull(self):
        '''
        Test for Perform a pull on the given repository
        '''
        with patch.dict(hg.__salt__, {'cmd.run_all':
                                      MagicMock(return_value={'retcode': 0,
                                                              'stdout': 'A'})}):
            self.assertEqual(hg.pull('cwd'), 'A')

    def test_update(self):
        '''
        Test for Update to a given revision
        '''
        with patch.dict(hg.__salt__, {'cmd.run_all':
                                      MagicMock(return_value={'retcode': 0,
                                                              'stdout': 'A'})}):
            self.assertEqual(hg.update('cwd', 'rev'), 'A')

    def test_clone(self):
        '''
        Test for Clone a new repository
        '''
        with patch.dict(hg.__salt__, {'cmd.run_all':
                                      MagicMock(return_value={'retcode': 0,
                                                              'stdout': 'A'})}):
            self.assertEqual(hg.clone('cwd', 'repository'), 'A')

    def test_status_single(self):
        '''
        Test for Status to a given repository
        '''
        with patch.dict(hg.__salt__, {'cmd.run_stdout':
                                        MagicMock(return_value=(
                                            'A added 0\n'
                                            'A added 1\n'
                                            'M modified'))}):
            self.assertEqual(hg.status('cwd'), {
                'added': ['added 0', 'added 1'],
                'modified': ['modified'],
            })

    def test_status_multiple(self):
        '''
        Test for Status to a given repository (cwd is list)
        '''
        with patch.dict(hg.__salt__, {
            'cmd.run_stdout': MagicMock(side_effect=(
                lambda *args, **kwargs: {
                    'dir 0': 'A file 0\n',
                    'dir 1': 'M file 1'
                }[kwargs['cwd']]))}):
            self.assertEqual(hg.status(['dir 0', 'dir 1']), {
                'dir 0': {'added': ['file 0']},
                'dir 1': {'modified': ['file 1']},
            })
