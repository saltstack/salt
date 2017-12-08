# -*- coding: utf-8 -*-
'''
    Unit tests for salt.utils.yamlloader.SaltYamlSafeLoader
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import collections
import textwrap

# Import Salt Libs
from yaml.constructor import ConstructorError
from salt.utils.yamlloader import SaltYamlSafeLoader
import salt.utils.files
from salt.ext import six

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON, mock_open

# Import 3rd-party libs
from salt.ext import six


@skipIf(NO_MOCK, NO_MOCK_REASON)
class YamlLoaderTestCase(TestCase):
    '''
    TestCase for salt.utils.yamlloader module
    '''

    @staticmethod
    def render_yaml(data):
        '''
        Takes a YAML string, puts it into a mock file, passes that to the YAML
        SaltYamlSafeLoader and then returns the rendered/parsed YAML data
        '''
        if six.PY2:
            # On Python 2, data read from a filehandle will not already be
            # unicode, so we need to encode it first to properly simulate
            # reading from a file. This is because unicode_literals is imported
            # and all of the data to be used in mock_open will be a unicode
            # type. Encoding will make it a str.
            data = salt.utils.data.encode(data)
        with patch('salt.utils.files.fopen', mock_open(read_data=data)) as mocked_file:
            with salt.utils.files.fopen(mocked_file) as mocked_stream:
                return SaltYamlSafeLoader(mocked_stream).get_data()

    @staticmethod
    def raise_error(value):
        raise TypeError('{0!r} is not a unicode string'.format(value))  # pylint: disable=repr-flag-used-in-string

    def assert_unicode(self, value):
        '''
        Make sure the entire data structure is unicode
        '''
        if six.PY3:
            return
        if isinstance(value, six.string_types):
            if not isinstance(value, six.text_type):
                self.raise_error(value)
        elif isinstance(value, collections.Mapping):
            for k, v in six.iteritems(value):
                self.assert_unicode(k)
                self.assert_unicode(v)
        elif isinstance(value, collections.Iterable):
            for item in value:
                self.assert_unicode(item)

    def assert_matches(self, ret, expected):
        self.assertEqual(ret, expected)
        self.assert_unicode(ret)

    def test_yaml_basics(self):
        '''
        Test parsing an ordinary path
        '''
        self.assert_matches(
            self.render_yaml(textwrap.dedent('''\
                p1:
                  - alpha
                  - beta''')),
            {'p1': ['alpha', 'beta']}
        )

    def test_yaml_merge(self):
        '''
        Test YAML anchors
        '''
        # Simple merge test
        self.assert_matches(
            self.render_yaml(textwrap.dedent('''\
                p1: &p1
                  v1: alpha
                p2:
                  <<: *p1
                  v2: beta''')),
            {'p1': {'v1': 'alpha'}, 'p2': {'v1': 'alpha', 'v2': 'beta'}}
        )

        # Test that keys/nodes are overwritten
        self.assert_matches(
            self.render_yaml(textwrap.dedent('''\
                p1: &p1
                  v1: alpha
                p2:
                  <<: *p1
                  v1: new_alpha''')),
            {'p1': {'v1': 'alpha'}, 'p2': {'v1': 'new_alpha'}}
        )

        # Test merging of lists
        self.assert_matches(
            self.render_yaml(textwrap.dedent('''\
                p1: &p1
                  v1: &v1
                    - t1
                    - t2
                p2:
                  v2: *v1''')),
            {"p2": {"v2": ["t1", "t2"]}, "p1": {"v1": ["t1", "t2"]}}
        )

    def test_yaml_duplicates(self):
        '''
        Test that duplicates still throw an error
        '''
        with self.assertRaises(ConstructorError):
            self.render_yaml(textwrap.dedent('''\
                p1: alpha
                p1: beta'''))

        with self.assertRaises(ConstructorError):
            self.render_yaml(textwrap.dedent('''\
                p1: &p1
                  v1: alpha
                p2:
                  <<: *p1
                  v2: beta
                  v2: betabeta'''))

    def test_yaml_with_unicode_literals(self):
        '''
        Test proper loading of unicode literals
        '''
        self.assert_matches(
            self.render_yaml(textwrap.dedent('''\
                foo:
                  a: Д
                  b: {'a': u'\\u0414'}''')),
            {'foo': {'a': u'\u0414', 'b': {'a': u'\u0414'}}}
        )
