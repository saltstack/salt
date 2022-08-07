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
                """
                {
                    "casks": [
                        {
                        "token": "saltstack",
                        "full_token": "smillerdev/saltstack/saltstack",
                        "tap": "smillerdev/saltstack",
                        "name": [
                            "saltstack"
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
                      "full_token": "day-o",
                      "tap": "homebrew/cask",
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
                      "full_token": "custom/tap/iterm2",
                      "tap": "custom/tap",
                      "url": "https://iterm2.com/downloads/stable/iTerm2-3_4_3.zip",
                      "version": "3.4.3"
                    },
                    {
                      "token": "discord",
                      "full_token": "discord",
                      "tap": null,
                      "name": [
                        "Discord"
                      ],
                      "desc": "Voice and text chat software",
                      "homepage": "https://discord.com/",
                      "url": "https://dl.discordapp.net/apps/osx/0.0.268/Discord.dmg",
                      "appcast": null,
                      "version": "0.0.268",
                      "versions": {
                      },
                      "installed": "0.0.266",
                      "outdated": false,
                      "sha256": "dfe12315b717ed06ac24d3eaacb700618e96cbb449ed63d2afadcdb70ad09c55",
                      "artifacts": [
                        {
                          "app": [
                            "Discord.app"
                          ]
                        },
                        {
                          "zap": [
                            {
                              "trash": [
                                "~/Library/Application Support/discord",
                                "~/Library/Caches/com.hnc.Discord",
                                "~/Library/Caches/com.hnc.Discord.ShipIt",
                                "~/Library/Cookies/com.hnc.Discord.binarycookies",
                                "~/Library/Preferences/com.hnc.Discord.helper.plist",
                                "~/Library/Preferences/com.hnc.Discord.plist",
                                "~/Library/Saved Application State/com.hnc.Discord.savedState"
                              ]
                            }
                          ]
                        }
                      ],
                      "caveats": null,
                      "depends_on": {
                      },
                      "conflicts_with": null,
                      "container": null,
                      "auto_updates": true
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
                            "pkgutil": "com.saltstack.salt",
                            "signal": {}
                            },
                            "salt-3004.2-py3-x86_64.pkg (Pkg)"
                        ],
                        "caveats": null,
                        "depends_on": {},
                        "conflicts_with": {
                            "cask": [
                            "saltstack-3001",
                            "saltstack-3000"
                            ]
                        },
                        "container": null,
                        "auto_updates": null
                        },
                        {
                        "token": "visual-studio-code",
                        "full_token": "visual-studio-code",
                        "tap": "homebrew/cask",
                        "name": [
                            "Microsoft Visual Studio Code",
                            "VS Code"
                        ],
                        "desc": "Open-source code editor",
                        "homepage": "https://code.visualstudio.com/",
                        "url": "https://update.code.visualstudio.com/1.70.0/darwin/stable",
                        "appcast": null,
                        "version": "1.70.0",
                        "versions": {},
                        "installed": "1.67.1",
                        "outdated": false,
                        "sha256": "ed6b3f9368ca3dd792fc18e74e3d4a4070cf36df4efd1d81db8c96df8c647dde",
                        "artifacts": [
                            [
                            "Visual Studio Code.app"
                            ],
                            [
                            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
                            ],
                            {
                            "trash": [
                                "~/.vscode",
                                "~/Library/Application Support/Code",
                                "~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.ApplicationRecentDocuments/com.microsoft.vscode.sfl*",
                                "~/Library/Caches/com.microsoft.VSCode.ShipIt",
                                "~/Library/Caches/com.microsoft.VSCode",
                                "~/Library/Preferences/ByHost/com.microsoft.VSCode.ShipIt.*.plist",
                                "~/Library/Preferences/com.microsoft.VSCode.helper.plist",
                                "~/Library/Preferences/com.microsoft.VSCode.plist",
                                "~/Library/Saved Application State/com.microsoft.VSCode.savedState"
                            ],
                            "signal": {}
                            }
                        ],
                        "caveats": null,
                        "depends_on": {},
                        "conflicts_with": null,
                        "container": null,
                        "auto_updates": true
                        }
                    ],
                    "formulae": [
                        {
                        "name": "salt",
                        "full_name": "salt",
                        "tap": "homebrew/core",
                        "oldname": "saltstack",
                        "aliases": [
                            "saltstack"
                        ],
                        "versioned_formulae": [],
                        "desc": "Dynamic infrastructure communication bus",
                        "license": "Apache-2.0",
                        "homepage": "https://saltproject.io/",
                        "versions": {
                            "stable": "3004.2",
                            "head": "HEAD",
                            "bottle": true
                        },
                        "urls": {
                            "stable": {
                            "url": "https://files.pythonhosted.org/packages/78/47/0acfc5d43fcf4b01c3f650ce884525dd2330b8827364e4509819f7e925d3/salt-3004.2.tar.gz",
                            "tag": null,
                            "revision": null
                            }
                        },
                        "revision": 1,
                        "version_scheme": 0,
                        "bottle": {
                            "stable": {
                            "rebuild": 0,
                            "root_url": "https://ghcr.io/v2/homebrew/core",
                            "files": {
                                "arm64_monterey": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/salt/blobs/sha256:e62a03420f4859b5d7370b7b4800b73b7b198f97a6ebae2a04d9e77e340a32dd",
                                "sha256": "e62a03420f4859b5d7370b7b4800b73b7b198f97a6ebae2a04d9e77e340a32dd"
                                },
                                "arm64_big_sur": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/salt/blobs/sha256:76308937ea092c4dfc0c661c228cca5c1114d2413ef50be71257d6dc4ee213ac",
                                "sha256": "76308937ea092c4dfc0c661c228cca5c1114d2413ef50be71257d6dc4ee213ac"
                                },
                                "monterey": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/salt/blobs/sha256:cd8258f57d8bd3b0d47ff3aae83ad0180784fcf312a647b33175e51b3a2de34a",
                                "sha256": "cd8258f57d8bd3b0d47ff3aae83ad0180784fcf312a647b33175e51b3a2de34a"
                                },
                                "big_sur": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/salt/blobs/sha256:1aee80b0ed6be7c2cda3fecba7ca5e7aea559945d96bafeb5fabea208c5b7a37",
                                "sha256": "1aee80b0ed6be7c2cda3fecba7ca5e7aea559945d96bafeb5fabea208c5b7a37"
                                },
                                "catalina": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/salt/blobs/sha256:9f81d609b9fbac2571099386ffaf3af3608b96fc03a411b04398051138513a76",
                                "sha256": "9f81d609b9fbac2571099386ffaf3af3608b96fc03a411b04398051138513a76"
                                },
                                "x86_64_linux": {
                                "cellar": ":any_skip_relocation",
                                "url": "https://ghcr.io/v2/homebrew/core/salt/blobs/sha256:24c490917bab507a7bcf60a0b53669182eb75369416da07b71b3eb983767c2de",
                                "sha256": "24c490917bab507a7bcf60a0b53669182eb75369416da07b71b3eb983767c2de"
                                }
                            }
                            }
                        },
                        "keg_only": false,
                        "keg_only_reason": null,
                        "options": [],
                        "build_dependencies": [
                            "swig"
                        ],
                        "dependencies": [
                            "libgit2",
                            "libyaml",
                            "openssl@1.1",
                            "python@3.10",
                            "six",
                            "zeromq"
                        ],
                        "recommended_dependencies": [],
                        "optional_dependencies": [],
                        "uses_from_macos": [
                            "libffi"
                        ],
                        "requirements": [],
                        "conflicts_with": [],
                        "caveats": "Sample configuration files have been placed in $(brew --prefix)/etc/saltstack.\\nSaltstack will not use these by default.\\n\\nHomebrew's installation does not include PyObjC.\\n",
                        "installed": [
                            {
                                "version": "3004.2",
                                "used_options": [],
                                "built_as_bottle": true,
                                "poured_from_bottle": true,
                                "runtime_dependencies": [],
                                "installed_as_dependency": false,
                                "installed_on_request": true
                            }
                        ],
                        "linked_keg": null,
                        "pinned": false,
                        "outdated": false,
                        "deprecated": false,
                        "deprecation_date": null,
                        "deprecation_reason": null,
                        "disabled": false,
                        "disable_date": null,
                        "disable_reason": null
                        },
                        {
                        "name": "jq",
                        "full_name": "jq",
                        "tap": "homebrew/core",
                        "oldname": null,
                        "aliases": [],
                        "versioned_formulae": [],
                        "desc": "Lightweight and flexible command-line JSON processor",
                        "license": "MIT",
                        "homepage": "https://stedolan.github.io/jq/",
                        "versions": {
                            "stable": "1.6",
                            "head": "HEAD",
                            "bottle": true
                        },
                        "urls": {
                            "stable": {
                            "url": "https://github.com/stedolan/jq/releases/download/jq-1.6/jq-1.6.tar.gz",
                            "tag": null,
                            "revision": null
                            }
                        },
                        "revision": 0,
                        "version_scheme": 0,
                        "bottle": {
                            "stable": {
                            "rebuild": 1,
                            "root_url": "https://ghcr.io/v2/homebrew/core",
                            "files": {
                                "arm64_monterey": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:f70e1ae8df182b242ca004492cc0a664e2a8195e2e46f30546fe78e265d5eb87",
                                "sha256": "f70e1ae8df182b242ca004492cc0a664e2a8195e2e46f30546fe78e265d5eb87"
                                },
                                "arm64_big_sur": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:674b3ae41c399f1e8e44c271b0e6909babff9fcd2e04a2127d25e2407ea4dd33",
                                "sha256": "674b3ae41c399f1e8e44c271b0e6909babff9fcd2e04a2127d25e2407ea4dd33"
                                },
                                "monterey": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:7fee6ea327062b37d34ef5346a84810a1752cc7146fff1223fab76c9b45686e0",
                                "sha256": "7fee6ea327062b37d34ef5346a84810a1752cc7146fff1223fab76c9b45686e0"
                                },
                                "big_sur": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:bf0f8577632af7b878b6425476f5b1ab9c3bf66d65affb0c455048a173a0b6bf",
                                "sha256": "bf0f8577632af7b878b6425476f5b1ab9c3bf66d65affb0c455048a173a0b6bf"
                                },
                                "catalina": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:820a3c85fcbb63088b160c7edf125d7e55fc2c5c1d51569304499c9cc4b89ce8",
                                "sha256": "820a3c85fcbb63088b160c7edf125d7e55fc2c5c1d51569304499c9cc4b89ce8"
                                },
                                "mojave": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:71f0e76c5b22e5088426c971d5e795fe67abee7af6c2c4ae0cf4c0eb98ed21ff",
                                "sha256": "71f0e76c5b22e5088426c971d5e795fe67abee7af6c2c4ae0cf4c0eb98ed21ff"
                                },
                                "high_sierra": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:dffcffa4ea13e8f0f2b45c5121e529077e135ae9a47254c32182231662ee9b72",
                                "sha256": "dffcffa4ea13e8f0f2b45c5121e529077e135ae9a47254c32182231662ee9b72"
                                },
                                "sierra": {
                                "cellar": ":any",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:bb4d19dc026c2d72c53eed78eaa0ab982e9fcad2cd2acc6d13e7a12ff658e877",
                                "sha256": "bb4d19dc026c2d72c53eed78eaa0ab982e9fcad2cd2acc6d13e7a12ff658e877"
                                },
                                "x86_64_linux": {
                                "cellar": ":any_skip_relocation",
                                "url": "https://ghcr.io/v2/homebrew/core/jq/blobs/sha256:2beea2c2c372ccf1081e9a5233fc3020470803254284aeecc071249d76b62338",
                                "sha256": "2beea2c2c372ccf1081e9a5233fc3020470803254284aeecc071249d76b62338"
                                }
                            }
                            }
                        },
                        "keg_only": false,
                        "keg_only_reason": null,
                        "options": [],
                        "build_dependencies": [],
                        "dependencies": [
                            "oniguruma"
                        ],
                        "recommended_dependencies": [],
                        "optional_dependencies": [],
                        "uses_from_macos": [],
                        "requirements": [],
                        "conflicts_with": [],
                        "caveats": null,
                        "installed": [
                            {
                                "version": "1.6",
                                "used_options": [],
                                "built_as_bottle": true,
                                "poured_from_bottle": true,
                                "runtime_dependencies": [
                                    {
                                    "full_name": "oniguruma",
                                    "version": "6.9.2"
                                    }
                                ],
                                "installed_as_dependency": false,
                                "installed_on_request": true
                            }
                        ],
                        "linked_keg": "1.6",
                        "pinned": false,
                        "outdated": false,
                        "deprecated": false,
                        "deprecation_date": null,
                        "deprecation_reason": null,
                        "disabled": false,
                        "disable_date": null,
                        "disable_reason": null
                        }
                    ]
                }
                """
            ),
            "stderr": "",
            "retcode": 0,
        }
    return result


