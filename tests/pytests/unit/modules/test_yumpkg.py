import logging
import os

import salt.modules.cmdmod as cmdmod
import salt.modules.pkg_resource as pkg_resource
import salt.modules.rpm_lowpkg as rpm
import salt.modules.yumpkg as yumpkg
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, Mock, call, patch

try:
    import pytest
except ImportError:
    pytest = None

log = logging.getLogger(__name__)


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


@pytest.fixture
def configure_loader_modules():

    return {
        yumpkg: {
            "__context__": {"yum_bin": "yum"},
            "__grains__": {
                "osarch": "x86_64",
                "os": "CentOS",
                "os_family": "RedHat",
                "osmajorrelease": 7,
            },
        },
        pkg_resource: {},
    }


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
                        pytest.fail("repo '{}' not checked".format(repo))


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
            name_and_arch: [installed]
            if kwargs.get("versions_as_list", False)
            else installed
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
                    "upgrade",
                ],
                env={},
                output_loglevel="trace",
                python_shell=False,
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


@pytest.mark.skipif(not yumpkg.HAS_YUM, reason="Could not import yum")
def test_yum_base_error():
    with patch("yum.YumBase") as mock_yum_yumbase:
        mock_yum_yumbase.side_effect = CommandExecutionError
        with pytest.raises(CommandExecutionError):
            yumpkg._get_yum_config()


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


@patch("salt.utils.systemd.has_scope", MagicMock(return_value=True))
def test_call_yum_in_scope():
    """
    Call Yum/Dnf within the scope.
    :return:
    """
    with patch.dict(yumpkg.__context__, {"yum_bin": "fake-yum"}):
        with patch.dict(
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
