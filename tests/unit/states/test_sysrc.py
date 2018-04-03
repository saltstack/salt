# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

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
import salt.states.sysrc as sysrc


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SysrcTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the sysrc state
    '''
    def setup_loader_modules(self):
        return {sysrc: {}}

    def test_managed(self):
        '''
            Test to ensure a sysrc variable is set to a specific value.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=[{'key1': {'salt': 'stack'}}, None, None])
        mock1 = MagicMock(return_value=True)
        with patch.dict(sysrc.__salt__, {"sysrc.get": mock,
                                         "sysrc.set": mock1}):
            ret.update({'comment': 'salt is already set to the desired'
                        ' value.'})
            self.assertDictEqual(sysrc.managed('salt', 'stack'), ret)

            with patch.dict(sysrc.__opts__, {"test": True}):
                ret.update({'changes': {'new': 'salt = stack will be set.',
                                        'old': None}, 'comment': 'The value'
                            ' of "salt" will be changed!', 'result': None})
                self.assertDictEqual(sysrc.managed('salt', 'stack'), ret)

            with patch.dict(sysrc.__opts__, {"test": False}):
                ret.update({'changes': {'new': True, 'old': None},
                            'comment': 'The value of "salt" was changed!',
                            'result': True})
                self.assertDictEqual(sysrc.managed('salt', 'stack'), ret)

    def test_absent(self):
        '''
            Test to ensure a sysrc variable is absent.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=[None, True, True])
        mock1 = MagicMock(return_value=True)
        with patch.dict(sysrc.__salt__, {"sysrc.get": mock,
                                         "sysrc.remove": mock1}):
            ret.update({'comment': '"salt" is already absent.'})
            self.assertDictEqual(sysrc.absent('salt'), ret)

            with patch.dict(sysrc.__opts__, {"test": True}):
                ret.update({'changes': {'new': '"salt" will be removed.',
                                        'old': True},
                            'comment': '"salt" will be removed!',
                            'result': None})
                self.assertDictEqual(sysrc.absent('salt'), ret)

            with patch.dict(sysrc.__opts__, {"test": False}):
                ret.update({'changes': {'new': True, 'old': True},
                            'comment': '"salt" was removed!',
                            'result': True})
                self.assertDictEqual(sysrc.absent('salt'), ret)
