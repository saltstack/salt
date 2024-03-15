import configparser
import logging
import os

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.pkg_resource as pkg_resource
import salt.modules.rpm_lowpkg as rpm
import salt.modules.yumpkg as yumpkg
import salt.utils.platform
from salt.exceptions import CommandExecutionError, MinionError, SaltInvocationError
from tests.support.mock import MagicMock, Mock, call, patch

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture
def configure_loader_modules():
    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    return {
        yumpkg: {
            "__context__": {"yum_bin": "yum"},
            "__grains__": {
                "osarch": "x86_64",
                "os": "CentOS",
                "os_family": "RedHat",
                "osmajorrelease": 7,
            },
            "__salt__": {
                "pkg_resource.add_pkg": _add_data,
            },
        },
        pkg_resource: {},
    }


@pytest.fixture(scope="module")
def list_repos_var():
    return {
        "base": {
            "file": "/etc/yum.repos.d/CentOS-Base.repo",
            "gpgcheck": "1",
            "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
            "mirrorlist": "http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=os&infra=$infra",
            "name": "CentOS-$releasever - Base",
        },
        "base-source": {
            "baseurl": "http://vault.centos.org/centos/$releasever/os/Source/",
            "enabled": "0",
            "file": "/etc/yum.repos.d/CentOS-Sources.repo",
            "gpgcheck": "1",
            "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
            "name": "CentOS-$releasever - Base Sources",
        },
        "updates": {
            "file": "/etc/yum.repos.d/CentOS-Base.repo",
            "gpgcheck": "1",
            "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
            "mirrorlist": "http://mirrorlist.centos.org/?release=$releasever&arch=$basearch&repo=updates&infra=$infra",
            "name": "CentOS-$releasever - Updates",
        },
        "updates-source": {
            "baseurl": "http://vault.centos.org/centos/$releasever/updates/Source/",
            "enabled": "0",
            "file": "/etc/yum.repos.d/CentOS-Sources.repo",
            "gpgcheck": "1",
            "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
            "name": "CentOS-$releasever - Updates Sources",
        },
    }


@pytest.fixture(
    ids=["yum", "dnf", "dnf5"],
    params=[
        {
            "context": {"yum_bin": "yum"},
            "grains": {"os": "CentOS", "osrelease": 7},
            "cmd": ["yum", "-y"],
        },
        {
            "context": {"yum_bin": "dnf"},
            "grains": {"os": "Fedora", "osrelease": 27},
            "cmd": ["dnf", "-y", "--best", "--allowerasing"],
        },
        {
            "context": {"yum_bin": "dnf5"},
            "grains": {"os": "Fedora", "osrelease": 39},
            "cmd": ["dnf5", "-y"],
        },
    ],
)
def yum_and_dnf(request):
    with patch.dict(yumpkg.__context__, request.param["context"]), patch.dict(
        yumpkg.__grains__, request.param["grains"]
    ), patch.dict(pkg_resource.__grains__, request.param["grains"]):
        yield request.param["cmd"]


def test__virtual_normal():
    assert yumpkg.__virtual__() == "pkg"


def test__virtual_yumpkg_api():
    with patch.dict(yumpkg.__opts__, {"yum_provider": "yumpkg_api"}):
        assert yumpkg.__virtual__() == (
            False,
            "Module yumpkg: yumpkg_api provider not available",
        )


def test__virtual_exception():
    with patch.dict(yumpkg.__grains__, {"os": 1}):
        assert yumpkg.__virtual__() == (
            False,
            "Module yumpkg: no yum based system detected",
        )


def test__virtual_no_yum():
    with patch.object(yumpkg, "_yum", MagicMock(return_value=None)):
        assert yumpkg.__virtual__() == (False, "DNF nor YUM found")


def test__virtual_non_yum_system():
    with patch.dict(yumpkg.__grains__, {"os_family": "ubuntu"}):
        assert yumpkg.__virtual__() == (
            False,
            "Module yumpkg: no yum based system detected",
        )


def test_strip_headers():
    output = os.linesep.join(["spongebob", "squarepants", "squidward"])
    args = ("spongebob", "squarepants")
    assert yumpkg._strip_headers(output, *args) == "squidward\n"


def test_get_copr_repo():
    result = yumpkg._get_copr_repo("copr:spongebob/squarepants")
    assert result == "copr:copr.fedorainfracloud.org:spongebob:squarepants"


def test_get_hold():
    line = "vim-enhanced-2:7.4.827-1.fc22"
    with patch.object(yumpkg, "_yum", MagicMock(return_value="dnf")):
        assert yumpkg._get_hold(line) == "vim-enhanced-2:7.4.827-1.fc22"


def test_get_options():
    result = yumpkg._get_options(
        repo="spongebob",
        disableexcludes="squarepants",
        __dunder_keyword="this is skipped",
        stringvalue="string_value",
        boolvalue=True,
        get_extra_options=True,
    )
    assert "--enablerepo=spongebob" in result
    assert "--disableexcludes=squarepants" in result
    assert "--stringvalue=string_value" in result
    assert "--boolvalue" in result


def test_list_pkgs():
    """
    Test packages listing.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    rpm_out = [
        "python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471",
        "alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475",
        "gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477",
        "rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477",
        "pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478",
        "yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479",
        "lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479",
        "qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480",
        "ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480",
        "shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481",
        "util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484",
        "openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485",
        "virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486",
    ]
    cmd_mod = MagicMock(return_value=os.linesep.join(rpm_out))
    with patch.dict(yumpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        yumpkg.__salt__,
        {"cmd.run": cmd_mod},
    ), patch.dict(yumpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        yumpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        yumpkg.__salt__, {"pkg_resource.stringify": MagicMock()}
    ), patch.dict(
        pkg_resource.__salt__, {"pkg.parse_arch": yumpkg.parse_arch}
    ):
        pkgs = yumpkg.list_pkgs(versions_as_list=True)
        for pkg_name, pkg_version in {
            "python-urlgrabber": "3.10-8.el7",
            "alsa-lib": "1.1.1-1.el7",
            "gnupg2": "2.0.22-4.el7",
            "rpm-python": "4.11.3-21.el7",
            "pygpgme": "0.3-9.el7",
            "yum": "3.4.3-150.el7.centos",
            "lzo": "2.06-8.el7",
            "qrencode-libs": "3.4.1-3.el7",
            "ustr": "1.0.4-16.el7",
            "shadow-utils": "2:4.1.5.1-24.el7",
            "util-linux": "2.23.2-33.el7",
            "openssh": "6.6.1p1-33.el7_3",
            "virt-what": "1.13-8.el7",
        }.items():
            assert pkgs.get(pkg_name) is not None
            assert pkgs[pkg_name] == [pkg_version]
        cmd_mod.assert_called_once_with(
            [
                "rpm",
                "-qa",
                "--nodigest",
                "--nosignature",
                "--queryformat",
                "%{NAME}_|-%{EPOCH}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}_|-(none)_|-%{INSTALLTIME}\n",
            ],
            output_loglevel="trace",
            python_shell=False,
        )


def test_list_pkgs_no_context():
    """
    Test packages listing.

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    rpm_out = [
        "python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471",
        "alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475",
        "gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477",
        "rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477",
        "pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478",
        "yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479",
        "lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479",
        "qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480",
        "ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480",
        "shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481",
        "util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484",
        "openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485",
        "virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486",
    ]
    with patch.dict(yumpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        yumpkg.__salt__,
        {"cmd.run": MagicMock(return_value=os.linesep.join(rpm_out))},
    ), patch.dict(yumpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        yumpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        yumpkg.__salt__, {"pkg_resource.stringify": MagicMock()}
    ), patch.dict(
        pkg_resource.__salt__, {"pkg.parse_arch": yumpkg.parse_arch}
    ), patch.object(
        yumpkg, "_list_pkgs_from_context"
    ) as list_pkgs_context_mock:
        pkgs = yumpkg.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()

        pkgs = yumpkg.list_pkgs(versions_as_list=True, use_context=False)
        list_pkgs_context_mock.assert_not_called()
        list_pkgs_context_mock.reset_mock()


