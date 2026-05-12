"""
Unit tests for salt.utils.nxos
"""

import json

import salt.utils.nxos as nxos
from tests.support.mock import MagicMock, patch


class TestNxapiClient:
    """
    Test cases for NxapiClient class
    """

    def test_parse_response_uds_read_limit(self):
        """
        Test that response.read() is called with a safe limit when connecting over UDS
        """
        # Create a mock response object
        mock_response = MagicMock()
        mock_json_data = {
            "ins_api": {
                "outputs": {
                    "output": {
                        "code": "200",
                        "msg": "Success",
                        "body": {"test": "data"},
                    }
                }
            }
        }
        mock_response.read.return_value.decode.return_value = json.dumps(mock_json_data)

        # Create NxapiClient with UDS connection
        with patch("os.path.exists", return_value=True):
            client = nxos.NxapiClient()

        # Ensure we're using UDS connection
        assert client.nxargs["connect_over_uds"] is True

        # Call parse_response with the mock response
        command_list = ["show version"]
        result = client.parse_response(mock_response, command_list)

        # Verify response.read() was called with the 10MB limit
        expected_limit = 10 * 1024 * 1024
        mock_response.read.assert_called_once_with(expected_limit)

        # Verify the result is correct
        assert result == [{"test": "data"}]

    def test_parse_response_uds_read_limit_value(self):
        """
        Test that the max_safe_read limit is exactly 10MB
        """
        # Create a mock response object
        mock_response = MagicMock()
        mock_json_data = {
            "ins_api": {
                "outputs": {
                    "output": {
                        "code": "200",
                        "msg": "Success",
                        "body": {"result": "ok"},
                    }
                }
            }
        }
        mock_response.read.return_value.decode.return_value = json.dumps(mock_json_data)

        # Create NxapiClient with UDS connection
        with patch("os.path.exists", return_value=True):
            client = nxos.NxapiClient()

        # Parse response
        command_list = ["test command"]
        client.parse_response(mock_response, command_list)

        # Get the actual argument passed to read()
        call_args = mock_response.read.call_args
        actual_limit = call_args[0][0] if call_args[0] else call_args[1].get("amt")

        # Verify it's exactly 10MB (10485760 bytes)
        assert actual_limit == 10485760
        assert actual_limit == 10 * 1024 * 1024
