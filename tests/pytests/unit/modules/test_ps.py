import salt.modules.ps
from tests.support.mock import MagicMock, patch

# TestCase Exceptions are tested in tests/unit/modules/test_ps.py


def test__status_when_process_is_found_with_matching_status_then_proc_info_should_be_returned():
    expected_result = [{"blerp": "whatever"}]
    with patch(
        "salt.utils.psutil_compat.process_iter",
        autospec=True,
        return_value=[MagicMock(info={"status": "fnord", "blerp": "whatever"})],
    ):

        actual_result = salt.modules.ps.status(filter="fnord")
        assert actual_result == expected_result


def test__status_when_no_matching_processes_then_no_results_should_be_returned():
    expected_result = []
    with patch(
        "salt.utils.psutil_compat.process_iter",
        autospec=True,
        return_value=[MagicMock(info={"status": "foo", "blerp": "whatever"})],
    ):

        actual_result = salt.modules.ps.status(filter="fnord")
        assert actual_result == expected_result


def test__status_when_some_matching_processes_then_only_correct_info_should_be_returned():
    expected_result = [{"name": "whatever", "pid": 9999}]
    with patch(
        "salt.utils.psutil_compat.process_iter",
        autospec=True,
        return_value=[
            MagicMock(info={"status": "fnord", "name": "whatever", "pid": 9999}),
            MagicMock(info={"status": "foo", "name": "wherever", "pid": 9998}),
            MagicMock(info={"status": "bar", "name": "whenever", "pid": 9997}),
        ],
    ):

        actual_result = salt.modules.ps.status(filter="fnord")
        assert actual_result == expected_result
