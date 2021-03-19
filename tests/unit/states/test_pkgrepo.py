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

    def test_new_key_url(self):
        '''
        Test when only the key_url is changed that a change is triggered
        '''
        kwargs = {
            'name': 'deb http://mock/ sid main',
            'disabled': False,
        }
        key_url = 'http://mock/changed_gpg.key'

        with patch.dict(pkgrepo.__salt__, {'pkg.get_repo': MagicMock(return_value=kwargs)}):
            ret = pkgrepo.managed(key_url=key_url, **kwargs)
            self.assertDictEqual({
                    'key_url': {
                        'old': None,
                        'new': key_url
                    }
                }, ret['changes'])

    def test_update_key_url(self):
        '''
        Test when only the key_url is changed that a change is triggered
        '''
        kwargs = {
            'name': 'deb http://mock/ sid main',
            'gpgcheck': 1,
            'disabled': False,
            'key_url': 'http://mock/gpg.key',
        }
        changed_kwargs = kwargs.copy()
        changed_kwargs['key_url'] = 'http://mock/gpg2.key'

        with patch.dict(pkgrepo.__salt__, {'pkg.get_repo': MagicMock(return_value=kwargs)}):
            ret = pkgrepo.managed(**changed_kwargs)
            self.assertIn('key_url', ret['changes'], 'Expected a change to key_url')
            self.assertDictEqual({
                'key_url': {
                    'old': kwargs['key_url'],
                    'new': changed_kwargs['key_url']
                }
            }, ret['changes'])
