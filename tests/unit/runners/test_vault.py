# -*- coding: utf-8 -*-
'''
Unit tests for the Vault runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    Mock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
from salt.ext import six
import salt.runners.vault as vault

log = logging.getLogger(__name__)


class VaultTest(TestCase, LoaderModuleMockMixin):
    '''
    Tests for the runner module of the Vault integration
    '''

    def setup_loader_modules(self):
        return {
            vault: {
            '__opts__': {'vault': {'url': "http://127.0.0.1", "auth": {'token': 'test', 'method': 'token'}}}
            }
        }

    def setUp(self):
        self.grains = {
                        'id': 'test-minion',
                        'roles': ['web', 'database'],
                        'aux': ['foo', 'bar'],
                        'deep': {
                            'foo': {
                                'bar': {
                                    'baz': [
                                        'hello',
                                        'world'
                                    ]
                                }
                            }
                        },
                        'mixedcase': 'UP-low-UP'
                      }

    def tearDown(self):
        del self.grains

    def test_pattern_list_expander(self):
        '''
        Ensure _expand_pattern_lists works as intended:
        - Expand list-valued patterns
        - Do not change non-list-valued tokens
        '''
        cases = {
                    'no-tokens-to-replace': ['no-tokens-to-replace'],
                    'single-dict:{minion}': ['single-dict:{minion}'],
                    'single-list:{grains[roles]}': ['single-list:web', 'single-list:database'],
                    'multiple-lists:{grains[roles]}+{grains[aux]}': [
                       'multiple-lists:web+foo',
                       'multiple-lists:web+bar',
                       'multiple-lists:database+foo',
                       'multiple-lists:database+bar',
                    ],
                    'single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}': [
                        'single-list-with-dicts:{grains[id]}+web+{grains[id]}',
                        'single-list-with-dicts:{grains[id]}+database+{grains[id]}'
                    ],
                    'deeply-nested-list:{grains[deep][foo][bar][baz]}': [
                        'deeply-nested-list:hello',
                        'deeply-nested-list:world'
                    ]
                }

        # The mappings dict is assembled in _get_policies, so emulate here
        mappings = {'minion': self.grains['id'], 'grains': self.grains}
        for case, correct_output in six.iteritems(cases):
            output = vault._expand_pattern_lists(case, **mappings)  # pylint: disable=protected-access
            diff = set(output).symmetric_difference(set(correct_output))
            if len(diff) != 0:
                log.debug('Test %s failed', case)
                log.debug('Expected:\n\t%s\nGot\n\t%s', output, correct_output)
                log.debug('Difference:\n\t%s', diff)
            self.assertEqual(output, correct_output)

    def test_get_policies_for_nonexisting_minions(self):
        minion_id = 'salt_master'
        # For non-existing minions, or the master-minion, grains will be None
        cases = {
                    'no-tokens-to-replace': ['no-tokens-to-replace'],
                    'single-dict:{minion}': ['single-dict:{0}'.format(minion_id)],
                    'single-list:{grains[roles]}': []
        }
        with patch('salt.utils.minions.get_minion_data',
                   MagicMock(return_value=(None, None, None))):
            for case, correct_output in six.iteritems(cases):
                test_config = {'policies': [case]}
                output = vault._get_policies(minion_id, test_config)  # pylint: disable=protected-access
                diff = set(output).symmetric_difference(set(correct_output))
                if len(diff) != 0:
                    log.debug('Test %s failed', case)
                    log.debug('Expected:\n\t%s\nGot\n\t%s', output, correct_output)
                    log.debug('Difference:\n\t%s', diff)
                self.assertEqual(output, correct_output)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_get_policies(self):
        '''
        Ensure _get_policies works as intended, including expansion of lists
        '''
        cases = {
                    'no-tokens-to-replace': ['no-tokens-to-replace'],
                    'single-dict:{minion}': ['single-dict:test-minion'],
                    'single-list:{grains[roles]}': ['single-list:web', 'single-list:database'],
                    'multiple-lists:{grains[roles]}+{grains[aux]}': [
                       'multiple-lists:web+foo',
                       'multiple-lists:web+bar',
                       'multiple-lists:database+foo',
                       'multiple-lists:database+bar',
                    ],
                    'single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}': [
                        'single-list-with-dicts:test-minion+web+test-minion',
                        'single-list-with-dicts:test-minion+database+test-minion'
                    ],
                    'deeply-nested-list:{grains[deep][foo][bar][baz]}': [
                        'deeply-nested-list:hello',
                        'deeply-nested-list:world'
                    ],
                    'should-not-cause-an-exception,but-result-empty:{foo}': [],
                    'Case-Should-Be-Lowered:{grains[mixedcase]}': [
                        'case-should-be-lowered:up-low-up'
                    ]
                }

        with patch('salt.utils.minions.get_minion_data',
                   MagicMock(return_value=(None, self.grains, None))):
            for case, correct_output in six.iteritems(cases):
                test_config = {'policies': [case]}
                output = vault._get_policies('test-minion', test_config)  # pylint: disable=protected-access
                diff = set(output).symmetric_difference(set(correct_output))
                if len(diff) != 0:
                    log.debug('Test %s failed', case)
                    log.debug('Expected:\n\t%s\nGot\n\t%s', output, correct_output)
                    log.debug('Difference:\n\t%s', diff)
                self.assertEqual(output, correct_output)


    def _mock_json_response(self, data):
        response = MagicMock()
        response.json = MagicMock(return_value=data)
        response.status_code = 200
        return Mock(return_value=response)


    # define matcher:
    # @urlmatch(netloc=r'^vault$')
    # def _vault_mock(url, request):
    #     return '{"": ""}'
    
    def test_generate_token(self):
        # open context to patch
        with patch('salt.runners.vault._validate_signature', MagicMock(return_value=None)):
            with patch('requests.post', self._mock_json_response({'auth': {'client_token': 'test'}})):
                result = vault.generate_token('test-minion', 'signature')
                log.debug('generate_token result: %s', result)
                self.assertTrue(isinstance(result, dict))
                self.assertFalse('error' in result)
                


    def test_get_vault_url(self):
        self.assertEqual(vault._get_vault_url(
            {"url": "http://127.0.0.1"}),
            "http://127.0.0.1/v1/auth/token/create")
        self.assertEqual(vault._get_vault_url(
            {"url": "https://127.0.0.1/test"}),
            "https://127.0.0.1/v1/auth/token/create")
        self.assertEqual(vault._get_vault_url(
            {"url": "http://127.0.0.1", "role_name": "therole"}),
            "http://127.0.0.1/v1/auth/token/create/therole")
        self.assertEqual(vault._get_vault_url(
            {"url": "https://127.0.0.1/test", "role_name": "therole"}),
            "https://127.0.0.1/v1/auth/token/create/therole")
        self.assertEqual(vault._get_vault_url(
            {"url": "https://127.0.0.1/test?s=test", "role_name": "therole&"}),
            "https://127.0.0.1/v1/auth/token/create/therole%26")
