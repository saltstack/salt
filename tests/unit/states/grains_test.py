# -*- coding: utf-8 -*-
'''
unit tests for the grains state
'''

from __future__ import absolute_import

# Import Python libs
import os

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock

ensure_in_syspath('../../')

from salt.modules import grains as grainsmod
from salt.states import grains as grains

import integration


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GrainsTestCase(TestCase):

    # 'present' function tests: 4

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
            'grains.setval': grainsmod.setval,
            'grains.delval': grainsmod.delval,
            'grains.append': grainsmod.append,
            'grains.remove': grainsmod.remove,
            'saltutil.sync_grains': MagicMock()
        }
        if not os.path.exists(os.path.join(integration.TMP, grains_test_dir)):
            os.mkdir(os.path.join(integration.TMP, grains_test_dir))

    def test_present_add(self):
        # Set a non existing grain
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval'}
        ret = grains.present(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': 'bar'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

    def test_present_already_set(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
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

    def test_present_overwrite(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        # Overwrite an existing grain
        ret = grains.present(
            name='foo',
            value='newbar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': 'newbar'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'newbar'})

        # Overwrite a grain to a list
        ret = grains.present(
            name='foo',
            value=['l1', 'l2'])
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': ['l1', 'l2']})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['l1', 'l2']})

        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        # Fails setting a grain to a dict
        ret = grains.present(
            name='foo',
            value={'k1': 'v1'})
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain value cannot be dict')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        # Clear a grain (set to None)
        ret = grains.present(
            name='foo',
            value=None)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['changes'], {'foo': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': None})

    def test_present_unknown_failure(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        # Unknown reason failure
        grainsmod.__salt__['grains.setval'] = MagicMock()
        ret = grains.present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Failed to set grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

    # 'absent' function tests: 3

    def test_absent_already(self):
        # Unset a non existent grain
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval'}
        ret = grains.absent(
            name='foo')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})

    def test_absent_unset(self):
        # Unset a grain
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        ret = grains.absent(
            name='foo')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value for grain foo was set to None')
        self.assertEqual(ret['changes'], {'grain': 'foo', 'value': None})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': None})

    def test_absent_delete(self):
        # Delete a grain
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        ret = grains.absent(
            name='foo',
            destructive=True)
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo was deleted')
        self.assertEqual(ret['changes'], {'deleted': 'foo'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})

    # 'append' function tests: 5

    def test_append(self):
        # Append to an existing list
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
        ret = grains.append(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz was added to grain foo')
        self.assertEqual(ret['changes'], {'added': 'baz'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar', 'baz']})

    def test_append_already(self):
        # Append to an existing list
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
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

    def test_append_fails_not_a_list(self):
        # Fail to append to an existing grain, not a list
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': {'bar': 'val'}}
        ret = grains.append(
            name='foo',
            value='baz')
        # Note from dr4Ke: should be false, IMO
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo is not a valid list')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': {'bar': 'val'}})

    def test_append_convert_to_list(self):
        # Append to an existing grain, converting to a list
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': {'bar': 'val'}}
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

    def test_append_fails_inexistent(self):
        # Append to a non existing grain
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval'}
        ret = grains.append(
            name='foo',
            value='bar')
        # Note from dr4Ke: should be false, IMO
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})

    # 'list_present' function tests: 5

    def test_list_present(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Append value baz to grain foo')
        self.assertEqual(ret['changes'], {'new': {'foo': ['bar', 'baz']}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar', 'baz']})

    def test_list_present_inexistent(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval'}
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Append value baz to grain foo')
        self.assertEqual(ret['changes'], {'new': {'foo': ['baz']}})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['baz']})

    def test_list_present_not_a_list(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        ret = grains.list_present(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo is not a valid list')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

    def test_list_present_already(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
        ret = grains.list_present(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar is already in grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar']})

    def test_list_present_unknown_failure(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
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

    # 'list_absent' function tests: 4

    def test_list_absent(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
        ret = grains.list_absent(
            name='foo',
            value='bar')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value bar was deleted from grain foo')
        self.assertEqual(ret['changes'], {'deleted': 'bar'})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': []})

    def test_list_absent_inexistent(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval'}
        ret = grains.list_absent(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Grain foo does not exist')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval'})

    def test_list_absent_not_a_list(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': 'bar'}
        ret = grains.list_absent(
            name='foo',
            value='bar')
        # Note from dr4Ke: should be false, IMO
        self.assertEqual(ret['result'], False)
        self.assertEqual(ret['comment'], 'Grain foo is not a valid list')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': 'bar'})

    def test_list_absent_already(self):
        grains.__grains__ = grainsmod.__grains__ = {'a': 'aval', 'foo': ['bar']}
        ret = grains.list_absent(
            name='foo',
            value='baz')
        self.assertEqual(ret['result'], True)
        self.assertEqual(ret['comment'], 'Value baz is absent from grain foo')
        self.assertEqual(ret['changes'], {})
        self.assertEqual(
            grains.__grains__,
            {'a': 'aval', 'foo': ['bar']})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsTestCase, needs_daemon=False)