def custom_add_pkg(ret, name, newest_version):
    ret[name] = newest_version
    return ret


# '_list_taps' function tests: 1


def test_list_taps(TAPS_STRING, TAPS_LIST, HOMEBREW_BIN):
    """
    Tests the return of the list of taps
    """
    mock_taps = MagicMock(return_value={"stdout": TAPS_STRING, "retcode": 0})
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
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


def test_tap_failure(HOMEBREW_BIN):
    """
    Tests if the tap installation failed
    """
    mock_failure = MagicMock(return_value={"stdout": "", "stderr": "", "retcode": 1})
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
        with patch.dict(
            mac_brew.__salt__,
            {
                "cmd.run_all": mock_failure,
                "file.get_user": mock_user,
                "cmd.run": mock_cmd,
            },
        ), patch("salt.modules.mac_brew_pkg._list_taps", MagicMock(return_value={})):
            assert not mac_brew._tap("homebrew/test")


def test_tap(TAPS_LIST, HOMEBREW_BIN):
    """
    Tests adding unofficial GitHub repos to the list of brew taps
    """
    mock_failure = MagicMock(return_value={"retcode": 0})
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
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


def test_homebrew_bin(HOMEBREW_BIN):
    """
    Tests the path to the homebrew binary
    """
    mock_path = MagicMock(return_value="/usr/local")
    with patch.dict(mac_brew.__salt__, {"cmd.run": mock_path}):
        assert mac_brew._homebrew_bin() == HOMEBREW_BIN


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
        "day-o": "3.0.1",
        "homebrew/cask/discord": "0.0.266",
        "discord": "0.0.266",
        "custom/tap/iterm2": "3.4.3",
        "iterm2": "3.4.3",
        "jq": "1.6",
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

    with patch("salt.modules.mac_brew_pkg._call_brew", custom_call_brew), patch.dict(
        mac_brew.__salt__,
        {
            "pkg_resource.add_pkg": custom_add_pkg,
            "pkg_resource.sort_pkglist": MagicMock(),
        },
    ), patch.object(mac_brew, "_list_pkgs_from_context") as list_pkgs_context_mock:
        mac_brew.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        mac_brew.list_pkgs(versions_as_list=True, use_context=False)
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
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
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


