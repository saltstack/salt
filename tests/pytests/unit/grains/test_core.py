import os

import pytest
import salt.grains.core as core
import salt.utils.platform
from tests.support.mock import MagicMock, patch

# import platform


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {core: {}}
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


def test_bsd_memdata_on_openbsd():
    _cmd_run_map = {
        "/sbin/sysctl -n hw.physmem": "4261076992",
        "/sbin/swapctl -sk": "total: 530113 1K-blocks allocated, 0 used, 530113 available",
    }
    _path_exists_map = {}

    cmd_run_mock = MagicMock(side_effect=lambda x: _cmd_run_map[x])
    path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
    empty_mock = MagicMock(return_value={})

    mock_openbsd_uname = (
        "OpenBSD",
        "puffy.lan",
        "6.7",
        "GENERIC.MP#374",
        "amd64",
        "amd64",
    )

    with patch("platform.uname", MagicMock(return_value=mock_openbsd_uname)):
        with patch.object(
            salt.utils.platform, "is_linux", MagicMock(return_value=False)
        ):
            with patch.object(
                salt.utils.platform, "is_openbsd", MagicMock(return_value=True)
            ):
                with patch.object(
                    salt.utils.platform, "is_proxy", MagicMock(return_value=False)
                ):
                    # Skip the init grain compilation (not pertinent)
                    with patch.object(os.path, "exists", path_exists_mock):
                        with patch("salt.utils.path.which") as mock:
                            mock.return_value = "/sbin/sysctl"
                            # Make a bunch of functions return empty dicts,
                            # we don't care about these grains for the
                            # purposes of this test.
                            with patch.object(core, "_bsd_cpudata", empty_mock):
                                with patch.object(core, "_hw_data", empty_mock):
                                    with patch.object(core, "_virtual", empty_mock):
                                        with patch.object(core, "_ps", empty_mock):
                                            # Mock the osarch
                                            with patch.dict(
                                                core.__salt__,
                                                {"cmd.run": cmd_run_mock},
                                            ):
                                                os_grains = core.os_data()

        assert os_grains.get("mem_total") == 4063
        assert os_grains.get("swap_total") == 517


def test_bsd_memdata_on_openbsd_without_swap():
    _cmd_run_map = {
        "/sbin/sysctl -n hw.physmem": "4261076992",
        "/sbin/swapctl -sk": "swapctl: no swap devices configured",
    }
    _path_exists_map = {}

    cmd_run_mock = MagicMock(side_effect=lambda x: _cmd_run_map[x])
    path_exists_mock = MagicMock(side_effect=lambda x: _path_exists_map[x])
    empty_mock = MagicMock(return_value={})

    mock_openbsd_uname = (
        "OpenBSD",
        "puffy.lan",
        "6.7",
        "GENERIC.MP#374",
        "amd64",
        "amd64",
    )

    with patch("platform.uname", MagicMock(return_value=mock_openbsd_uname)):
        with patch.object(
            salt.utils.platform, "is_linux", MagicMock(return_value=False)
        ):
            with patch.object(
                salt.utils.platform, "is_openbsd", MagicMock(return_value=True)
            ):
                with patch.object(
                    salt.utils.platform, "is_proxy", MagicMock(return_value=False)
                ):
                    # Skip the init grain compilation (not pertinent)
                    with patch.object(os.path, "exists", path_exists_mock):
                        with patch("salt.utils.path.which") as mock:
                            mock.return_value = "/sbin/sysctl"
                            # Make a bunch of functions return empty dicts,
                            # we don't care about these grains for the
                            # purposes of this test.
                            with patch.object(core, "_bsd_cpudata", empty_mock):
                                with patch.object(core, "_hw_data", empty_mock):
                                    with patch.object(core, "_virtual", empty_mock):
                                        with patch.object(core, "_ps", empty_mock):
                                            # Mock the osarch
                                            with patch.dict(
                                                core.__salt__,
                                                {"cmd.run": cmd_run_mock},
                                            ):
                                                os_grains = core.os_data()

        assert os_grains.get("mem_total") == 4063
        assert os_grains.get("swap_total") == 0
