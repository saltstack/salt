"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""
import pytest

import salt.modules.localemod as localemod
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase


class LocalemodTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.localemod
    """

    locale_ctl_out = """
   System Locale: LANG=de_DE.utf8
                  LANGUAGE=de_DE.utf8
       VC Keymap: n/a
      X11 Layout: us
       X11 Model: pc105
    """
    locale_ctl_notset = """
       System Locale: n/a

       VC Keymap: n/a
      X11 Layout: n/a
       X11 Model: n/a
    """
    locale_ctl_out_empty = ""
    locale_ctl_out_broken = """
    System error:Recursive traversal of loopback mount points
    """
    locale_ctl_out_structure = """
       Main: printers=We're upgrading /dev/null
             racks=hardware stress fractures
             failure=Ionisation from the air-conditioning
    Cow say: errors=We're out of slots on the server
             hardware=high pressure system failure
     Reason: The vendor put the bug there.
    """

    def setup_loader_modules(self):
        return {localemod: {}}

    def test_list_avail(self):
        """
        Test for Lists available (compiled) locales
        """
        with patch.dict(
            localemod.__salt__, {"cmd.run": MagicMock(return_value="A\nB")}
        ):
            assert localemod.list_avail() == ["A", "B"]

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run": MagicMock(return_value=locale_ctl_out)},
    )
    def test_localectl_status_parser(self):
        """
        Test localectl status parser.
        :return:
        """
        out = localemod._localectl_status()
        assert isinstance(out, dict)
        for key in ["system_locale", "vc_keymap", "x11_layout", "x11_model"]:
            assert key in out
        assert isinstance(out["system_locale"], dict)
        assert "LANG" in out["system_locale"]
        assert "LANGUAGE" in out["system_locale"]
        assert (
            out["system_locale"]["LANG"]
            == out["system_locale"]["LANGUAGE"]
            == "de_DE.utf8"
        )
        assert isinstance(out["vc_keymap"], dict)
        assert "data" in out["vc_keymap"]
        assert out["vc_keymap"]["data"] is None
        assert isinstance(out["x11_layout"], dict)
        assert "data" in out["x11_layout"]
        assert out["x11_layout"]["data"] == "us"
        assert isinstance(out["x11_model"], dict)
        assert "data" in out["x11_model"]
        assert out["x11_model"]["data"] == "pc105"

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run": MagicMock(return_value=locale_ctl_notset)},
    )
    def test_localectl_status_parser_notset(self):
        """
        Test localectl status parser.
        :return:
        """
        out = localemod._localectl_status()
        assert isinstance(out, dict)
        for key in ["system_locale", "vc_keymap", "x11_layout"]:
            assert key in out
        assert isinstance(out["system_locale"], dict)
        assert "data" in out["system_locale"]
        assert out["system_locale"]["data"] is None
        assert isinstance(out["vc_keymap"], dict)
        assert "data" in out["vc_keymap"]
        assert out["vc_keymap"]["data"] is None
        assert isinstance(out["x11_layout"], dict)
        assert "data" in out["x11_layout"]
        assert out["x11_layout"]["data"] is None

    @patch("salt.modules.localemod.dbus", MagicMock())
    def test_dbus_locale_parser_matches(self):
        """
        Test dbus locale status parser matching the results.
        :return:
        """
        i_dbus = MagicMock()
        i_dbus.Get = MagicMock(return_value=["LANG=de_DE.utf8"])
        dbus = MagicMock(return_value=i_dbus)

        with patch("salt.modules.localemod.dbus.Interface", dbus):
            out = localemod._parse_dbus_locale()
            assert isinstance(out, dict)
            assert "LANG" in out
            assert out["LANG"] == "de_DE.utf8"

    @patch("salt.modules.localemod.dbus", MagicMock())
    @patch("salt.modules.localemod.log", MagicMock())
    def test_dbus_locale_parser_doesnot_matches(self):
        """
        Test dbus locale status parser does not matching the results.
        :return:
        """
        i_dbus = MagicMock()
        i_dbus.Get = MagicMock(return_value=["Fatal error right in front of screen"])
        dbus = MagicMock(return_value=i_dbus)

        with patch("salt.modules.localemod.dbus.Interface", dbus):
            out = localemod._parse_dbus_locale()
            assert isinstance(out, dict)
            assert "LANG" not in out
            assert localemod.log.error.called
            msg = (
                localemod.log.error.call_args[0][0]
                % localemod.log.error.call_args[0][1]
            )
            assert (
                msg == 'Odd locale parameter "Fatal error right in front of screen"'
                " detected in dbus locale output. This should not happen. You should"
                " probably investigate what caused this."
            )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch("salt.modules.localemod.log", MagicMock())
    def test_localectl_status_parser_no_systemd(self):
        """
        Test localectl status parser raises an exception if no systemd installed.
        :return:
        """
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod._localectl_status()
        assert 'Unable to find "localectl"' in str(exc_info.value)
        assert not localemod.log.debug.called

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run": MagicMock(return_value=locale_ctl_out_empty)},
    )
    def test_localectl_status_parser_empty(self):
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod._localectl_status()
        assert 'Unable to parse result of "localectl"' in str(exc_info.value)

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run": MagicMock(return_value=locale_ctl_out_broken)},
    )
    def test_localectl_status_parser_broken(self):
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod._localectl_status()
        assert 'Unable to parse result of "localectl"' in str(exc_info.value)

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run": MagicMock(return_value=locale_ctl_out_structure)},
    )
    def test_localectl_status_parser_structure(self):
        out = localemod._localectl_status()
        assert isinstance(out, dict)
        for key in ["main", "cow_say"]:
            assert isinstance(out[key], dict)
            for in_key in out[key]:
                assert isinstance(out[key][in_key], str)
        assert isinstance(out["reason"]["data"], str)

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Ubuntu", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch(
        "salt.modules.localemod._parse_dbus_locale",
        MagicMock(return_value={"LANG": "en_US.utf8"}),
    )
    @patch(
        "salt.modules.localemod._localectl_status",
        MagicMock(return_value={"system_locale": {"LANG": "de_DE.utf8"}}),
    )
    @patch("salt.utils.systemd.booted", MagicMock(return_value=True))
    def test_get_locale_with_systemd_nodbus(self):
        """
        Test getting current system locale with systemd but no dbus available.
        :return:
        """
        assert localemod.get_locale() == "de_DE.utf8"

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Ubuntu", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", True)
    @patch(
        "salt.modules.localemod._parse_dbus_locale",
        MagicMock(return_value={"LANG": "en_US.utf8"}),
    )
    @patch(
        "salt.modules.localemod._localectl_status",
        MagicMock(return_value={"system_locale": {"LANG": "de_DE.utf8"}}),
    )
    @patch("salt.utils.systemd.booted", MagicMock(return_value=True))
    def test_get_locale_with_systemd_and_dbus(self):
        """
        Test getting current system locale with systemd and dbus available.
        :return:
        """
        assert localemod.get_locale() == "en_US.utf8"

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__grains__", {"os_family": "Suse", "osmajorrelease": 12}
    )
    @patch("salt.modules.localemod.dbus", True)
    @patch(
        "salt.modules.localemod._parse_dbus_locale",
        MagicMock(return_value={"LANG": "en_US.utf8"}),
    )
    @patch(
        "salt.modules.localemod._localectl_status",
        MagicMock(return_value={"system_locale": {"LANG": "de_DE.utf8"}}),
    )
    @patch("salt.modules.localemod.__salt__", {"cmd.run": MagicMock()})
    @patch("salt.utils.systemd.booted", MagicMock(return_value=True))
    def test_get_locale_with_systemd_and_dbus_sle12(self):
        """
        Test getting current system locale with systemd and dbus available on SLE12.
        :return:
        """
        localemod.get_locale()
        assert (
            localemod.__salt__["cmd.run"].call_args[0][0]
            == 'grep "^RC_LANG" /etc/sysconfig/language'
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "RedHat", "osmajorrelease": 12},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", {"cmd.run": MagicMock()})
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_redhat(self):
        """
        Test getting current system locale with systemd and dbus available on RedHat.
        :return:
        """
        localemod.get_locale()
        assert (
            localemod.__salt__["cmd.run"].call_args[0][0]
            == 'grep "^LANG=" /etc/sysconfig/i18n'
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Debian", "osmajorrelease": 12},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", {"cmd.run": MagicMock()})
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_debian(self):
        """
        Test getting current system locale with systemd and dbus available on Debian.
        :return:
        """
        localemod.get_locale()
        assert (
            localemod.__salt__["cmd.run"].call_args[0][0]
            == 'grep "^LANG=" /etc/default/locale'
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Gentoo", "osmajorrelease": 12},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", {"cmd.run": MagicMock()})
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_gentoo(self):
        """
        Test getting current system locale with systemd and dbus available on Gentoo.
        :return:
        """
        localemod.get_locale()
        assert (
            localemod.__salt__["cmd.run"].call_args[0][0]
            == "eselect --brief locale show"
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Solaris", "osmajorrelease": 12},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", {"cmd.run": MagicMock()})
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_solaris(self):
        """
        Test getting current system locale with systemd and dbus available on Solaris.
        :return:
        """
        localemod.get_locale()
        assert (
            localemod.__salt__["cmd.run"].call_args[0][0]
            == 'grep "^LANG=" /etc/default/init'
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "BSD", "osmajorrelease": 8, "oscodename": "DrunkDragon"},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", {"cmd.run": MagicMock()})
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_get_locale_with_no_systemd_unknown(self):
        """
        Test getting current system locale with systemd and dbus available on Gentoo.
        :return:
        """
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod.get_locale()
        assert '"DrunkDragon" is unsupported' in str(exc_info.value)

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Ubuntu", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.utils.systemd.booted", MagicMock(return_value=True))
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    def test_set_locale_with_systemd_nodbus(self):
        """
        Test setting current system locale with systemd but no dbus available.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert localemod._localectl_set.call_args[0][0] == "de_DE.utf8"

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Ubuntu", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", True)
    @patch("salt.utils.systemd.booted", MagicMock(return_value=True))
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    def test_set_locale_with_systemd_and_dbus(self):
        """
        Test setting current system locale with systemd and dbus available.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert localemod._localectl_set.call_args[0][0] == "de_DE.utf8"

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    @patch(
        "salt.modules.localemod.__grains__", {"os_family": "Suse", "osmajorrelease": 12}
    )
    @patch("salt.modules.localemod.dbus", True)
    @patch("salt.modules.localemod.__salt__", MagicMock())
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=True))
    def test_set_locale_with_systemd_and_dbus_sle12(self):
        """
        Test setting current system locale with systemd and dbus available on SLE12.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__["file.replace"].called
        assert (
            localemod.__salt__["file.replace"].call_args[0][0]
            == "/etc/sysconfig/language"
        )
        assert localemod.__salt__["file.replace"].call_args[0][1] == "^RC_LANG=.*"
        assert localemod.__salt__["file.replace"].call_args[0][
            2
        ] == 'RC_LANG="{}"'.format(loc)

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "RedHat", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", MagicMock())
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_redhat(self):
        """
        Test setting current system locale with systemd and dbus available on RedHat.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__["file.replace"].called
        assert (
            localemod.__salt__["file.replace"].call_args[0][0] == "/etc/sysconfig/i18n"
        )
        assert localemod.__salt__["file.replace"].call_args[0][1] == "^LANG=.*"
        assert localemod.__salt__["file.replace"].call_args[0][2] == 'LANG="{}"'.format(
            loc
        )

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/update-locale"))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Debian", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", MagicMock())
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_debian(self):
        """
        Test setting current system locale with systemd and dbus available on Debian.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__["file.replace"].called
        assert (
            localemod.__salt__["file.replace"].call_args[0][0] == "/etc/default/locale"
        )
        assert localemod.__salt__["file.replace"].call_args[0][1] == "^LANG=.*"
        assert localemod.__salt__["file.replace"].call_args[0][2] == 'LANG="{}"'.format(
            loc
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Debian", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", MagicMock())
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_debian_no_update_locale(self):
        """
        Test setting current system locale with systemd and dbus available on Debian but update-locale is not installed.
        :return:
        """
        loc = "de_DE.utf8"
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert 'Cannot set locale: "update-locale" was not found.' in str(
            exc_info.value
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Gentoo", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch("salt.modules.localemod.__salt__", MagicMock())
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_gentoo(self):
        """
        Test setting current system locale with systemd and dbus available on Gentoo.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert (
            localemod.__salt__["cmd.retcode"].call_args[0][0]
            == "eselect --brief locale set de_DE.utf8"
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Solaris", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch(
        "salt.modules.localemod.__salt__",
        {
            "locale.list_avail": MagicMock(return_value=["de_DE.utf8"]),
            "file.replace": MagicMock(),
        },
    )
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_solaris_with_list_avail(self):
        """
        Test setting current system locale with systemd and dbus available on Solaris.
        The list_avail returns the proper locale.
        :return:
        """
        loc = "de_DE.utf8"
        localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert localemod.__salt__["file.replace"].called
        assert localemod.__salt__["file.replace"].call_args[0][0] == "/etc/default/init"
        assert localemod.__salt__["file.replace"].call_args[0][1] == "^LANG=.*"
        assert localemod.__salt__["file.replace"].call_args[0][2] == 'LANG="{}"'.format(
            loc
        )

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__",
        {"os_family": "Solaris", "osmajorrelease": 42},
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch(
        "salt.modules.localemod.__salt__",
        {
            "locale.list_avail": MagicMock(return_value=["en_GB.utf8"]),
            "file.replace": MagicMock(),
        },
    )
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_solaris_without_list_avail(self):
        """
        Test setting current system locale with systemd and dbus is not available on Solaris.
        The list_avail does not return the proper locale.
        :return:
        """
        loc = "de_DE.utf8"
        assert not localemod.set_locale(loc)
        assert not localemod._localectl_set.called
        assert not localemod.__salt__["file.replace"].called

    @patch("salt.utils.path.which", MagicMock(return_value=None))
    @patch(
        "salt.modules.localemod.__grains__", {"os_family": "BSD", "osmajorrelease": 42}
    )
    @patch("salt.modules.localemod.dbus", None)
    @patch(
        "salt.modules.localemod.__salt__",
        {
            "locale.list_avail": MagicMock(return_value=["en_GB.utf8"]),
            "file.replace": MagicMock(),
        },
    )
    @patch("salt.modules.localemod._localectl_set", MagicMock())
    @patch("salt.utils.systemd.booted", MagicMock(return_value=False))
    def test_set_locale_with_no_systemd_unknown(self):
        """
        Test setting current system locale without systemd on unknown system.
        :return:
        """
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod.set_locale("de_DE.utf8")
        assert "Unsupported platform" in str(exc_info.value)

    @patch(
        "salt.utils.locales.normalize_locale",
        MagicMock(return_value="en_US.UTF-8 UTF-8"),
    )
    @patch(
        "salt.modules.localemod.__salt__",
        {"locale.list_avail": MagicMock(return_value=["A", "B"])},
    )
    def test_avail(self):
        """
        Test for Check if a locale is available
        """
        assert localemod.avail("locale")

    @patch("salt.modules.localemod.log", MagicMock())
    @patch("salt.utils.path.which", MagicMock(return_value="/some/dir/path"))
    @patch("salt.modules.localemod.__grains__", {"os": "Debian"})
    @patch(
        "salt.modules.localemod.__salt__",
        {"file.search": MagicMock(return_value=False)},
    )
    def test_gen_locale_not_valid(self):
        """
        Tests the return of gen_locale when the provided locale is not found
        """
        assert not localemod.gen_locale("foo")
        assert localemod.log.error.called
        msg = localemod.log.error.call_args[0][0] % (
            localemod.log.error.call_args[0][1],
            localemod.log.error.call_args[0][2],
        )
        assert (
            msg == 'The provided locale "foo" is not found in /usr/share/i18n/SUPPORTED'
        )

    @patch("salt.modules.localemod.log", MagicMock())
    @patch("salt.modules.localemod.__grains__", {"os_family": "Suse"})
    @patch("os.listdir", MagicMock(return_value=[]))
    @patch("salt.utils.locales.join_locale", MagicMock(return_value="en_GB.utf8"))
    def test_gen_locale_suse_invalid(self):
        """
        Tests the location where gen_locale is searching for generated paths.
        :return:
        """
        assert not localemod.gen_locale("de_DE.utf8")
        assert localemod.log.error.called
        msg = localemod.log.error.call_args[0][0] % (
            localemod.log.error.call_args[0][1],
            localemod.log.error.call_args[0][2],
        )
        assert localemod.os.listdir.call_args[0][0] == "/usr/share/locale"
        assert (
            msg == 'The provided locale "en_GB.utf8" is not found in /usr/share/locale'
        )

    @patch("salt.modules.localemod.log", MagicMock())
    @patch("salt.modules.localemod.__grains__", {"os_family": "Suse"})
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run_all": MagicMock(return_value={"retcode": 0})},
    )
    @patch("os.listdir", MagicMock(return_value=["de_DE"]))
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("salt.utils.locales.join_locale", MagicMock(return_value="de_DE.utf8"))
    @patch("salt.utils.path.which", MagicMock(side_effect=[None, "/usr/bin/localedef"]))
    def test_gen_locale_suse_valid(self):
        """
        Tests the location where gen_locale is calling localedef on Suse os-family.
        :return:
        """
        localemod.gen_locale("de_DE.utf8")
        assert localemod.__salt__["cmd.run_all"].call_args[0][0] == [
            "localedef",
            "--force",
            "-i",
            "de_DE",
            "-f",
            "utf8",
            "de_DE.utf8",
            "--quiet",
        ]

    @patch("salt.modules.localemod.log", MagicMock())
    @patch("salt.modules.localemod.__grains__", {"os_family": "Suse"})
    @patch(
        "salt.modules.localemod.__salt__",
        {"cmd.run_all": MagicMock(return_value={"retcode": 0})},
    )
    @patch("os.listdir", MagicMock(return_value=["de_DE"]))
    @patch("os.path.exists", MagicMock(return_value=False))
    @patch("salt.utils.locales.join_locale", MagicMock(return_value="de_DE.utf8"))
    @patch("salt.utils.path.which", MagicMock(return_value=None))
    def test_gen_locale_suse_localedef_error_handling(self):
        """
        Tests the location where gen_locale is handling error while calling not installed localedef on Suse os-family.
        :return:
        """
        with pytest.raises(CommandExecutionError) as exc_info:
            localemod.gen_locale("de_DE.utf8")
        assert (
            'Command "locale-gen" or "localedef" was not found on this system.'
            in str(exc_info.value)
        )

    def test_gen_locale_debian(self):
        """
        Tests the return of successful gen_locale on Debian system
        """
        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(localemod.__grains__, {"os": "Debian"}), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch.dict(
            localemod.__salt__,
            {
                "file.search": MagicMock(return_value=True),
                "file.replace": MagicMock(return_value=True),
                "cmd.run_all": MagicMock(return_value=ret),
            },
        ):
            assert localemod.gen_locale("en_US.UTF-8 UTF-8")

    def test_gen_locale_debian_no_charmap(self):
        """
        Tests the return of successful gen_locale on Debian system without a charmap
        """
        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(localemod.__grains__, {"os": "Debian"}), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch.dict(
            localemod.__salt__,
            {
                "file.search": lambda s, p, flags: not len(p.split()) == 1,
                "file.replace": MagicMock(return_value=True),
                "cmd.run_all": MagicMock(return_value=ret),
            },
        ):
            assert localemod.gen_locale("en_US.UTF-8")

    def test_gen_locale_ubuntu(self):
        """
        Test the return of successful gen_locale on Ubuntu system
        """
        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(
            localemod.__salt__,
            {
                "file.replace": MagicMock(return_value=True),
                "file.touch": MagicMock(return_value=None),
                "file.append": MagicMock(return_value=None),
                "cmd.run_all": MagicMock(return_value=ret),
            },
        ), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch(
            "os.listdir", MagicMock(return_value=["en_US"])
        ), patch.dict(
            localemod.__grains__, {"os": "Ubuntu"}
        ):
            assert localemod.gen_locale("en_US.UTF-8")

    def test_gen_locale_gentoo(self):
        """
        Tests the return of successful gen_locale on Gentoo system
        """
        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(localemod.__grains__, {"os_family": "Gentoo"}), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch("os.listdir", MagicMock(return_value=["en_US.UTF-8"])), patch.dict(
            localemod.__salt__,
            {
                "file.search": MagicMock(return_value=True),
                "file.replace": MagicMock(return_value=True),
                "cmd.run_all": MagicMock(return_value=ret),
            },
        ):
            assert localemod.gen_locale("en_US.UTF-8 UTF-8")

    def test_gen_locale_gentoo_no_charmap(self):
        """
        Tests the return of successful gen_locale on Gentoo system without a charmap
        """

        def file_search(search, pattern, flags):
            """
            mock file.search
            """
            if len(pattern.split()) == 1:
                return False
            else:  # charmap was supplied
                return True

        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(localemod.__grains__, {"os_family": "Gentoo"}), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch("os.listdir", MagicMock(return_value=["en_US.UTF-8"])), patch.dict(
            localemod.__salt__,
            {
                "file.search": file_search,
                "file.replace": MagicMock(return_value=True),
                "cmd.run_all": MagicMock(return_value=ret),
            },
        ):
            assert localemod.gen_locale("en_US.UTF-8")

    def test_gen_locale(self):
        """
        Tests the return of successful gen_locale
        """
        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(
            localemod.__salt__,
            {"cmd.run_all": MagicMock(return_value=ret), "file.replace": MagicMock()},
        ), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch(
            "os.listdir", MagicMock(return_value=["en_US"])
        ):
            assert localemod.gen_locale("en_US.UTF-8")

    def test_gen_locale_verbose(self):
        """
        Tests the return of successful gen_locale
        """
        ret = {"stdout": "saltines", "stderr": "biscuits", "retcode": 0, "pid": 1337}
        with patch.dict(
            localemod.__salt__,
            {"cmd.run_all": MagicMock(return_value=ret), "file.replace": MagicMock()},
        ), patch(
            "salt.utils.path.which", MagicMock(return_value="/some/dir/path")
        ), patch(
            "os.listdir", MagicMock(return_value=["en_US"])
        ):
            assert localemod.gen_locale("en_US.UTF-8", verbose=True) == ret

    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/localctl"))
    def test_parse_localectl(self):
        localectl_out = (
            "   System Locale: LANG=en_US.UTF-8\n"
            "                  LANGUAGE=en_US:en\n"
            "       VC Keymap: n/a"
        )
        mock_cmd = Mock(return_value=localectl_out)
        with patch.dict(localemod.__salt__, {"cmd.run": mock_cmd}):
            ret = localemod._localectl_status()["system_locale"]
            assert {"LANG": "en_US.UTF-8", "LANGUAGE": "en_US:en"} == ret
