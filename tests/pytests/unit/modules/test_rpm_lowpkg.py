"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import textwrap

import pytest

import salt.modules.cmdmod
import salt.modules.rpm_lowpkg as rpm
import salt.utils.path
from tests.support.mock import MagicMock, patch

try:
    import rpm

    HAS_RPM = True
except ImportError:
    HAS_RPM = False
# pylint: enable=unused-import


def _called_with_root(mock):
    cmd = " ".join(mock.call_args[0][0])
    return cmd.startswith("rpm --root /")


@pytest.fixture
def configure_loader_modules():
    return {rpm: {"rpm": MagicMock(return_value=MagicMock)}}


def test___virtual___openeuler():
    patch_which = patch("salt.utils.path.which", return_value=True)
    with patch.dict(
        rpm.__grains__, {"os": "openEuler", "os_family": "openEuler"}
    ), patch_which:
        assert rpm.__virtual__() == "lowpkg"


def test___virtual___issabel_pbx():
    patch_which = patch("salt.utils.path.which", return_value=True)
    with patch.dict(
        rpm.__grains__, {"os": "Issabel Pbx", "os_family": "IssabeL PBX"}
    ), patch_which:
        assert rpm.__virtual__() == "lowpkg"


def test___virtual___virtuozzo():
    patch_which = patch("salt.utils.path.which", return_value=True)
    with patch.dict(
        rpm.__grains__, {"os": "virtuozzo", "os_family": "VirtuoZZO"}
    ), patch_which:
        assert rpm.__virtual__() == "lowpkg"


def test___virtual___with_no_rpm():
    patch_which = patch("salt.utils.path.which", return_value=False)
    ret = rpm.__virtual__()
    assert isinstance(ret, tuple)
    assert ret[0] is False


# 'list_pkgs' function tests: 2


def test_list_pkgs():
    """
    Test if it list the packages currently installed in a dict
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm.__salt__, {"cmd.run": mock}):
        assert rpm.list_pkgs() == {}
        assert not _called_with_root(mock)


def test_list_pkgs_root():
    """
    Test if it list the packages currently installed in a dict,
    called with root parameter
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm.__salt__, {"cmd.run": mock}):
        rpm.list_pkgs(root="/")
        assert _called_with_root(mock)


# 'verify' function tests: 2


def test_verify():
    """
    Test if it runs an rpm -Va on a system, and returns the
    results in a dict
    """
    mock = MagicMock(
        return_value={"stdout": "", "stderr": "", "retcode": 0, "pid": 12345}
    )
    with patch.dict(rpm.__salt__, {"cmd.run_all": mock}):
        assert rpm.verify("httpd") == {}
        assert not _called_with_root(mock)


def test_verify_root():
    """
    Test if it runs an rpm -Va on a system, and returns the
    results in a dict, called with root parameter
    """
    mock = MagicMock(
        return_value={"stdout": "", "stderr": "", "retcode": 0, "pid": 12345}
    )
    with patch.dict(rpm.__salt__, {"cmd.run_all": mock}):
        rpm.verify("httpd", root="/")
        assert _called_with_root(mock)


# 'file_list' function tests: 2


def test_file_list():
    """
    Test if it list the files that belong to a package.
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm.__salt__, {"cmd.run": mock}):
        assert rpm.file_list("httpd") == {"errors": [], "files": []}
        assert not _called_with_root(mock)


def test_file_list_root():
    """
    Test if it list the files that belong to a package, using the
    root parameter.
    """

    mock = MagicMock(return_value="")
    with patch.dict(rpm.__salt__, {"cmd.run": mock}):
        rpm.file_list("httpd", root="/")
        assert _called_with_root(mock)


# 'file_dict' function tests: 2


def test_file_dict():
    """
    Test if it list the files that belong to a package
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm.__salt__, {"cmd.run": mock}):
        assert rpm.file_dict("httpd") == {"errors": [], "packages": {}}
        assert not _called_with_root(mock)


def test_file_dict_root():
    """
    Test if it list the files that belong to a package
    """
    mock = MagicMock(return_value="")
    with patch.dict(rpm.__salt__, {"cmd.run": mock}):
        rpm.file_dict("httpd", root="/")
        assert _called_with_root(mock)


# 'owner' function tests: 1


