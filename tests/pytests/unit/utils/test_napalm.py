"""
Unit tests for salt.utils.napalm helpers.
"""

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
