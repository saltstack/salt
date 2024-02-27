"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import pytest

import salt.modules.genesis as genesis
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {genesis: {}}


def test_bootstrap():
    """
    Test for Create an image for a specific platform.
    """
    # Changed in 3.7.0 pformat no longer includes the comma
    exception_string = "Exception({})".format(repr("foo"))
    mock = MagicMock(return_value=False)
    with patch.dict(genesis.__salt__, {"file.directory_exists": mock}):
        mock = MagicMock(side_effect=Exception("foo"))
        with patch.dict(genesis.__salt__, {"file.mkdir": mock}):
            assert genesis.bootstrap("platform", "root") == {"Error": exception_string}

    with patch.object(genesis, "_bootstrap_yum", return_value="A"):
        with patch.dict(
            genesis.__salt__,
            {
                "mount.umount": MagicMock(),
                "file.rmdir": MagicMock(),
                "file.directory_exists": MagicMock(),
            },
        ):
            with patch.dict(
                genesis.__salt__, {"disk.blkid": MagicMock(return_value={})}
            ):
                assert genesis.bootstrap("rpm", "root", "dir") is None

    common_parms = {
        "platform": "deb",
        "root": "root",
        "img_format": "dir",
        "arch": "amd64",
        "flavor": "stable",
        "static_qemu": "qemu",
    }

    param_sets = [
        {
            "params": {},
            "cmd": [
                "debootstrap",
                "--foreign",
                "--arch",
                "amd64",
                "stable",
                "root",
                "http://ftp.debian.org/debian/",
            ],
        },
        {
            "params": {"pkgs": "vim"},
            "cmd": [
                "debootstrap",
                "--foreign",
                "--arch",
                "amd64",
                "--include",
                "vim",
                "stable",
                "root",
                "http://ftp.debian.org/debian/",
            ],
        },
        {
            "params": {"pkgs": "vim,emacs"},
            "cmd": [
                "debootstrap",
                "--foreign",
                "--arch",
                "amd64",
                "--include",
                "vim,emacs",
                "stable",
                "root",
                "http://ftp.debian.org/debian/",
            ],
        },
        {
            "params": {"pkgs": ["vim", "emacs"]},
            "cmd": [
                "debootstrap",
                "--foreign",
                "--arch",
                "amd64",
                "--include",
                "vim,emacs",
                "stable",
                "root",
                "http://ftp.debian.org/debian/",
            ],
        },
        {
            "params": {"pkgs": ["vim", "emacs"], "exclude_pkgs": ["vim", "foo"]},
            "cmd": [
                "debootstrap",
                "--foreign",
                "--arch",
                "amd64",
                "--include",
                "vim,emacs",
                "--exclude",
                "vim,foo",
                "stable",
                "root",
                "http://ftp.debian.org/debian/",
            ],
        },
    ]

    for param_set in param_sets:

        with patch.dict(
            genesis.__salt__,
            {
                "mount.umount": MagicMock(),
                "file.rmdir": MagicMock(),
                "file.directory_exists": MagicMock(),
                "cmd.run": MagicMock(),
                "disk.blkid": MagicMock(return_value={}),
            },
        ):
            with patch("salt.modules.genesis.salt.utils.path.which", return_value=True):
                with patch(
                    "salt.modules.genesis.salt.utils.validate.path.is_executable",
                    return_value=True,
                ):
                    param_set["params"].update(common_parms)
                    assert genesis.bootstrap(**param_set["params"]) is None
                    genesis.__salt__["cmd.run"].assert_any_call(
                        param_set["cmd"], python_shell=False
                    )

    with patch.object(genesis, "_bootstrap_pacman", return_value="A") as pacman_patch:
        with patch.dict(
            genesis.__salt__,
            {
                "mount.umount": MagicMock(),
                "file.rmdir": MagicMock(),
                "file.directory_exists": MagicMock(),
                "disk.blkid": MagicMock(return_value={}),
            },
        ):
            genesis.bootstrap("pacman", "root", "dir")
            pacman_patch.assert_called_with(
                "root", img_format="dir", exclude_pkgs=[], pkgs=[]
            )


def test_avail_platforms():
    """
    Test for Return which platforms are available
    """
    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        assert not genesis.avail_platforms()["deb"]


def test_pack():
    """
    Test for Pack up a directory structure, into a specific format
    """
    with patch.object(genesis, "_tar", return_value="tar"):
        assert genesis.pack("name", "root") is None


def test_unpack():
    """
    Test for Unpack an image into a directory structure
    """
    with patch.object(genesis, "_untar", return_value="untar"):
        assert genesis.unpack("name", "root") is None
