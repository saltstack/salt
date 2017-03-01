# -*- coding: utf-8 -*-
'''
Unit tests for the Vault runner
'''

# Import Python Libs
from __future__ import absolute_import
import logging
from salt.ext import six
from salt.runners import vault

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


log = logging.getLogger(__name__)
ensure_in_syspath('../../')

vault.__opts__ = {}


class VaultTest(TestCase):
    '''
    Tests for the runner module of the Vault integration
    '''

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
                        'dictlist': [
                            {'foo': 'bar'},
                            {'baz': 'qux'}
                        ]
                      }

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
                log.debug('Test {0} failed'.format(case))
                log.debug('Expected:\n\t{0}\nGot\n\t{1}'.format(output, correct_output))
                log.debug('Difference:\n\t{0}'.format(diff))
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
                    'should-not-cause-an-exception,but-result-empty:{foo}': []
                }

        with patch('salt.utils.minions.get_minion_data',
                   MagicMock(return_value=(None, self.grains, None))):
            for case, correct_output in six.iteritems(cases):
                test_config = {'policies': [case]}
                output = vault._get_policies('test-minion', test_config)  # pylint: disable=protected-access
                diff = set(output).symmetric_difference(set(correct_output))
                if len(diff) != 0:
                    log.debug('Test {0} failed'.format(case))
                    log.debug('Expected:\n\t{0}\nGot\n\t{1}'.format(output, correct_output))
                    log.debug('Difference:\n\t{0}'.format(diff))
                self.assertEqual(output, correct_output)


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(VaultTest, needs_daemon=False)
