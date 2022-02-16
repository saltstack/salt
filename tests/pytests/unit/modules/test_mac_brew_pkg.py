"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""
import textwrap

import pytest
import salt.modules.mac_brew_pkg as mac_brew
import salt.utils.pkg
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def TAPS_STRING():
    return "homebrew/dupes\nhomebrew/science\nhomebrew/x11"


@pytest.fixture
def TAPS_LIST():
    return ["homebrew/dupes", "homebrew/science", "homebrew/x11"]


@pytest.fixture
def HOMEBREW_BIN():
    return "/usr/local/bin/brew"


@pytest.fixture
def configure_loader_modules():
    return {mac_brew: {"__opts__": {"user": MagicMock(return_value="bar")}}}


def custom_call_brew(*cmd, failhard=True):
    result = dict()
    if cmd == ("info", "--json=v2", "--installed"):
        result = {
            "stdout": textwrap.dedent(
                """\
                {
                  "casks": [
                    {
                      "appcast": null,
                      "artifacts": [
                        [
                          "Day-3.0/Day-O.app"
                        ],
                        {
                          "signal": {},
                          "trash": "~/Library/Preferences/com.shauninman.Day-O.plist"
                        }
                      ],
                      "auto_updates": null,
                      "caveats": null,
                      "conflicts_with": null,
                      "container": null,
                      "depends_on": {},
                      "desc": null,
                      "homepage": "https://shauninman.com/archive/2020/04/08/day_o_mac_menu_bar_clock_for_catalina",
                      "installed": "3.0.1",
                      "name": [
                        "Day-O"
                      ],
                      "outdated": false,
                      "sha256": "4963f503c1e47bfa0f8bdbbbe5694d6a7242d298fb44ff68af80d42f1eaebaf9",
                      "token": "day-o",
                      "url": "https://shauninman.com/assets/downloads/Day-3.0.zip",
                      "version": "3.0.1"
                    },
                    {
                      "appcast": null,
                      "artifacts": [
                        [
                          "iTerm.app"
                        ],
                        {
                          "signal": {},
                          "trash": [
                            "~/Library/Application Support/iTerm",
                            "~/Library/Application Support/iTerm2",
                            "~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/com.googlecode.iterm2.sfl*",
                            "~/Library/Caches/com.googlecode.iterm2",
                            "~/Library/Preferences/com.googlecode.iterm2.plist",
                            "~/Library/Saved Application State/com.googlecode.iterm2.savedState"
                          ]
                        }
                      ],
                      "auto_updates": true,
                      "caveats": null,
                      "conflicts_with": {
                        "cask": [
                          "iterm2-beta"
                        ]
                      },
                      "container": null,
                      "depends_on": {
                        "macos": {
                          ">=": [
                            "10.12"
                          ]
                        }
                      },
                      "desc": "Terminal emulator as alternative to Apple's Terminal app",
                      "homepage": "https://www.iterm2.com/",
                      "installed": "3.4.3",
                      "name": [
                        "iTerm2"
                      ],
                      "outdated": false,
                      "sha256": "9ed73844838bddf797eadf37e5f7da3771308c3f74d38cd422c18eebaaa8f6b9",
                      "token": "iterm2",
                      "url": "https://iterm2.com/downloads/stable/iTerm2-3_4_3.zip",
                      "version": "3.4.3"
                    }
                  ],
                  "formulae": [
                    {
                      "aliases": [],
                      "bottle": {
                        "stable": {
                          "cellar": ":any",
                          "files": {
                            "arm64_big_sur": {
                              "sha256": "674b3ae41c399f1e8e44c271b0e6909babff9fcd2e04a2127d25e2407ea4dd33",
                              "url": "https://homebrew.bintray.com/bottles/jq-1.6.arm64_big_sur.bottle.1.tar.gz"
                            },
                            "big_sur": {
                              "sha256": "bf0f8577632af7b878b6425476f5b1ab9c3bf66d65affb0c455048a173a0b6bf",
                              "url": "https://homebrew.bintray.com/bottles/jq-1.6.big_sur.bottle.1.tar.gz"
                            },
                            "catalina": {
                              "sha256": "820a3c85fcbb63088b160c7edf125d7e55fc2c5c1d51569304499c9cc4b89ce8",
                              "url": "https://homebrew.bintray.com/bottles/jq-1.6.catalina.bottle.1.tar.gz"
                            },
                            "high_sierra": {
                              "sha256": "dffcffa4ea13e8f0f2b45c5121e529077e135ae9a47254c32182231662ee9b72",
                              "url": "https://homebrew.bintray.com/bottles/jq-1.6.high_sierra.bottle.1.tar.gz"
                            },
                            "mojave": {
                              "sha256": "71f0e76c5b22e5088426c971d5e795fe67abee7af6c2c4ae0cf4c0eb98ed21ff",
                              "url": "https://homebrew.bintray.com/bottles/jq-1.6.mojave.bottle.1.tar.gz"
                            },
                            "sierra": {
                              "sha256": "bb4d19dc026c2d72c53eed78eaa0ab982e9fcad2cd2acc6d13e7a12ff658e877",
                              "url": "https://homebrew.bintray.com/bottles/jq-1.6.sierra.bottle.1.tar.gz"
                            }
                          },
                          "prefix": "/usr/local",
                          "rebuild": 1,
                          "root_url": "https://homebrew.bintray.com/bottles"
                        }
                      },
                      "bottle_disabled": false,
                      "build_dependencies": [],
                      "caveats": null,
                      "conflicts_with": [],
                      "dependencies": [
                        "oniguruma"
                      ],
                      "deprecated": false,
                      "deprecation_date": null,
                      "deprecation_reason": null,
                      "desc": "Lightweight and flexible command-line JSON processor",
                      "disable_date": null,
                      "disable_reason": null,
                      "disabled": false,
                      "full_name": "jq",
                      "homepage": "https://stedolan.github.io/jq/",
                      "installed": [
                        {
                          "built_as_bottle": true,
                          "installed_as_dependency": false,
                          "installed_on_request": true,
                          "poured_from_bottle": true,
                          "runtime_dependencies": [
                            {
                              "full_name": "oniguruma",
                              "version": "6.9.6"
                            }
                          ],
                          "used_options": [],
                          "version": "1.6"
                        }
                      ],
                      "keg_only": false,
                      "license": "MIT",
                      "linked_keg": "1.6",
                      "name": "jq",
                      "oldname": null,
                      "optional_dependencies": [],
                      "options": [],
                      "outdated": false,
                      "pinned": false,
                      "recommended_dependencies": [],
                      "requirements": [],
                      "revision": 0,
                      "urls": {
                        "stable": {
                          "revision": null,
                          "tag": null,
                          "url": "https://github.com/stedolan/jq/releases/download/jq-1.6/jq-1.6.tar.gz"
                        }
                      },
                      "uses_from_macos": [],
                      "version_scheme": 0,
                      "versioned_formulae": [],
                      "versions": {
                        "bottle": true,
                        "head": "HEAD",
                        "stable": "1.6"
                      }
                    },
                    {
                      "aliases": [],
                      "bottle": {
                        "stable": {
                          "cellar": ":any",
                          "files": {
                            "arm64_big_sur": {
                              "sha256": "c84206005787304416ed81094bd3a0cdd2ae8eb62649db5a3a44fa14b276d09f",
                              "url": "https://homebrew.bintray.com/bottles/xz-5.2.5.arm64_big_sur.bottle.tar.gz"
                            },
                            "big_sur": {
                              "sha256": "4fbd4a9e3eb49c27e83bd125b0e76d386c0e12ae1139d4dc9e31841fb8880a35",
                              "url": "https://homebrew.bintray.com/bottles/xz-5.2.5.big_sur.bottle.tar.gz"
                            },
                            "catalina": {
                              "sha256": "2dcc8e0121c934d1e34ffdb37fcd70f0f7b5c2f4755f2f7cbcf360e9e54cb43b",
                              "url": "https://homebrew.bintray.com/bottles/xz-5.2.5.catalina.bottle.tar.gz"
                            },
                            "high_sierra": {
                              "sha256": "1491b2b20c40c3cb0b990f520768d7e876e4ab4a7dc1da9994d0150da34ba5c6",
                              "url": "https://homebrew.bintray.com/bottles/xz-5.2.5.high_sierra.bottle.tar.gz"
                            },
                            "mojave": {
                              "sha256": "44483961b5d2b535b0ece1936c9d40b4bc7d9c7281646cca0fb476291ab9d4dc",
                              "url": "https://homebrew.bintray.com/bottles/xz-5.2.5.mojave.bottle.tar.gz"
                            }
                          },
                          "prefix": "/usr/local",
                          "rebuild": 0,
                          "root_url": "https://homebrew.bintray.com/bottles"
                        }
                      },
                      "bottle_disabled": false,
                      "build_dependencies": [],
                      "caveats": null,
                      "conflicts_with": [],
                      "dependencies": [],
                      "deprecated": false,
                      "deprecation_date": null,
                      "deprecation_reason": null,
                      "desc": "General-purpose data compression with high compression ratio",
                      "disable_date": null,
                      "disable_reason": null,
                      "disabled": false,
                      "full_name": "xz",
                      "homepage": "https://tukaani.org/xz/",
                      "installed": [
                        {
                          "built_as_bottle": true,
                          "installed_as_dependency": true,
                          "installed_on_request": false,
                          "poured_from_bottle": true,
                          "runtime_dependencies": [],
                          "used_options": [],
                          "version": "5.2.5"
                        }
                      ],
                      "keg_only": false,
                      "license": "GPL-2.0",
                      "linked_keg": "5.2.5",
                      "name": "xz",
                      "oldname": null,
                      "optional_dependencies": [],
                      "options": [],
                      "outdated": false,
                      "pinned": false,
                      "recommended_dependencies": [],
                      "requirements": [],
                      "revision": 0,
                      "urls": {
                        "stable": {
                          "revision": null,
                          "tag": null,
                          "url": "https://downloads.sourceforge.net/project/lzmautils/xz-5.2.5.tar.gz"
                        }
                      },
                      "uses_from_macos": [],
                      "version_scheme": 0,
                      "versioned_formulae": [],
                      "versions": {
                        "bottle": true,
                        "head": null,
                        "stable": "5.2.5"
                      }
                    }
                  ]
                }
                """
            ),
            "stderr": "",
            "retcode": 0,
        }
    elif cmd == ("list", "--cask", "--versions"):
        result = {
            "stdout": "day-o 3.0.1\niterm2 3.4.3",
            "stderr": "",
            "retcode": 0,
        }
    elif cmd == ("info", "--cask", "iterm2"):
        result = {
            "stdout": textwrap.dedent(
                """\
                iterm2: 3.4.3 (auto_updates)
                https://www.iterm2.com/
                /usr/local/Caskroom/iterm2/3.4.3 (119B)
                From: https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/iterm2.rb
                ==> Name
                iTerm2
                ==> Description
                Terminal emulator as alternative to Apple's Terminal app
                ==> Artifacts
                iTerm.app (App)
                ==> Analytics
                install: 18,869 (30 days), 61,676 (90 days), 233,825 (365 days)
                """
            ),
            "stderr": "",
            "retcode": 0,
        }
    elif cmd == ("info", "--cask", "day-o"):
        result = {
            "stdout": textwrap.dedent(
                """\
                day-o: 3.0.1
                https://shauninman.com/archive/2020/04/08/day_o_mac_menu_bar_clock_for_catalina
                /usr/local/Caskroom/day-o/3.0.1 (7.3KB)
                From: https://github.com/Homebrew/homebrew-cask/blob/HEAD/Casks/day-o.rb
                ==> Name
                Day-O
                ==> Description
                None
                ==> Artifacts
                Day-3.0/Day-O.app (App)
                ==> Analytics
                install: 30 (30 days), 96 (90 days), 525 (365 days)
                """
            ),
            "stderr": "",
            "retcode": "",
        }

    return result


