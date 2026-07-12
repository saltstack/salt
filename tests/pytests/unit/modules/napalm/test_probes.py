"""
Unit tests for the napalm_probes execution module.
"""

import pytest

import salt.modules.napalm_probes as napalm_probes
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {napalm_probes: {"__salt__": {"config.get": MagicMock(return_value={})}}}


def _mock_device():
    return patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    )


# --- read pass-throughs -----------------------------------------------------


def test_config():
    with _mock_device():
        ret = napalm_probes.config()
        assert ret["result"] is True
        assert ret["out"] == napalm_test_support.TEST_PROBES_CONFIG.copy()


def test_results():
    with _mock_device():
        ret = napalm_probes.results()
        assert ret["result"] is True
        assert ret["out"] == napalm_test_support.TEST_PROBES_RESULTS.copy()


# --- config writers: route onto the driver's resolved template (#62170) -----

RESOLVED = "/opt/napalm/junos/templates/tpl.j2"
PROBES = {"new_probe": {"new_test1": {}}}


def _route(func):
    device = napalm_test_support.MockNapalmDevice()
    load_template = MagicMock(return_value={"result": True, "comment": "", "out": None})
    tpath = MagicMock(return_value=RESOLVED)
    with patch("salt.utils.napalm.get_device", MagicMock(return_value=device)), patch(
        "salt.utils.napalm.template_path", tpath
    ), patch.dict(napalm_probes.__salt__, {"net.load_template": load_template}):
        ret = func(PROBES, test=True, commit=False)
    return ret, tpath, load_template, device


@pytest.mark.parametrize(
    "func_name, template_name",
    [
        ("set_probes", "set_probes"),
        ("delete_probes", "delete_probes"),
        ("schedule_probes", "schedule_probes"),
    ],
)
def test_writer_routes_resolved_template(func_name, template_name):
    ret, tpath, load_template, device = _route(getattr(napalm_probes, func_name))
    assert ret == {"result": True, "comment": "", "out": None}
    assert tpath.call_args[0][1] == template_name
    load_template.assert_called_once()
    args, kwargs = load_template.call_args
    assert args[0] == RESOLVED
    assert kwargs["probes"] == PROBES
    assert kwargs["test"] is True
    assert kwargs["commit"] is False
    assert kwargs["inherit_napalm_device"] is device


@pytest.mark.parametrize(
    "func_name, template_name",
    [
        ("set_probes", "set_probes"),
        ("delete_probes", "delete_probes"),
        ("schedule_probes", "schedule_probes"),
    ],
)
def test_writer_no_template_for_driver(func_name, template_name):
    with _mock_device(), patch(
        "salt.utils.napalm.template_path", MagicMock(return_value=None)
    ):
        ret = getattr(napalm_probes, func_name)(PROBES)
    assert ret["result"] is False
    assert f"'{template_name}'" in ret["comment"]
    assert "not available" in ret["comment"]
