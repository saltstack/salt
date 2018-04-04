# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Libs
from salt.utils import args

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArgsTestCase(TestCase):
    '''
    TestCase for salt.utils.args module
    '''

    def test_condition_input_string(self):
        '''
        Test passing a jid on the command line
        '''
        cmd = args.condition_input(['*', 'foo.bar', 20141020201325675584], None)
        self.assertIsInstance(cmd[2], str)

    def test_yamlify_arg(self):
        '''
        Test that we properly yamlify CLI input. In several of the tests below
        assertIs is used instead of assertEqual. This is because we want to
        confirm that the return value is not a copy of the original, but the
        same instance as the original.
        '''
        def _yamlify_arg(item):
            log.debug('Testing yamlify_arg with %r', item)
            return args.yamlify_arg(item)

        # Make sure non-strings are just returned back
        for item in (True, False, None, 123, 45.67, ['foo'], {'foo': 'bar'}):
            self.assertIs(_yamlify_arg(item), item)

        # Make sure whitespace-only isn't loaded as None
        for item in ('', '\t', ' '):
            self.assertIs(_yamlify_arg(item), item)

        # This value would be loaded as an int (123), the underscores would be
        # ignored. Test that we identify this case and return the original
        # value.
        item = '1_2_3'
        self.assertIs(_yamlify_arg(item), item)

        # The '#' is treated as a comment when not part of a data structure, we
        # don't want that behavior
        for item in ('# hash at beginning', 'Hello world! # hash elsewhere'):
            self.assertIs(_yamlify_arg(item), item)

        # However we _do_ want the # to be intact if it _is_ within a data
        # structure.
        item = '["foo", "bar", "###"]'
        self.assertEqual(_yamlify_arg(item), ["foo", "bar", "###"])
        item = '{"foo": "###"}'
        self.assertEqual(_yamlify_arg(item), {"foo": "###"})

        # The string "None" should load _as_ None
        self.assertIs(_yamlify_arg('None'), None)

        # Leading dashes, or strings containing colons, will result in lists
        # and dicts, and we only want to load lists and dicts when the strings
        # look like data structures.
        for item in ('- foo', 'foo: bar'):
            self.assertIs(_yamlify_arg(item), item)

        # Make sure we don't load '|' as ''
        item = '|'
        self.assertIs(_yamlify_arg(item), item)

        # Make sure we load ints, floats, and strings correctly
        self.assertEqual(_yamlify_arg('123'), 123)
        self.assertEqual(_yamlify_arg('45.67'), 45.67)
        self.assertEqual(_yamlify_arg('foo'), 'foo')

        # We tested list/dict loading above, but there is separate logic when
        # the string contains a '#', so we need to test again here.
        self.assertEqual(_yamlify_arg('["foo", "bar"]'), ["foo", "bar"])
        self.assertEqual(_yamlify_arg('{"foo": "bar"}'), {"foo": "bar"})
