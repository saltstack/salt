# -*- coding: utf-8 -*-
'''
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.pkgrepo as pkgrepo


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgrepoTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.pkgrepo
    '''

    def setup_loader_modules(self):
        return {
            pkgrepo: {
                '__opts__': {'test': True},
                '__grains__': {'os': '', 'os_family': ''}
            }
        }

    # 'update_packaging_site' function tests: 1

    def test_update_key_url(self):
        '''
        Test when only the key_url is changed that a change is triggered
        '''
        kwargs = {
            'humanname': 'Mocked Repo',
            'name': 'deb http://mock/ stretch main',
            'gpgcheck': 1,
            'key_url': 'http://mock/changed_gpg.key',
        }
        previous_state = {
            'humanname': 'Mocked Repo',
            'name': 'deb http://mock/ stretch main',
            'gpgcheck': 1,
            'key_url': 'http://mock/gpg.key',
            'disabled': False,
        }

        with patch.dict(pkgrepo.__salt__, {'pkg.get_repo': MagicMock(return_value=previous_state)}):
            ret = pkgrepo.managed(**kwargs)
            # pprint(ret)
            self.assertDictEqual({
                'old': previous_state['key_url'],
                'new': kwargs['key_url'],
            }, ret['changes'].get('key_url', dict()))
