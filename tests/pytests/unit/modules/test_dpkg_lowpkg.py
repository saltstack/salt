import os

import salt.modules.dpkg_lowpkg as dpkg
from tests.support.mock import MagicMock, mock_open, patch


def test_get_pkg_license():
    """
    Test _get_pkg_license for ignore errors on reading license from copyright files
    """
    license_read_mock = mock_open(read_data="")
    with patch.object(os.path, "exists", MagicMock(return_value=True)), patch(
        "salt.utils.files.fopen", license_read_mock
    ):
        dpkg._get_pkg_license("bash")

        assert license_read_mock.calls[0].args[0] == "/usr/share/doc/bash/copyright"
        assert license_read_mock.calls[0].kwargs["errors"] == "ignore"
