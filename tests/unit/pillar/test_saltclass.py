# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.pillar.saltclass as saltclass
from salt.exceptions import SaltException

base_path = os.path.dirname(os.path.realpath(__file__))
fake_minion_id1 = 'fake_id1'
fake_minion_id2 = 'fake_id2'
fake_minion_id3 = 'fake_id3'
fake_minion_id4 = 'fake_id4'
fake_minion_id5 = 'fake_id5'


fake_pillar = {}
fake_args = ({'path': os.path.abspath(
                        os.path.join(base_path, '..', '..', 'integration',
                                     'files', 'saltclass', 'examples-new'))})
fake_opts = {}
fake_salt = {}
fake_grains = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltclassTestCase(TestCase, LoaderModuleMockMixin):
    '''
    New tests for salt.pillar.saltclass
    '''

    def setup_loader_modules(self):
        return {saltclass: {'__opts__': fake_opts,
                            '__salt__': fake_salt,
                            '__grains__': fake_grains}}

    def test_simple_case(self):
        expected_result = {
            'L0A':
                {
                    'dict':
                        {'k1': 'L0A-1', 'k2': 'L0A-2'},
                    'list': ['L0A-1', 'L0A-2'],
                    'plaintext': u'plaintext_from_L0A'
                },
            'L0B':
                {
                    'list': ['L0B-1', 'L0B-2'],
                    'plaintext': 'plaintext_from_L0B'
                }
        }
        result = saltclass.ext_pillar(fake_minion_id1, {}, fake_args)
        filtered_result = {k: result[k] for k in ('L0A', 'L0B') if k in result}
        self.assertDictEqual(filtered_result, expected_result)

    def test_metainformation(self):
        expected_result = {
            '__saltclass__': {'classes': ['L2.A',
                                          'L1.A',
                                          'L0.A',
                                          'L1.B',
                                          'L0.B',
                                          'L0.B.otherclass'],
                              'environment': 'customenv',
                              'nodename': 'fake_id1',
                              'states': ['state_A', 'state_B']}
        }
        result = saltclass.ext_pillar(fake_minion_id1, {}, fake_args)
        filtered_result = {'__saltclass__': result.get('__saltclass__')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_plaintext_pillar_overwrite(self):
        expected_result = {
            'same_plaintext_pillar': 'from_L0B'
        }
        result = saltclass.ext_pillar(fake_minion_id1, {}, fake_args)
        filtered_result = {'same_plaintext_pillar': result.get('same_plaintext_pillar')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_list_pillar_extension(self):
        expected_result = {
            'same_list_pillar': ['L0A-1', 'L0A-2', 'L0B-1', 'L0B-2']
        }
        result = saltclass.ext_pillar(fake_minion_id1, {}, fake_args)
        filtered_result = {'same_list_pillar': result.get('same_list_pillar')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_list_override_with_no_ancestor(self):
        expected_result = {
            'single-list-override': [1, 2]
        }
        result = saltclass.ext_pillar(fake_minion_id1, {}, fake_args)
        filtered_result = {'single-list-override': result.get('single-list-override')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_list_override(self):
        expected_result = {
            'same_list_pillar': ['L0C-1', 'L0C-2']
        }
        result = saltclass.ext_pillar(fake_minion_id2, {}, fake_args)
        filtered_result = {'same_list_pillar': result.get('same_list_pillar')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_pillar_expansion(self):
        expected_result = {
            'expansion':
                {
                    'dict': {'k1': 'L0C-1', 'k2': 'L0C-2'},
                    'list': ['L0C-1', 'L0C-2'],
                    'plaintext': 'plaintext_from_L0C'
                }
        }
        result = saltclass.ext_pillar(fake_minion_id2, {}, fake_args)
        filtered_result = {'expansion': result.get('expansion')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_pillars_in_jinja(self):
        expected_states = ['state_B', 'state_C.1', 'state_C.9999']
        result = saltclass.ext_pillar(fake_minion_id2, {}, fake_args)
        filtered_result = result['__saltclass__']['states']
        for v in expected_states:
            self.assertIn(v, filtered_result)

    def test_cornercases(self):
        expected_result = {'nonsaltclass_pillar': 'value'}
        result = saltclass.ext_pillar(fake_minion_id3, {'nonsaltclass_pillar': 'value'}, fake_args)
        filtered_result = {'nonsaltclass_pillar': result.get('nonsaltclass_pillar')}
        self.assertDictEqual(filtered_result, expected_result)

    def test_nonsaltclass_pillars(self):
        nonsaltclass_pillars = {
            'plaintext_no_override': 'not_from_saltclass',
            'plaintext_with_override': 'not_from_saltclass',
            'list': [1, 2],
            'dict': {
                'a': 1,
                'b': 1
            }
        }
        expected_result = {
            'plaintext_no_override': 'not_from_saltclass',
            'plaintext_with_override': 'saltclass',
            'list': [1, 2, 3],
            'dict': {
                'a': 1,
                'b': 2,
                'c': 1
            }
        }
        result = saltclass.ext_pillar(fake_minion_id4, nonsaltclass_pillars, fake_args)
        filtered_result = {}
        for key in expected_result.keys():
            filtered_result[key] = result.get(key)
        self.assertDictEqual(filtered_result, expected_result)

    def test_fail(self):
        self.assertRaises(SaltException, saltclass.ext_pillar, fake_minion_id5, {}, fake_args)