def test_list_pkgs_with_attr():
    """
    Test packages listing with the attr parameter

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    rpm_out = [
        "python-urlgrabber_|-(none)_|-3.10_|-8.el7_|-noarch_|-(none)_|-1487838471",
        "alsa-lib_|-(none)_|-1.1.1_|-1.el7_|-x86_64_|-(none)_|-1487838475",
        "gnupg2_|-(none)_|-2.0.22_|-4.el7_|-x86_64_|-(none)_|-1487838477",
        "rpm-python_|-(none)_|-4.11.3_|-21.el7_|-x86_64_|-(none)_|-1487838477",
        "pygpgme_|-(none)_|-0.3_|-9.el7_|-x86_64_|-(none)_|-1487838478",
        "yum_|-(none)_|-3.4.3_|-150.el7.centos_|-noarch_|-(none)_|-1487838479",
        "lzo_|-(none)_|-2.06_|-8.el7_|-x86_64_|-(none)_|-1487838479",
        "qrencode-libs_|-(none)_|-3.4.1_|-3.el7_|-x86_64_|-(none)_|-1487838480",
        "ustr_|-(none)_|-1.0.4_|-16.el7_|-x86_64_|-(none)_|-1487838480",
        "shadow-utils_|-2_|-4.1.5.1_|-24.el7_|-x86_64_|-(none)_|-1487838481",
        "util-linux_|-(none)_|-2.23.2_|-33.el7_|-x86_64_|-(none)_|-1487838484",
        "openssh_|-(none)_|-6.6.1p1_|-33.el7_3_|-x86_64_|-(none)_|-1487838485",
        "virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486",
    ]
    with patch.dict(yumpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        yumpkg.__salt__,
        {"cmd.run": MagicMock(return_value=os.linesep.join(rpm_out))},
    ), patch.dict(yumpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        yumpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        yumpkg.__salt__, {"pkg_resource.stringify": MagicMock()}
    ), patch.dict(
        pkg_resource.__salt__, {"pkg.parse_arch": yumpkg.parse_arch}
    ):
        pkgs = yumpkg.list_pkgs(
            attr=["epoch", "release", "arch", "install_date_time_t"]
        )
        for pkg_name, pkg_attr in {
            "python-urlgrabber": {
                "version": "3.10",
                "release": "8.el7",
                "arch": "noarch",
                "install_date_time_t": 1487838471,
                "epoch": None,
            },
            "alsa-lib": {
                "version": "1.1.1",
                "release": "1.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838475,
                "epoch": None,
            },
            "gnupg2": {
                "version": "2.0.22",
                "release": "4.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838477,
                "epoch": None,
            },
            "rpm-python": {
                "version": "4.11.3",
                "release": "21.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838477,
                "epoch": None,
            },
            "pygpgme": {
                "version": "0.3",
                "release": "9.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838478,
                "epoch": None,
            },
            "yum": {
                "version": "3.4.3",
                "release": "150.el7.centos",
                "arch": "noarch",
                "install_date_time_t": 1487838479,
                "epoch": None,
            },
            "lzo": {
                "version": "2.06",
                "release": "8.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838479,
                "epoch": None,
            },
            "qrencode-libs": {
                "version": "3.4.1",
                "release": "3.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838480,
                "epoch": None,
            },
            "ustr": {
                "version": "1.0.4",
                "release": "16.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838480,
                "epoch": None,
            },
            "shadow-utils": {
                "epoch": "2",
                "version": "4.1.5.1",
                "release": "24.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838481,
            },
            "util-linux": {
                "version": "2.23.2",
                "release": "33.el7",
                "arch": "x86_64",
                "install_date_time_t": 1487838484,
                "epoch": None,
            },
            "openssh": {
                "version": "6.6.1p1",
                "release": "33.el7_3",
                "arch": "x86_64",
                "install_date_time_t": 1487838485,
                "epoch": None,
            },
            "virt-what": {
                "version": "1.13",
                "release": "8.el7",
                "install_date_time_t": 1487838486,
                "arch": "x86_64",
                "epoch": None,
            },
        }.items():

            assert pkgs.get(pkg_name) is not None
            assert pkgs[pkg_name] == [pkg_attr]


def test_list_pkgs_with_attr_multiple_versions():
    """
    Test packages listing with the attr parameter reporting multiple version installed

    :return:
    """

    def _add_data(data, key, value):
        data.setdefault(key, []).append(value)

    rpm_out = [
        "glibc_|-(none)_|-2.12_|-1.212.el6_|-i686_|-(none)_|-1542394210"
        "glibc_|-(none)_|-2.12_|-1.212.el6_|-x86_64_|-(none)_|-1542394204",
        "virt-what_|-(none)_|-1.13_|-8.el7_|-x86_64_|-(none)_|-1487838486",
        "virt-what_|-(none)_|-1.10_|-2.el7_|-x86_64_|-(none)_|-1387838486",
    ]
    with patch.dict(yumpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        yumpkg.__salt__,
        {"cmd.run": MagicMock(return_value=os.linesep.join(rpm_out))},
    ), patch.dict(yumpkg.__salt__, {"pkg_resource.add_pkg": _add_data}), patch.dict(
        yumpkg.__salt__,
        {"pkg_resource.format_pkg_list": pkg_resource.format_pkg_list},
    ), patch.dict(
        yumpkg.__salt__, {"pkg_resource.stringify": MagicMock()}
    ), patch.dict(
        pkg_resource.__salt__, {"pkg.parse_arch": yumpkg.parse_arch}
    ):
        pkgs = yumpkg.list_pkgs(
            attr=["epoch", "release", "arch", "install_date_time_t"]
        )
        expected_pkg_list = {
            "glibc": [
                {
                    "version": "2.12",
                    "release": "1.212.el6",
                    "install_date_time_t": 1542394210,
                    "arch": "i686",
                    "epoch": None,
                },
                {
                    "version": "2.12",
                    "release": "1.212.el6",
                    "install_date_time_t": 1542394204,
                    "arch": "x86_64",
                    "epoch": None,
                },
            ],
            "virt-what": [
                {
                    "version": "1.10",
                    "release": "2.el7",
                    "install_date_time_t": 1387838486,
                    "arch": "x86_64",
                    "epoch": None,
                },
                {
                    "version": "1.13",
                    "release": "8.el7",
                    "install_date_time_t": 1487838486,
                    "arch": "x86_64",
                    "epoch": None,
                },
            ],
        }
        for pkgname, pkginfo in pkgs.items():
            assert pkginfo == expected_pkg_list[pkgname]
            assert len(pkginfo) == len(expected_pkg_list[pkgname])


def test_list_patches():
    """
    Test patches listing.

    :return:
    """
    yum_out = [
        "i my-fake-patch-not-installed-1234 recommended   "
        " spacewalk-usix-2.7.5.2-2.2.noarch",
        "  my-fake-patch-not-installed-1234 recommended   "
        " spacewalksd-5.0.26.2-21.2.x86_64",
        "i my-fake-patch-not-installed-1234 recommended   "
        " suseRegisterInfo-3.1.1-18.2.x86_64",
        "i my-fake-patch-installed-1234 recommended       "
        " my-package-one-1.1-0.1.x86_64",
        "i my-fake-patch-installed-1234 recommended       "
        " my-package-two-1.1-0.1.x86_64",
    ]

    expected_patches = {
        "my-fake-patch-not-installed-1234": {
            "installed": False,
            "summary": [
                "spacewalk-usix-2.7.5.2-2.2.noarch",
                "spacewalksd-5.0.26.2-21.2.x86_64",
                "suseRegisterInfo-3.1.1-18.2.x86_64",
            ],
        },
        "my-fake-patch-installed-1234": {
            "installed": True,
            "summary": [
                "my-package-one-1.1-0.1.x86_64",
                "my-package-two-1.1-0.1.x86_64",
            ],
        },
    }

    with patch.dict(yumpkg.__grains__, {"osarch": "x86_64"}), patch.dict(
        yumpkg.__salt__,
        {"cmd.run_stdout": MagicMock(return_value=os.linesep.join(yum_out))},
    ):
        patches = yumpkg.list_patches()
        assert patches["my-fake-patch-not-installed-1234"]["installed"] is False
        assert len(patches["my-fake-patch-not-installed-1234"]["summary"]) == 3
        for _patch in expected_patches["my-fake-patch-not-installed-1234"]["summary"]:
            assert _patch in patches["my-fake-patch-not-installed-1234"]["summary"]

        assert patches["my-fake-patch-installed-1234"]["installed"] is True
        assert len(patches["my-fake-patch-installed-1234"]["summary"]) == 2
        for _patch in expected_patches["my-fake-patch-installed-1234"]["summary"]:
            assert _patch in patches["my-fake-patch-installed-1234"]["summary"]


def test_list_patches_refresh():
    expected = ["spongebob"]
    mock_get_patches = MagicMock(return_value=expected)
    patch_get_patches = patch.object(yumpkg, "_get_patches", mock_get_patches)
    patch_refresh_db = patch.object(yumpkg, "refresh_db", MagicMock())
    with patch_refresh_db, patch_get_patches:
        result = yumpkg.list_patches(refresh=True)
        assert result == expected


def test_latest_version_with_options():
    with patch.object(yumpkg, "list_pkgs", MagicMock(return_value={})):

        # with fromrepo
        cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.latest_version("foo", refresh=False, fromrepo="good", branch="foo")
            cmd.assert_called_once_with(
                [
                    "yum",
                    "--quiet",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                    "list",
                    "available",
                    "foo",
                ],
                env={},
                ignore_retcode=True,
                output_loglevel="trace",
                python_shell=False,
            )

        # without fromrepo
        cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.latest_version(
                "foo",
                refresh=False,
                enablerepo="good",
                disablerepo="bad",
                branch="foo",
            )
            cmd.assert_called_once_with(
                [
                    "yum",
                    "--quiet",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                    "list",
                    "available",
                    "foo",
                ],
                env={},
                ignore_retcode=True,
                output_loglevel="trace",
                python_shell=False,
            )

        # without fromrepo, but within the scope
        cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch("salt.utils.systemd.has_scope", MagicMock(return_value=True)):
            with patch.dict(
                yumpkg.__salt__,
                {"cmd.run_all": cmd, "config.get": MagicMock(return_value=True)},
            ):
                yumpkg.latest_version(
                    "foo",
                    refresh=False,
                    enablerepo="good",
                    disablerepo="bad",
                    branch="foo",
                )
                cmd.assert_called_once_with(
                    [
                        "systemd-run",
                        "--scope",
                        "yum",
                        "--quiet",
                        "--disablerepo=bad",
                        "--enablerepo=good",
                        "--branch=foo",
                        "list",
                        "available",
                        "foo",
                    ],
                    env={},
                    ignore_retcode=True,
                    output_loglevel="trace",
                    python_shell=False,
                )


def test_list_repo_pkgs_attribute_error():
    patch_get_options = patch.object(yumpkg, "_get_options", MagicMock())
    mock_run = MagicMock(return_value="3.4.5")
    patch_run = patch.dict(yumpkg.__salt__, {"cmd.run": mock_run})
    mock_yum = MagicMock(return_value={"retcode": 0, "stdout": ""})
    patch_yum = patch.object(yumpkg, "_call_yum", mock_yum)
    with patch_get_options, patch_run, patch_yum:
        assert yumpkg.list_repo_pkgs(fromrepo=1, disablerepo=2, enablerepo=3) == {}


def test_list_repo_pkgs_byrepo(list_repos_var):
    patch_get_options = patch.object(yumpkg, "_get_options", MagicMock())
    stdout_installed = """\
Installed Packages
spongebob.x86_64     1.1.el9_1    @bikini-bottom-rpms
squarepants.x86_64   1.2.el9_1    @bikini-bottom-rpms
patrick.noarch       1.3.el9_1    @rock-bottom-rpms
squidward.x86_64     1.4.el9_1    @rock-bottom-rpms"""
    stdout_available = """\
