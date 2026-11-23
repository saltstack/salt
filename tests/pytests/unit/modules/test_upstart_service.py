"""
Unit tests for the upstart_service module
"""

import warnings

import pytest

import salt.modules.upstart_service as upstart
import salt.utils.files

pytestmark = [
    pytest.mark.skip_on_windows(reason="Upstart is not available on Windows"),
]


@pytest.fixture
def configure_loader_modules():
    return {upstart: {}}


def test_upstart_enable_removes_manual_without_deprecation_warning(
    tmp_path, monkeypatch
):
    """
    Enabling a service removes the "manual" line from its files. re.sub must
    not get count and flags as positional arguments (deprecated in Python 3.13).
    """
    conf = tmp_path / "svc.conf"
    override = tmp_path / "svc.override"
    conf.write_text("description x\nmanual\nexec /bin/true\n")
    override.write_text("manual\n")
    paths = {
        "/etc/init/svc.conf": str(conf),
        "/etc/init/svc.override": str(override),
    }
    real_fopen = salt.utils.files.fopen
    enabled = iter([False, True])

    monkeypatch.setattr(upstart, "_upstart_is_enabled", lambda name: next(enabled))
    monkeypatch.setattr(upstart.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(upstart.os, "access", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        salt.utils.files,
        "fopen",
        lambda path, mode="r", **kwargs: real_fopen(
            paths.get(path, path), mode, **kwargs
        ),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert upstart._upstart_enable("svc") is True

    assert conf.read_text() == "description x\nexec /bin/true\n"
    assert override.read_text() == ""