def test_owner():
    """
    Test if it return the name of the package that owns the file.
    """
    assert rpm.owner() == ""

    ret = "file /usr/bin/salt-jenkins-build is not owned by any package"
    mock = MagicMock(return_value=ret)
    with patch.dict(rpm.__salt__, {"cmd.run_stdout": mock}):
        assert rpm.owner("/usr/bin/salt-jenkins-build") == ""
        assert not _called_with_root(mock)

    ret = {
        "/usr/bin/vim": "vim-enhanced-7.4.160-1.e17.x86_64",
        "/usr/bin/python": "python-2.7.5-16.e17.x86_64",
    }
    mock = MagicMock(
        side_effect=[
            "python-2.7.5-16.e17.x86_64",
            "vim-enhanced-7.4.160-1.e17.x86_64",
        ]
    )
    with patch.dict(rpm.__salt__, {"cmd.run_stdout": mock}):
        assert rpm.owner("/usr/bin/python", "/usr/bin/vim") == ret
        assert not _called_with_root(mock)


def test_owner_root():
    """
    Test if it return the name of the package that owns the file,
    using the parameter root.
    """
    assert rpm.owner() == ""

    ret = "file /usr/bin/salt-jenkins-build is not owned by any package"
    mock = MagicMock(return_value=ret)
    with patch.dict(rpm.__salt__, {"cmd.run_stdout": mock}):
        rpm.owner("/usr/bin/salt-jenkins-build", root="/")
        assert _called_with_root(mock)


# 'checksum' function tests: 2


def test_checksum():
    """
    Test if checksum validate as expected
    """
    ret = {
        "file1.rpm": True,
        "file2.rpm": False,
        "file3.rpm": False,
    }

    mock = MagicMock(side_effect=[True, 0, True, 1, False, 0])
    with patch.dict(rpm.__salt__, {"file.file_exists": mock, "cmd.retcode": mock}):
        assert rpm.checksum("file1.rpm", "file2.rpm", "file3.rpm") == ret
        assert not _called_with_root(mock)


def test_checksum_root():
    """
    Test if checksum validate as expected, using the parameter
    root
    """
    mock = MagicMock(side_effect=[True, 0])
    with patch.dict(rpm.__salt__, {"file.file_exists": mock, "cmd.retcode": mock}):
        rpm.checksum("file1.rpm", root="/")
        assert _called_with_root(mock)


@pytest.mark.parametrize("rpm_lib", ["HAS_RPM", "rpmdev-vercmp"])
def test_version_cmp_rpm_all_libraries(rpm_lib):
    """
    Test package version when each library is installed
    """
    rpmdev = salt.utils.path.which("rpmdev-vercmp")
    patch_cmd = patch.dict(rpm.__salt__, {"cmd.run_all": salt.modules.cmdmod.run_all})
    if rpm_lib == "rpmdev-vercmp":
        if rpmdev:
            patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
        else:
            pytest.skip("The rpmdev-vercmp binary is not installed")
    elif rpm_lib == "HAS_RPM":
        if HAS_RPM:
            patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", True)
        else:
            pytest.skip("The RPM lib is not installed, skipping")
    else:
        pytest.skip("The Python RPM lib is not installed, skipping")

    with patch_rpm, patch_cmd:
        assert rpm.version_cmp("1", "2") == -1
        assert rpm.version_cmp("2.9.1-6.el7_2.3", "2.9.1-6.el7.4") == -1
        assert rpm.version_cmp("3.2", "3.0") == 1
        assert rpm.version_cmp("3.0", "3.0") == 0
        assert rpm.version_cmp("1:2.9.1-6.el7_2.3", "2.9.1-6.el7.4") == 1
        assert rpm.version_cmp("1:2.9.1-6.el7_2.3", "1:2.9.1-6.el7.4") == -1
        assert rpm.version_cmp("2:2.9.1-6.el7_2.3", "1:2.9.1-6.el7.4") == 1
        assert rpm.version_cmp("3:2.9.1-6.el7.4", "3:2.9.1-6.el7.4") == 0
        assert rpm.version_cmp("3:2.9.1-6.el7.4", "3:2.9.1-7.el7.4") == -1
        assert rpm.version_cmp("3:2.9.1-8.el7.4", "3:2.9.1-7.el7.4") == 1
        assert rpm.version_cmp("3.23-6.el9", "3.23") == 0
        assert rpm.version_cmp("3.23", "3.23-6.el9") == 0
        assert rpm.version_cmp("release_web_294-6", "release_web_294_applepay-1") == -1


def test_version_cmp_rpm():
    """
    Test package version if RPM-Python is installed

    :return:
    """
    mock_label = MagicMock(return_value=-1)
    mock_log = MagicMock()
    patch_label = patch("salt.modules.rpm_lowpkg.rpm.labelCompare", mock_label)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", True)
    with patch_label, patch_rpm, patch_log:
        assert -1 == rpm.version_cmp("1", "2")
        assert not mock_log.warning.called
        assert mock_label.called