Available Packages
plankton.noarch      2.1-1.el9_2    bikini-bottom-rpms
dennis.x86_64        2.2-2.el9      bikini-bottom-rpms
man-ray.x86_64       2.3-1.el9_2    bikini-bottom-rpms
doodlebob.x86_64     2.4-1.el9_2    bikini-bottom-rpms"""
    run_all_side_effect = (
        {"retcode": 0, "stdout": stdout_installed},
        {"retcode": 0, "stdout": stdout_available},
    )
    patch_salt = patch.dict(
        yumpkg.__salt__,
        {
            "cmd.run": MagicMock(return_value="3.4.5"),
            "cmd.run_all": MagicMock(side_effect=run_all_side_effect),
            "config.get": MagicMock(return_value=False),
        },
    )
    patch_list_repos = patch.object(
        yumpkg,
        "list_repos",
        MagicMock(return_value=list_repos_var),
    )
    with patch_get_options, patch_salt, patch_list_repos:
        expected = {
            "bikini-bottom-rpms": {
                "dennis": ["2.2-2.el9"],
                "doodlebob": ["2.4-1.el9_2"],
                "man-ray": ["2.3-1.el9_2"],
                "plankton": ["2.1-1.el9_2"],
                "spongebob": ["1.1.el9_1"],
                "squarepants": ["1.2.el9_1"],
            },
            "rock-bottom-rpms": {
                "patrick": ["1.3.el9_1"],
                "squidward": ["1.4.el9_1"],
            },
        }
        result = yumpkg.list_repo_pkgs(byrepo=True)
        assert result == expected


def test_list_repo_pkgs_with_options(list_repos_var):
    """
    Test list_repo_pkgs with and without fromrepo

    NOTE: mock_calls is a stack. The most recent call is indexed
    with 0, while the first call would have the highest index.
    """
    really_old_yum = MagicMock(return_value="3.2.0")
    older_yum = MagicMock(return_value="3.4.0")
    newer_yum = MagicMock(return_value="3.4.5")
    list_repos_mock = MagicMock(return_value=list_repos_var)
    kwargs = {
        "output_loglevel": "trace",
        "ignore_retcode": True,
        "python_shell": False,
        "env": {},
    }

    with patch.object(yumpkg, "list_repos", list_repos_mock):

        # Test with really old yum. The fromrepo argument has no effect on
        # the yum commands we'd run.
        with patch.dict(yumpkg.__salt__, {"cmd.run": really_old_yum}):

            cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
            with patch.dict(
                yumpkg.__salt__,
                {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
            ):
                yumpkg.list_repo_pkgs("foo")
                # We should have called cmd.run_all twice
                assert len(cmd.mock_calls) == 2

                # Check args from first call
                assert cmd.mock_calls[1][1] == (
                    ["yum", "--quiet", "list", "available"],
                )

                # Check kwargs from first call
                assert cmd.mock_calls[1][2] == kwargs

                # Check args from second call
                assert cmd.mock_calls[0][1] == (
                    ["yum", "--quiet", "list", "installed"],
                )

                # Check kwargs from second call
                assert cmd.mock_calls[0][2] == kwargs

        # Test with really old yum. The fromrepo argument has no effect on
        # the yum commands we'd run.
        with patch.dict(yumpkg.__salt__, {"cmd.run": older_yum}):

            cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
            with patch.dict(
                yumpkg.__salt__,
                {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
            ):
                yumpkg.list_repo_pkgs("foo")
                # We should have called cmd.run_all twice
                assert len(cmd.mock_calls) == 2

                # Check args from first call
                assert cmd.mock_calls[1][1] == (
                    ["yum", "--quiet", "--showduplicates", "list", "available"],
                )

                # Check kwargs from first call
                assert cmd.mock_calls[1][2] == kwargs

                # Check args from second call
                assert cmd.mock_calls[0][1] == (
                    ["yum", "--quiet", "--showduplicates", "list", "installed"],
                )

                # Check kwargs from second call
                assert cmd.mock_calls[0][2] == kwargs

        # Test with newer yum. We should run one yum command per repo, so
        # fromrepo would limit how many calls we make.
        with patch.dict(yumpkg.__salt__, {"cmd.run": newer_yum}):

            # When fromrepo is used, we would only run one yum command, for
            # that specific repo.
            cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
            with patch.dict(
                yumpkg.__salt__,
                {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
            ):
                yumpkg.list_repo_pkgs("foo", fromrepo="base")
                # We should have called cmd.run_all once
                assert len(cmd.mock_calls) == 1

                # Check args
                assert cmd.mock_calls[0][1] == (
                    [
                        "yum",
                        "--quiet",
                        "--showduplicates",
                        "repository-packages",
                        "base",
                        "list",
                        "foo",
                    ],
                )
                # Check kwargs
                assert cmd.mock_calls[0][2] == kwargs

            # Test enabling base-source and disabling updates. We should
            # get two calls, one for each enabled repo. Because dict
            # iteration order will vary, different Python versions will be
            # do them in different orders, which is OK, but it will just
            # mean that we will have to check both the first and second
            # mock call both times.
            cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
            with patch.dict(
                yumpkg.__salt__,
                {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
            ):
                yumpkg.list_repo_pkgs(
                    "foo", enablerepo="base-source", disablerepo="updates"
                )
                # We should have called cmd.run_all twice
                assert len(cmd.mock_calls) == 2

                for repo in ("base", "base-source"):
                    for index in (0, 1):
                        try:
                            # Check args
                            assert cmd.mock_calls[index][1] == (
                                [
                                    "yum",
                                    "--quiet",
                                    "--showduplicates",
                                    "repository-packages",
                                    repo,
                                    "list",
                                    "foo",
                                ],
                            )
                            # Check kwargs
                            assert cmd.mock_calls[index][2] == kwargs
                            break
                        except AssertionError:
                            continue
                    else:
                        pytest.fail(f"repo '{repo}' not checked")


def test_list_upgrades_dnf():
    """
    The subcommand should be "upgrades" with dnf
    """
    with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}):
        # with fromrepo
        cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.list_upgrades(refresh=False, fromrepo="good", branch="foo")
            cmd.assert_called_once_with(
                [
                    "dnf",
                    "--quiet",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                    "list",
                    "upgrades",
                ],
                env={},
                output_loglevel="trace",
                ignore_retcode=True,
                python_shell=False,
            )

        # without fromrepo
        cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.list_upgrades(
                refresh=False, enablerepo="good", disablerepo="bad", branch="foo"
            )
            cmd.assert_called_once_with(
                [
                    "dnf",
                    "--quiet",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                    "list",
                    "upgrades",
                ],
                env={},
                output_loglevel="trace",
                ignore_retcode=True,
                python_shell=False,
            )


def test_list_upgrades_refresh():
    mock_call_yum = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.object(yumpkg, "refresh_db", MagicMock()):
        with patch.object(yumpkg, "_call_yum", mock_call_yum):
            assert yumpkg.list_upgrades(refresh=True) == {}


def test_list_upgrades_error():
    mock_return = {"retcode": 1, "Error:": "Error"}
    mock_call_yum = MagicMock(return_value=mock_return)
    with patch.object(yumpkg, "_call_yum", mock_call_yum):
        assert yumpkg.list_upgrades(refresh=False) == {}


def test_list_downloaded():
    mock_walk = MagicMock(
        return_value=[
            (
                "/var/cache/yum",
                [],
                ["pkg1-3.1-16.1.x86_64.rpm", "pkg2-1.2-13.2.x86_64.rpm"],
            )
        ]
    )
    mock_pkginfo = MagicMock(
        side_effect=[
            {
                "name": "pkg1",
                "version": "3.1",
            },
            {
                "name": "pkg2",
                "version": "1.2",
            },
        ]
    )
    mock_getctime = MagicMock(return_value=1696536082.861206)
    mock_getsize = MagicMock(return_value=75701688)
    with patch.dict(yumpkg.__salt__, {"lowpkg.bin_pkg_info": mock_pkginfo}), patch(
        "salt.utils.path.os_walk", mock_walk
    ), patch("os.path.getctime", mock_getctime), patch("os.path.getsize", mock_getsize):
        result = yumpkg.list_downloaded()
    expected = {
        "pkg1": {
            "3.1": {
                "creation_date_time": "2023-10-05T14:01:22",
                "creation_date_time_t": 1696536082,
                "path": "/var/cache/yum/pkg1-3.1-16.1.x86_64.rpm",
                "size": 75701688,
            },
        },
        "pkg2": {
            "1.2": {
                "creation_date_time": "2023-10-05T14:01:22",
                "creation_date_time_t": 1696536082,
                "path": "/var/cache/yum/pkg2-1.2-13.2.x86_64.rpm",
                "size": 75701688,
            },
        },
    }
    assert (
        result["pkg1"]["3.1"]["creation_date_time_t"]
        == expected["pkg1"]["3.1"]["creation_date_time_t"]
    )
    assert result["pkg1"]["3.1"]["path"] == expected["pkg1"]["3.1"]["path"]
    assert result["pkg1"]["3.1"]["size"] == expected["pkg1"]["3.1"]["size"]
    assert (
        result["pkg2"]["1.2"]["creation_date_time_t"]
        == expected["pkg2"]["1.2"]["creation_date_time_t"]
    )
    assert result["pkg2"]["1.2"]["path"] == expected["pkg2"]["1.2"]["path"]
    assert result["pkg2"]["1.2"]["size"] == expected["pkg2"]["1.2"]["size"]


def test_list_installed_patches():
    mock_get_patches = MagicMock(return_value="spongebob")
    with patch.object(yumpkg, "_get_patches", mock_get_patches):
        result = yumpkg.list_installed_patches()
        assert result == "spongebob"


def test_list_upgrades_yum():
    """
    The subcommand should be "updates" with yum
    """
    # with fromrepo
    cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(
        yumpkg.__salt__,
        {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
    ):
        yumpkg.list_upgrades(refresh=False, fromrepo="good", branch="foo")
        cmd.assert_called_once_with(
            [
                "yum",
                "--quiet",
                "--disablerepo=*",
                "--enablerepo=good",
                "--branch=foo",
                "list",
                "updates",
            ],
            env={},
            output_loglevel="trace",
            ignore_retcode=True,
            python_shell=False,
        )

    # without fromrepo
    cmd = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(
        yumpkg.__salt__,
        {"cmd.run_all": cmd, "config.get": MagicMock(return_value=False)},
    ):
        yumpkg.list_upgrades(
            refresh=False, enablerepo="good", disablerepo="bad", branch="foo"
        )
        cmd.assert_called_once_with(
            [
                "yum",
                "--quiet",
                "--disablerepo=bad",
                "--enablerepo=good",
                "--branch=foo",
                "list",
                "updates",
            ],
            env={},
            output_loglevel="trace",
            ignore_retcode=True,
            python_shell=False,
        )


def test_modified():
    mock = MagicMock()
    with patch.dict(yumpkg.__salt__, {"lowpkg.modified": mock}):
        yumpkg.modified("spongebob", "squarepants")
        mock.assert_called_once_with("spongebob", "squarepants")


def test_clean_metadata_with_options():

    with patch("salt.utils.pkg.clear_rtag", Mock()):

        # With check_update=True we will do a cmd.run to run the clean_cmd, and
        # then a separate cmd.retcode to check for updates.

        # with fromrepo
        yum_call = MagicMock()
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": yum_call, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.clean_metadata(check_update=True, fromrepo="good", branch="foo")

            assert yum_call.call_count == 2
            yum_call.assert_any_call(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "clean",
                    "expire-cache",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                env={},
                ignore_retcode=True,
                output_loglevel="trace",
                python_shell=False,
            )
            yum_call.assert_any_call(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "check-update",
                    "--setopt=autocheck_running_kernel=false",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                output_loglevel="trace",
                env={},
                ignore_retcode=True,
                python_shell=False,
            )


def test_del_repo_error():
    basedir = "/mr/krabs"
    ret_dict = {
        "spongebob": {"file": "/square/pants"},
        "patrick": {"file": "/squid/ward"},
    }
    mock_list = MagicMock(return_value=ret_dict)
    patch_list = patch.object(yumpkg, "list_repos", mock_list)
    with patch_list:
        result = yumpkg.del_repo("plankton", basedir=basedir)
        expected = "Error: the plankton repo does not exist in ['/mr/krabs']"
        assert result == expected

        result = yumpkg.del_repo("copr:plankton/karen", basedir=basedir)
        expected = "Error: the copr:copr.fedorainfracloud.org:plankton:karen repo does not exist in ['/mr/krabs']"
        assert result == expected


def test_del_repo_single_file():
    basedir = "/mr/krabs"
    ret_dict = {
        "spongebob": {"file": "/square/pants"},
        "patrick": {"file": "/squid/ward"},
    }
    mock_list = MagicMock(return_value=ret_dict)
    patch_list = patch.object(yumpkg, "list_repos", mock_list)
    with patch_list, patch("os.remove"):
        result = yumpkg.del_repo("spongebob", basedir=basedir)
        expected = "File /square/pants containing repo spongebob has been removed"
        assert result == expected


def test_download_error_no_packages():
    patch_which = patch("salt.utils.path.which", MagicMock(return_value="path.exe"))
    with patch_which, pytest.raises(SaltInvocationError):
        yumpkg.download()


def test_download():
    patch_which = patch("salt.utils.path.which", MagicMock(return_value="path.exe"))
    patch_exists = patch("os.path.exists", MagicMock(return_value=False))
    patch_makedirs = patch("os.makedirs")
    mock_listdir = MagicMock(side_effect=([], ["spongebob-1.2.rpm"]))
    patch_listdir = patch("os.listdir", mock_listdir)
    mock_run = MagicMock()
    dict_salt = {
        "cmd.run": mock_run,
    }
    patch_salt = patch.dict(yumpkg.__salt__, dict_salt)
    with patch_which, patch_exists, patch_makedirs, patch_listdir, patch_salt:
        result = yumpkg.download("spongebob")
        cmd = ["yumdownloader", "-q", "--destdir=/var/cache/yum/packages", "spongebob"]
        mock_run.assert_called_once_with(
            cmd, output_loglevel="trace", python_shell=False
        )
        expected = {"spongebob": "/var/cache/yum/packages/spongebob-1.2.rpm"}
        assert result == expected


def test_download_failed():
    patch_which = patch("salt.utils.path.which", MagicMock(return_value="path.exe"))
    patch_exists = patch("os.path.exists", MagicMock(return_value=True))
    mock_listdir = MagicMock(return_value=["spongebob-1.2.rpm", "junk.txt"])
    patch_listdir = patch("os.listdir", mock_listdir)
    patch_unlink = patch("os.unlink")
    mock_run = MagicMock()
    dict_salt = {
        "cmd.run": mock_run,
    }
    patch_salt = patch.dict(yumpkg.__salt__, dict_salt)
    with patch_which, patch_exists, patch_listdir, patch_unlink, patch_salt:
        result = yumpkg.download("spongebob", "patrick")
        cmd = [
            "yumdownloader",
            "-q",
            "--destdir=/var/cache/yum/packages",
            "spongebob",
            "patrick",
        ]
        mock_run.assert_called_once_with(
            cmd, output_loglevel="trace", python_shell=False
        )
        expected = {
            "_error": "The following package(s) failed to download: patrick",
            "spongebob": "/var/cache/yum/packages/spongebob-1.2.rpm",
        }
        assert result == expected


def test_download_missing_yumdownloader():
    patch_which = patch("salt.utils.path.which", MagicMock(return_value=None))
    with patch_which, pytest.raises(CommandExecutionError):
        yumpkg.download("spongebob")


def test_download_to_purge():
    patch_which = patch("salt.utils.path.which", MagicMock(return_value="path.exe"))
    patch_exists = patch("os.path.exists", MagicMock(return_value=True))
    mock_listdir = MagicMock(return_value=["spongebob-1.2.rpm", "junk.txt"])
    patch_listdir = patch("os.listdir", mock_listdir)
    patch_unlink = patch("os.unlink")
    mock_run = MagicMock()
    dict_salt = {
        "cmd.run": mock_run,
    }
    patch_salt = patch.dict(yumpkg.__salt__, dict_salt)
    with patch_which, patch_exists, patch_listdir, patch_unlink, patch_salt:
        result = yumpkg.download("spongebob")
        cmd = ["yumdownloader", "-q", "--destdir=/var/cache/yum/packages", "spongebob"]
        mock_run.assert_called_once_with(
            cmd, output_loglevel="trace", python_shell=False
        )
        expected = {"spongebob": "/var/cache/yum/packages/spongebob-1.2.rpm"}
        assert result == expected


def test_download_unlink_error():
    patch_which = patch("salt.utils.path.which", MagicMock(return_value="path.exe"))
    patch_exists = patch("os.path.exists", MagicMock(return_value=True))
    se_listdir = (
        ["spongebob-1.2.rpm", "junk.txt"],
        ["spongebob1.2.rpm", "junk.txt"],
    )
    mock_listdir = MagicMock(side_effect=se_listdir)
    patch_listdir = patch("os.listdir", mock_listdir)
    patch_unlink = patch("os.unlink", MagicMock(side_effect=OSError))
    mock_run = MagicMock()
    dict_salt = {
        "cmd.run": mock_run,
    }
    patch_salt = patch.dict(yumpkg.__salt__, dict_salt)
    with patch_which, patch_exists, patch_listdir, patch_unlink, patch_salt:
        with pytest.raises(CommandExecutionError):
            yumpkg.download("spongebob")


def test_file_dict():
    mock = MagicMock()
    with patch.dict(yumpkg.__salt__, {"lowpkg.file_dict": mock}):
        yumpkg.file_dict("spongebob", "squarepants")
        mock.assert_called_once_with("spongebob", "squarepants")


def test_file_list():
    mock = MagicMock()
    with patch.dict(yumpkg.__salt__, {"lowpkg.file_list": mock}):
        yumpkg.file_list("spongebob", "squarepants")
        mock.assert_called_once_with("spongebob", "squarepants")


def test_refresh_db_with_options():

    with patch("salt.utils.pkg.clear_rtag", Mock()):

        # With check_update=True we will do a cmd.run to run the clean_cmd, and
        # then a separate cmd.retcode to check for updates.

        # with fromrepo
        yum_call = MagicMock()
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": yum_call, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.refresh_db(check_update=True, fromrepo="good", branch="foo")

            assert yum_call.call_count == 2
            yum_call.assert_any_call(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "clean",
                    "expire-cache",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                env={},
                ignore_retcode=True,
                output_loglevel="trace",
                python_shell=False,
            )
            yum_call.assert_any_call(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "check-update",
                    "--setopt=autocheck_running_kernel=false",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                output_loglevel="trace",
                env={},
                ignore_retcode=True,
                python_shell=False,
            )

        # without fromrepo
        yum_call = MagicMock()
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": yum_call, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.refresh_db(
                check_update=True,
                enablerepo="good",
                disablerepo="bad",
                branch="foo",
            )
            assert yum_call.call_count == 2
            yum_call.assert_any_call(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "clean",
                    "expire-cache",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                env={},
                ignore_retcode=True,
                output_loglevel="trace",
                python_shell=False,
            )
            yum_call.assert_any_call(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "check-update",
                    "--setopt=autocheck_running_kernel=false",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                output_loglevel="trace",
                env={},
                ignore_retcode=True,
                python_shell=False,
            )

        # With check_update=False we will just do a cmd.run for the clean_cmd

        # with fromrepo
        yum_call = MagicMock()
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": yum_call, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.refresh_db(check_update=False, fromrepo="good", branch="foo")
            assert yum_call.call_count == 1
            yum_call.assert_called_once_with(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "clean",
                    "expire-cache",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                env={},
                output_loglevel="trace",
                ignore_retcode=True,
                python_shell=False,
            )

        # without fromrepo
        yum_call = MagicMock()
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": yum_call, "config.get": MagicMock(return_value=False)},
        ):
            yumpkg.refresh_db(
                check_update=False,
                enablerepo="good",
                disablerepo="bad",
                branch="foo",
            )
            assert yum_call.call_count == 1
            yum_call.assert_called_once_with(
                [
                    "yum",
                    "--quiet",
                    "--assumeyes",
                    "clean",
                    "expire-cache",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                ],
                env={},
                output_loglevel="trace",
                ignore_retcode=True,
                python_shell=False,
            )


def test_install_with_options():
    parse_targets = MagicMock(return_value=({"foo": None}, "repository"))
    with patch.object(yumpkg, "list_pkgs", MagicMock(return_value={})), patch.object(
        yumpkg, "list_holds", MagicMock(return_value=[])
    ), patch.dict(
        yumpkg.__salt__, {"pkg_resource.parse_targets": parse_targets}
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):

        # with fromrepo
        cmd = MagicMock(return_value={"retcode": 0})
        with patch.dict(yumpkg.__salt__, {"cmd.run_all": cmd}):
            yumpkg.install(
                refresh=False,
                fromrepo="good",
                branch="foo",
                setopt="obsoletes=0,plugins=0",
            )
            cmd.assert_called_once_with(
                [
                    "yum",
                    "-y",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                    "--setopt",
                    "obsoletes=0",
                    "--setopt",
                    "plugins=0",
                    "install",
                    "foo",
                ],
                env={},
                output_loglevel="trace",
                python_shell=False,
                ignore_retcode=False,
                redirect_stderr=True,
            )

        # without fromrepo
        cmd = MagicMock(return_value={"retcode": 0})
        with patch.dict(yumpkg.__salt__, {"cmd.run_all": cmd}):
            yumpkg.install(
                refresh=False,
                enablerepo="good",
                disablerepo="bad",
                branch="foo",
                setopt="obsoletes=0,plugins=0",
            )
            cmd.assert_called_once_with(
                [
                    "yum",
                    "-y",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                    "--setopt",
                    "obsoletes=0",
                    "--setopt",
                    "plugins=0",
                    "install",
                    "foo",
                ],
                env={},
                output_loglevel="trace",
                python_shell=False,
                ignore_retcode=False,
                redirect_stderr=True,
            )


def test_remove_retcode_error():
    """
    Tests that we throw an error if retcode isn't 0
    """
    name = "foo"
    installed = "8:3.8.12-4.n.el7"
    list_pkgs_mock = MagicMock(
        side_effect=lambda **kwargs: {
            name: [installed] if kwargs.get("versions_as_list", False) else installed
        }
    )
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 1, "stdout": "", "stderr": "error"}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: installed}, "repository")
        ),
    }
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock), patch.dict(
        yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}
    ):
        with pytest.raises(CommandExecutionError):
            yumpkg.remove("spongebob")


def test_remove_with_epoch():
    """
    Tests that we properly identify a version containing an epoch for
    deinstallation.

    You can deinstall pkgs only without the epoch if no arch is provided:

    .. code-block:: bash

        yum remove PackageKit-yum-1.1.10-2.el7.centos
    """
    name = "foo"
    installed = "8:3.8.12-4.n.el7"
    list_pkgs_mock = MagicMock(
        side_effect=lambda **kwargs: {
            name: [installed] if kwargs.get("versions_as_list", False) else installed
        }
    )
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: installed}, "repository")
        ),
    }
    full_pkg_string = "-".join((name, installed[2:]))
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock):

        with patch.dict(yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}):
            expected = ["yum", "-y", "remove", full_pkg_string]
            yumpkg.remove(name)
            call = cmd_mock.mock_calls[0][1][0]
            assert call == expected, call


def test_remove_with_epoch_and_arch_info():
    """
    Tests that we properly identify a version containing an epoch and arch
    deinstallation.

    You can deinstall pkgs with or without epoch in combination with the arch.
    Here we test for the absence of the epoch, but the presence for the arch:

    .. code-block:: bash

        yum remove PackageKit-yum-1.1.10-2.el7.centos.x86_64
    """
    arch = "x86_64"
    name = "foo"
    name_and_arch = name + "." + arch
    installed = "8:3.8.12-4.n.el7"
    list_pkgs_mock = MagicMock(
        side_effect=lambda **kwargs: {
            name_and_arch: (
                [installed] if kwargs.get("versions_as_list", False) else installed
            )
        }
    )
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name_and_arch: installed}, "repository")
        ),
    }
    full_pkg_string = "-".join((name, installed[2:]))
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock):

        with patch.dict(yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}):
            expected = ["yum", "-y", "remove", full_pkg_string + "." + arch]
            yumpkg.remove(name)
            call = cmd_mock.mock_calls[0][1][0]
            assert call == expected, call


def test_remove_with_wildcard():
    """
    Tests that we properly identify a version containing an epoch for
    deinstallation.

    You can deinstall pkgs only without the epoch if no arch is provided:

    .. code-block:: bash

        yum remove foo*

        yum remove pkgs='[{"foo*": "8:3.8.12-4.n.el7"}]'
    """
    name = "foobarpkg"
    installed = "8:3.8.12-4.n.el7"
    list_pkgs_mock = MagicMock(
        side_effect=lambda **kwargs: {
            name: [installed] if kwargs.get("versions_as_list", False) else installed
        }
    )
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: installed}, "repository")
        ),
    }
    full_pkg_string = "-".join((name, installed[2:]))
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock):

        with patch.dict(yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}):
            expected = ["yum", "-y", "remove", full_pkg_string]
            yumpkg.remove("foo*")
            call = cmd_mock.mock_calls[0][1][0]
            assert call == expected, call

            expected = ["yum", "-y", "remove", full_pkg_string]
            yumpkg.remove(pkgs=[{"foo*": "8:3.8.12-4.n.el7"}])
            call = cmd_mock.mock_calls[0][1][0]
            assert call == expected, call


def test_install_with_epoch():
    """
    Tests that we properly identify a version containing an epoch as an
    upgrade instead of a downgrade.
    """
    name = "foo"
    old = "8:3.8.12-6.n.el7"
    new = "9:3.8.12-4.n.el7"
    list_pkgs_mock = MagicMock(
        side_effect=lambda **kwargs: {
            name: [old] if kwargs.get("versions_as_list", False) else old
        }
    )
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: new}, "repository")
        ),
    }
    full_pkg_string = "-".join((name, new[2:]))
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock):

        # Test yum
        expected = ["yum", "-y", "install", full_pkg_string]
        with patch.dict(yumpkg.__context__, {"yum_bin": "yum"}), patch.dict(
            yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}
        ):
            yumpkg.install("foo", version=new)
            call = cmd_mock.mock_calls[0][1][0]
            assert call == expected, call

        # Test dnf
        expected = [
            "dnf",
            "-y",
            "--best",
            "--allowerasing",
            "install",
            full_pkg_string,
        ]
        yumpkg.__context__.pop("yum_bin")
        cmd_mock.reset_mock()
        with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}), patch.dict(
            yumpkg.__grains__, {"os": "Fedora", "osrelease": 27}
        ):
            yumpkg.install("foo", version=new)
            call = cmd_mock.mock_calls[0][1][0]
            assert call == expected, call


def test_install_minion_error():
    patch_get_options = patch.object(yumpkg, "_get_options", MagicMock())
    patch_salt = patch.dict(
        yumpkg.__salt__,
        {
            "pkg_resource.parse_targets": MagicMock(side_effect=MinionError),
        },
    )
    with patch_get_options, patch_salt:
        with pytest.raises(CommandExecutionError):
            yumpkg.install("spongebob")


def test_install_no_pkg_params():
    patch_get_options = patch.object(yumpkg, "_get_options", MagicMock())
    parse_return = ("", "junk")
    patch_salt = patch.dict(
        yumpkg.__salt__,
        {
            "pkg_resource.parse_targets": MagicMock(return_value=parse_return),
        },
    )
    with patch_get_options, patch_salt:
        assert yumpkg.install("spongebob") == {}


# My dufus attempt... but I gave up
# def test_install_repo_fancy_versions():
#     patch_get_options = patch.object(yumpkg, "_get_options", MagicMock())
#     packages = {
#         "spongbob": "1*",
#         "squarepants": ">1.2",
#     }
#     parse_return = (packages, "repository")
#     patch_salt = patch.dict(
#         yumpkg.__salt__,
#         {
#             "pkg_resource.parse_targets": MagicMock(return_value=parse_return),
#         },
#     )
#     list_pkgs = {"vim": "1.1,1.2", "git": "2.1,2.2"}
#     list_pkgs_list = {"vim": ["1.1", "1.2"], "git": ["2.1", "2.2"]}
#     mock_list_pkgs = MagicMock(side_effect=(list_pkgs, list_pkgs_list))
#     patch_list_pkgs = patch.object(yumpkg, "list_pkgs", mock_list_pkgs)
#     with patch_get_options, patch_salt, patch_list_pkgs:
#         assert yumpkg.install("spongebob") == {}


@pytest.mark.skipif(not salt.utils.platform.is_linux(), reason="Only run on Linux")
def test_install_error_reporting():
    """
    Tests that we properly report yum/dnf errors.
    """
    name = "foo"
    old = "8:3.8.12-6.n.el7"
    new = "9:3.8.12-4.n.el7"
    list_pkgs_mock = MagicMock(
        side_effect=lambda **kwargs: {
            name: [old] if kwargs.get("versions_as_list", False) else old
        }
    )
    salt_mock = {
        "cmd.run_all": cmdmod.run_all,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: new}, "repository")
        ),
    }
    full_pkg_string = "-".join((name, new[2:]))
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock), patch.object(
        yumpkg, "_yum", MagicMock(return_value="cat")
    ):

        expected = {
            "changes": {},
            "errors": [
                "cat: invalid option -- 'y'\nTry 'cat --help' for more information."
            ],
        }
        with pytest.raises(CommandExecutionError) as exc_info:
            yumpkg.install("foo", version=new)
        assert exc_info.value.info == expected, exc_info.value.info


def test_remove_error():
    mock_salt = {"pkg_resource.parse_targets": MagicMock(side_effect=MinionError)}
    with patch.dict(yumpkg.__salt__, mock_salt):
        with pytest.raises(CommandExecutionError):
            yumpkg.remove("spongebob")


def test_remove_not_installed():
    """
    Tests that no exception raised on removing not installed package
    """
    name = "foo"
    list_pkgs_mock = MagicMock(return_value={})
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: None}, "repository")
        ),
    }
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock):

        # Test yum
        with patch.dict(yumpkg.__context__, {"yum_bin": "yum"}), patch.dict(
            yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}
        ):
            yumpkg.remove(name)
            cmd_mock.assert_not_called()

        # Test dnf
        yumpkg.__context__.pop("yum_bin")
        cmd_mock.reset_mock()
        with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}), patch.dict(
            yumpkg.__grains__, {"os": "Fedora", "osrelease": 27}
        ):
            yumpkg.remove(name)
            cmd_mock.assert_not_called()


def test_upgrade_error():
    patch_yum = patch.object(yumpkg, "_yum", return_value="yum")
    patch_get_options = patch.object(yumpkg, "_get_options")
    patch_list_pkgs = patch.object(yumpkg, "list_pkgs")
    salt_dict = {"pkg_resource.parse_targets": MagicMock(side_effect=MinionError)}
    patch_salt = patch.dict(yumpkg.__salt__, salt_dict)
    with patch_yum, patch_get_options, patch_list_pkgs, patch_salt:
        with pytest.raises(CommandExecutionError):
            yumpkg.upgrade("spongebob", refresh=False)


def test_upgrade_with_options():
    with patch.object(yumpkg, "list_pkgs", MagicMock(return_value={})), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):

        # with fromrepo
        cmd = MagicMock(return_value={"retcode": 0})
        with patch.dict(yumpkg.__salt__, {"cmd.run_all": cmd}):
            yumpkg.upgrade(
                refresh=False,
                fromrepo="good",
                exclude="kernel*",
                branch="foo",
                setopt="obsoletes=0,plugins=0",
                skip_verify=True,
            )
            cmd.assert_called_once_with(
                [
                    "yum",
                    "--quiet",
                    "-y",
                    "--disablerepo=*",
                    "--enablerepo=good",
                    "--branch=foo",
                    "--setopt",
                    "obsoletes=0",
                    "--setopt",
                    "plugins=0",
                    "--exclude=kernel*",
                    "--nogpgcheck",
                    "upgrade",
                ],
                env={},
                output_loglevel="trace",
                python_shell=False,
            )

        # with fromrepo
        cmd = MagicMock(return_value={"retcode": 1})
        with patch.dict(yumpkg.__salt__, {"cmd.run_all": cmd}):
            with pytest.raises(CommandExecutionError):
                yumpkg.upgrade(
                    refresh=False,
                    fromrepo="good",
                    exclude="kernel*",
                    branch="foo",
                    setopt="obsoletes=0,plugins=0",
                    skip_verify=True,
                )

        # without fromrepo
        cmd = MagicMock(return_value={"retcode": 0})
        with patch.dict(yumpkg.__salt__, {"cmd.run_all": cmd}):
            yumpkg.upgrade(
                refresh=False,
                enablerepo="good",
                disablerepo="bad",
                exclude="kernel*",
                branch="foo",
                setopt="obsoletes=0,plugins=0",
            )
            cmd.assert_called_once_with(
                [
                    "yum",
                    "--quiet",
                    "-y",
                    "--disablerepo=bad",
                    "--enablerepo=good",
                    "--branch=foo",
                    "--setopt",
                    "obsoletes=0",
                    "--setopt",
                    "plugins=0",
                    "--exclude=kernel*",
                    "upgrade",
                ],
                env={},
                output_loglevel="trace",
                python_shell=False,
            )


def test_upgrade_available():
    mock_return = MagicMock(return_value="non-empty value")
    patch_latest_version = patch.object(yumpkg, "latest_version", mock_return)
    with patch_latest_version:
        assert yumpkg.upgrade_available("foo") is True


def test_verify_args():
    mock_verify = MagicMock()
    with patch.dict(yumpkg.__salt__, {"lowpkg.verify": mock_verify}):
        yumpkg.verify("spongebob")
        mock_verify.assert_called_once_with("spongebob")


def test_verify_kwargs():
    mock_verify = MagicMock()
    with patch.dict(yumpkg.__salt__, {"lowpkg.verify": mock_verify}):
        yumpkg.verify(spongebob="squarepants")
        mock_verify.assert_called_once_with(spongebob="squarepants")


def test_purge_not_installed():
    """
    Tests that no exception raised on purging not installed package
    """
    name = "foo"
    list_pkgs_mock = MagicMock(return_value={})
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )
    salt_mock = {
        "cmd.run_all": cmd_mock,
        "lowpkg.version_cmp": rpm.version_cmp,
        "pkg_resource.parse_targets": MagicMock(
            return_value=({name: None}, "repository")
        ),
    }
    with patch.object(yumpkg, "list_pkgs", list_pkgs_mock), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ), patch.dict(yumpkg.__salt__, salt_mock):

        # Test yum
        with patch.dict(yumpkg.__context__, {"yum_bin": "yum"}), patch.dict(
            yumpkg.__grains__, {"os": "CentOS", "osrelease": 7}
        ):
            yumpkg.purge(name)
            cmd_mock.assert_not_called()

        # Test dnf
        yumpkg.__context__.pop("yum_bin")
        cmd_mock.reset_mock()
        with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}), patch.dict(
            yumpkg.__grains__, {"os": "Fedora", "osrelease": 27}
        ):
            yumpkg.purge(name)
            cmd_mock.assert_not_called()


def test_info_installed_with_all_versions():
    """
    Test the return information of all versions for the named package(s), installed on the system.

    :return:
    """
    run_out = {
        "virgo-dummy": [
            {
                "build_date": "2015-07-09T10:55:19Z",
                "vendor": "openSUSE Build Service",
                "description": (
                    "This is the Virgo dummy package used for testing SUSE Manager"
                ),
                "license": "GPL-2.0",
                "build_host": "sheep05",
                "url": "http://www.suse.com",
                "build_date_time_t": 1436432119,
                "relocations": "(not relocatable)",
                "source_rpm": "virgo-dummy-1.0-1.1.src.rpm",
                "install_date": "2016-02-23T16:31:57Z",
                "install_date_time_t": 1456241517,
                "summary": "Virgo dummy package",
                "version": "1.0",
                "signature": (
                    "DSA/SHA1, Thu Jul  9 08:55:33 2015, Key ID 27fa41bd8a7c64f9"
                ),
                "release": "1.1",
                "group": "Applications/System",
                "arch": "i686",
                "size": "17992",
            },
            {
                "build_date": "2015-07-09T10:15:19Z",
                "vendor": "openSUSE Build Service",
                "description": (
                    "This is the Virgo dummy package used for testing SUSE Manager"
                ),
                "license": "GPL-2.0",
                "build_host": "sheep05",
                "url": "http://www.suse.com",
                "build_date_time_t": 1436432119,
                "relocations": "(not relocatable)",
                "source_rpm": "virgo-dummy-1.0-1.1.src.rpm",
                "install_date": "2016-02-23T16:31:57Z",
                "install_date_time_t": 14562415127,
                "summary": "Virgo dummy package",
                "version": "1.0",
                "signature": (
                    "DSA/SHA1, Thu Jul  9 08:55:33 2015, Key ID 27fa41bd8a7c64f9"
                ),
                "release": "1.1",
                "group": "Applications/System",
                "arch": "x86_64",
                "size": "13124",
            },
        ],
        "libopenssl1_0_0": [
            {
                "build_date": "2015-11-04T23:20:34Z",
                "vendor": "SUSE LLC <https://www.suse.com/>",
                "description": "The OpenSSL Project is a collaborative effort.",
                "license": "OpenSSL",
                "build_host": "sheep11",
                "url": "https://www.openssl.org/",
                "build_date_time_t": 1446675634,
                "relocations": "(not relocatable)",
                "source_rpm": "openssl-1.0.1i-34.1.src.rpm",
                "install_date": "2016-02-23T16:31:35Z",
                "install_date_time_t": 1456241495,
                "summary": "Secure Sockets and Transport Layer Security",
                "version": "1.0.1i",
                "signature": (
                    "RSA/SHA256, Wed Nov  4 22:21:34 2015, Key ID 70af9e8139db7c82"
                ),
                "release": "34.1",
                "group": "Productivity/Networking/Security",
                "packager": "https://www.suse.com/",
                "arch": "x86_64",
                "size": "2576912",
            }
        ],
    }
    with patch.dict(yumpkg.__salt__, {"lowpkg.info": MagicMock(return_value=run_out)}):
        installed = yumpkg.info_installed(all_versions=True)
        # Test overall products length
        assert len(installed) == 2

        # Test multiple versions for the same package
        for pkg_name, pkg_info_list in installed.items():
            assert len(pkg_info_list) == 2 if pkg_name == "virgo-dummy" else 1
            for info in pkg_info_list:
                assert info["arch"] in ("x86_64", "i686")


def test_pkg_hold_yum():
    """
    Tests that we properly identify versionlock plugin when using yum
    for RHEL/CentOS 7 and Fedora < 22
    """

    # Test RHEL/CentOS 7
    list_pkgs_mock = {
        "yum-plugin-versionlock": "0:1.0.0-0.n.el7",
        "yum-versionlock": "0:1.0.0-0.n.el7",
    }

    cmd = MagicMock(return_value={"retcode": 0})
    with patch.object(
        yumpkg, "list_pkgs", MagicMock(return_value=list_pkgs_mock)
    ), patch.object(yumpkg, "list_holds", MagicMock(return_value=[])), patch.dict(
        yumpkg.__salt__, {"cmd.run_all": cmd}
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):
        yumpkg.hold("foo")
        cmd.assert_called_once_with(
            ["yum", "versionlock", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )

    # Test Fedora 20
    cmd = MagicMock(return_value={"retcode": 0})
    with patch.dict(yumpkg.__context__, {"yum_bin": "yum"}), patch.dict(
        yumpkg.__grains__, {"os": "Fedora", "osrelease": 20}
    ), patch.object(
        yumpkg, "list_pkgs", MagicMock(return_value=list_pkgs_mock)
    ), patch.object(
        yumpkg, "list_holds", MagicMock(return_value=[])
    ), patch.dict(
        yumpkg.__salt__, {"cmd.run_all": cmd}
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):
        yumpkg.hold("foo")
        cmd.assert_called_once_with(
            ["yum", "versionlock", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_pkg_hold_tdnf():
    """
    Tests that we raise a SaltInvocationError if we try to use
    hold-related functions on Photon OS.
    """
    with patch.dict(yumpkg.__context__, {"yum_bin": "tdnf"}):
        with pytest.raises(SaltInvocationError) as exc_info:
            yumpkg.hold("foo")


def test_hold_empty():
    """
    Tests that we raise a SaltInvocationError if nothing is passed
    """
    with patch.object(yumpkg, "_check_versionlock", MagicMock()):
        with pytest.raises(SaltInvocationError):
            yumpkg.hold()


def test_hold_pkgs_and_sources_error():
    """
    Tests that we raise a SaltInvocationError if both pkgs and sources is passed
    """
    with patch.object(yumpkg, "_check_versionlock", MagicMock()):
        with pytest.raises(SaltInvocationError):
            yumpkg.hold(pkgs=["foo", "bar"], sources=["src1", "src2"])


def test_hold_pkgs_sources():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    patch_list_holds = patch.object(yumpkg, "list_holds", MagicMock())
    mock_call_yum = MagicMock(return_value={"retcode": 0})
    patch_call_yum = patch.object(yumpkg, "_call_yum", mock_call_yum)
    patch_opts = patch.dict(yumpkg.__opts__, {"test": False})
    expected = {
        "foo": {
            "name": "foo",
            "changes": {
                "new": "hold",
                "old": "",
            },
            "result": True,
            "comment": "Package foo is now being held.",
        },
        "bar": {
            "name": "bar",
            "changes": {
                "new": "hold",
                "old": "",
            },
            "result": True,
            "comment": "Package bar is now being held.",
        },
    }
    sources = [{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]
    pkgs = ["foo", "bar"]
    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts:
        result = yumpkg.hold(sources=sources)
        assert result == expected
    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts:
        result = yumpkg.hold(pkgs=pkgs)
        assert result == expected


def test_hold_test_true():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    patch_list_holds = patch.object(yumpkg, "list_holds", MagicMock())
    mock_call_yum = MagicMock(return_value={"retcode": 0})
    patch_call_yum = patch.object(yumpkg, "_call_yum", mock_call_yum)
    patch_opts = patch.dict(yumpkg.__opts__, {"test": True})
    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts:
        result = yumpkg.hold(name="foo")
    expected = {
        "foo": {
            "name": "foo",
            "changes": {},
            "result": None,
            "comment": "Package foo is set to be held.",
        },
    }
    assert result == expected


def test_hold_fails():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    patch_list_holds = patch.object(yumpkg, "list_holds", MagicMock())
    mock_call_yum = MagicMock(return_value={"retcode": 1})
    patch_call_yum = patch.object(yumpkg, "_call_yum", mock_call_yum)
    patch_opts = patch.dict(yumpkg.__opts__, {"test": False})
    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts:
        result = yumpkg.hold(name="foo")
    expected = {
        "foo": {
            "name": "foo",
            "changes": {},
            "result": False,
            "comment": "Package foo was unable to be held.",
        },
    }
    assert result == expected


def test_hold_already_held():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    mock_list_holds = MagicMock(return_value=["foo"])
    patch_list_holds = patch.object(yumpkg, "list_holds", mock_list_holds)
    with patch_versionlock, patch_list_holds:
        result = yumpkg.hold(name="foo")
    expected = {
        "foo": {
            "name": "foo",
            "changes": {},
            "result": True,
            "comment": "Package foo is already set to be held.",
        },
    }
    assert result == expected


def test_unhold_empty():
    """
    Tests that we raise a SaltInvocationError if nothing is passed
    """
    with patch.object(yumpkg, "_check_versionlock", MagicMock()):
        with pytest.raises(SaltInvocationError):
            yumpkg.unhold()


def test_unhold_pkgs_and_sources_error():
    """
    Tests that we raise a SaltInvocationError if both pkgs and sources is passed
    """
    with patch.object(yumpkg, "_check_versionlock", MagicMock()):
        with pytest.raises(SaltInvocationError):
            yumpkg.unhold(pkgs=["foo", "bar"], sources=["src1", "src2"])


def test_unhold_pkgs_sources():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    mock_list_holds = MagicMock(return_value=["foo", "bar"])
    patch_list_holds = patch.object(yumpkg, "list_holds", mock_list_holds)
    mock_call_yum = MagicMock(return_value={"retcode": 0})
    patch_call_yum = patch.object(yumpkg, "_call_yum", mock_call_yum)
    patch_opts = patch.dict(yumpkg.__opts__, {"test": False})
    patch_yum = patch.object(yumpkg, "_yum", MagicMock(return_value="dnf"))
    expected = {
        "foo": {
            "name": "foo",
            "changes": {
                "new": "",
                "old": "hold",
            },
            "result": True,
            "comment": "Package foo is no longer held.",
        },
        "bar": {
            "name": "bar",
            "changes": {
                "new": "",
                "old": "hold",
            },
            "result": True,
            "comment": "Package bar is no longer held.",
        },
    }
    sources = [{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]
    pkgs = ["foo", "bar"]
    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts, patch_yum:
        result = yumpkg.unhold(sources=sources)
        assert result == expected

    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts, patch_yum:
        result = yumpkg.unhold(pkgs=pkgs)
        assert result == expected


def test_unhold_test_true():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    mock_list_holds = MagicMock(return_value=["foo"])
    patch_list_holds = patch.object(yumpkg, "list_holds", mock_list_holds)
    patch_opts = patch.dict(yumpkg.__opts__, {"test": True})
    patch_yum = patch.object(yumpkg, "_yum", MagicMock(return_value="dnf"))
    with patch_versionlock, patch_list_holds, patch_opts, patch_yum:
        result = yumpkg.unhold(name="foo")
    expected = {
        "foo": {
            "name": "foo",
            "changes": {},
            "result": None,
            "comment": "Package foo is set to be unheld.",
        },
    }
    assert result == expected


def test_unhold_fails():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    mock_list_holds = MagicMock(return_value=["foo"])
    patch_list_holds = patch.object(yumpkg, "list_holds", mock_list_holds)
    mock_call_yum = MagicMock(return_value={"retcode": 1})
    patch_call_yum = patch.object(yumpkg, "_call_yum", mock_call_yum)
    patch_opts = patch.dict(yumpkg.__opts__, {"test": False})
    patch_yum = patch.object(yumpkg, "_yum", MagicMock(return_value="dnf"))
    with patch_versionlock, patch_list_holds, patch_call_yum, patch_opts, patch_yum:
        result = yumpkg.unhold(name="foo")
    expected = {
        "foo": {
            "name": "foo",
            "changes": {},
            "result": False,
            "comment": "Package foo was unable to be unheld.",
        },
    }
    assert result == expected


def test_unhold_already_unheld():
    patch_versionlock = patch.object(yumpkg, "_check_versionlock", MagicMock())
    mock_list_holds = MagicMock(return_value=[])
    patch_list_holds = patch.object(yumpkg, "list_holds", mock_list_holds)
    with patch_versionlock, patch_list_holds:
        result = yumpkg.unhold(name="foo")
    expected = {
        "foo": {
            "name": "foo",
            "changes": {},
            "result": True,
            "comment": "Package foo is not being held.",
        },
    }
    assert result == expected


def test_owner_empty():
    assert yumpkg.owner() == ""


def test_owner_not_owned():
    mock_stdout = MagicMock(return_value="not owned")
    expected = {
        "/fake/path1": "",
        "/fake/path2": "",
    }
    with patch.dict(yumpkg.__salt__, {"cmd.run_stdout": mock_stdout}):
        result = yumpkg.owner(*expected.keys())
        assert result == expected


def test_owner_not_owned_single():
    mock_stdout = MagicMock(return_value="not owned")
    with patch.dict(yumpkg.__salt__, {"cmd.run_stdout": mock_stdout}):
        result = yumpkg.owner("/fake/path")
        assert result == ""


def test_parse_repo_file_error():
    mock_read = MagicMock(
        side_effect=configparser.MissingSectionHeaderError("spongebob", 101, "test2")
    )
    with patch.object(configparser.ConfigParser, "read", mock_read):
        result = yumpkg._parse_repo_file("spongebob")
        assert result == ("", {})


def test_pkg_hold_dnf():
    """
    Tests that we properly identify versionlock plugin when using dnf
    for RHEL/CentOS 8 and Fedora >= 22
    """

    # Test RHEL/CentOS 8
    list_pkgs_mock = {
        "python2-dnf-plugin-versionlock": "0:1.0.0-0.n.el8",
        "python3-dnf-plugin-versionlock": "0:1.0.0-0.n.el8",
    }

    yumpkg.__context__.pop("yum_bin")
    cmd = MagicMock(return_value={"retcode": 0})
    with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}), patch.dict(
        yumpkg.__grains__, {"osmajorrelease": 8}
    ), patch.object(
        yumpkg, "list_pkgs", MagicMock(return_value=list_pkgs_mock)
    ), patch.object(
        yumpkg, "list_holds", MagicMock(return_value=[])
    ), patch.dict(
        yumpkg.__salt__, {"cmd.run_all": cmd}
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):
        yumpkg.hold("foo")
        cmd.assert_called_once_with(
            ["dnf", "versionlock", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )

    # Test Fedora 26+
    cmd = MagicMock(return_value={"retcode": 0})
    with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}), patch.dict(
        yumpkg.__grains__, {"os": "Fedora", "osrelease": 26}
    ), patch.object(
        yumpkg, "list_pkgs", MagicMock(return_value=list_pkgs_mock)
    ), patch.object(
        yumpkg, "list_holds", MagicMock(return_value=[])
    ), patch.dict(
        yumpkg.__salt__, {"cmd.run_all": cmd}
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):
        yumpkg.hold("foo")
        cmd.assert_called_once_with(
            ["dnf", "versionlock", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )

    # Test Fedora 22-25
    list_pkgs_mock = {
        "python-dnf-plugins-extras-versionlock": "0:1.0.0-0.n.el8",
        "python3-dnf-plugins-extras-versionlock": "0:1.0.0-0.n.el8",
    }

    cmd = MagicMock(return_value={"retcode": 0})
    with patch.dict(yumpkg.__context__, {"yum_bin": "dnf"}), patch.dict(
        yumpkg.__grains__, {"os": "Fedora", "osrelease": 25}
    ), patch.object(
        yumpkg, "list_pkgs", MagicMock(return_value=list_pkgs_mock)
    ), patch.object(
        yumpkg, "list_holds", MagicMock(return_value=[])
    ), patch.dict(
        yumpkg.__salt__, {"cmd.run_all": cmd}
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):
        yumpkg.hold("foo")
        cmd.assert_called_once_with(
            ["dnf", "versionlock", "foo"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_get_yum_config_no_config():
    with patch("os.path.exists", MagicMock(return_value=False)):
        with pytest.raises(CommandExecutionError):
            yumpkg._get_yum_config()


def test_get_yum_config(grains):
    os_family = grains["os_family"]
    if os_family in ("Arch", "Debian", "Suse"):
        pytest.skip(f"{os_family} does not have yum.conf")
    setting = "cache_dir"
    if os_family == "RedHat":
        # This one seems to be in all of them...
        # If this ever breaks in the future, we'll need to get more specific
        # than os_family
        setting = "installonly_limit"
    result = yumpkg._get_yum_config()
    assert setting in result


def test_get_yum_config_value_none(grains):
    os_family = grains["os_family"]
    if os_family in ("Arch", "Debian", "Suse"):
        pytest.skip(f"{os_family} does not have yum.conf")
    result = yumpkg._get_yum_config_value("spongebob")
    assert result is None


def test_get_yum_config_unreadable():
    with patch.object(
        configparser.ConfigParser, "read", MagicMock(side_effect=OSError)
    ):
        with pytest.raises(CommandExecutionError):
            yumpkg._get_yum_config()


def test_get_yum_config_no_main(caplog):
    mock_false = MagicMock(return_value=False)
    with patch.object(configparser.ConfigParser, "read"), patch.object(
        configparser.ConfigParser, "has_section", mock_false
    ), patch("os.path.exists", MagicMock(return_value=True)):
        yumpkg._get_yum_config()
        assert "Could not find [main] section" in caplog.text


def test_normalize_basedir_str():
    basedir = "/etc/yum/yum.conf,/etc/yum.conf"
    result = yumpkg._normalize_basedir(basedir)
    assert result == ["/etc/yum/yum.conf", "/etc/yum.conf"]


def test_normalize_basedir_error():
    basedir = 1
    with pytest.raises(SaltInvocationError):
        yumpkg._normalize_basedir(basedir)


def test_normalize_name_noarch():
    assert yumpkg.normalize_name("zsh.noarch") == "zsh"


def test_latest_version_no_names():
    assert yumpkg.latest_version() == ""


def test_latest_version_nonzero_retcode():
    yum_ret = {"retcode": 1, "stderr": "some error"}
    mock_call_yum = MagicMock(return_value=yum_ret)
    patch_call_yum = patch.object(yumpkg, "_call_yum", mock_call_yum)
    list_pkgs_ret = {"foo": "1.1", "bar": "2.2"}
    mock_list_pkgs = MagicMock(return_value=list_pkgs_ret)
    patch_list_pkgs = patch.object(yumpkg, "list_pkgs", mock_list_pkgs)
    patch_get_options = patch.object(yumpkg, "_get_options", MagicMock())
    patch_refresh_db = patch.object(yumpkg, "refresh_db", MagicMock())
    with patch_list_pkgs, patch_call_yum, patch_get_options, patch_refresh_db:
        assert yumpkg.latest_version("foo", "bar") == {"foo": "", "bar": ""}


def test_group_info():
    """
    Test yumpkg.group_info parsing
    """
    expected = {
        "conditional": [],
        "default": ["qgnomeplatform", "xdg-desktop-portal-gtk"],
        "description": (
            "GNOME is a highly intuitive and user friendly desktop environment."
        ),
        "group": "GNOME",
        "id": "gnome-desktop",
        "mandatory": [
            "NetworkManager-libreswan-gnome",
            "PackageKit-command-not-found",
            "PackageKit-gtk3-module",
            "abrt-desktop",
            "at-spi2-atk",
            "at-spi2-core",
            "avahi",
            "baobab",
            "caribou",
            "caribou-gtk2-module",
            "caribou-gtk3-module",
            "cheese",
            "chrome-gnome-shell",
            "compat-cheese314",
            "control-center",
            "dconf",
            "empathy",
            "eog",
            "evince",
            "evince-nautilus",
            "file-roller",
            "file-roller-nautilus",
            "firewall-config",
            "firstboot",
            "fprintd-pam",
            "gdm",
            "gedit",
            "glib-networking",
            "gnome-bluetooth",
            "gnome-boxes",
            "gnome-calculator",
            "gnome-classic-session",
            "gnome-clocks",
            "gnome-color-manager",
            "gnome-contacts",
            "gnome-dictionary",
            "gnome-disk-utility",
            "gnome-font-viewer",
            "gnome-getting-started-docs",
            "gnome-icon-theme",
            "gnome-icon-theme-extras",
            "gnome-icon-theme-symbolic",
            "gnome-initial-setup",
            "gnome-packagekit",
            "gnome-packagekit-updater",
            "gnome-screenshot",
            "gnome-session",
            "gnome-session-xsession",
            "gnome-settings-daemon",
            "gnome-shell",
            "gnome-software",
            "gnome-system-log",
            "gnome-system-monitor",
            "gnome-terminal",
            "gnome-terminal-nautilus",
            "gnome-themes-standard",
            "gnome-tweak-tool",
            "gnome-user-docs",
            "gnome-weather",
            "gucharmap",
            "gvfs-afc",
            "gvfs-afp",
            "gvfs-archive",
            "gvfs-fuse",
            "gvfs-goa",
            "gvfs-gphoto2",
            "gvfs-mtp",
            "gvfs-smb",
            "initial-setup-gui",
            "libcanberra-gtk2",
            "libcanberra-gtk3",
            "libproxy-mozjs",
            "librsvg2",
            "libsane-hpaio",
            "metacity",
            "mousetweaks",
            "nautilus",
            "nautilus-sendto",
            "nm-connection-editor",
            "orca",
            "redhat-access-gui",
            "sane-backends-drivers-scanners",
            "seahorse",
            "setroubleshoot",
            "sushi",
            "totem",
            "totem-nautilus",
            "vinagre",
            "vino",
            "xdg-user-dirs-gtk",
            "yelp",
        ],
        "optional": [
            "",
            "alacarte",
            "dconf-editor",
            "dvgrab",
            "fonts-tweak-tool",
            "gconf-editor",
            "gedit-plugins",
            "gnote",
            "libappindicator-gtk3",
            "seahorse-nautilus",
            "seahorse-sharing",
            "vim-X11",
            "xguest",
        ],
        "type": "package group",
    }
    cmd_out = """Group: GNOME
     Group-Id: gnome-desktop
     Description: GNOME is a highly intuitive and user friendly desktop environment.
     Mandatory Packages:
       =NetworkManager-libreswan-gnome
       =PackageKit-command-not-found
       =PackageKit-gtk3-module
        abrt-desktop
       =at-spi2-atk
       =at-spi2-core
       =avahi
       =baobab
       -caribou
       -caribou-gtk2-module
       -caribou-gtk3-module
       =cheese
       =chrome-gnome-shell
       =compat-cheese314
       =control-center
       =dconf
       =empathy
       =eog
       =evince
       =evince-nautilus
       =file-roller
       =file-roller-nautilus
       =firewall-config
       =firstboot
        fprintd-pam
       =gdm
       =gedit
       =glib-networking
       =gnome-bluetooth
       =gnome-boxes
       =gnome-calculator
       =gnome-classic-session
       =gnome-clocks
       =gnome-color-manager
       =gnome-contacts
       =gnome-dictionary
       =gnome-disk-utility
       =gnome-font-viewer
       =gnome-getting-started-docs
       =gnome-icon-theme
       =gnome-icon-theme-extras
       =gnome-icon-theme-symbolic
       =gnome-initial-setup
       =gnome-packagekit
       =gnome-packagekit-updater
       =gnome-screenshot
       =gnome-session
       =gnome-session-xsession
       =gnome-settings-daemon
       =gnome-shell
       =gnome-software
       =gnome-system-log
       =gnome-system-monitor
       =gnome-terminal
       =gnome-terminal-nautilus
       =gnome-themes-standard
       =gnome-tweak-tool
       =gnome-user-docs
       =gnome-weather
       =gucharmap
       =gvfs-afc
       =gvfs-afp
       =gvfs-archive
       =gvfs-fuse
       =gvfs-goa
       =gvfs-gphoto2
       =gvfs-mtp
       =gvfs-smb
        initial-setup-gui
       =libcanberra-gtk2
       =libcanberra-gtk3
       =libproxy-mozjs
       =librsvg2
       =libsane-hpaio
       =metacity
       =mousetweaks
       =nautilus
       =nautilus-sendto
       =nm-connection-editor
       =orca
       -redhat-access-gui
       =sane-backends-drivers-scanners
       =seahorse
       =setroubleshoot
       =sushi
       =totem
       =totem-nautilus
       =vinagre
       =vino
       =xdg-user-dirs-gtk
       =yelp
     Default Packages:
       =qgnomeplatform
       =xdg-desktop-portal-gtk
     Optional Packages:
       alacarte
       dconf-editor
       dvgrab
       fonts-tweak-tool
       gconf-editor
       gedit-plugins
       gnote
       libappindicator-gtk3
       seahorse-nautilus
       seahorse-sharing
       vim-X11
       xguest
    """
    with patch.dict(
        yumpkg.__salt__, {"cmd.run_stdout": MagicMock(return_value=cmd_out)}
    ):
        info = yumpkg.group_info("@gnome-desktop")
        assert info == expected


def test_group_install():
    group_info = (
        {
            "default": ["spongebob", "gary", "patrick"],
            "mandatory": ["spongebob", "gary"],
        },
        {
            "default": ["mr_krabs", "pearl_krabs", "plankton"],
            "mandatory": ["mr_krabs", "pearl_krabs"],
        },
    )
    mock_info = MagicMock(side_effect=group_info)
    patch_info = patch.object(yumpkg, "group_info", mock_info)
    mock_list_pkgs = MagicMock(return_value=[])
    patch_list_pkgs = patch.object(yumpkg, "list_pkgs", mock_list_pkgs)
    patch_install = patch.object(yumpkg, "install", MagicMock())
    expected = [
        "mr_krabs",
        "gary",
        "pearl_krabs",
        "plankton",
        "spongebob",
        "patrick",
    ]
    with patch_info, patch_list_pkgs, patch_install:
        yumpkg.group_install("spongebob,mr_krabs")
        _, kwargs = yumpkg.install.call_args
        assert kwargs["pkgs"].sort() == expected.sort()


def test_group_install_include():
    group_info = (
        {
            "default": ["spongebob", "gary", "patrick"],
            "mandatory": ["spongebob", "gary"],
        },
        {
            "default": ["mr_krabs", "pearl_krabs", "plankton"],
            "mandatory": ["mr_krabs", "pearl_krabs"],
        },
    )
    mock_info = MagicMock(side_effect=group_info)
    patch_info = patch.object(yumpkg, "group_info", mock_info)
    mock_list_pkgs = MagicMock(return_value=[])
    patch_list_pkgs = patch.object(yumpkg, "list_pkgs", mock_list_pkgs)
    patch_install = patch.object(yumpkg, "install", MagicMock())
    expected = [
        "mr_krabs",
        "gary",
        "pearl_krabs",
        "plankton",
        "spongebob",
        "patrick",
    ]
    with patch_info, patch_list_pkgs, patch_install:
        yumpkg.group_install("spongebob,mr_krabs", include="napoleon")
        _, kwargs = yumpkg.install.call_args
        expected.append("napoleon")
        assert kwargs["pkgs"].sort() == expected.sort()


def test_group_install_skip():
    group_info = (
        {
            "default": ["spongebob", "gary", "patrick"],
            "mandatory": ["spongebob", "gary"],
        },
        {
            "default": ["mr_krabs", "pearl_krabs", "plankton"],
            "mandatory": ["mr_krabs", "pearl_krabs"],
        },
    )
    mock_info = MagicMock(side_effect=group_info)
    patch_info = patch.object(yumpkg, "group_info", mock_info)
    mock_list_pkgs = MagicMock(return_value=[])
    patch_list_pkgs = patch.object(yumpkg, "list_pkgs", mock_list_pkgs)
    patch_install = patch.object(yumpkg, "install", MagicMock())
    expected = [
        "mr_krabs",
        "gary",
        "pearl_krabs",
        "spongebob",
        "patrick",
    ]
    with patch_info, patch_list_pkgs, patch_install:
        yumpkg.group_install("spongebob,mr_krabs", skip="plankton")
        _, kwargs = yumpkg.install.call_args
        assert kwargs["pkgs"].sort() == expected.sort()


def test_group_install_already_present():
    group_info = (
        {
            "default": ["spongebob", "gary", "patrick"],
            "mandatory": ["spongebob", "gary"],
        },
        {
            "default": ["mr_krabs", "pearl_krabs", "plankton"],
            "mandatory": ["mr_krabs", "pearl_krabs"],
        },
    )
    mock_info = MagicMock(side_effect=group_info)
    patch_info = patch.object(yumpkg, "group_info", mock_info)
    patch_install = patch.object(yumpkg, "install", MagicMock())
    expected = [
        "mr_krabs",
        "gary",
        "pearl_krabs",
        "plankton",
        "spongebob",
        "patrick",
    ]
    mock_list_pkgs = MagicMock(return_value=expected)
    patch_list_pkgs = patch.object(yumpkg, "list_pkgs", mock_list_pkgs)
    with patch_info, patch_list_pkgs, patch_install:
        assert yumpkg.group_install("spongebob,mr_krabs") == {}


def test_group_install_no_groups():
    with pytest.raises(SaltInvocationError):
        yumpkg.group_install(None)


def test_group_install_non_list_groups():
    with pytest.raises(SaltInvocationError):
        yumpkg.group_install(1)


def test_group_install_non_list_skip():
    with pytest.raises(SaltInvocationError):
        yumpkg.group_install(name="string", skip=1)


def test_group_install_non_list_include():
    with pytest.raises(SaltInvocationError):
        yumpkg.group_install(name="string", include=1)


def test_group_list():
    mock_out = MagicMock(
        return_value="""\