def custom_add_pkg(ret, name, newest_version):
    ret[name] = newest_version
    return ret


# '_list_taps' function tests: 1


def test_list_taps(TAPS_STRING, TAPS_LIST):
    """
    Tests the return of the list of taps
    """
    mock_taps = MagicMock(return_value={"stdout": TAPS_STRING, "retcode": 0})
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch.dict(
            mac_brew.__salt__,
            {"file.get_user": mock_user, "cmd.run_all": mock_taps, "cmd.run": mock_cmd},
        ):
            assert mac_brew._list_taps() == TAPS_LIST


# '_tap' function tests: 3


def test_tap_installed(TAPS_LIST):
    """
    Tests if tap argument is already installed or not
    """
    with patch(
        "salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value=TAPS_LIST)
    ):
        assert mac_brew._tap("homebrew/science")


def test_tap_failure():
    """
    Tests if the tap installation failed
    """
    mock_failure = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 1})
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch.dict(
            mac_brew.__salt__,
            {
                "cmd.run_all": mock_failure,
                "file.get_user": mock_user,
                "cmd.run": mock_cmd,
            },
        ), patch("salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value={})):
            assert not mac_brew._tap("homebrew/test")


def test_tap(TAPS_LIST):
    """
    Tests adding unofficial GitHub repos to the list of brew taps
    """
    mock_failure = MagicMock(return_value={"retcode": 0})
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch.dict(
            mac_brew.__salt__,
            {
                "cmd.run_all": mock_failure,
                "file.get_user": mock_user,
                "cmd.run": mock_cmd,
            },
        ), patch(
            "salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value=TAPS_LIST)
        ):
            assert mac_brew._tap("homebrew/test")


# '_homebrew_bin' function tests: 1


def test_homebrew_bin():
    """
    Tests the path to the homebrew binary
    """
    mock_path = MagicMock(return_value="/usr/local")
    with patch.dict(mac_brew.__salt__, {"cmd.run": mock_path}):
        assert mac_brew._homebrew_bin() == "/usr/local/bin/brew"


# 'list_pkgs' function tests: 2
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_list_pkgs_removed():
    """
    Tests removed implementation
    """
    assert mac_brew.list_pkgs(removed=True) == {}


def test_list_pkgs_versions_true():
    """
    Tests if pkg.list_pkgs is already in context and is a list
    """
    mock_context = {"foo": ["bar"]}
    with patch.dict(mac_brew.__context__, {"pkg.list_pkgs": mock_context}):
        assert mac_brew.list_pkgs(versions_as_list=True) == mock_context


def test_list_pkgs_homebrew_cask_pakages():
    """
    Tests if pkg.list_pkgs list properly homebrew cask packages
    """
    expected_pkgs = {
        "homebrew/cask/day-o": "3.0.1",
        "homebrew/cask/iterm2": "3.4.3",
        "jq": "1.6",
        "xz": "5.2.5",
    }

    with patch("salt.modules.mac_brew_pkg._call_brew", custom_call_brew), patch.dict(
        mac_brew.__salt__,
        {
            "pkg_resource.add_pkg": custom_add_pkg,
            "pkg_resource.sort_pkglist": MagicMock(),
        },
    ):
        assert mac_brew.list_pkgs(versions_as_list=True) == expected_pkgs


def test_list_pkgs_no_context():
    """
    Tests removed implementation
    """

    expected_pkgs = {
        "zsh": "5.7.1",
        "homebrew/cask/macvim": "8.1.151",
        "homebrew/cask-fonts/font-firacode-nerd-font": "2.0.0",
    }

    with patch("salt.modules.mac_brew_pkg._call_brew", custom_call_brew), patch.dict(
        mac_brew.__salt__,
        {
            "pkg_resource.add_pkg": custom_add_pkg,
            "pkg_resource.sort_pkglist": MagicMock(),
        },
    ), patch.object(mac_brew, "_list_pkgs_from_context") as list_pkgs_context_mock:
        pkgs = mac_brew.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = mac_brew.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


# 'version' function tests: 1


def test_version():
    """
    Tests version name returned
    """
    mock_version = MagicMock(return_value="0.1.5")
    with patch.dict(mac_brew.__salt__, {"pkg_resource.version": mock_version}):
        assert mac_brew.version("foo") == "0.1.5"


# 'latest_version' function tests: 0
# It has not been fully implemented

# 'remove' function tests: 1
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_remove():
    """
    Tests if package to be removed exists
    """
    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch(
        "salt.modules.mac_brew_pkg.list_pkgs", return_value={"test": "0.1.5"}
    ), patch.dict(mac_brew.__salt__, {"pkg_resource.parse_targets": mock_params}):
        assert mac_brew.remove("foo") == {}


# 'refresh_db' function tests: 2


def test_refresh_db_failure(HOMEBREW_BIN):
    """
    Tests an update of homebrew package repository failure
    """
    mock_user = MagicMock(return_value="foo")
    mock_failure = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 1})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch.dict(
            mac_brew.__salt__, {"file.get_user": mock_user, "cmd.run_all": mock_failure}
        ), patch(
            "salt.modules.mac_brew_pkg._homebrew_bin",
            MagicMock(return_value=HOMEBREW_BIN),
        ):
            with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
                pytest.raises(CommandExecutionError, mac_brew.refresh_db)