def test_version_cmp_rpmdev_vercmp():
    """
    Test package version if rpmdev-vercmp is installed

    :return:
    """
    mock__salt__ = MagicMock(return_value={"retcode": 12})
    mock_log = MagicMock()
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
    patch_which = patch("salt.utils.path.which", return_value=True)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)

    with patch_rpm, patch_which, patch_log:
        with patch.dict(rpm.__salt__, {"cmd.run_all": mock__salt__}):
            assert -1 == rpm.version_cmp("1", "2")
            assert mock__salt__.called
            assert mock_log.warning.called
            assert (
                mock_log.warning.mock_calls[0][1][0]
                == "Please install a package that provides rpm.labelCompare for more accurate version comparisons."
            )
            assert (
                mock_log.warning.mock_calls[1][1][0]
                == "Installing the rpmdevtools package may surface dev tools in production."
            )


def test_version_cmp_python():
    """
    Test package version if falling back to python

    :return:
    """
    mock_log = MagicMock()
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
    mock_version_cmp = MagicMock(return_value=-1)
    patch_cmp = patch("salt.utils.versions.version_cmp", mock_version_cmp)
    patch_which = patch("salt.utils.path.which", return_value=False)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)

    with patch_rpm, patch_cmp, patch_which, patch_log:
        assert -1 == rpm.version_cmp("1", "2")
        assert mock_version_cmp.called
        assert mock_log.warning.called
        assert (
            mock_log.warning.mock_calls[0][1][0]
            == "Please install a package that provides rpm.labelCompare for more accurate version comparisons."
        )
        assert (
            mock_log.warning.mock_calls[1][1][0]
            == "Falling back on salt.utils.versions.version_cmp() for version comparisons"
        )


@pytest.mark.skip_on_windows
def test_info():
    """
    Confirm that a nonzero retcode does not raise an exception.
    """
    rpm_out = textwrap.dedent(
        """\
        name: bash
        relocations: (not relocatable)
        version: 4.4.19
        vendor: CentOS
        release: 10.el8
        build_date_time_t: 1573230816
        build_date: 1573230816
        install_date_time_t: 1578952147
        install_date: 1578952147
        build_host: x86-01.mbox.centos.org
        group: Unspecified
        source_rpm: bash-4.4.19-10.el8.src.rpm
        size: 6930068
        arch: x86_64
        license: GPLv3+
        signature: RSA/SHA256, Wed Dec  4 22:45:04 2019, Key ID 05b555b38483c65d
        packager: CentOS Buildsys <bugs@centos.org>
        url: https://www.gnu.org/software/bash
        summary: The GNU Bourne Again shell
        edition: 4.4.19-10.el8
        description:
        The GNU Bourne Again shell (Bash) is a shell or command language
        interpreter that is compatible with the Bourne shell (sh). Bash
        incorporates useful features from the Korn shell (ksh) and the C shell
        (csh). Most sh scripts can be run by bash without modification.
        -----"""
    )
    dunder_salt = {
        "cmd.run_stdout": MagicMock(return_value="LONGSIZE"),
        "cmd.run_all": MagicMock(
            return_value={
                "retcode": 123,
                "stdout": rpm_out,
                "stderr": "",
                "pid": 12345,
            }
        ),
    }
    expected = {
        "bash": {
            "relocations": "(not relocatable)",
            "version": "4.4.19",
            "vendor": "CentOS",
            "release": "10.el8",
            "build_date_time_t": 1573230816,
            "build_date": "2019-11-08T16:33:36Z",
            "install_date_time_t": 1578952147,
            "install_date": "2020-01-13T21:49:07Z",
            "build_host": "x86-01.mbox.centos.org",
            "group": "Unspecified",
            "source_rpm": "bash-4.4.19-10.el8.src.rpm",
            "size": "6930068",
            "arch": "x86_64",
            "license": "GPLv3+",
            "signature": "RSA/SHA256, Wed Dec  4 22:45:04 2019, Key ID 05b555b38483c65d",
            "packager": "CentOS Buildsys <bugs@centos.org>",
            "url": "https://www.gnu.org/software/bash",
            "summary": "The GNU Bourne Again shell",
            "description": "The GNU Bourne Again shell (Bash) is a shell or command language\ninterpreter that is compatible with the Bourne shell (sh). Bash\nincorporates useful features from the Korn shell (ksh) and the C shell\n(csh). Most sh scripts can be run by bash without modification.",
        }
    }
    with patch.dict(rpm.__salt__, dunder_salt):
        result = rpm.info("bash")
        assert result == expected, result
