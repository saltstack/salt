"""
Tests for set_locale on Debian 13+ (issue #68425).

Debian trixie (13) removed support for ``localectl set-locale``; Salt must
fall through to the existing ``update-locale`` + ``/etc/default/locale``
path on Debian 13 and newer while preserving the prior behaviour on
Debian 12.
"""

import pytest

import salt.modules.localemod as localemod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {localemod: {"__context__": {}, "__salt__": {}}}


@patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/update-locale"))
@patch(
    "salt.modules.localemod.__grains__",
    {"os_family": "Debian", "osmajorrelease": 13},
)
@patch("salt.modules.localemod._localectl_set", MagicMock())
@patch("salt.utils.systemd.booted", MagicMock(return_value=True))
def test_set_locale_debian13_skips_localectl():
    """Debian 13 with systemd must use update-locale, not localectl."""
    with patch.dict(
        localemod.__salt__,
        {"file.replace": MagicMock(), "cmd.run": MagicMock()},
    ):
        localemod.set_locale("de_DE.utf8")
        assert not localemod._localectl_set.called
        assert localemod.__salt__["file.replace"].called
        assert (
            localemod.__salt__["file.replace"].call_args[0][0] == "/etc/default/locale"
        )


@patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/update-locale"))
@patch(
    "salt.modules.localemod.__grains__",
    {"os_family": "Debian", "osmajorrelease": 14},
)
@patch("salt.modules.localemod._localectl_set", MagicMock())
@patch("salt.utils.systemd.booted", MagicMock(return_value=True))
def test_set_locale_debian14_skips_localectl():
    """Future Debian releases (>=13) also fall through to update-locale."""
    with patch.dict(
        localemod.__salt__,
        {"file.replace": MagicMock(), "cmd.run": MagicMock()},
    ):
        localemod.set_locale("de_DE.utf8")
        assert not localemod._localectl_set.called


@patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localectl"))
@patch(
    "salt.modules.localemod.__grains__",
    {"os_family": "Debian", "osmajorrelease": 12},
)
@patch("salt.modules.localemod._localectl_set", MagicMock())
@patch("salt.utils.systemd.booted", MagicMock(return_value=True))
def test_set_locale_debian12_still_uses_localectl():
    """Debian 12 path is unchanged (regression guard)."""
    localemod.set_locale("de_DE.utf8")
    assert localemod._localectl_set.called
    assert localemod._localectl_set.call_args[0][0] == "de_DE.utf8"
