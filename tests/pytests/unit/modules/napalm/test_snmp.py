"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

import pytest

import salt.modules.napalm_snmp as napalm_snmp
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {napalm_snmp: {"__salt__": {"config.get": MagicMock(return_value={})}}}


def _mock_device():
    return patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    )


def test_config():
    with _mock_device():
        ret = napalm_snmp.config()
        assert ret["out"] == napalm_test_support.TEST_SNMP_INFO.copy()


# --- config writers: route onto the driver's resolved template (#62170) -----

RESOLVED = "/opt/napalm/junos/templates/tpl.j2"


def _route(func, **kwargs):
    device = napalm_test_support.MockNapalmDevice()
    load_template = MagicMock(return_value={"result": True, "comment": "", "out": None})
    tpath = MagicMock(return_value=RESOLVED)
    with patch("salt.utils.napalm.get_device", MagicMock(return_value=device)), patch(
        "salt.utils.napalm.template_path", tpath
    ), patch.dict(napalm_snmp.__salt__, {"net.load_template": load_template}):
        ret = func(test=True, commit=False, **kwargs)
    return ret, tpath, load_template, device


@pytest.mark.parametrize(
    "func_name, template_name",
    [
        ("update_config", "snmp_config"),
        ("remove_config", "delete_snmp_config"),
    ],
)
def test_writer_routes_resolved_template(func_name, template_name):
    ret, tpath, load_template, device = _route(
        getattr(napalm_snmp, func_name), location="Greenwich, UK"
    )
    assert ret == {"result": True, "comment": "", "out": None}
    assert tpath.call_args[0][1] == template_name
    load_template.assert_called_once()
    _args, kwargs = load_template.call_args
    # snmp builds a dict and calls net.load_template(**dic), so the resolved
    # path arrives as the template_name kwarg, not positionally.
    assert kwargs["template_name"] == RESOLVED
    assert kwargs["location"] == "Greenwich, UK"
    assert kwargs["test"] is True
    assert kwargs["commit"] is False
    assert kwargs["inherit_napalm_device"] is device


@pytest.mark.parametrize(
    "func_name, template_name",
    [
        ("update_config", "snmp_config"),
        ("remove_config", "delete_snmp_config"),
    ],
)
def test_writer_no_template_for_driver(func_name, template_name):
    with _mock_device(), patch(
        "salt.utils.napalm.template_path", MagicMock(return_value=None)
    ):
        ret = getattr(napalm_snmp, func_name)(location="x")
    assert ret["result"] is False
    # Exact quoted name: "'snmp_config'" must not match "'delete_snmp_config'".
    assert f"'{template_name}'" in ret["comment"]
    assert "not available" in ret["comment"]
