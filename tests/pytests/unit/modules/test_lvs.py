"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.lvs
"""


import pytest

import salt.modules.lvs as lvs
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {lvs: {}}


def test_add_service():
    """
    Test for Add a virtual service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.add_service() == "stderr"


def test_edit_service():
    """
    Test for Edit the virtual service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.edit_service() == "stderr"


def test_delete_service():
    """
    Test for Delete the virtual service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.delete_service() == "stderr"


def test_add_server():
    """
    Test for Add a real server to a virtual service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.add_server() == "stderr"


def test_edit_server():
    """
    Test for Edit a real server to a virtual service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.edit_server() == "stderr"


def test_delete_server():
    """
    Test for Delete the realserver from the virtual service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.delete_server() == "stderr"


def test_clear():
    """
    Test for Clear the virtual server table
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.dict(
            lvs.__salt__,
            {
                "cmd.run_all": MagicMock(
                    return_value={"retcode": "ret", "stderr": "stderr"}
                )
            },
        ):
            assert lvs.clear() == "stderr"


def test_get_rules():
    """
    Test for Get the virtual server rules
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.dict(lvs.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            assert lvs.get_rules() == "A"


def test_list_():
    """
    Test for List the virtual server table
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.list_("p", "s") == "stderr"


def test_zero():
    """
    Test for Zero the packet, byte and rate counters in a
     service or all services.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                assert lvs.zero("p", "s") == "stderr"


def test_check_service():
    """
    Test for Check the virtual service exists.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                with patch.object(lvs, "get_rules", return_value="C"):
                    assert lvs.check_service("p", "s") == "Error: service not exists"


def test_check_server():
    """
    Test for Check the real server exists in the specified service.
    """
    with patch.object(lvs, "__detect_os", return_value="C"):
        with patch.object(lvs, "_build_cmd", return_value="B"):
            with patch.dict(
                lvs.__salt__,
                {
                    "cmd.run_all": MagicMock(
                        return_value={"retcode": "ret", "stderr": "stderr"}
                    )
                },
            ):
                with patch.object(lvs, "get_rules", return_value="C"):
                    assert lvs.check_server("p", "s") == "Error: server not exists"
