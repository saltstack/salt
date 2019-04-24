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
fake_minion_id6 = 'fake_id6'
fake_minion_id7 = 'fake_id7'
fake_minion_id8 = 'fake_id8'

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
    Tests for salt.pillar.saltclass
    TODO: change node and class names in mocks to make them more readable - all these A, B, C, X, L0 are unreadable
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
        for key in expected_result:
            filtered_result[key] = result.get(key)
        self.assertDictEqual(filtered_result, expected_result)

    def test_wrong_yaml_format(self):
        self.assertRaisesRegex(SaltException, r'^Pillars in fake_id5 is not a valid dict$',
                               saltclass.ext_pillar, fake_minion_id5, {}, fake_args)

    def test_globbing(self):
        result = saltclass.ext_pillar(fake_minion_id6, {}, fake_args)
        expected_result = {'A1': 'A1',
                           'A2': 'A2',
                           'A3': 'A3',
                           'B-init': 'B-init',
                           'B1': 'B1',
                           'B2': 'B2',
                           'B3': 'B3',
                           'C': 'C',
                           'C1': 'C1',
                           'C2': 'C2',
                           'D-init': 'D-init',
                           'D1': 'D1',
                           'X': 'X',
                           'X-init': 'X-init',
                           '__saltclass__': {'classes': ['L0.D.X',
                                                         'L0.D.X.X',
                                                         'L0.D.Y.B',
                                                         'L0.D.Y.B.B1',
                                                         'L0.D.Y.B.B2',
                                                         'L0.D.Y.B.B3',
                                                         'L0.D.Y.A.A1',
                                                         'L0.D.Y.A.A2',
                                                         'L0.D.Y.A.A3',
                                                         'L0.D.Y.C.C',
                                                         'L0.D.Y.C.C1',
                                                         'L0.D.Y.C.C2',
                                                         'L0.D.Y.D.D1',
                                                         'L0.D.Y.D'],
                                             'environment': 'base',
                                             'nodename': 'fake_id6',
                                             'states': ['X-init',
                                                        'X',
                                                        'B-init',
                                                        'B1',
                                                        'B2',
                                                        'B3',
                                                        'A11',
                                                        'A12',
                                                        'A2',
                                                        'A31',
                                                        'A32',
                                                        'C',
                                                        'C1',
                                                        'C2',
                                                        'D1',
                                                        'D-init']}}
        self.assertDictEqual(result, expected_result)

    def test_failed_expansion(self):
        self.assertRaisesRegex(SaltException, r'^Unable to expand \${fakepillar}$',
                               saltclass.ext_pillar, fake_minion_id7, {}, fake_args)

    def test_complex_expansion(self):
        result = saltclass.ext_pillar(fake_minion_id8, {}, fake_args)
        expected_result = {'A': {'B': {'C': {'tree': {'pillar': 'abracadabra'}}}},
                           'X': {'X': 'abra', 'head': 'ab', 'tail': 'ra'},
                           'Y': {'Y': 'cadabra',
                                 'aux': {'part1': 'dab', 'part2': 'ra'},
                                 'head': 'ca',
                                 'tail': 'dabra'},
                           '__saltclass__': {'classes': ['M0.A', 'M0.Z', 'M0.B'],
                                             'environment': '',
                                             'nodename': 'fake_id8',
                                             'states': ['A', 'Z', 'B']},
                           'key1': 'abc',
                           'key2': 'def',
                           'key3': 'abcdef',
                           'key4': 'key1: abc, key2: def, key3: abcdef \\${nonexistent}',
                           'list': ['foo', 'bar'],
                           'nested-expansion': 'abracadabra',
                           'network': {'interfaces': {'eth0': {'ipaddr': '1.1.1.1'}},
                                       'iptables': {'rules': [
                                           '-A PREROUTING -s 1.2.3.4/32 -d 1.1.1.1 -p tcp --dport 1234 5.6.7.8:1234']}},
                           'other_pillar': {'B': {'C': {'tree': {'pillar': 'abracadabra'}}}},
                           'some': {'tree': {'pillar': 'abracadabra'}}}
        self.assertDictEqual(result, expected_result)