Available Environment Groups:
   Spongebob
   Squarepants
Installed Environment Groups:
   Patrick
Installed Groups:
   Squidward
   Sandy
Available Groups:
   Mr. Krabs
   Plankton
Available Language Groups:
   Gary the Snail [sb]\
    """
    )
    patch_grplist = patch.dict(yumpkg.__salt__, {"cmd.run_stdout": mock_out})
    with patch_grplist:
        result = yumpkg.group_list()
    expected = {
        "installed": ["Squidward", "Sandy"],
        "available": ["Mr. Krabs", "Plankton"],
        "installed environments": ["Patrick"],
        "available environments": ["Spongebob", "Squarepants"],
        "available languages": {
            "Gary the Snail [sb]": {
                "language": "sb",
                "name": "Gary the Snail",
            },
        },
    }
    assert result == expected


def test_get_repo_with_existent_repo(list_repos_var):
    """
    Test get_repo with an existent repository
    Expected return is a populated dictionary
    """
    repo = "base-source"
    kwargs = {
        "baseurl": "http://vault.centos.org/centos/$releasever/os/Source/",
        "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
        "name": "CentOS-$releasever - Base Sources",
        "enabled": True,
    }
    parse_repo_file_return = (
        "",
        {
            "base-source": {
                "baseurl": "http://vault.centos.org/centos/$releasever/os/Source/",
                "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
                "name": "CentOS-$releasever - Base Sources",
                "enabled": "1",
            }
        },
    )
    expected = {
        "baseurl": "http://vault.centos.org/centos/$releasever/os/Source/",
        "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
        "name": "CentOS-$releasever - Base Sources",
        "enabled": "1",
    }
    patch_list_repos = patch.object(
        yumpkg, "list_repos", autospec=True, return_value=list_repos_var
    )
    patch_parse_repo_file = patch.object(
        yumpkg,
        "_parse_repo_file",
        autospec=True,
        return_value=parse_repo_file_return,
    )

    with patch_list_repos, patch_parse_repo_file:
        ret = yumpkg.get_repo(repo, **kwargs)
    assert ret == expected, ret


def test_get_repo_with_non_existent_repo(list_repos_var):
    """
    Test get_repo with an non existent repository
    Expected return is an empty dictionary
    """
    repo = "non-existent-repository"
    kwargs = {
        "baseurl": "http://fake.centos.org/centos/$releasever/os/Non-Existent/",
        "gpgkey": "file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7",
        "name": "CentOS-$releasever - Non-Existent Repository",
        "enabled": True,
    }
    expected = {}
    patch_list_repos = patch.object(
        yumpkg, "list_repos", autospec=True, return_value=list_repos_var
    )

    with patch_list_repos:
        ret = yumpkg.get_repo(repo, **kwargs)
    assert ret == expected, ret


def test_pkg_update_dnf():
    """
    Tests that the proper CLI options are added when obsoletes=False
    """
    name = "foo"
    old = "1.2.2-1.fc31"
    new = "1.2.3-1.fc31"
    cmd_mock = MagicMock(return_value={"retcode": 0})
    list_pkgs_mock = MagicMock(side_effect=[{name: old}, {name: new}])
    parse_targets_mock = MagicMock(return_value=({"foo": None}, "repository"))
    with patch.dict(
        yumpkg.__salt__,
        {"cmd.run_all": cmd_mock, "pkg_resource.parse_targets": parse_targets_mock},
    ), patch.object(yumpkg, "refresh_db", MagicMock()), patch.object(
        yumpkg, "list_pkgs", list_pkgs_mock
    ), patch.object(
        yumpkg, "_yum", MagicMock(return_value="dnf")
    ), patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=False)
    ):
        ret = yumpkg.update(name, setopt="obsoletes=0,plugins=0")
        expected = {name: {"old": old, "new": new}}
        assert ret == expected, ret

        cmd_mock.assert_called_once_with(
            [
                "dnf",
                "--quiet",
                "-y",
                "--setopt",
                "plugins=0",
                "--setopt",
                "obsoletes=False",
                "upgrade",
                "foo",
            ],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_call_yum_default():
    """
    Call default Yum/Dnf.
    :return:
    """
    with patch.dict(yumpkg.__context__, {"yum_bin": "fake-yum"}):
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=False)},
        ):
            yumpkg._call_yum(["-y", "--do-something"])  # pylint: disable=W0106
            yumpkg.__salt__["cmd.run_all"].assert_called_once_with(
                ["fake-yum", "-y", "--do-something"],
                env={},
                output_loglevel="trace",
                python_shell=False,
            )


def test_call_yum_in_scope():
    """
    Call Yum/Dnf within the scope.
    :return:
    """
    with patch(
        "salt.utils.systemd.has_scope", MagicMock(return_value=True)
    ), patch.dict(yumpkg.__context__, {"yum_bin": "fake-yum"}), patch.dict(
        yumpkg.__salt__,
        {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=True)},
    ):

        yumpkg._call_yum(["-y", "--do-something"])  # pylint: disable=W0106
        yumpkg.__salt__["cmd.run_all"].assert_called_once_with(
            ["systemd-run", "--scope", "fake-yum", "-y", "--do-something"],
            env={},
            output_loglevel="trace",
            python_shell=False,
        )


def test_call_yum_with_kwargs():
    """
    Call Yum/Dnf with the optinal keyword arguments.
    :return:
    """
    with patch.dict(yumpkg.__context__, {"yum_bin": "fake-yum"}):
        with patch.dict(
            yumpkg.__salt__,
            {"cmd.run_all": MagicMock(), "config.get": MagicMock(return_value=False)},
        ):
            yumpkg._call_yum(
                ["-y", "--do-something"],
                python_shell=True,
                output_loglevel="quiet",
                ignore_retcode=False,
                username="Darth Vader",
            )  # pylint: disable=W0106
            yumpkg.__salt__["cmd.run_all"].assert_called_once_with(
                ["fake-yum", "-y", "--do-something"],
                env={},
                ignore_retcode=False,
                output_loglevel="quiet",
                python_shell=True,
                username="Darth Vader",
            )


@pytest.mark.skipif(not salt.utils.systemd.booted(), reason="Requires systemd")
def test_services_need_restart():
    """
    Test that dnf needs-restarting output is parsed and
    salt.utils.systemd.pid_to_service is called as expected.
    """
    expected = ["firewalld", "salt-minion"]

    dnf_mock = Mock(
        return_value="123 : /usr/bin/firewalld\n456 : /usr/bin/salt-minion\n"
    )
    systemd_mock = Mock(side_effect=["firewalld", "salt-minion"])
    with patch("salt.modules.yumpkg._yum", Mock(return_value="dnf")):
        with patch.dict(yumpkg.__salt__, {"cmd.run_stdout": dnf_mock}), patch(
            "salt.utils.systemd.pid_to_service", systemd_mock
        ):
            assert sorted(yumpkg.services_need_restart()) == expected
            systemd_mock.assert_has_calls([call("123"), call("456")])


def test_services_need_restart_requires_systemd():
    """Test that yumpkg.services_need_restart raises an error if systemd is unavailable."""
    with patch("salt.modules.yumpkg._yum", Mock(return_value="dnf")):
        with patch("salt.utils.systemd.booted", Mock(return_value=False)):
            pytest.raises(CommandExecutionError, yumpkg.services_need_restart)


def test_services_need_restart_requires_dnf():
    """Test that yumpkg.services_need_restart raises an error if DNF is unavailable."""
    with patch("salt.modules.yumpkg._yum", Mock(return_value="yum")):
        pytest.raises(CommandExecutionError, yumpkg.services_need_restart)


def test_services_need_restart_no_dnf_output():
    patch_yum = patch("salt.modules.yumpkg._yum", Mock(return_value="dnf"))
    patch_booted = patch("salt.utils.systemd.booted", Mock(return_value=True))
    mock_run_stdout = MagicMock(return_value="")
    patch_run_stdout = patch.dict(yumpkg.__salt__, {"cmd.run_stdout": mock_run_stdout})
    with patch_yum, patch_booted, patch_run_stdout:
        assert yumpkg.services_need_restart() == []


def test_61003_pkg_should_not_fail_when_target_not_in_old_pkgs():
    patch_list_pkgs = patch(
        "salt.modules.yumpkg.list_pkgs", return_value={}, autospec=True
    )
    patch_salt = patch.dict(
        yumpkg.__salt__,
        {
            "pkg_resource.parse_targets": Mock(
                return_value=[
                    {
                        "fnord-this-is-not-actually-a-package": "fnord-this-is-not-actually-a-package-1.2.3"
                    }
                ]
            )
        },
    )
    with patch_list_pkgs, patch_salt:
        # During the 3004rc1 we discoverd that if list_pkgs was missing
        # packages that were returned by parse_targets that yumpkg.remove would
        # catch on fire.  This ensures that won't go undetected again.
        yumpkg.remove()


@pytest.mark.parametrize(
    "new,full_pkg_string",
    (
        (42, "fnord-42"),
        (12, "fnord-12"),
        ("42:1.2.3", "fnord-1.2.3"),
    ),
)
def test_59705_version_as_accidental_float_should_become_text(
    new, full_pkg_string, yum_and_dnf
):
    name = "fnord"
    expected_cmd = yum_and_dnf + ["install"]
    if expected_cmd[0] == "dnf5":
        expected_cmd += ["--best", "--allowerasing"]
    expected_cmd += [full_pkg_string]
    cmd_mock = MagicMock(
        return_value={"pid": 12345, "retcode": 0, "stdout": "", "stderr": ""}
    )

    def fake_parse(*args, **kwargs):
        return {name: kwargs["version"]}, "repository"

    patch_yum_salt = patch.dict(
        yumpkg.__salt__,
        {
            "cmd.run": MagicMock(return_value=""),
            "cmd.run_all": cmd_mock,
            "lowpkg.version_cmp": rpm.version_cmp,
            "pkg_resource.parse_targets": fake_parse,
            "pkg_resource.format_pkg_list": pkg_resource.format_pkg_list,
        },
    )
    patch_systemd = patch("salt.utils.systemd.has_scope", MagicMock(return_value=False))
    with patch_systemd, patch_yum_salt:
        yumpkg.install("fnord", version=new)
        call = cmd_mock.mock_calls[0][1][0]
        assert call == expected_cmd