def test_refresh_db(HOMEBREW_BIN):
    """
    Tests a successful update of homebrew package repository
    """
    mock_user = MagicMock(return_value="foo")
    mock_success = MagicMock(return_value={"retcode": 0})
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch.dict(
            mac_brew.__salt__, {"file.get_user": mock_user, "cmd.run_all": mock_success}
        ), patch(
            "salt.modules.mac_brew_pkg._homebrew_bin",
            MagicMock(return_value=HOMEBREW_BIN),
        ):
            with patch.object(salt.utils.pkg, "clear_rtag", Mock()):
                assert mac_brew.refresh_db()


# 'install' function tests: 1
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_install():
    """
    Tests if package to be installed exists
    """
    mock_params = MagicMock(return_value=[None, None])
    with patch.dict(mac_brew.__salt__, {"pkg_resource.parse_targets": mock_params}):
        assert mac_brew.install("name=foo") == {}


# "hold" function tests: 2
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_hold():
    """
    Tests holding if package is installed
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}
    )
    _expected = {
        "foo": {
            "changes": {"new": "hold", "old": "install"},
            "comment": "Package foo is now being held.",
            "name": "foo",
            "result": True,
        }
    }

    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch(
            "salt.modules.mac_brew_pkg.list_pkgs", return_value={"foo": "0.1.5"}
        ), patch.dict(
            mac_brew.__salt__,
            {
                "file.get_user": mock_user,
                "pkg_resource.parse_targets": mock_params,
                "cmd.run_all": mock_cmd_all,
                "cmd.run": mock_cmd,
            },
        ):
            assert mac_brew.hold("foo") == _expected


def test_hold_not_installed():
    """
    Tests holding if package is not installed
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}
    )
    _expected = {
        "foo": {
            "changes": {},
            "comment": "Package foo does not have a state.",
            "name": "foo",
            "result": False,
        }
    }

    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch("salt.modules.mac_brew_pkg.list_pkgs", return_value={}), patch.dict(
            mac_brew.__salt__,
            {
                "file.get_user": mock_user,
                "pkg_resource.parse_targets": mock_params,
                "cmd.run_all": mock_cmd_all,
                "cmd.run": mock_cmd,
            },
        ):
            assert mac_brew.hold("foo") == _expected


