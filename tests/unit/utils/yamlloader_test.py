# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.utils.yamlloader import SaltYamlSafeLoader
import salt.utils

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
    mock_open
)

ensure_in_syspath('../../')


def _render_yaml(data):
    '''
    Takes a YAML string, puts it into a mock file, passes it to the YAML
    SaltYamlSafeLoader and then returns the rendered/parsed YAML data
    '''
    with patch('salt.utils.fopen', mock_open(read_data=data)) as m:
        with salt.utils.fopen(m) as fp:
            return SaltYamlSafeLoader(fp).get_data()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class YamlLoaderTestCase(TestCase):
    '''
    TestCase for salt.utils.yamlloader module
    '''

    def test_yaml_basics(self):
        '''
        Test parsing an ordinary path
        '''

        result = _render_yaml(b'''
p1:
  - alpha
  - beta''')
        self.assertEqual(
            result,
            {'p1':['alpha', 'beta']}
        )

    def test_yaml_merge(self):
        '''
        Test YAML anchors
        '''

        # Simple merge test
        self.assertEqual(
            _render_yaml(b'''
p1: &p1
  v1: alpha
p2:
  <<: *p1
  v2: beta'''),
            {
                'p1':{'v1':'alpha'},
                'p2':{'v1':'alpha','v2':'beta'}
            }
        )

        # Test that keys/nodes are overwritten
        self.assertEqual(
            _render_yaml(b'''
p1: &p1
  v1: alpha
p2:
  <<: *p1
  v1: new_alpha'''),
            {
                'p1':{'v1':'alpha'},
                'p2':{'v1':'new_alpha'}
            }
        )

        # Test merging of lists
        self.assertEqual(
            _render_yaml(b'''
p1: &p1
  v1: &v1
    - t1
    - t2
    - t3
p2:
  v2: *v1'''),
            {
                "p2": {"v2": ["t1", "t2", "t3"]}, 
                "p1": {"v1": ["t1", "t2", "t3"]}
            }
        )

    def test_yaml_duplicates(self):
        '''
        Test that duplicates still throw an error
        '''
        from yaml.constructor import ConstructorError

        with self.assertRaises(ConstructorError):
            _render_yaml(b'''
p1: alpha
p1: beta''')

        with self.assertRaises(ConstructorError):
            _render_yaml(b'''
p1: &p1
  v1: alpha
p2:
  <<: *p1
  v2: beta
  v2: betabeta''')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(YamlLoaderTestCase, needs_daemon=False)