# 'list_upgrades' function tests: 1
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_list_upgrades():
    """
    Tests if pkg.list_upgrades list all items
    """
    expected_pkgs = {
        "visual-studio-code": "1.70.0",
        "firefox": "103.0.1",
        "salt": "3004.2",
    }

    with patch("salt.modules.mac_brew_pkg._call_brew", custom_call_brew), patch.dict(
        mac_brew.__salt__,
        {
            "pkg_resource.add_pkg": custom_add_pkg,
            "pkg_resource.sort_pkglist": MagicMock(),
        },
    ):
        assert mac_brew.list_upgrades(refresh=False) == expected_pkgs


# 'upgrade_available' function tests: 1
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_upgrade_available():
    """
    Tests if pkg.upgrade_available returns the correct info
    """
    with patch("salt.modules.mac_brew_pkg._call_brew", custom_call_brew), patch.dict(
        mac_brew.__salt__,
        {
            "pkg_resource.add_pkg": custom_add_pkg,
            "pkg_resource.sort_pkglist": MagicMock(),
        },
    ):
        assert mac_brew.upgrade_available("salt", refresh=False)


# "hold" function tests: 2
# Only tested a few basics
# Full functionality should be tested in integration phase


def test_hold(HOMEBREW_BIN):
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
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
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


