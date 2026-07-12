"""
Unit tests for salt.utils.napalm helpers.
"""

import types

import salt.utils.napalm as napalm_utils
from tests.support.mock import MagicMock, patch


class _BaseDriver:
    pass


class _ConcreteDriver(_BaseDriver):
    pass


def _getfile_map(mapping):
    """
    Build an ``inspect.getfile`` replacement that returns a distinct path per
    class and raises (like the real one) for anything not in the map -- notably
    ``object``, so the resolver's exception-continue is genuinely exercised.
    """

    def fake_getfile(klass):
        try:
            return mapping[klass]
        except KeyError:
            raise TypeError(f"{klass!r} is a built-in class")

    return fake_getfile


def _ship(directory, template_name):
    tpl_dir = directory / "templates"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / f"{template_name}.j2").write_text("system { }")
    return tpl_dir / f"{template_name}.j2"


def test_template_path_walks_mro_to_base(tmp_path):
    """
    Templates can be inherited: the concrete driver ships none but a base class
    does. The resolver must walk the MRO (concrete -> base) and skip ``object``
    (which raises from getfile) rather than stopping at the first class.
    """
    (tmp_path / "concrete").mkdir()
    base_tpl = _ship(tmp_path / "base", "set_ntp_peers")

    device = {"DRIVER": _ConcreteDriver()}
    getfile = _getfile_map(
        {
            _ConcreteDriver: str(tmp_path / "concrete" / "driver.py"),
            _BaseDriver: str(tmp_path / "base" / "base.py"),
        }
    )
    with patch("salt.utils.napalm.inspect.getfile", side_effect=getfile):
        resolved = napalm_utils.template_path(device, "set_ntp_peers")
    assert resolved == str(base_tpl)


def test_template_path_prefers_concrete_over_base(tmp_path):
    """
    When both the concrete driver and a base class ship the same template, the
    concrete override wins -- the walk must be concrete-first, not reversed.
    """
    concrete_tpl = _ship(tmp_path / "concrete", "set_ntp_peers")
    _ship(tmp_path / "base", "set_ntp_peers")

    device = {"DRIVER": _ConcreteDriver()}
    getfile = _getfile_map(
        {
            _ConcreteDriver: str(tmp_path / "concrete" / "driver.py"),
            _BaseDriver: str(tmp_path / "base" / "base.py"),
        }
    )
    with patch("salt.utils.napalm.inspect.getfile", side_effect=getfile):
        resolved = napalm_utils.template_path(device, "set_ntp_peers")
    assert resolved == str(concrete_tpl)


def test_template_path_skips_oserror(tmp_path):
    """
    ``inspect.getfile`` raises ``OSError`` for classes with no on-disk source
    (frozen / ``__main__``); that class must be skipped, not propagated.
    """
    base_tpl = _ship(tmp_path / "base", "set_ntp_peers")

    def getfile(klass):
        if klass is _BaseDriver:
            return str(tmp_path / "base" / "base.py")
        raise OSError("source code not available")  # _ConcreteDriver + object

    device = {"DRIVER": _ConcreteDriver()}
    with patch("salt.utils.napalm.inspect.getfile", side_effect=getfile):
        resolved = napalm_utils.template_path(device, "set_ntp_peers")
    assert resolved == str(base_tpl)


