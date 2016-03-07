# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt testing libs
from salttesting import TestCase
from salttesting.mock import Mock, patch, mock_open

# Import Salt libs
from salt.states import kapacitor

kapacitor.__opts__ = {'test': False}
kapacitor.__salt__ = {}
kapacitor.__env__ = 'test'


def _present(name='testname',
             tick_script='/tmp/script.tick',
             task_type='stream',
             database='testdb',
             retention_policy='default',
             enable=True,
             task=None,
             define_result=True,
             enable_result=True,
             script='test'):
    get_mock = Mock(return_value=task)
    define_mock = Mock(return_value=define_result)
    enable_mock = Mock(return_value=enable_result)
    with patch.dict(kapacitor.__salt__, {
        'kapacitor.get_task': get_mock,
        'kapacitor.define_task': define_mock,
        'kapacitor.enable_task': enable_mock,
    }):
        with patch('salt.utils.fopen', mock_open(read_data=script)) as open_mock:
            retval = kapacitor.task_present(name, tick_script, task_type=task_type,
                database=database, retention_policy=retention_policy, enable=enable)
    return retval, get_mock, define_mock, enable_mock


class KapacitorTestCase(TestCase):
    def test_task_present_new_task(self):
        ret, get_mock, define_mock, enable_mock = _present()
        get_mock.assert_called_once_with('testname')
        define_mock.assert_called_once_with('testname', '/tmp/script.tick',
            database='testdb', retention_policy='default', task_type='stream')
        enable_mock.assert_called_once_with('testname')
        self.assertIn('diff', ret['changes'])
        self.assertIn('enabled', ret['changes'])
        self.assertEqual(True, ret['changes']['enabled'])

    def test_task_present_existing_task(self):
        old_task = {'TICKscript': 'old_task', 'Enabled': True}
        ret, get_mock, define_mock, enable_mock = _present(task=old_task)
        get_mock.assert_called_once_with('testname')
        define_mock.assert_called_once_with('testname', '/tmp/script.tick',
            database='testdb', retention_policy='default', task_type='stream')
        self.assertEqual(False, enable_mock.called)
        self.assertIn('diff', ret['changes'])
        self.assertNotIn('enabled', ret['changes'])

    def test_task_present_not_enabled(self):
        old_task = {'TICKscript': 'test', 'Enabled': False}
        ret, get_mock, define_mock, enable_mock = _present(task=old_task)
        get_mock.assert_called_once_with('testname')
        self.assertEqual(False, define_mock.called)
        enable_mock.assert_called_once_with('testname')
        self.assertNotIn('diff', ret['changes'])
        self.assertIn('enabled', ret['changes'])
        self.assertEqual(True, ret['changes']['enabled'])