def test_hold_pinned():
    """
    Tests holding if package is already pinned
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}
    )
    _expected = {
        "foo": {
            "changes": {},
            "comment": "Package foo is already set to be held.",
            "name": "foo",
            "result": True,
        }
    }

    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch(
        "salt.modules.mac_brew_pkg.list_pkgs", return_value={"foo": "0.1.5"}
    ), patch(
        "salt.modules.mac_brew_pkg._list_pinned", return_value=["foo"]
    ), patch.dict(
        mac_brew.__salt__,
        {
            "file.get_user": mock_user,
            "pkg_resource.parse_targets": mock_params,
            "cmd.run_all": mock_cmd_all,
            "cmd.run": mock_cmd,
        },
    ):
        assert mac_brew.hold("foo") == _expected


# "unhold" function tests: 2
# Only tested a few basics
# Full functionality should be tested in integration phase
def test_unhold():
    """
    Tests unholding if package is installed
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}
    )
    _expected = {
        "foo": {
            "changes": {"new": "install", "old": "hold"},
            "comment": "Package foo is no longer being held.",
            "name": "foo",
            "result": True,
        }
    }

    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch("salt.utils.path.which", MagicMock(return_value="/usr/local/bin/brew")):
        with patch(
            "salt.modules.mac_brew_pkg.list_pkgs", return_value={"foo": "0.1.5"}
        ), patch(
            "salt.modules.mac_brew_pkg._list_pinned", return_value=["foo"]
        ), patch.dict(
            mac_brew.__salt__,
            {
                "file.get_user": mock_user,
                "pkg_resource.parse_targets": mock_params,
                "cmd.run_all": mock_cmd_all,
                "cmd.run": mock_cmd,
            },
        ):
            assert mac_brew.unhold("foo") == _expected


