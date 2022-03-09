"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import pytest
import salt.modules.cmdmod
import salt.modules.rpm_lowpkg as rpm
import salt.utils.path
from tests.support.mock import MagicMock, patch

# pylint: disable=unused-import
try:
    import rpm as rpm_lib

    HAS_RPM = True
except ImportError:
    HAS_RPM = False

try:
    import rpm_vercmp

    HAS_PY_RPM = True
except ImportError:
    HAS_PY_RPM = False
# pylint: enable=unused-import


def _called_with_root(mock):
    cmd = " ".join(mock.call_args[0][0])
    return cmd.startswith("rpm --root /")


@pytest.fixture
def configure_loader_modules():
    return {rpm: {"rpm": MagicMock(return_value=MagicMock)}}


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


@pytest.mark.parametrize("rpm_lib", ["HAS_RPM", "HAS_PY_RPM", "rpmdev-vercmp"])
def test_version_cmp_rpm_all_libraries(rpm_lib):
    """
    Test package version when each library is installed
    """
    rpmdev = salt.utils.path.which("rpmdev-vercmp")
    patch_cmd = patch.dict(rpm.__salt__, {"cmd.run_all": salt.modules.cmdmod.run_all})
    if rpm_lib == "rpmdev-vercmp":
        if rpmdev:
            patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
            patch_py_rpm = patch("salt.modules.rpm_lowpkg.HAS_PY_RPM", False)
        else:
            pytest.skip("The rpmdev-vercmp binary is not installed")
    elif rpm_lib == "HAS_RPM":
        if HAS_RPM:
            patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", True)
            patch_py_rpm = patch("salt.modules.rpm_lowpkg.HAS_PY_RPM", False)
        else:
            pytest.skip("The RPM lib is not installed, skipping")
    elif rpm_lib == "HAS_PY_RPM":
        if HAS_PY_RPM:
            patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
            patch_py_rpm = patch("salt.modules.rpm_lowpkg.HAS_PY_RPM", True)
        else:
            pytest.skip("The Python RPM lib is not installed, skipping")

    with patch_rpm, patch_py_rpm, patch_cmd:
        assert -1 == rpm.version_cmp("1", "2")
        assert -1 == rpm.version_cmp("2.9.1-6.el7_2.3", "2.9.1-6.el7.4")
        assert 1 == rpm.version_cmp("3.2", "3.0")
        assert 0 == rpm.version_cmp("3.0", "3.0")
        assert 1 == rpm.version_cmp("1:2.9.1-6.el7_2.3", "2.9.1-6.el7.4")
        assert -1 == rpm.version_cmp("1:2.9.1-6.el7_2.3", "1:2.9.1-6.el7.4")
        assert 1 == rpm.version_cmp("2:2.9.1-6.el7_2.3", "1:2.9.1-6.el7.4")
        assert 0 == rpm.version_cmp("3:2.9.1-6.el7.4", "3:2.9.1-6.el7.4")
        assert -1 == rpm.version_cmp("3:2.9.1-6.el7.4", "3:2.9.1-7.el7.4")
        assert 1 == rpm.version_cmp("3:2.9.1-8.el7.4", "3:2.9.1-7.el7.4")


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


def test_version_cmp_rpmutils():
    """
    Test package version if rpmUtils.miscutils called

    :return:
    """
    mock_log = MagicMock()
    mock_rpmUtils = MagicMock()
    mock_rpmUtils.miscutils = MagicMock()
    mock_rpmUtils.miscutils.compareEVR = MagicMock(return_value=-1)
    patch_utils = patch("salt.modules.rpm_lowpkg.rpmUtils", mock_rpmUtils, create=True)
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
    patch_utils_lib = patch("salt.modules.rpm_lowpkg.HAS_RPMUTILS", True)
    patch_py_rpm = patch("salt.modules.rpm_lowpkg.HAS_PY_RPM", False)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)

    with patch_utils, patch_rpm, patch_py_rpm, patch_utils_lib, patch_log:
        assert -1 == rpm.version_cmp("1", "2")
        assert mock_log.warning.called
        assert mock_rpmUtils.miscutils.compareEVR.called


def test_version_cmp_rpmdev_vercmp():
    """
    Test package version if rpmdev-vercmp is installed

    :return:
    """
    mock__salt__ = MagicMock(return_value={"retcode": 12})
    mock_log = MagicMock()
    patch_rpm = patch("salt.modules.rpm_lowpkg.HAS_RPM", False)
    patch_rpmutils = patch("salt.modules.rpm_lowpkg.HAS_RPMUTILS", False)
    patch_py_rpm = patch("salt.modules.rpm_lowpkg.HAS_PY_RPM", False)
    patch_which = patch("salt.utils.path.which", return_value=True)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)

    with patch_rpm, patch_rpmutils, patch_py_rpm, patch_which, patch_log:
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
    patch_rpmutils = patch("salt.modules.rpm_lowpkg.HAS_RPMUTILS", False)
    mock_version_cmp = MagicMock(return_value=-1)
    patch_py_rpm = patch("salt.modules.rpm_lowpkg.HAS_PY_RPM", False)
    patch_cmp = patch("salt.utils.versions.version_cmp", mock_version_cmp)
    patch_which = patch("salt.utils.path.which", return_value=False)
    patch_log = patch("salt.modules.rpm_lowpkg.log", mock_log)

    with patch_rpm, patch_rpmutils, patch_py_rpm, patch_cmp, patch_which, patch_log:
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
