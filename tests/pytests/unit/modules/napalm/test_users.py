"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

import pytest

import salt.modules.napalm_network as napalm_network
import salt.modules.napalm_users as napalm_users
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {
            "config.get": MagicMock(
                return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
            ),
            "file.file_exists": napalm_test_support.true,
            "file.join": napalm_test_support.join,
            "file.get_managed": napalm_test_support.get_managed_file,
            "random.hash": napalm_test_support.random_hash,
            "net.load_template": napalm_network.load_template,
        }
    }

    return {napalm_users: module_globals, napalm_network: module_globals}


def test_config():
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ):
        ret = napalm_users.config()
        assert ret["out"] == napalm_test_support.TEST_USERS.copy()


class _BaseDriver:
    pass


class _ConcreteDriver(_BaseDriver):
    pass


def _getfile_map(mapping):
    """
    Build an ``inspect.getfile`` replacement that returns a distinct path per
    class and raises (like the real one) for anything not in the map -- notably
    ``object``, so the loop's exception-continue is genuinely exercised.
    """

    def fake_getfile(klass):
        try:
            return mapping[klass]
        except KeyError:
            raise TypeError(f"{klass!r} is a built-in class")

    return fake_getfile


def test_napalm_template_path_walks_mro_to_base(tmp_path):
    """
    #62170: templates can be inherited -- the concrete driver ships none but a
    base class does. The resolver must walk the MRO (concrete -> base) and skip
    ``object`` (which raises from getfile) rather than stopping at the first
    class.
    """
    concrete_dir = tmp_path / "concrete"
    concrete_dir.mkdir()
    base_tpl = tmp_path / "base" / "templates"
    base_tpl.mkdir(parents=True)
    (base_tpl / "set_users.j2").write_text("system { }")

    device = {"DRIVER": _ConcreteDriver()}
    getfile = _getfile_map(
        {
            _ConcreteDriver: str(concrete_dir / "driver.py"),
            _BaseDriver: str(tmp_path / "base" / "base.py"),
        }
    )
    with patch("salt.modules.napalm_users.inspect.getfile", side_effect=getfile):
        resolved = napalm_users._napalm_template_path(device, "set_users")
    assert resolved == str(base_tpl / "set_users.j2")


def test_napalm_template_path_missing_returns_none(tmp_path):
    """
    Drivers that do not ship a given template anywhere in the MRO (e.g. ios has
    no user templates) resolve to ``None`` rather than an unusable path -- and
    the ``object`` -> exception step must not escape the helper.
    """
    (tmp_path / "concrete").mkdir()
    (tmp_path / "base").mkdir()
    device = {"DRIVER": _ConcreteDriver()}
    getfile = _getfile_map(
        {
            _ConcreteDriver: str(tmp_path / "concrete" / "driver.py"),
            _BaseDriver: str(tmp_path / "base" / "base.py"),
        }
    )
    with patch("salt.modules.napalm_users.inspect.getfile", side_effect=getfile):
        assert napalm_users._napalm_template_path(device, "set_users") is None
    # No device / driver at all is handled too.
    assert napalm_users._napalm_template_path({}, "set_users") is None
    assert napalm_users._napalm_template_path(None, "set_users") is None


def test_set_users_routes_resolved_template():
    """
    #62170: set_users must hand the resolved absolute template path (not the
    bare "set_users" name, which no longer resolves) to net.load_template.
    """
    resolved = "/opt/napalm/junos/templates/set_users.j2"
    load_template = MagicMock(return_value={"result": True, "comment": "", "out": None})
    template_path = MagicMock(return_value=resolved)
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ), patch.object(napalm_users, "_napalm_template_path", template_path), patch.dict(
        napalm_users.__salt__, {"net.load_template": load_template}
    ):
        ret = napalm_users.set_users({"mircea": {"level": 1}}, test=True, commit=False)
    assert ret == {"result": True, "comment": "", "out": None}
    # It must ask for the "set_users" template, not "delete_users" (guards the
    # copy-paste between the two near-identical functions).
    assert template_path.call_args[0][1] == "set_users"
    load_template.assert_called_once()
    args, kwargs = load_template.call_args
    assert args[0] == resolved
    assert kwargs["users"] == {"mircea": {"level": 1}}
    assert kwargs["test"] is True
    assert kwargs["commit"] is False
    # The open proxy device is threaded through so the load reuses the session.
    assert "inherit_napalm_device" in kwargs


def test_delete_users_routes_resolved_template():
    """
    #62170: delete_users resolves and uses delete_users.j2 the same way.
    """
    resolved = "/opt/napalm/junos/templates/delete_users.j2"
    load_template = MagicMock(return_value={"result": True, "comment": "", "out": None})
    template_path = MagicMock(return_value=resolved)
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ), patch.object(napalm_users, "_napalm_template_path", template_path), patch.dict(
        napalm_users.__salt__, {"net.load_template": load_template}
    ):
        ret = napalm_users.delete_users({"mircea": {}})
    assert ret == {"result": True, "comment": "", "out": None}
    assert template_path.call_args[0][1] == "delete_users"
    load_template.assert_called_once()
    args, kwargs = load_template.call_args
    assert args[0] == resolved
    assert "inherit_napalm_device" in kwargs


def test_set_users_no_template_for_driver():
    """
    When the driver ships no such template, set_users returns a clear error
    instead of leaking the confusing "Local file source set_users does not
    exist" message from the fileserver.
    """
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ), patch.object(
        napalm_users, "_napalm_template_path", MagicMock(return_value=None)
    ):
        ret = napalm_users.set_users({"mircea": {}})
    assert ret["result"] is False
    assert "not available" in ret["comment"]


def test_delete_users_no_template_for_driver():
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ), patch.object(
        napalm_users, "_napalm_template_path", MagicMock(return_value=None)
    ):
        ret = napalm_users.delete_users({"mircea": {}})
    assert ret["result"] is False
    assert "not available" in ret["comment"]