def test_template_path_missing_returns_none(tmp_path):
    """
    Drivers that ship no matching template anywhere in the MRO (e.g. ios has no
    user templates) resolve to ``None``, and a device with no / an empty /
    a missing ``DRIVER`` is handled too.
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
    with patch("salt.utils.napalm.inspect.getfile", side_effect=getfile):
        assert napalm_utils.template_path(device, "set_ntp_peers") is None
    # A truthy device whose DRIVER key is absent -> None (not a KeyError).
    assert napalm_utils.template_path({"NOT_DRIVER": object()}, "x") is None
    # No device / driver at all is handled too.
    assert napalm_utils.template_path({}, "x") is None
    assert napalm_utils.template_path(None, "x") is None


def test_template_not_available_shape():
    """
    The failure payload mirrors net.load_template's shape and names the driver.
    """
    ret = napalm_utils.template_not_available("set_ntp_peers", {"DRIVER_NAME": "ios"})
    assert ret["result"] is False
    assert ret["out"] is None
    assert (
        ret["comment"]
        == "The 'set_ntp_peers' template is not available for the 'ios' driver."
    )
    # Tolerates a missing / None device without raising.
    assert napalm_utils.template_not_available("x", None)["result"] is False


def test_template_not_available_closes_non_always_alive():
    """
    Because it short-circuits net.load_template, the failure path must close the
    per-call connection a non-always-alive proxy / minion opened.
    """
    driver = MagicMock()
    device = {"DRIVER": driver, "DRIVER_NAME": "junos", "__opts__": {"id": "sw01"}}
    with patch("salt.utils.napalm.not_always_alive", MagicMock(return_value=True)):
        napalm_utils.template_not_available("set_ntp_peers", device)
    driver.close.assert_called_once()


def test_template_not_available_leaves_always_alive_open():
    """An always-alive proxy's persistent session must NOT be closed here."""
    driver = MagicMock()
    device = {"DRIVER": driver, "DRIVER_NAME": "junos", "__opts__": {"id": "sw01"}}
    with patch("salt.utils.napalm.not_always_alive", MagicMock(return_value=False)):
        napalm_utils.template_not_available("set_ntp_peers", device)
    driver.close.assert_not_called()
    # CLOSE explicitly False also suppresses the close.
    with patch("salt.utils.napalm.not_always_alive", MagicMock(return_value=True)):
        napalm_utils.template_not_available(
            "set_ntp_peers",
            {"DRIVER": driver, "__opts__": {"id": "sw01"}, "CLOSE": False},
        )
    driver.close.assert_not_called()


def test_get_device_opts_null_optional_args():
    # ``optional_args: null`` in the config yields None from ``.get(..., {})``
    # (the default only applies to a missing key), which then crashed the
    # ``"config_lock" not in ...`` membership test.
    opts = {"napalm": {"driver": "junos", "optional_args": None}}
    device = napalm_utils.get_device_opts(opts)
    assert isinstance(device["OPTIONAL_ARGS"], dict)
    assert device["OPTIONAL_ARGS"]["config_lock"] is False


def test_get_device_opts_does_not_mutate_caller():
    # The injected config_lock / keepalive must land in a copy, not in the
    # caller's live opts / pillar ``optional_args`` dict.
    optional_args = {"port": 830}
    opts = {"napalm": {"driver": "junos", "optional_args": optional_args}}
    napalm_utils.get_device_opts(opts)
    assert optional_args == {"port": 830}


def _wrapped_with_opts(opts):
    """A ``proxy_napalm_wrap``-decorated function whose module globals carry the
    given ``__opts__`` (so we can drive the wrapper without a real minion)."""

    def _fn(*args, **kwargs):
        return "ok"

    func_globals = {
        "__opts__": opts,
        "__proxy__": {},
        "__salt__": {"config.get": MagicMock(return_value={"driver": "junos"})},
    }
    fn = types.FunctionType(_fn.__code__, func_globals, "_fn")
    return napalm_utils.proxy_napalm_wrap(fn)


def test_proxy_napalm_wrap_force_reconnect_straight_minion():
    # force_reconnect on a straight (non-proxy) minion has no ``opts['proxy']``;
    # the wrapper must not blindly do ``opts['proxy'].update(...)`` (KeyError).
    # The override reaches the device through clean_kwargs on the straight path.
    opts = {"napalm": {"driver": "junos"}}
    wrapped = _wrapped_with_opts(opts)
    get_device = MagicMock(return_value={"DRIVER": MagicMock()})
    with patch("salt.utils.napalm.get_device", get_device):
        result = wrapped(force_reconnect=True)
    assert result == "ok"
    get_device.assert_called_once()
    assert get_device.call_args[0][0]["napalm"].get("force_reconnect") is True
