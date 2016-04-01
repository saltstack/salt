# -*- coding: utf-8 -*-
'''
unit tests for the grains state
'''

from __future__ import absolute_import

# Import Python libs
import os
import yaml

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

ensure_in_syspath('../../')

from salt.modules import grains as grainsmod
from salt.states import grains as grains

import integration


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsTestCase(TestCase):

    def setUp(self):
        grains_test_dir = '__salt_test_state_grains'
        grainsmod.__opts__ = grains.__opts__ = {
            'test': False,
            'conf_file': os.path.join(integration.TMP, grains_test_dir, 'minion'),
            'cachedir':  os.path.join(integration.TMP, grains_test_dir),
            'local': True,
        }

        grainsmod.__salt__ = grains.__salt__ = {
            'cmd.run_all': MagicMock(return_value={
                'pid': 5,
                'retcode': 0,
                'stderr': '',
                'stdout': ''}),
            'grains.get':    grainsmod.get,
            'grains.set':    grainsmod.set,
            'grains.setval': grainsmod.setval,
            'grains.delval': grainsmod.delval,
            'grains.append': grainsmod.append,
            'grains.remove': grainsmod.remove,
            'saltutil.sync_grains': MagicMock()
        }
        if not os.path.exists(os.path.join(integration.TMP, grains_test_dir)):
            os.mkdir(os.path.join(integration.TMP, grains_test_dir))

    def assertGrainFileContent(self, grains_string):
        if os.path.isdir(grains.__opts__['conf_file']):
            grains_file = os.path.join(
                grains.__opts__['conf_file'],
                'grains')
        else:
            grains_file = os.path.join(
                os.path.dirname(grains.__opts__['conf_file']),
                'grains')
        with open(grains_file, "r") as grf:
            grains_data = grf.read()
        self.assertMultiLineEqual(grains_string, grains_data)

    def setGrains(self, grains_data):
        grains.__grains__ = grainsmod.__grains__ = grains_data
        if os.path.isdir(grains.__opts__['conf_file']):
            grains_file = os.path.join(
                grains.__opts__['conf_file'],
                'grains')
        else:
            grains_file = os.path.join(
                os.path.dirname(grains.__opts__['conf_file']),
                'grains')
        cstr = yaml.safe_dump(grains_data, default_flow_style=False)
        with open(grains_file, "w+") as grf:
            grf.write(cstr)

    # 'present' function tests: 12

    def test_present_add(self):
        # Set a non existing grain
        self.setGrains({'a': 'aval'})
        ret = grains.present(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': 'bar'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: bar\n"
        )

        # Set a non existing nested grain
        self.setGrains({'a': 'aval'})
        ret = grains.present(
            name='foo:is:nested',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': 'bar'}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested: bar\n"
        )

        # Set a non existing nested dict grain
        self.setGrains({'a': 'aval'})
        ret = grains.present(
            name='foo:is:nested',
            value={'bar': 'is a dict'})
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': {'bar': 'is a dict'}}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': {'bar': 'is a dict'}}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested:\n"
                                  + "      bar: is a dict\n"
        )

    def test_present_add_key_to_existing(self):
        self.setGrains({'a': 'aval', 'foo': {'k1': 'v1'}})
        # Fails setting a grain to a dict
        ret = grains.present(
            name='foo:k2',
            value='v2')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Set grain foo:k2 to v2')
        self.assertEqual(ret['changes'], {'foo': {'k2': 'v2', 'k1': 'v1'}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'k1': 'v1', 'k2': 'v2'}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  k1: v1\n"
                                  + "  k2: v2\n"
        )

    def test_present_already_set(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Grain already set
        ret = grains.present(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain is already set')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Nested grain already set
        ret = grains.present(
            name='foo:is:nested',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain is already set')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Nested dict grain already set
        ret = grains.present(
            name='foo:is',
            value={'nested': 'bar'})
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain is already set')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})

    def test_present_overwrite(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Overwrite an existing grain
        ret = grains.present(
            name='foo',
            value='newbar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': 'newbar'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'newbar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: newbar\n"
        )

        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Clear a grain (set to None)
        ret = grains.present(
            name='foo',
            value=None)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': None})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: null\n"
        )

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Overwrite an existing nested grain
        ret = grains.present(
            name='foo:is:nested',
            value='newbar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': 'newbar'}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'newbar'}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested: newbar\n"
        )

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Clear a nested grain (set to None)
        ret = grains.present(
            name='foo:is:nested',
            value=None)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': None}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': None}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested: null\n"
        )

    def test_present_fail_overwrite(self):
        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'val'}}})
        # Overwrite an existing grain
        ret = grains.present(
            name='foo:is',
            value='newbar')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['changes'], {})
        self.assertEqual(ret['comment'], 'The key \'foo:is\' exists but is a dict or a list. Use \'force=True\' to overwrite.')
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'val'}}})

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'val'}}})
        # Clear a grain (set to None)
        ret = grains.present(
            name='foo:is',
            value=None)
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['changes'], {})
        self.assertEqual(ret['comment'], 'The key \'foo:is\' exists but is a dict or a list. Use \'force=True\' to overwrite.')
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'val'}}})

    def test_present_fails_to_set_dict_or_list(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Fails to overwrite a grain to a list
        ret = grains.present(
            name='foo',
            value=['l1', 'l2'])
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'The key \'foo\' exists and the '
                                       + 'given value is a dict or a list. '
                                       + 'Use \'force=True\' to overwrite.')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Fails setting a grain to a dict
        ret = grains.present(
            name='foo',
            value={'k1': 'v1'})
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'The key \'foo\' exists and the given '
                                       + 'value is a dict or a list. Use '
                                       + '\'force=True\' to overwrite.')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Fails to overwrite a nested grain to a list
        ret = grains.present(
            name='foo,is,nested',
            value=['l1', 'l2'],
            delimiter=',')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['changes'], {})
        self.assertEqual(ret['comment'], 'The key \'foo:is:nested\' exists and the '
                                       + 'given value is a dict or a list. '
                                       + 'Use \'force=True\' to overwrite.')
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Fails setting a nested grain to a dict
        ret = grains.present(
            name='foo:is:nested',
            value={'k1': 'v1'})
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'The key \'foo:is:nested\' exists and the '
                                       + 'given value is a dict or a list. '
                                       + 'Use \'force=True\' to overwrite.')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})

    def test_present_fail_merge_dict(self):
        self.setGrains({'a': 'aval', 'foo': {'k1': 'v1'}})
        # Fails setting a grain to a dict
        ret = grains.present(
            name='foo',
            value={'k2': 'v2'})
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'The key \'foo\' exists but '
                                       + 'is a dict or a list. '
                                       + 'Use \'force=True\' to overwrite.')
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'k1': 'v1'}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  k1: v1\n"
        )

    def test_present_force_to_set_dict_or_list(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Force to overwrite a grain to a list
        ret = grains.present(
            name='foo',
            value=['l1', 'l2'],
            force=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Set grain foo to [\'l1\', \'l2\']')
        self.assertEqual(ret['changes'], {'foo': ['l1', 'l2']})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['l1', 'l2']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- l1\n"
                                  + "- l2\n"
        )

        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Force setting a grain to a dict
        ret = grains.present(
            name='foo',
            value={'k1': 'v1'},
            force=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Set grain foo to {\'k1\': \'v1\'}')
        self.assertEqual(ret['changes'], {'foo': {'k1': 'v1'}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'k1': 'v1'}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  k1: v1\n"
        )

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
        # Force to overwrite a nested grain to a list
        ret = grains.present(
            name='foo,is,nested',
            value=['l1', 'l2'],
            delimiter=',',
            force=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': ['l1', 'l2']}}})
        self.assertEqual(ret['comment'], 'Set grain foo:is:nested to [\'l1\', \'l2\']')
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': ['l1', 'l2']}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested:\n"
                                  + "    - l1\n"
                                  + "    - l2\n"
        )

        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}, 'and': 'other'}})
        # Force setting a nested grain to a dict
        ret = grains.present(
            name='foo:is:nested',
            value={'k1': 'v1'},
            force=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Set grain foo:is:nested to {\'k1\': \'v1\'}')
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': {'k1': 'v1'}}, 'and': 'other'}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': {'k1': 'v1'}}, 'and': 'other'}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  and: other\n"
                                  + "  is:\n"
                                  + "    nested:\n"
                                  + "      k1: v1\n"
        )

    def test_present_fails_to_convert_value_to_key(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Fails converting a value to a nested grain key
        ret = grains.present(
            name='foo:is:nested',
            value={'k1': 'v1'})
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'The key \'foo\' value is \'bar\', '
                               + 'which is different from the provided '
                               + 'key \'is\'. Use \'force=True\' to overwrite.')
        self.assertEqual(ret['changes'], {})

    def test_present_overwrite_test(self):
        grains.__opts__['test'] = True
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Overwrite an existing grain
        ret = grains.present(
            name='foo',
            value='newbar')
        self.assertEqual(ret['result'], None)
        self.assertEqual(ret['changes'], {'changed': {'foo': 'newbar'}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: bar\n"
        )

    def test_present_convert_value_to_key(self):
        self.setGrains({'a': 'aval', 'foo': 'is'})
        # Converts a value to a nested grain key
        ret = grains.present(
            name='foo:is:nested',
            value={'k1': 'v1'})
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Set grain foo:is:nested to {\'k1\': \'v1\'}')
        self.assertEqual(ret['changes'], {'foo': {'is': {'nested': {'k1': 'v1'}}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': {'k1': 'v1'}}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested:\n"
                                  + "      k1: v1\n"
        )

        self.setGrains({'a': 'aval', 'foo': ['one', 'is', 'correct']})
        # Converts a list element to a nested grain key
        ret = grains.present(
            name='foo:is:nested',
            value={'k1': 'v1'})
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Set grain foo:is:nested to {\'k1\': \'v1\'}')
        self.assertEqual(ret['changes'], {'foo': ['one', {'is': {'nested': {'k1': 'v1'}}}, 'correct']})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['one', {'is': {'nested': {'k1': 'v1'}}}, 'correct']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- one\n"
                                  + "- is:\n"
                                  + "    nested:\n"
                                  + "      k1: v1\n"
                                  + "- correct\n"
        )

    @patch('salt.modules.grains.setval')
    def test_present_unknown_failure(self, mocked_setval):
        mocked_setval.return_value = 'Failed to set grain foo'
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Unknown reason failure
        ret = grains.present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Failed to set grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: bar\n"
        )

    # 'absent' function tests: 6

    def test_absent_already(self):
        # Unset a non existent grain
        self.setGrains({'a': 'aval'})
        ret = grains.absent(
            name='foo')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})
        self.assertGrainFileContent("a: aval\n")

        # Unset a non existent nested grain
        self.setGrains({'a': 'aval'})
        ret = grains.absent(
            name='foo:is:nested')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo:is:nested does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})
        self.assertGrainFileContent("a: aval\n")

    def test_absent_unset(self):
        # Unset a grain
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        ret = grains.absent(
            name='foo')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value for grain foo was set to None')
        self.assertEqual(ret['changes'], {'grain': 'foo', 'value': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': None})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: null\n"
        )

        # Unset grain when its value is False
        self.setGrains({'a': 'aval', 'foo': False})
        ret = grains.absent(
            name='foo')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value for grain foo was set to None')
        self.assertEqual(ret['changes'], {'grain': 'foo', 'value': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': None})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: null\n"
        )

        # Unset a nested grain
        self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']})
        ret = grains.absent(
            name='foo,is,nested',
            delimiter=',')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value for grain foo:is:nested was set to None')
        self.assertEqual(ret['changes'], {'grain': 'foo:is:nested', 'value': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['order', {'is': {'nested': None}}, 'correct']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- order\n"
                                  + "- is:\n"
                                  + "    nested: null\n"
                                  + "- correct\n"
        )

        # Unset a nested value don't change anything
        self.setGrains({'a': 'aval', 'foo': ['order', {'is': 'nested'}, 'correct']})
        ret = grains.absent(
            name='foo:is:nested')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo:is:nested does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['order', {'is': 'nested'}, 'correct']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- order\n"
                                  + "- is: nested\n"
                                  + "- correct\n"
        )

    def test_absent_unset_test(self):
        grains.__opts__['test'] = True
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        # Overwrite an existing grain
        ret = grains.absent(name='foo')
        self.assertEqual(ret['result'], None)
        self.assertEqual(ret['changes'], {'grain': 'foo', 'value': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: bar\n"
        )

    def test_absent_fails_nested_complex_grain(self):
        # Unset a nested complex grain
        self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']})
        ret = grains.absent(
            name='foo:is')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'The key \'foo:is\' exists but is a dict or a list. Use \'force=True\' to overwrite.')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- order\n"
                                  + "- is:\n"
                                  + "    nested: bar\n"
                                  + "- correct\n"
        )

    def test_absent_force_nested_complex_grain(self):
        # Unset a nested complex grain
        self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']})
        ret = grains.absent(
            name='foo:is',
            force=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value for grain foo:is was set to None')
        self.assertEqual(ret['changes'], {'grain': 'foo:is', 'value': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['order', {'is': None}, 'correct']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- order\n"
                                  + "- is: null\n"
                                  + "- correct\n"
        )

    def test_absent_delete(self):
        # Delete a grain
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        ret = grains.absent(
            name='foo',
            destructive=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo was deleted')
        self.assertEqual(ret['changes'], {'deleted': 'foo'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})
        self.assertGrainFileContent("a: aval\n")

        # Delete a previously unset grain
        self.setGrains({'a': 'aval', 'foo': None})
        ret = grains.absent(
            name='foo',
            destructive=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo was deleted')
        self.assertEqual(ret['changes'], {'deleted': 'foo'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})
        self.assertGrainFileContent("a: aval\n")

        # Delete a nested grain
        self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar', 'other': 'value'}}, 'correct']})
        ret = grains.absent(
            name='foo:is:nested',
            destructive=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo:is:nested was deleted')
        self.assertEqual(ret['changes'], {'deleted': 'foo:is:nested'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['order', {'is': {'other': 'value'}}, 'correct']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- order\n"
                                  + "- is:\n"
                                  + "    other: value\n"
                                  + "- correct\n"
        )

    # 'append' function tests: 6

    def test_append(self):
        # Append to an existing list
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        ret = grains.append(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz was added to grain foo')
        self.assertEqual(ret['changes'], {'added': 'baz'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar', 'baz']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar\n"
                                  + "- baz\n"
        )

    def test_append_nested(self):
        # Append to an existing nested list
        self.setGrains({'a': 'aval', 'foo': {'list': ['bar']}})
        ret = grains.append(
            name='foo,list',
            value='baz',
            delimiter=',')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz was added to grain foo:list')
        self.assertEqual(ret['changes'], {'added': 'baz'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'list': ['bar', 'baz']}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  list:\n"
                                  + "  - bar\n"
                                  + "  - baz\n"
        )

    def test_append_already(self):
        # Append to an existing list
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        ret = grains.append(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar is already in the list '
                                       + 'for grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar\n"
        )

    def test_append_fails_not_a_list(self):
        # Fail to append to an existing grain, not a list
        self.setGrains({'a': 'aval', 'foo': {'bar': 'val'}})
        ret = grains.append(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo is not a valid list')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'bar': 'val'}})

    def test_append_convert_to_list(self):
        # Append to an existing grain, converting to a list
        self.setGrains({'a': 'aval', 'foo': {'bar': 'val'}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  bar: val\n"
        )
        ret = grains.append(
            name='foo',
            value='baz',
            convert=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz was added to grain foo')
        self.assertEqual(ret['changes'], {'added': 'baz'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': [{'bar': 'val'}, 'baz']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar: val\n"
                                  + "- baz\n"
        )

        # Append to an existing grain, converting to a list a multi-value dict
        self.setGrains({'a': 'aval', 'foo': {'bar': 'val', 'other': 'value'}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  bar: val\n"
                                  + "  other: value\n"
        )
        ret = grains.append(
            name='foo',
            value='baz',
            convert=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz was added to grain foo')
        self.assertEqual(ret['changes'], {'added': 'baz'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': [{'bar': 'val', 'other': 'value'}, 'baz']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar: val\n"
                                  + "  other: value\n"
                                  + "- baz\n"
        )

    def test_append_fails_inexistent(self):
        # Append to a non existing grain
        self.setGrains({'a': 'aval'})
        ret = grains.append(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})

    # 'list_present' function tests: 7

    def test_list_present(self):
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Append value baz to grain foo')
        self.assertEqual(ret['changes'], {'new': {'foo': ['bar', 'baz']}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar', 'baz']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar\n"
                                  + "- baz\n"
        )

    def test_list_present_nested(self):
        self.setGrains({'a': 'aval', 'foo': {'is': {'nested': ['bar']}}})
        ret = grains.list_present(
            name='foo,is,nested',
            value='baz',
            delimiter=',')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Append value baz to grain foo:is:nested')
        self.assertEqual(ret['changes'], {'new': {'foo': {'is': {'nested': ['bar', 'baz']}}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': ['bar', 'baz']}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested:\n"
                                  + "    - bar\n"
                                  + "    - baz\n"
        )

    def test_list_present_inexistent(self):
        self.setGrains({'a': 'aval'})
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Append value baz to grain foo')
        self.assertEqual(ret['changes'], {'new': {'foo': ['baz']}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['baz']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- baz\n"
        )

    def test_list_present_inexistent_nested(self):
        self.setGrains({'a': 'aval'})
        ret = grains.list_present(
            name='foo:is:nested',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Append value baz to grain foo:is:nested')
        self.assertEqual(ret['changes'], {'new': {'foo': {'is': {'nested': ['baz']}}}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'is': {'nested': ['baz']}}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  is:\n"
                                  + "    nested:\n"
                                  + "    - baz\n"
        )

    def test_list_present_not_a_list(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo is not a valid list')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: bar\n"
        )

    def test_list_present_nested_already(self):
        self.setGrains({'a': 'aval', 'b': {'foo': ['bar']}})
        ret = grains.list_present(
            name='b:foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar is already in grain b:foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'b': {'foo': ['bar']}})
        self.assertGrainFileContent("a: aval\n"
                                  + "b:\n"
                                  + "  foo:\n"
                                  + "  - bar\n"
        )

    def test_list_present_already(self):
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        ret = grains.list_present(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar is already in grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar\n"
        )

    def test_list_present_unknown_failure(self):
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        # Unknown reason failure
        grainsmod.__salt__['grains.append'] = MagicMock()
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Failed append value baz to grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar\n"
        )

    # 'list_absent' function tests: 6

    def test_list_absent(self):
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        ret = grains.list_absent(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar was deleted from grain foo')
        self.assertEqual(ret['changes'], {'deleted': ['bar']})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': []})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: []\n"
        )

    def test_list_absent_nested(self):
        self.setGrains({'a': 'aval', 'foo': {'list': ['bar']}})
        ret = grains.list_absent(
            name='foo:list',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar was deleted from grain foo:list')
        self.assertEqual(ret['changes'], {'deleted': ['bar']})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'list': []}})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "  list: []\n"
        )

    def test_list_absent_inexistent(self):
        self.setGrains({'a': 'aval'})
        ret = grains.list_absent(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})
        self.assertGrainFileContent("a: aval\n")

    def test_list_absent_inexistent_nested(self):
        self.setGrains({'a': 'aval'})
        ret = grains.list_absent(
            name='foo:list',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo:list does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})
        self.assertGrainFileContent("a: aval\n")

    def test_list_absent_not_a_list(self):
        self.setGrains({'a': 'aval', 'foo': 'bar'})
        ret = grains.list_absent(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo is not a valid list')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo: bar\n"
        )

    def test_list_absent_already(self):
        self.setGrains({'a': 'aval', 'foo': ['bar']})
        ret = grains.list_absent(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz is absent from grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar']})
        self.assertGrainFileContent("a: aval\n"
                                  + "foo:\n"
                                  + "- bar\n"
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsTestCase, needs_daemon=False)
