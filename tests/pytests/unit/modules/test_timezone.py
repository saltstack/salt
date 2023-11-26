import os
from tempfile import NamedTemporaryFile

import pytest

import salt.modules.timezone as timezone
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, mock_open, patch

GET_ZONE_FILE = "salt.modules.timezone._get_zone_file"
GET_LOCALTIME_PATH = "salt.modules.timezone._get_localtime_path"
TEST_TZ = "UTC"


@pytest.fixture
def configure_loader_modules():
    return {
        timezone: {
            "__grains__": {"os": "", "os_family": "Ubuntu"},
            "__salt__": {
                "file.sed": MagicMock(),
                "cmd.run": MagicMock(),
                "cmd.retcode": MagicMock(return_value=0),
            },
        }
    }


@pytest.fixture
def tempfiles():
    tempfiles = []
    yield tempfiles
    for tempfile in tempfiles:
        try:
            os.remove(tempfile.name)
        except OSError:
            pass
    del tempfiles


@pytest.fixture
def patch_os():
    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        with patch("os.path.exists", MagicMock(return_value=True)):
            with patch("os.unlink", MagicMock()):
                with patch("os.symlink", MagicMock()):
                    yield


def test_zone_compare_equal(tempfiles):
    etc_localtime = create_tempfile_with_contents("a", tempfiles)
    zone_path = create_tempfile_with_contents("a", tempfiles)

    with patch(GET_ZONE_FILE, lambda p: zone_path.name):
        with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):

            assert timezone.zone_compare("foo")


def test_zone_compare_arch(tempfiles):
    """
    test zone_compare function when OS is arch
    """
    etc_localtime = create_tempfile_with_contents("a", tempfiles)
    zone_path = create_tempfile_with_contents("a", tempfiles)
    mock_zone = MagicMock(return_value="foo")
    patch_zone = patch.object(timezone, "get_zone", mock_zone)

    with patch_zone:
        with patch.dict(timezone.__grains__, {"os_family": "Arch"}):
            with patch(GET_ZONE_FILE, lambda p: zone_path.name):
                with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):
                    with patch("os.path.isfile", return_value=False):
                        assert timezone.zone_compare("foo")
                        mock_zone.assert_called()


def test_zone_compare_nonexistent(tempfiles):
    etc_localtime = create_tempfile_with_contents("a", tempfiles)

    with patch(GET_ZONE_FILE, lambda p: "/foopath/nonexistent"):
        with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):

            pytest.raises(SaltInvocationError, timezone.zone_compare, "foo")


def test_zone_compare_unequal(tempfiles):
    etc_localtime = create_tempfile_with_contents("a", tempfiles)
    zone_path = create_tempfile_with_contents("b", tempfiles)

    with patch(GET_ZONE_FILE, lambda p: zone_path.name):
        with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):

            assert not timezone.zone_compare("foo")


def test_missing_localtime():
    with patch(GET_ZONE_FILE, lambda p: "/nonexisting"):
        with patch(GET_LOCALTIME_PATH, lambda: "/also-missing"):
            pytest.raises(CommandExecutionError, timezone.zone_compare, "foo")


def create_tempfile_with_contents(contents, tempfiles=None):
    temp = NamedTemporaryFile(delete=False)
    temp.write(salt.utils.stringutils.to_bytes(contents))
    temp.close()
    tempfiles.append(temp)
    return temp


def test_get_zone_centos():
    """
    Test CentOS is recognized
    :return:
    """
    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        with patch.dict(timezone.__grains__, {"os": "centos"}):
            with patch(
                "salt.modules.timezone._get_zone_etc_localtime",
                MagicMock(return_value=TEST_TZ),
            ):
                assert timezone.get_zone() == TEST_TZ


def test_get_zone_os_family_rh_suse():
    """
    Test RedHat and Suse are recognized
    :return:
    """
    for osfamily in ["RedHat", "Suse"]:
        with patch("salt.utils.path.which", MagicMock(return_value=False)):
            with patch.dict(timezone.__grains__, {"os_family": [osfamily]}):
                with patch(
                    "salt.modules.timezone._get_zone_sysconfig",
                    MagicMock(return_value=TEST_TZ),
                ):
                    assert timezone.get_zone() == TEST_TZ


def test_get_zone_os_family_debian_gentoo():
    """
    Test Debian and Gentoo are recognized
    :return:
    """
    for osfamily in ["Debian", "Gentoo"]:
        with patch("salt.utils.path.which", MagicMock(return_value=False)):
            with patch.dict(timezone.__grains__, {"os_family": [osfamily]}):
                with patch(
                    "salt.modules.timezone._get_zone_etc_timezone",
                    MagicMock(return_value=TEST_TZ),
                ):
                    assert timezone.get_zone() == TEST_TZ


def test_get_zone_os_family_allbsd_nilinuxrt_slackware():
    """
    Test *BSD, NILinuxRT and Slackware are recognized
    :return:
    """
    for osfamily in ["FreeBSD", "OpenBSD", "NetBSD", "NILinuxRT", "Slackware"]:
        with patch("salt.utils.path.which", MagicMock(return_value=False)):
            with patch.dict(timezone.__grains__, {"os_family": osfamily}):
                with patch(
                    "salt.modules.timezone._get_zone_etc_localtime",
                    MagicMock(return_value=TEST_TZ),
                ):
                    assert timezone.get_zone() == TEST_TZ


