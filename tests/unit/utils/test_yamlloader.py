# -*- coding: utf-8 -*-
'''
    Unit tests for salt.utils.yamlloader.SaltYamlSafeLoader
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from yaml.constructor import ConstructorError
from salt.utils.yamlloader import SaltYamlSafeLoader
import salt.utils

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON, mock_open


@skipIf(NO_MOCK, NO_MOCK_REASON)
class YamlLoaderTestCase(TestCase):
    '''
    TestCase for salt.utils.yamlloader module
    '''

    @staticmethod
    def _render_yaml(data):
        '''
        Takes a YAML string, puts it into a mock file, passes that to the YAML
        SaltYamlSafeLoader and then returns the rendered/parsed YAML data
        '''
        with patch('salt.utils.fopen', mock_open(read_data=data)) as mocked_file:
            with salt.utils.fopen(mocked_file) as mocked_stream:
                return SaltYamlSafeLoader(mocked_stream).get_data()

    def test_yaml_basics(self):
        '''
        Test parsing an ordinary path
        '''

        self.assertEqual(
            self._render_yaml(b'''
p1:
  - alpha
  - beta'''),
            {'p1': ['alpha', 'beta']}
        )

    def test_yaml_merge(self):
        '''
        Test YAML anchors
        '''

        # Simple merge test
        self.assertEqual(
            self._render_yaml(b'''
p1: &p1
  v1: alpha
p2:
  <<: *p1
  v2: beta'''),
            {'p1': {'v1': 'alpha'}, 'p2': {'v1': 'alpha', 'v2': 'beta'}}
        )

        # Test that keys/nodes are overwritten
        self.assertEqual(
            self._render_yaml(b'''
p1: &p1
  v1: alpha
p2:
  <<: *p1
  v1: new_alpha'''),
            {'p1': {'v1': 'alpha'}, 'p2': {'v1': 'new_alpha'}}
        )

        # Test merging of lists
        self.assertEqual(
            self._render_yaml(b'''
p1: &p1
  v1: &v1
    - t1
    - t2
p2:
  v2: *v1'''),
            {"p2": {"v2": ["t1", "t2"]}, "p1": {"v1": ["t1", "t2"]}}
        )

    def test_yaml_duplicates(self):
        '''
        Test that duplicates still throw an error
        '''
        with self.assertRaises(ConstructorError):
            self._render_yaml(b'''
p1: alpha
p1: beta''')

        with self.assertRaises(ConstructorError):
            self._render_yaml(b'''
p1: &p1
  v1: alpha
p2:
  <<: *p1
  v2: beta
  v2: betabeta''')
