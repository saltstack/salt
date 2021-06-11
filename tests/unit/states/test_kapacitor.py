# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.states.kapacitor as kapacitor

# Import Salt testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import Mock, mock_open, patch
from tests.support.unit import TestCase


def _present(
    name="testname",
    tick_script="/tmp/script.tick",
    task_type="stream",
    database="testdb",
    retention_policy="default",
    dbrps=None,
    enable=True,
    task=None,
    define_result=True,
    enable_result=True,
    disable_result=True,
    script="testscript",
):
    """
    Run a "kapacitor.present" state after setting up mocks, and return the
    state return value as well as the mocks to make assertions.
    """
    get_mock = Mock(return_value=task)

    if isinstance(define_result, bool):
        define_result = {"success": define_result}
    define_mock = Mock(return_value=define_result)

    if isinstance(enable_result, bool):
        enable_result = {"success": enable_result}
    enable_mock = Mock(return_value=enable_result)

    if isinstance(disable_result, bool):
        disable_result = {"success": disable_result}
    disable_mock = Mock(return_value=disable_result)

    with patch.dict(
        kapacitor.__salt__,
        {
            "kapacitor.get_task": get_mock,
            "kapacitor.define_task": define_mock,
            "kapacitor.enable_task": enable_mock,
            "kapacitor.disable_task": disable_mock,
        },
    ):
        with patch("salt.utils.files.fopen", mock_open(read_data=script)) as open_mock:
            retval = kapacitor.task_present(
                name,
                tick_script,
                task_type=task_type,
                database=database,
                retention_policy=retention_policy,
                enable=enable,
                dbrps=dbrps,
            )

    return retval, get_mock, define_mock, enable_mock, disable_mock


def _task(
    script="testscript", enabled=True, task_type="stream", db="testdb", rp="default"
):
    return {
        "script": script,
        "enabled": enabled,
        "type": task_type,
        "dbrps": [{"db": db, "rp": rp}],
    }


class KapacitorTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {kapacitor: {"__opts__": {"test": False}, "__env__": "test"}}

    def test_task_present_new_task(self):
        ret, get_mock, define_mock, enable_mock, _ = _present(
            dbrps=["testdb2.default_rp"]
        )
        get_mock.assert_called_once_with("testname")
        define_mock.assert_called_once_with(
            "testname",
            "/tmp/script.tick",
            database="testdb",
            retention_policy="default",
            task_type="stream",
            dbrps=["testdb2.default_rp", "testdb.default"],
        )
        enable_mock.assert_called_once_with("testname")
        self.assertIn("TICKscript diff", ret["changes"])
        self.assertIn("enabled", ret["changes"])
        self.assertEqual(True, ret["changes"]["enabled"]["new"])

    def test_task_present_existing_task_updated_script(self):
        ret, get_mock, define_mock, enable_mock, _ = _present(
            task=_task(script="oldscript")
        )
        get_mock.assert_called_once_with("testname")
        define_mock.assert_called_once_with(
            "testname",
            "/tmp/script.tick",
            database="testdb",
            retention_policy="default",
            task_type="stream",
            dbrps=["testdb.default"],
        )
        self.assertEqual(False, enable_mock.called)
        self.assertIn("TICKscript diff", ret["changes"])
        self.assertNotIn("enabled", ret["changes"])

    def test_task_present_existing_task_not_enabled(self):
        ret, get_mock, define_mock, enable_mock, _ = _present(task=_task(enabled=False))
        get_mock.assert_called_once_with("testname")
        self.assertEqual(False, define_mock.called)
        enable_mock.assert_called_once_with("testname")
        self.assertNotIn("diff", ret["changes"])
        self.assertIn("enabled", ret["changes"])
        self.assertEqual(True, ret["changes"]["enabled"]["new"])

    def test_task_present_disable_existing_task(self):
        ret, get_mock, define_mock, _, disable_mock = _present(
            task=_task(), enable=False
        )
        get_mock.assert_called_once_with("testname")
        self.assertEqual(False, define_mock.called)
        disable_mock.assert_called_once_with("testname")
        self.assertNotIn("diff", ret["changes"])
        self.assertIn("enabled", ret["changes"])
        self.assertEqual(False, ret["changes"]["enabled"]["new"])