def test_get_zone_os_family_slowlaris():
    """
    Test Slowlaris is recognized
    :return:
    """
    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        with patch.dict(timezone.__grains__, {"os_family": ["Solaris"]}):
            with patch(
                "salt.modules.timezone._get_zone_solaris",
                MagicMock(return_value=TEST_TZ),
            ):
                assert timezone.get_zone() == TEST_TZ


def test_get_zone_os_family_aix():
    """
    Test IBM AIX is recognized
    :return:
    """
    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        with patch.dict(timezone.__grains__, {"os_family": ["AIX"]}):
            with patch(
                "salt.modules.timezone._get_zone_aix",
                MagicMock(return_value=TEST_TZ),
            ):
                assert timezone.get_zone() == TEST_TZ


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_zone_os_family_nilinuxrt(patch_os):
    """
    Test zone set on NILinuxRT
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["NILinuxRT"]}), patch.dict(
        timezone.__grains__, {"lsb_distrib_id": "nilrt"}
    ):
        assert timezone.set_zone(TEST_TZ)


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_zone_os_family_allbsd_slackware(patch_os):
    """
    Test zone set on *BSD and Slackware
    :return:
    """
    for osfamily in ["FreeBSD", "OpenBSD", "NetBSD", "Slackware"]:
        with patch.dict(timezone.__grains__, {"os_family": osfamily}):
            assert timezone.set_zone(TEST_TZ)


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_zone_redhat(patch_os):
    """
    Test zone set on RH series
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["RedHat"]}):
        assert timezone.set_zone(TEST_TZ)
        name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
        assert args == ("/etc/sysconfig/clock", "^ZONE=.*", 'ZONE="UTC"')


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_zone_suse(patch_os):
    """
    Test zone set on SUSE series
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["Suse"]}):
        assert timezone.set_zone(TEST_TZ)
        name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
        assert args == ("/etc/sysconfig/clock", "^TIMEZONE=.*", 'TIMEZONE="UTC"')


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_zone_gentoo(patch_os):
    """
    Test zone set on Gentoo series
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["Gentoo"]}):
        with patch("salt.utils.files.fopen", mock_open()) as m_open:
            assert timezone.set_zone(TEST_TZ)
            fh_ = m_open.filehandles["/etc/timezone"][0]
            assert fh_.call.args == ("/etc/timezone", "w"), fh_.call.args
            assert fh_.write_calls == ["UTC", "\n"], fh_.write_calls


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_zone_debian(patch_os):
    """
    Test zone set on Debian series
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["Debian"]}):
        with patch("salt.utils.files.fopen", mock_open()) as m_open:
            assert timezone.set_zone(TEST_TZ)
            fh_ = m_open.filehandles["/etc/timezone"][0]
            assert fh_.call.args == ("/etc/timezone", "w"), fh_.call.args
            assert fh_.write_calls == ["UTC", "\n"], fh_.write_calls


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_timedate_utc():
    """
    Test get hwclock UTC/localtime
    :return:
    """
    with patch("salt.utils.path.which", MagicMock(return_value=True)):
        with patch("os.path.exists", MagicMock(return_value=True)):
            with patch("os.unlink", MagicMock()):
                with patch("os.symlink", MagicMock()):
                    with patch(
                        "salt.modules.timezone._timedatectl",
                        MagicMock(return_value={"stdout": "rtc in local tz"}),
                    ):
                        assert timezone.get_hwclock() == "UTC"
                    with patch(
                        "salt.modules.timezone._timedatectl",
                        MagicMock(return_value={"stdout": "rtc in local tz:yes"}),
                    ):
                        assert timezone.get_hwclock() == "localtime"


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_suse(patch_os):
    """
    Test get hwclock on SUSE
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["Suse"]}):
        timezone.get_hwclock()
        name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[0]
        assert args == (["tail", "-n", "1", "/etc/adjtime"],)
        assert kwarg == {"python_shell": False}


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_redhat(patch_os):
    """
    Test get hwclock on RedHat
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["RedHat"]}):
        timezone.get_hwclock()
        name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[0]
        assert args == (["tail", "-n", "1", "/etc/adjtime"],)
        assert kwarg == {"python_shell": False}


def _test_get_hwclock_debian(
    patch_os,
):  # TODO: Enable this when testing environment is working properly
    """
    Test get hwclock on Debian
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["Debian"]}):
        timezone.get_hwclock()
        name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[0]
        assert args == (["tail", "-n", "1", "/etc/adjtime"],)
        assert kwarg == {"python_shell": False}


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_solaris(patch_os):
    """
    Test get hwclock on Solaris
    :return:
    """
    # Incomplete
    with patch.dict(timezone.__grains__, {"os_family": ["Solaris"]}):
        assert timezone.get_hwclock() == "UTC"
        with patch("salt.utils.files.fopen", mock_open()):
            assert timezone.get_hwclock() == "localtime"


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_aix(patch_os):
    """
    Test get hwclock on AIX
    :return:
    """
    # Incomplete
    hwclock = "localtime"
    if not os.path.isfile("/etc/environment"):
        hwclock = "UTC"
    with patch.dict(timezone.__grains__, {"os_family": ["AIX"]}):
        assert timezone.get_hwclock() == hwclock


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_slackware_with_adjtime(patch_os):
    """
    Test get hwclock on Slackware with /etc/adjtime present
    :return:
    """
    with patch.dict(timezone.__grains__, {"os_family": ["Slackware"]}):
        timezone.get_hwclock()
        name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[0]
        assert args == (["tail", "-n", "1", "/etc/adjtime"],)
        assert kwarg == {"python_shell": False}


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_get_hwclock_slackware_without_adjtime():
    """
    Test get hwclock on Slackware without /etc/adjtime present
    :return:
    """
    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        with patch("os.path.exists", MagicMock(return_value=False)):
            with patch("os.unlink", MagicMock()):
                with patch("os.symlink", MagicMock()):
                    with patch.dict(timezone.__grains__, {"os_family": ["Slackware"]}):
                        with patch(
                            "salt.utils.files.fopen", mock_open(read_data="UTC")
                        ):
                            assert timezone.get_hwclock() == "UTC"
                        with patch(
                            "salt.utils.files.fopen", mock_open(read_data="localtime")
                        ):
                            assert timezone.get_hwclock() == "localtime"


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_timedatectl():
    """
    Test set hwclock with timedatectl
    :return:
    """
    with patch("salt.utils.path.which", MagicMock(return_value=True)):
        timezone.set_hwclock("UTC")
        name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[0]
    assert args == (["timedatectl", "set-local-rtc", "false"],)

    with patch("salt.utils.path.which", MagicMock(return_value=True)):
        timezone.set_hwclock("localtime")
    with patch("salt.utils.path.which", MagicMock(return_value=True)):
        name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[1]
    assert args == (["timedatectl", "set-local-rtc", "true"],)


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_aix_nilinuxrt(patch_os):
    """
    Test set hwclock on AIX and NILinuxRT
    :return:
    """
    for osfamily in ["AIX", "NILinuxRT"]:
        with patch.dict(timezone.__grains__, {"os_family": osfamily}):
            with pytest.raises(SaltInvocationError):
                assert timezone.set_hwclock("forty two")
            assert timezone.set_hwclock("UTC")


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_solaris(patch_os):
    """
    Test set hwclock on Solaris
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(
            timezone.__grains__, {"os_family": ["Solaris"], "cpuarch": "x86"}
        ):
            with pytest.raises(SaltInvocationError):
                assert timezone.set_hwclock("forty two")
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[0]
            assert args == (["rtc", "-z", "GMT"],)
            assert kwargs == {"python_shell": False}


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_arch(patch_os):
    """
    Test set hwclock on arch
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(timezone.__grains__, {"os_family": ["Arch"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[0]
            assert args == (["timezonectl", "set-local-rtc", "false"],)
            assert kwargs == {"python_shell": False}


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_redhat(patch_os):
    """
    Test set hwclock on RedHat
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(timezone.__grains__, {"os_family": ["RedHat"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/sysconfig/clock", "^ZONE=.*", 'ZONE="TEST_TIMEZONE"')


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_suse(patch_os):
    """
    Test set hwclock on SUSE
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(timezone.__grains__, {"os_family": ["Suse"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == (
                "/etc/sysconfig/clock",
                "^TIMEZONE=.*",
                'TIMEZONE="TEST_TIMEZONE"',
            )


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_debian(patch_os):
    """
    Test set hwclock on Debian
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(timezone.__grains__, {"os_family": ["Debian"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/default/rcS", "^UTC=.*", "UTC=yes")

            assert timezone.set_hwclock("localtime")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[1]
            assert args == ("/etc/default/rcS", "^UTC=.*", "UTC=no")


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_gentoo(patch_os):
    """
    Test set hwclock on Gentoo
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(timezone.__grains__, {"os_family": ["Gentoo"]}):
            with pytest.raises(SaltInvocationError):
                timezone.set_hwclock("forty two")

            timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/conf.d/hwclock", "^clock=.*", 'clock="UTC"')

            timezone.set_hwclock("localtime")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[1]
            assert args == ("/etc/conf.d/hwclock", "^clock=.*", 'clock="local"')


@pytest.mark.skip_on_windows(reason="os.symlink not available in Windows")
def test_set_hwclock_slackware(patch_os):
    """
    Test set hwclock on Slackware
    :return:
    """
    with patch(
        "salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE")
    ):
        with patch.dict(timezone.__grains__, {"os_family": ["Slackware"]}):
            with pytest.raises(SaltInvocationError):
                timezone.set_hwclock("forty two")

            timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/hardwareclock", "^(UTC|localtime)", "UTC")

            timezone.set_hwclock("localtime")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[1]
            assert args == ("/etc/hardwareclock", "^(UTC|localtime)", "localtime")
