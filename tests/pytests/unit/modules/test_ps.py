import salt.modules.ps
from tests.support.mock import patch, MagicMock

def test_when_no_filter_is_provided_then_no_results_are_returned():
    expected_result = []
    
    actual_result = salt.modules.ps.status(filter=[])
    assert actual_result == expected_result


def test_when_process_is_found_with_matching_status_then_proc_info_should_be_returned():
    expected_result = [{'blerp': 'whatever'}]
    with patch('salt.utils.psutil_compat.process_iter', autospec=True, return_value=[MagicMock(info={'status': 'fnord', 'blerp': 'whatever'})]):
        actual_result = salt.modules.ps.status(filter='fnord')
        assert actual_result == expected_result


def test_when_no_matching_processes_then_no_results_should_be_returned():
    ...

def test_when_some_matching_processes_then_only_correct_info_should_be_returned():
    ...

def test_when_access_denied_from_psutil_then_(): # no results returned? message is returned?
    ...

def 