def test_hold_not_installed(HOMEBREW_BIN):
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
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
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
def test_unhold(HOMEBREW_BIN):
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
    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
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


def test_info_installed(HOMEBREW_BIN):
    """
    Tests info_installed method
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={
            "pid": 12345,
            "retcode": 0,
            "stderr": "",
            "stdout": textwrap.dedent(
                """\
                {
                  "formulae": [
                    {
                      "name": "salt",
                      "full_name": "cdalvaro/tap/salt",
                      "tap": "cdalvaro/tap",
                      "aliases": []
                    },
                    {
                      "name": "vim",
                      "full_name": "vim",
                      "tap": "homebrew/core",
                      "aliases": []
                    }
                  ],
                  "casks": [
                    {
                      "token": "visual-studio-code",
                      "full_token": "visual-studio-code",
                      "tap": null,
                      "name": [
                        "MicrosoftVisualStudioCode",
                        "VSCode"
                      ]
                    }
                  ]
                }
             """
            ),
        }
    )
    _expected = {
        "cdalvaro/tap/salt": {
            "name": "salt",
            "full_name": "cdalvaro/tap/salt",
            "tap": "cdalvaro/tap",
            "aliases": [],
        },
        "vim": {
            "name": "vim",
            "full_name": "vim",
            "tap": "homebrew/core",
            "aliases": [],
        },
        "visual-studio-code": {
            "token": "visual-studio-code",
            "full_token": "visual-studio-code",
            "tap": None,
            "name": ["MicrosoftVisualStudioCode", "VSCode"],
        },
    }

    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
        with patch("salt.modules.mac_brew_pkg.list_pkgs", return_value={}), patch(
            "salt.modules.mac_brew_pkg._list_pinned", return_value=["foo"]
        ), patch.dict(
            mac_brew.__salt__,
            {
                "file.get_user": mock_user,
                "cmd.run_all": mock_cmd_all,
                "cmd.run": mock_cmd,
            },
        ):
            assert (
                mac_brew.info_installed(
                    "cdalvaro/tap/salt", "vim", "visual-studio-code"
                )
                == _expected
            )


def test_list_upgrades(HOMEBREW_BIN):
    """
    Tests list_upgrades method
    """
    mock_user = MagicMock(return_value="foo")
    mock_cmd = MagicMock(return_value="")
    mock_cmd_all = MagicMock(
        return_value={
            "pid": 12345,
            "retcode": 0,
            "stderr": "",
            "stdout": textwrap.dedent(
                """\
                {
                  "formulae": [
                    {
                      "name": "cmake",
                      "installed_versions": ["3.19.3"],
                      "current_version": "3.19.4",
                      "pinned": false,
                      "pinned_version": null
                    },
                    {
                      "name": "fzf",
                      "installed_versions": ["0.25.0"],
                      "current_version": "0.25.1",
                      "pinned": false,
                      "pinned_version": null
                    }
                  ],
                  "casks": [
                    {
                      "name": "ksdiff",
                      "installed_versions": "2.2.0,122",
                      "current_version": "2.3.6,123-jan-18-2021"
                    }
                  ]
                }
                """
            ),
        }
    )
    _expected = {
        "cmake": "3.19.4",
        "fzf": "0.25.1",
        "ksdiff": "2.3.6,123-jan-18-2021",
    }

    with patch("salt.utils.path.which", MagicMock(return_value=HOMEBREW_BIN)):
        with patch("salt.modules.mac_brew_pkg.list_pkgs", return_value={}), patch(
            "salt.modules.mac_brew_pkg._list_pinned", return_value=["foo"]
        ), patch.dict(
            mac_brew.__salt__,
            {
                "file.get_user": mock_user,
                "cmd.run_all": mock_cmd_all,
                "cmd.run": mock_cmd,
            },
        ):
            assert (
                mac_brew.list_upgrades(refresh=False, include_casks=True) == _expected
            )
