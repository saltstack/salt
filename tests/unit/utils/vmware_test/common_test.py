# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for common functions in salt.utils.vmware
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import Salt testing libraries
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, \
        PropertyMock

# Import Salt libraries
import salt.utils.vmware
# Import Third Party Libs
try:
    from pyVmomi import vim
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not HAS_PYVMOMI, 'The \'pyvmomi\' library is missing')
@patch('salt.utils.vmware.time.time', MagicMock(return_value=1))
@patch('salt.utils.vmware.time.sleep', MagicMock(return_value=None))
class WaitForTaskTestCase(TestCase):
    '''Tests for salt.utils.vmware.wait_for_task'''

    def test_info_state_running(self):
        mock_task = MagicMock()
        # The 'bad' values are invalid in the while loop
        prop_mock_state = PropertyMock(side_effect=['running', 'bad', 'bad',
                                                    'success'])
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 4)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_state_queued(self):
        mock_task = MagicMock()
        # The 'bad' values are invalid in the while loop
        prop_mock_state = PropertyMock(side_effect=['bad', 'queued', 'bad',
                                                    'bad', 'success'])
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 5)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_state_success(self):
        mock_task = MagicMock()
        prop_mock_state = PropertyMock(return_value='success')
        prop_mock_result = PropertyMock()
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).result = prop_mock_result
        salt.utils.vmware.wait_for_task(mock_task,
                                        'fake_instance_name',
                                        'task_type')
        self.assertEqual(prop_mock_state.call_count, 3)
        self.assertEqual(prop_mock_result.call_count, 1)

    def test_info_state_different_no_error_attr(self):
        mock_task = MagicMock()
        # The 'bad' values are invalid in the while loop
        prop_mock_state = PropertyMock(return_value='error')
        prop_mock_error = PropertyMock(side_effect=Exception('error exc'))
        type(mock_task.info).state = prop_mock_state
        type(mock_task.info).error = prop_mock_error
        with self.assertRaises(Exception) as excinfo:
            salt.utils.vmware.wait_for_task(mock_task,
                                            'fake_instance_name',
                                            'task_type')
        self.assertEqual(prop_mock_state.call_count, 3)
        self.assertEqual(prop_mock_error.call_count, 1)
        self.assertEqual('error exc', excinfo.exception.message)


#    def test_correct_filter_spec(self):
if __name__ == '__main__':
    from integration import run_tests
    run_tests(WaitForTaskTestCase, needs_daemon=False)
    
