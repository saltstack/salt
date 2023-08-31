"""
Test the winrepo runner
"""


import textwrap

import pytest

import salt.runners.winrepo as winrepo
import salt.utils.files
import salt.utils.stringutils

# Can't use raw string with unicode_literals, since the \u in the uninstaller
# will be interpreted as a unicode code point and the interpreter will raise a
# SyntaxError.


@pytest.fixture
def winrepo_sls():
    _winrepo_sls = textwrap.dedent(
        """
    winscp_x86:
      5.7.5:
          full_name: 'WinSCP 5.7.5'
          installer: 'http://heanet.dl.sourceforge.net/project/winscp/WinSCP/5.7.5/winscp575setup.exe'
          install_flags: '/SP- /verysilent /norestart'
          uninstaller: '%PROGRAMFILES%\\WinSCP\\unins000.exe'
          uninstall_flags: '/verysilent'
          msiexec: False
          locale: en_US
          reboot: False
      5.7.4:
          full_name: 'WinSCP 5.7.4'
          installer: 'http://cznic.dl.sourceforge.net/project/winscp/WinSCP/5.7.4/winscp574setup.exe'
          install_flags: '/SP- /verysilent /norestart'
          uninstaller: '%PROGRAMFILES%\\WinSCP\\unins000.exe'
          uninstall_flags: '/verysilent'
          msiexec: False
          locale: en_US
          reboot: False
    """
    )
    return _winrepo_sls


@pytest.fixture
def winrepo_genrepo_data():
    _winrepo_genrepo_data = {
        "name_map": {"WinSCP 5.7.4": "winscp_x86", "WinSCP 5.7.5": "winscp_x86"},
        "repo": {
            "winscp_x86": {
                "5.7.5": {
                    "full_name": "WinSCP 5.7.5",
                    "installer": "http://heanet.dl.sourceforge.net/project/winscp/WinSCP/5.7.5/winscp575setup.exe",
                    "install_flags": "/SP- /verysilent /norestart",
                    "uninstaller": "%PROGRAMFILES%\\WinSCP\\unins000.exe",
                    "uninstall_flags": "/verysilent",
                    "msiexec": False,
                    "locale": "en_US",
                    "reboot": False,
                },
                "5.7.4": {
                    "full_name": "WinSCP 5.7.4",
                    "installer": "http://cznic.dl.sourceforge.net/project/winscp/WinSCP/5.7.4/winscp574setup.exe",
                    "install_flags": "/SP- /verysilent /norestart",
                    "uninstaller": "%PROGRAMFILES%\\WinSCP\\unins000.exe",
                    "uninstall_flags": "/verysilent",
                    "msiexec": False,
                    "locale": "en_US",
                    "reboot": False,
                },
            }
        },
    }
    return _winrepo_genrepo_data


@pytest.fixture
def winrepo_dir(tmp_path):
    dir_name = tmp_path / "winrepo_dir"
    dir_name.mkdir()
    return dir_name


@pytest.fixture
def extmods_dir(tmp_path):
    dir_name = tmp_path / "extmods_dir"
    dir_name.mkdir()
    return dir_name


@pytest.fixture
def winrepo_sls_dir(winrepo_dir):
    dir_name = winrepo_dir / "repo_sls"
    dir_name.mkdir()
    return dir_name


@pytest.fixture
def configure_loader_modules(winrepo_dir, extmods_dir):
    return {
        winrepo: {
            "__opts__": {
                "winrepo_cachefile": "winrepo.p",
                "optimization_order": [0, 1, 2],
                "renderer": "yaml",
                "renderer_blacklist": [],
                "renderer_whitelist": [],
                "file_roots": {"base": [str(winrepo_dir)]},
                "winrepo_dir": str(winrepo_dir),
                "extension_modules": str(extmods_dir),
            }
        }
    }


def test_genrepo(winrepo_sls, winrepo_genrepo_data, winrepo_sls_dir):
    """
    Test winrepo.genrepo runner
    """
    sls_file = str(winrepo_sls_dir / "wireshark.sls")
    # Add a winrepo SLS file
    with salt.utils.files.fopen(sls_file, "w") as fp_:
        fp_.write(salt.utils.stringutils.to_str(winrepo_sls))
    assert winrepo.genrepo() == winrepo_genrepo_data
