import pytest

import salt.modules.pkg as pkg
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pkg: {"__opts__": {"file_client": "local"}, "__salt__": {}}}


def test_virtual_only_loads_for_onedir_when_bindings_missing():
    with patch("salt.utils.pkg.check_bundled", MagicMock(return_value=True)), patch(
        "salt.utils.pkg.onedir_missing_pkg_bindings", MagicMock(return_value=True)
    ):
        ret = pkg.__virtual__()
        assert ret == "pkg"


def test_list_pkgs_rpm_parsing():
    with patch("salt.utils.pkg.check_bundled", MagicMock(return_value=True)), patch(
        "salt.utils.pkg.onedir_missing_pkg_bindings", MagicMock(return_value=True)
    ), patch("salt.utils.path.which", MagicMock(side_effect=lambda x: x == "rpm")):
        with patch.dict(
            pkg.__salt__,
            {
                "cmd.retcode": MagicMock(return_value=0),
                "cmd.run_stdout": MagicMock(
                    return_value="salt\t3007.10-1\nsalt-minion\t3007.10-1\n"
                ),
            },
        ):
            ret = pkg.list_pkgs()
            assert ret["salt"] == "3007.10-1"
            assert ret["salt-minion"] == "3007.10-1"


def test_version_multiple_names():
    with patch("salt.utils.pkg.check_bundled", MagicMock(return_value=True)), patch(
        "salt.utils.pkg.onedir_missing_pkg_bindings", MagicMock(return_value=True)
    ), patch("salt.utils.path.which", MagicMock(side_effect=lambda x: x == "rpm")):
        with patch.dict(
            pkg.__salt__,
            {
                "cmd.retcode": MagicMock(return_value=0),
                "cmd.run_stdout": MagicMock(
                    return_value="salt\t3007.10-1\nsalt-ssh\t3007.10-1\n"
                ),
            },
        ):
            ret = pkg.version("salt", "salt-ssh")
            assert ret == {"salt": "3007.10-1", "salt-ssh": "3007.10-1"}