def test_unhold_not_installed():
    """
    Tests unholding if package is not installed
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}
    )
    _expected = {
        "foo": {
            "changes": {},
            "comment": "Package foo does not have a state.",
            "name": "foo",
            "result": False,
        }
    }

    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch("salt.modules.mac_brew_pkg.list_pkgs", return_value={}), patch(
        "salt.modules.mac_brew_pkg._list_pinned", return_value=["foo"]
    ), patch.dict(
        mac_brew.__salt__,
        {
            "file.get_user": mock_user,
            "pkg_resource.parse_targets": mock_params,
            "cmd.run_all": mock_cmd_all,
            "cmd.run": mock_cmd,
        },
    ):
        assert mac_brew.unhold("foo") == _expected


def test_unhold_not_pinned():
    """
    Tests unholding if package is not installed
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stderr": "", "stdout": ""}
    )
    _expected = {
        "foo": {
            "changes": {},
            "comment": "Package foo is already set not to be held.",
            "name": "foo",
            "result": True,
        }
    }

    mock_params = MagicMock(return_value=({"foo": None}, "repository"))
    with patch(
        "salt.modules.mac_brew_pkg.list_pkgs", return_value={"foo": "0.1.5"}
    ), patch("salt.modules.mac_brew_pkg._list_pinned", return_value=[]), patch.dict(
        mac_brew.__salt__,
        {
            "file.get_user": mock_user,
            "pkg_resource.parse_targets": mock_params,
            "cmd.run_all": mock_cmd_all,
            "cmd.run": mock_cmd,
        },
    ):
        assert mac_brew.unhold("foo") == _expected
