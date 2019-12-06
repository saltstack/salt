# -*- coding: utf-8 -*-
'''
unit tests for the grains state
'''

from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import os
import contextlib

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.utils.files
import salt.utils.stringutils
import salt.utils.yaml
import salt.modules.grains as grainsmod
import salt.states.grains as grains
from salt.ext import six


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        grains_test_dir = '__salt_test_state_grains'
        if not os.path.exists(os.path.join(RUNTIME_VARS.TMP, grains_test_dir)):
            os.makedirs(os.path.join(RUNTIME_VARS.TMP, grains_test_dir))
        loader_globals = {
            '__opts__': {
                'test': False,
                'conf_file': os.path.join(RUNTIME_VARS.TMP, grains_test_dir, 'minion'),
                'cachedir':  os.path.join(RUNTIME_VARS.TMP, grains_test_dir),
                'local': True,
            },
            '__salt__': {
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
        }
        return {grains: loader_globals, grainsmod: loader_globals}

    def assertGrainFileContent(self, grains_string):
        if os.path.isdir(grains.__opts__['conf_file']):
            grains_file = os.path.join(
                grains.__opts__['conf_file'],
                'grains')
        else:
            grains_file = os.path.join(
                os.path.dirname(grains.__opts__['conf_file']),
                'grains')
        with salt.utils.files.fopen(grains_file, "r") as grf:
            grains_data = salt.utils.stringutils.to_unicode(grf.read())
        self.assertMultiLineEqual(grains_string, grains_data)

    @contextlib.contextmanager
    def setGrains(self, grains_data):
        with patch.dict(grains.__grains__, grains_data):
            with patch.dict(grainsmod.__grains__, grains_data):
                if os.path.isdir(grains.__opts__['conf_file']):
                    grains_file = os.path.join(
                        grains.__opts__['conf_file'],
                        'grains')
                else:
                    grains_file = os.path.join(
                        os.path.dirname(grains.__opts__['conf_file']), 'grains')
                with salt.utils.files.fopen(grains_file, "w+") as grf:
                    salt.utils.yaml.safe_dump(grains_data, grf, default_flow_style=False)
                yield

    # 'exists' function tests: 2

    def test_exists_missing(self):
        with self.setGrains({'a': 'aval'}):
            ret = grains.exists(name='foo')
            self.assertEqual(ret['result'], False)
            self.assertEqual(ret['comment'], 'Grain does not exist')
            self.assertEqual(ret['changes'], {})

    def test_exists_found(self):
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
            # Grain already set
            ret = grains.exists(name='foo')
            self.assertEqual(ret['result'], True)
            self.assertEqual(ret['comment'], 'Grain exists')
            self.assertEqual(ret['changes'], {})

    # 'present' function tests: 12

    def test_present_add(self):
        # Set a non existing grain
        with self.setGrains({'a': 'aval'}):
            ret = grains.present(name='foo', value='bar')
            self.assertEqual(ret['result'], True)
            self.assertEqual(ret['changes'], {'foo': 'bar'})
            self.assertEqual(grains.__grains__, {'a': 'aval', 'foo': 'bar'})
            self.assertGrainFileContent("a: aval\nfoo: bar\n")

        # Set a non existing nested grain
        with self.setGrains({'a': 'aval'}):
            ret = grains.present(name='foo:is:nested', value='bar')
            self.assertEqual(ret['result'], True)
            self.assertEqual(ret['changes'], {'foo': {'is': {'nested': 'bar'}}})
            self.assertEqual(grains.__grains__, {'a': 'aval', 'foo': {'is': {'nested': 'bar'}}})
            self.assertGrainFileContent("a: aval\n"
                                        "foo:\n"
                                        "  is:\n"
                                        "    nested: bar\n"
            )

        # Set a non existing nested dict grain
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval', 'foo': {'k1': 'v1'}}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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

        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
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
        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'val'}}}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'val'}}}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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

        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
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
        with self.setGrains({'a': 'aval', 'foo': {'k1': 'v1'}}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
            # Force to overwrite a grain to a list
            ret = grains.present(
                name='foo',
                value=['l1', 'l2'],
                force=True)
            self.assertEqual(ret['result'], True)
            self.assertEqual(
                ret['comment'],
                "Set grain foo to ['l1', 'l2']" if six.PY3
                    else "Set grain foo to [u'l1', u'l2']"
            )
            self.assertEqual(ret['changes'], {'foo': ['l1', 'l2']})
            self.assertEqual(
                grains.__grains__,
                {'a': 'aval', 'foo': ['l1', 'l2']})
            self.assertGrainFileContent("a: aval\n"
                                      + "foo:\n"
                                      + "- l1\n"
                                      + "- l2\n"
            )

        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
            # Force setting a grain to a dict
            ret = grains.present(
                name='foo',
                value={'k1': 'v1'},
                force=True)
            self.assertEqual(ret['result'], True)
            self.assertEqual(
                ret['comment'],
                "Set grain foo to {'k1': 'v1'}" if six.PY3
                    else "Set grain foo to {u'k1': u'v1'}"
            )
            self.assertEqual(ret['changes'], {'foo': {'k1': 'v1'}})
            self.assertEqual(
                grains.__grains__,
                {'a': 'aval', 'foo': {'k1': 'v1'}})
            self.assertGrainFileContent("a: aval\n"
                                      + "foo:\n"
                                      + "  k1: v1\n"
            )

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}}}):
            # Force to overwrite a nested grain to a list
            ret = grains.present(
                name='foo,is,nested',
                value=['l1', 'l2'],
                delimiter=',',
                force=True)
            self.assertEqual(ret['result'], True)
            self.assertEqual(ret['changes'], {'foo': {'is': {'nested': ['l1', 'l2']}}})
            self.assertEqual(
                ret['comment'],
                "Set grain foo:is:nested to ['l1', 'l2']" if six.PY3
                    else "Set grain foo:is:nested to [u'l1', u'l2']"
            )
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

        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': 'bar'}, 'and': 'other'}}):
            # Force setting a nested grain to a dict
            ret = grains.present(
                name='foo:is:nested',
                value={'k1': 'v1'},
                force=True)
            self.assertEqual(ret['result'], True)
            self.assertEqual(
                ret['comment'],
                "Set grain foo:is:nested to {'k1': 'v1'}" if six.PY3
                    else "Set grain foo:is:nested to {u'k1': u'v1'}"
            )
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with patch.dict(grains.__opts__, {'test': True}):
            with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval', 'foo': 'is'}):
            # Converts a value to a nested grain key
            ret = grains.present(
                name='foo:is:nested',
                value={'k1': 'v1'})
            self.assertEqual(ret['result'], True)
            self.assertEqual(
                ret['comment'],
                "Set grain foo:is:nested to {'k1': 'v1'}" if six.PY3
                    else "Set grain foo:is:nested to {u'k1': u'v1'}"
            )
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

        with self.setGrains({'a': 'aval', 'foo': ['one', 'is', 'correct']}):
            # Converts a list element to a nested grain key
            ret = grains.present(
                name='foo:is:nested',
                value={'k1': 'v1'})
            self.assertEqual(ret['result'], True)
            self.assertEqual(
                ret['comment'],
                "Set grain foo:is:nested to {'k1': 'v1'}" if six.PY3
                    else "Set grain foo:is:nested to {u'k1': u'v1'}"
            )
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

    def test_present_unknown_failure(self):
        with patch('salt.modules.grains.setval') as mocked_setval:
            mocked_setval.return_value = 'Failed to set grain foo'
            with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval', 'foo': False}):
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
        with self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']}):
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
        with self.setGrains({'a': 'aval', 'foo': ['order', {'is': 'nested'}, 'correct']}):
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
        with patch.dict(grains.__opts__, {'test': True}):
            with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']}):
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
        with self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar'}}, 'correct']}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval', 'foo': None}):
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
        with self.setGrains({'a': 'aval', 'foo': ['order', {'is': {'nested': 'bar', 'other': 'value'}}, 'correct']}):
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
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
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
        with self.setGrains({'a': 'aval', 'foo': {'list': ['bar']}}):
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
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
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
        with self.setGrains({'a': 'aval', 'foo': {'bar': 'val'}}):
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
        with self.setGrains({'a': 'aval', 'foo': {'bar': 'val'}}):
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
        with self.setGrains({'a': 'aval', 'foo': {'bar': 'val', 'other': 'value'}}):
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
        with self.setGrains({'a': 'aval'}):
            ret = grains.append(
                name='foo',
                value='bar')
            self.assertEqual(ret['result'], False)
            self.assertEqual(ret['comment'], 'Grain foo does not exist')
            self.assertEqual(ret['changes'], {})
            self.assertEqual(
                grains.__grains__,
                {'a': 'aval'})

    def test_append_convert_to_list_empty(self):
        # Append to an existing list
        with self.setGrains({'foo': None}):
            ret = grains.append(name='foo',
                                value='baz',
                                convert=True)
            self.assertEqual(ret['result'], True)
            self.assertEqual(ret['comment'], 'Value baz was added to grain foo')
            self.assertEqual(ret['changes'], {'added': 'baz'})
            self.assertEqual(
                grains.__grains__,
                {'foo': ['baz']})
            self.assertGrainFileContent("foo:\n"
                                      + "- baz\n")

    # 'list_present' function tests: 7

    def test_list_present(self):
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
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
        with self.setGrains({'a': 'aval', 'foo': {'is': {'nested': ['bar']}}}):
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
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval', 'b': {'foo': ['bar']}}):
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
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
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
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
            # Unknown reason failure

            with patch.dict(grainsmod.__salt__, {'grains.append': MagicMock()}):
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
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
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
        with self.setGrains({'a': 'aval', 'foo': {'list': ['bar']}}):
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
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval'}):
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
        with self.setGrains({'a': 'aval', 'foo': 'bar'}):
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
        with self.setGrains({'a': 'aval', 'foo': ['bar']}):
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
