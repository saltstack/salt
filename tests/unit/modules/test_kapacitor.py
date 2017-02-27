# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import json

# Import Salt libs
from salt.modules import kapacitor

# Import Salt testing libs
from tests.support.unit import TestCase
from tests.support.mock import Mock, patch

kapacitor.__salt__ = {
    'pkg.version': Mock(return_value='9999'),
    'config.option': Mock(side_effect=lambda key, default: default)
}
kapacitor.__env__ = 'test'


class KapacitorTestCase(TestCase):
    def test_get_task_success(self):
        http_body = json.dumps({
            'script': 'test',
            'type': 'stream',
            'dbrps': [{'db': 'db', 'rp': 'rp'}],
            'status': 'enabled',
        })
        query_ret = {'body': http_body, 'status': 200}
        with patch('salt.utils.http.query', return_value=query_ret) as http_mock:
            task = kapacitor.get_task('taskname')
        http_mock.assert_called_once_with('http://localhost:9092/kapacitor/v1/tasks/taskname?skip-format=true', status=True)
        self.assertEqual('test', task['script'])

    def test_get_task_not_found(self):
        query_ret = {'body': '{"Error":"unknown task taskname"}', 'status': 404}
        with patch('salt.utils.http.query', return_value=query_ret) as http_mock:
            task = kapacitor.get_task('taskname')
        http_mock.assert_called_once_with('http://localhost:9092/kapacitor/v1/tasks/taskname?skip-format=true', status=True)
        self.assertEqual(None, task)

    def test_define_task(self):
        cmd_mock = Mock(return_value={'retcode': 0})
        with patch.dict(kapacitor.__salt__, {'cmd.run_all': cmd_mock}):
            kapacitor.define_task('taskname', '/tmp/script.tick')
        cmd_mock.assert_called_once_with('kapacitor define taskname '
            '-tick /tmp/script.tick -type stream')

    def test_enable_task(self):
        cmd_mock = Mock(return_value={'retcode': 0})
        with patch.dict(kapacitor.__salt__, {'cmd.run_all': cmd_mock}):
            kapacitor.enable_task('taskname')
        cmd_mock.assert_called_once_with('kapacitor enable taskname')

    def test_disable_task(self):
        cmd_mock = Mock(return_value={'retcode': 0})
        with patch.dict(kapacitor.__salt__, {'cmd.run_all': cmd_mock}):
            kapacitor.disable_task('taskname')
        cmd_mock.assert_called_once_with('kapacitor disable taskname')

    def test_delete_task(self):
        cmd_mock = Mock(return_value={'retcode': 0})
        with patch.dict(kapacitor.__salt__, {'cmd.run_all': cmd_mock}):
            kapacitor.delete_task('taskname')
        cmd_mock.assert_called_once_with('kapacitor delete tasks taskname')
