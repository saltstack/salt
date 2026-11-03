"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

import pytest

import salt.modules.napalm_ntp as napalm_ntp
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {napalm_ntp: {"__salt__": {"config.get": MagicMock(return_value={})}}}


def _mock_device():
    return patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    )


# --- read pass-throughs (unchanged behaviour) -------------------------------


def test_peers():
    with _mock_device():
        assert "172.17.17.1" in napalm_ntp.peers()["out"]


def test_servers():
    with _mock_device():
        assert "172.17.17.1" in napalm_ntp.servers()["out"]


def test_stats():
    with _mock_device():
        assert napalm_ntp.stats()["out"][0]["reachability"] == 377


# --- config writers: route onto the driver's resolved template (#62170) -----

RESOLVED = "/opt/napalm/junos/templates/tpl.j2"


def _route(func, *args):
    """Run a config writer with template resolution + net.load_template mocked."""
    device = napalm_test_support.MockNapalmDevice()
    load_template = MagicMock(return_value={"result": True, "comment": "", "out": None})
    tpath = MagicMock(return_value=RESOLVED)
    with patch("salt.utils.napalm.get_device", MagicMock(return_value=device)), patch(
        "salt.utils.napalm.template_path", tpath
    ), patch.dict(napalm_ntp.__salt__, {"net.load_template": load_template}):
        ret = func(*args, test=True, commit=False)
    return ret, tpath, load_template, device


@pytest.mark.parametrize(
    "func_name, template_name, arg_key, values",
    [
        ("set_peers", "set_ntp_peers", "peers", ("1.2.3.4", "5.6.7.8")),
        ("set_servers", "set_ntp_servers", "servers", ("2.2.3.4", "6.6.7.8")),
        ("delete_peers", "delete_ntp_peers", "peers", ("1.2.3.4", "5.6.7.8")),
        ("delete_servers", "delete_ntp_servers", "servers", ("2.2.3.4", "6.6.7.8")),
    ],
)
def test_writer_routes_resolved_template(func_name, template_name, arg_key, values):
    ret, tpath, load_template, device = _route(getattr(napalm_ntp, func_name), *values)
    assert ret == {"result": True, "comment": "", "out": None}
    # Correct template name requested (guards a set/delete or peers/servers mixup).
    assert tpath.call_args[0][1] == template_name
    load_template.assert_called_once()
    args, kwargs = load_template.call_args
    # Absolute resolved path passed, not the bare name.
    assert args[0] == RESOLVED
    assert values[0] in kwargs[arg_key]
    assert kwargs["test"] is True
    assert kwargs["commit"] is False
    # The open proxy device is threaded through by identity (guards =None / wrong).
    assert kwargs["inherit_napalm_device"] is device


@pytest.mark.parametrize(
    "func_name, template_name",
    [
        ("set_peers", "set_ntp_peers"),
        ("set_servers", "set_ntp_servers"),
        ("delete_peers", "delete_ntp_peers"),
        ("delete_servers", "delete_ntp_servers"),
    ],
)
def test_writer_no_template_for_driver(func_name, template_name):
    with _mock_device(), patch(
        "salt.utils.napalm.template_path", MagicMock(return_value=None)
    ):
        ret = getattr(napalm_ntp, func_name)("1.2.3.4")
    assert ret["result"] is False
    # Exact quoted name (guards a set/delete literal swap in the failure branch).
    assert f"'{template_name}'" in ret["comment"]
    assert "not available" in ret["comment"]
