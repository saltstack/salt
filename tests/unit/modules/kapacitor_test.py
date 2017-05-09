# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.modules import kapacitor

# Import Salt testing libs
from salttesting import TestCase
from salttesting.mock import Mock, patch

kapacitor.__salt__ = {
    'config.option': Mock(side_effect=lambda key, default: default)
}
kapacitor.__env__ = 'test'


class KapacitorTestCase(TestCase):
    def test_get_task_success(self):
        with patch('salt.utils.http.query', return_value={'body': '{"foo":"bar"}'}) as http_mock:
            task = kapacitor.get_task('taskname')
        http_mock.assert_called_once_with('http://localhost:9092/task?name=taskname')
        assert {'foo': 'bar'} == task

    def test_get_task_not_found(self):
        with patch('salt.utils.http.query', return_value={'body': '{"Error":"unknown task taskname"}'}) as http_mock:
            task = kapacitor.get_task('taskname')
        http_mock.assert_called_once_with('http://localhost:9092/task?name=taskname')
        assert None == task

    def test_define_task(self):
        cmd_mock = Mock(return_value=True)
        with patch.dict(kapacitor.__salt__, {'cmd.retcode': cmd_mock}):
            kapacitor.define_task('taskname', '/tmp/script.tick')
        cmd_mock.assert_called_once_with('kapacitor define -name taskname -tick /tmp/script.tick -type stream')

    def test_enable_task(self):
        cmd_mock = Mock(return_value=True)
        with patch.dict(kapacitor.__salt__, {'cmd.retcode': cmd_mock}):
            kapacitor.enable_task('taskname')
        cmd_mock.assert_called_once_with('kapacitor enable taskname')

    def test_disable_task(self):
        cmd_mock = Mock(return_value=True)
        with patch.dict(kapacitor.__salt__, {'cmd.retcode': cmd_mock}):
            kapacitor.disable_task('taskname')
        cmd_mock.assert_called_once_with('kapacitor disable taskname')

    def test_delete_task(self):
        cmd_mock = Mock(return_value=True)
        with patch.dict(kapacitor.__salt__, {'cmd.retcode': cmd_mock}):
            kapacitor.delete_task('taskname')
        cmd_mock.assert_called_once_with('kapacitor delete tasks taskname')
