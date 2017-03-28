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
    patch
)

# Import Salt Libs
import salt.states.postgres_extension as postgres_extension


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresExtensionTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.postgres_extension
    '''
    def setup_loader_modules(self):
        return {postgres_extension: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named extension is present
        with the specified privileges.
        '''
        name = 'frank'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock = MagicMock(return_value={})
        with patch.dict(postgres_extension.__salt__,
                        {'postgres.create_metadata': mock}):
            with patch.dict(postgres_extension.__opts__, {'test': True}):
                comt = ('Extension {0} is set to be created'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_extension.present(name), ret)

            with patch.dict(postgres_extension.__opts__, {'test': False}):
                comt = ('Extension {0} is already present'.format(name))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(postgres_extension.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named extension is absent.
        '''
        name = 'frank'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(side_effect=[True, False])
        mock = MagicMock(side_effect=[True, True, True, False])
        with patch.dict(postgres_extension.__salt__,
                        {'postgres.is_installed_extension': mock,
                         'postgres.drop_extension': mock_t}):
            with patch.dict(postgres_extension.__opts__, {'test': True}):
                comt = ('Extension {0} is set to be removed'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_extension.absent(name), ret)

            with patch.dict(postgres_extension.__opts__, {'test': False}):
                comt = ('Extension {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Absent'}})
                self.assertDictEqual(postgres_extension.absent(name), ret)

                comt = ('Extension {0} failed to be removed'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(postgres_extension.absent(name), ret)

            comt = ('Extension {0} is not present, so it cannot be removed'
                    .format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(postgres_extension.absent(name), ret)
