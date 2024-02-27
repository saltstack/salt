"""
Module for managing timezone on POSIX-like systems.
"""

import errno
import filecmp
import logging
import os
import re
import string

import salt.utils.files
import salt.utils.hashutils
import salt.utils.itertools
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.config import DEFAULT_HASH_TYPE
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "timezone"


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return (
            False,
            "The timezone execution module failed to load: "
            "win_timezone.py should replace this module on Windows."
            "There was a problem loading win_timezone.py.",
        )

    if salt.utils.platform.is_darwin():
        return (
            False,
            "The timezone execution module failed to load: "
            "mac_timezone.py should replace this module on macOS."
            "There was a problem loading mac_timezone.py.",
        )

    return __virtualname__


def _timedatectl():
    """
    get the output of timedatectl
    """
    ret = __salt__["cmd.run_all"](["timedatectl"], python_shell=False)

    if ret["retcode"] != 0:
        msg = "timedatectl failed: {}".format(ret["stderr"])
        raise CommandExecutionError(msg)

    return ret


def _get_zone_solaris():
    tzfile = "/etc/TIMEZONE"
    with salt.utils.files.fopen(tzfile, "r") as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            if "TZ=" in line:
                zonepart = line.rstrip("\n").split("=")[-1]
                return zonepart.strip("'\"") or "UTC"
    raise CommandExecutionError("Unable to get timezone from " + tzfile)


def _get_adjtime_timezone():
    """
    Return the timezone in /etc/adjtime of the system clock
    """
    adjtime_file = "/etc/adjtime"
    if os.path.exists(adjtime_file):
        cmd = ["tail", "-n", "1", adjtime_file]
        return __salt__["cmd.run"](cmd, python_shell=False)
    elif os.path.exists("/dev/rtc"):
        raise CommandExecutionError(
            "Unable to get hwclock timezone from " + adjtime_file
        )
    else:
        # There is no RTC.
        return None


def _get_zone_sysconfig():
    tzfile = "/etc/sysconfig/clock"
    with salt.utils.files.fopen(tzfile, "r") as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            if re.match(r"^\s*#", line):
                continue
            if "ZONE" in line and "=" in line:
                zonepart = line.rstrip("\n").split("=")[-1]
                return zonepart.strip("'\"") or "UTC"
    raise CommandExecutionError("Unable to get timezone from " + tzfile)


def _get_zone_etc_localtime():
    tzfile = _get_localtime_path()
    tzdir = "/usr/share/zoneinfo/"
    tzdir_len = len(tzdir)
    try:
        olson_name = os.path.normpath(os.path.join("/etc", os.readlink(tzfile)))
        if olson_name.startswith(tzdir):
            return olson_name[tzdir_len:]
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            if "FreeBSD" in __grains__["os_family"]:
                return get_zonecode()
            raise CommandExecutionError(tzfile + " does not exist")
        elif exc.errno == errno.EINVAL:
            if "FreeBSD" in __grains__["os_family"]:
                return get_zonecode()
            log.warning(
                "%s is not a symbolic link. Attempting to match it to zoneinfo files.",
                tzfile,
            )
            # Regular file. Try to match the hash.
            hash_type = __opts__.get("hash_type", DEFAULT_HASH_TYPE)
            tzfile_hash = salt.utils.hashutils.get_hash(tzfile, hash_type)
            # Not a link, just a copy of the tzdata file
            for root, dirs, files in salt.utils.path.os_walk(tzdir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    olson_name = full_path[tzdir_len:]
                    if olson_name[0] in string.ascii_lowercase:
                        continue
                    if tzfile_hash == salt.utils.hashutils.get_hash(
                        full_path, hash_type
                    ):
                        return olson_name
    raise CommandExecutionError("Unable to determine timezone")


def _get_zone_etc_timezone():
    tzfile = "/etc/timezone"
    try:
        with salt.utils.files.fopen(tzfile, "r") as fp_:
            return salt.utils.stringutils.to_unicode(fp_.read()).strip()
    except OSError as exc:
        raise CommandExecutionError(
            f"Problem reading timezone file {tzfile}: {exc.strerror}"
        )


def _get_zone_aix():
    tzfile = "/etc/environment"
    with salt.utils.files.fopen(tzfile, "r") as fp_:
        for line in fp_:
            line = salt.utils.stringutils.to_unicode(line)
            if "TZ=" in line:
                zonepart = line.rstrip("\n").split("=")[-1]
                return zonepart.strip("'\"") or "UTC"
    raise CommandExecutionError("Unable to get timezone from " + tzfile)


def get_zone():
    """
    Get current timezone (i.e. America/Denver)

    .. versionchanged:: 2016.11.4

    .. note::

        On AIX operating systems, Posix values can also be returned
        'CST6CDT,M3.2.0/2:00:00,M11.1.0/2:00:00'

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zone
    """
    if salt.utils.path.which("timedatectl"):
        ret = _timedatectl()

        for line in (
            x.strip() for x in salt.utils.itertools.split(ret["stdout"], "\n")
        ):
            try:
                return re.match(r"Time ?zone:\s+(\S+)", line).group(1)
            except AttributeError:
                pass

        raise CommandExecutionError(
            "Failed to parse timedatectl output: {}\n"
            "Please file an issue with SaltStack".format(ret["stdout"])
        )

    else:
        if __grains__["os"].lower() == "centos":
            return _get_zone_etc_localtime()
        os_family = __grains__["os_family"]
        for family in ("RedHat", "Suse"):
            if family in os_family:
                return _get_zone_sysconfig()
        for family in ("Debian", "Gentoo"):
            if family in os_family:
                return _get_zone_etc_timezone()
        if os_family in ("FreeBSD", "OpenBSD", "NetBSD", "NILinuxRT", "Slackware"):
            return _get_zone_etc_localtime()
        elif "Solaris" in os_family:
            return _get_zone_solaris()
        elif "AIX" in os_family:
            return _get_zone_aix()
    raise CommandExecutionError("Unable to get timezone")


def get_zonecode():
    """
    Get current timezone (i.e. PST, MDT, etc)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_zonecode
    """
    return __salt__["cmd.run"](["date", "+%Z"], python_shell=False)


def get_offset():
    """
    Get current numeric timezone offset from UTC (i.e. -0700)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_offset
    """
    if "AIX" not in __grains__["os_family"]:
        return __salt__["cmd.run"](["date", "+%z"], python_shell=False)

    salt_path = "/opt/salt/bin/date"

    if not os.path.exists(salt_path):
        return f"date in salt binaries does not exist: {salt_path}"

    return __salt__["cmd.run"]([salt_path, "+%z"], python_shell=False)


def set_zone(timezone):
    """
    Unlinks, then symlinks /etc/localtime to the set timezone.

    The timezone is crucial to several system processes, each of which SHOULD
    be restarted (for instance, whatever you system uses as its cron and
    syslog daemons). This will not be automagically done and must be done
    manually!

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_zone 'America/Denver'

    .. versionchanged:: 2016.11.4

    .. note::

        On AIX operating systems, Posix values are also allowed, see below

    .. code-block:: bash

        salt '*' timezone.set_zone 'CST6CDT,M3.2.0/2:00:00,M11.1.0/2:00:00'

    """
    if salt.utils.path.which("timedatectl"):
        try:
            __salt__["cmd.run"](f"timedatectl set-timezone {timezone}")
        except CommandExecutionError:
            pass

    if "Solaris" in __grains__["os_family"] or "AIX" in __grains__["os_family"]:
        zonepath = f"/usr/share/lib/zoneinfo/{timezone}"
    else:
        zonepath = f"/usr/share/zoneinfo/{timezone}"

    if not os.path.exists(zonepath) and "AIX" not in __grains__["os_family"]:
        return f"Zone does not exist: {zonepath}"

    tzfile = _get_localtime_path()
    if os.path.exists(tzfile):
        os.unlink(tzfile)

    if "Solaris" in __grains__["os_family"]:
        __salt__["file.sed"]("/etc/default/init", "^TZ=.*", f"TZ={timezone}")
    elif "AIX" in __grains__["os_family"]:
        # timezone could be Olson or Posix
        curtzstring = get_zone()
        cmd = ["chtz", timezone]
        result = __salt__["cmd.retcode"](cmd, python_shell=False)
        if result == 0:
            return True

        # restore orig timezone, since AIX chtz failure sets UTC
        cmd = ["chtz", curtzstring]
        __salt__["cmd.retcode"](cmd, python_shell=False)
        return False
    else:
        os.symlink(zonepath, tzfile)

    if "RedHat" in __grains__["os_family"]:
        __salt__["file.sed"]("/etc/sysconfig/clock", "^ZONE=.*", f'ZONE="{timezone}"')
    elif "Suse" in __grains__["os_family"]:
        __salt__["file.sed"](
            "/etc/sysconfig/clock", "^TIMEZONE=.*", f'TIMEZONE="{timezone}"'
        )
    elif "Debian" in __grains__["os_family"] or "Gentoo" in __grains__["os_family"]:
        with salt.utils.files.fopen("/etc/timezone", "w") as ofh:
            ofh.write(salt.utils.stringutils.to_str(timezone).strip())
            ofh.write("\n")

    return True


def zone_compare(timezone):
    """
    Compares the given timezone name with the system timezone name.
    Checks the hash sum between the given timezone, and the one set in
    /etc/localtime. Returns True if names and hash sums match, and False if not.
    Mostly useful for running state checks.

    .. versionchanged:: 2016.3.0

    .. note::

        On Solaris-like operating systems only a string comparison is done.

    .. versionchanged:: 2016.11.4

    .. note::

        On AIX operating systems only a string comparison is done.

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.zone_compare 'America/Denver'
    """
    if "Solaris" in __grains__["os_family"] or "AIX" in __grains__["os_family"]:
        return timezone == get_zone()

    if "Arch" in __grains__["os_family"] or "FreeBSD" in __grains__["os_family"]:
        if not os.path.isfile(_get_localtime_path()):
            return timezone == get_zone()

    tzfile = _get_localtime_path()
    zonepath = _get_zone_file(timezone)
    try:
        return filecmp.cmp(tzfile, zonepath, shallow=False)
    except OSError as exc:
        problematic_file = exc.filename
        if problematic_file == zonepath:
            raise SaltInvocationError(f'Can\'t find a local timezone "{timezone}"')
        elif problematic_file == tzfile:
            raise CommandExecutionError(
                "Failed to read {} to determine current timezone: {}".format(
                    tzfile, exc.strerror
                )
            )
        raise


def _get_localtime_path():
    if (
        "NILinuxRT" in __grains__["os_family"]
        and "nilrt" in __grains__["lsb_distrib_id"]
    ):
        return "/etc/natinst/share/localtime"
    return "/etc/localtime"


def _get_zone_file(timezone):
    return f"/usr/share/zoneinfo/{timezone}"


def get_hwclock():
    """
    Get current hardware clock setting (UTC or localtime)

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.get_hwclock
    """
    if salt.utils.path.which("timedatectl"):
        ret = _timedatectl()
        for line in (x.strip() for x in ret["stdout"].splitlines()):
            if "rtc in local tz" in line.lower():
                try:
                    if line.split(":")[-1].strip().lower() == "yes":
                        return "localtime"
                    else:
                        return "UTC"
                except IndexError:
                    pass

        raise CommandExecutionError(
            "Failed to parse timedatectl output: {}\n"
            "Please file an issue with SaltStack".format(ret["stdout"])
        )

    else:
        os_family = __grains__["os_family"]
        for family in ("RedHat", "Suse", "NILinuxRT"):
            if family in os_family:
                return _get_adjtime_timezone()

        if "Debian" in __grains__["os_family"]:
            # Original way to look up hwclock on Debian-based systems
            try:
                with salt.utils.files.fopen("/etc/default/rcS", "r") as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if re.match(r"^\s*#", line):
                            continue
                        if "UTC=" in line:
                            is_utc = line.rstrip("\n").split("=")[-1].lower()
                            if is_utc == "yes":
                                return "UTC"
                            else:
                                return "localtime"
            except OSError as exc:
                pass
            # Since Wheezy
            return _get_adjtime_timezone()

        if "Gentoo" in __grains__["os_family"]:
            if not os.path.exists("/etc/adjtime"):
                offset_file = "/etc/conf.d/hwclock"
                try:
                    with salt.utils.files.fopen(offset_file, "r") as fp_:
                        for line in fp_:
                            line = salt.utils.stringutils.to_unicode(line)
                            if line.startswith("clock="):
                                line = line.rstrip("\n")
                                line = line.split("=")[-1].strip("'\"")
                                if line == "UTC":
                                    return line
                                if line == "local":
                                    return "LOCAL"
                        raise CommandExecutionError(
                            f"Correct offset value not found in {offset_file}"
                        )
                except OSError as exc:
                    raise CommandExecutionError(
                        "Problem reading offset file {}: {}".format(
                            offset_file, exc.strerror
                        )
                    )
            return _get_adjtime_timezone()

        if "Solaris" in __grains__["os_family"]:
            offset_file = "/etc/rtc_config"
            try:
                with salt.utils.files.fopen(offset_file, "r") as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if line.startswith("zone_info=GMT"):
                            return "UTC"
                    return "localtime"
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    # offset file does not exist
                    return "UTC"
                raise CommandExecutionError(
                    "Problem reading offset file {}: {}".format(
                        offset_file, exc.strerror
                    )
                )

        if "AIX" in __grains__["os_family"]:
            offset_file = "/etc/environment"
            try:
                with salt.utils.files.fopen(offset_file, "r") as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if line.startswith("TZ=UTC"):
                            return "UTC"
                    return "localtime"
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    # offset file does not exist
                    return "UTC"
                raise CommandExecutionError(
                    "Problem reading offset file {}: {}".format(
                        offset_file, exc.strerror
                    )
                )

        if "Slackware" in __grains__["os_family"]:
            if not os.path.exists("/etc/adjtime"):
                offset_file = "/etc/hardwareclock"
                try:
                    with salt.utils.files.fopen(offset_file, "r") as fp_:
                        for line in fp_:
                            line = salt.utils.stringutils.to_unicode(line)
                            if line.startswith("UTC"):
                                return "UTC"
                        return "localtime"
                except OSError as exc:
                    if exc.errno == errno.ENOENT:
                        return "UTC"
            return _get_adjtime_timezone()


def set_hwclock(clock):
    """
    Sets the hardware clock to be either UTC or localtime

    CLI Example:

    .. code-block:: bash

        salt '*' timezone.set_hwclock UTC
    """
    if salt.utils.path.which("timedatectl"):
        cmd = [
            "timedatectl",
            "set-local-rtc",
            "true" if clock == "localtime" else "false",
        ]
        return __salt__["cmd.retcode"](cmd, python_shell=False) == 0
    else:
        os_family = __grains__["os_family"]
        if os_family in ("AIX", "NILinuxRT"):
            if clock.lower() != "utc":
                raise SaltInvocationError("UTC is the only permitted value")
            return True

        timezone = get_zone()

        if "Solaris" in __grains__["os_family"]:
            if clock.lower() not in ("localtime", "utc"):
                raise SaltInvocationError(
                    "localtime and UTC are the only permitted values"
                )
            if "sparc" in __grains__["cpuarch"]:
                raise SaltInvocationError(
                    "UTC is the only choice for SPARC architecture"
                )
            cmd = ["rtc", "-z", "GMT" if clock.lower() == "utc" else timezone]
            return __salt__["cmd.retcode"](cmd, python_shell=False) == 0

        zonepath = f"/usr/share/zoneinfo/{timezone}"

        if not os.path.exists(zonepath):
            raise CommandExecutionError(f"Zone '{zonepath}' does not exist")

        os.unlink("/etc/localtime")
        os.symlink(zonepath, "/etc/localtime")

        if "Arch" in __grains__["os_family"]:
            cmd = [
                "timezonectl",
                "set-local-rtc",
                "true" if clock == "localtime" else "false",
            ]
            return __salt__["cmd.retcode"](cmd, python_shell=False) == 0
        elif "RedHat" in __grains__["os_family"]:
            __salt__["file.sed"](
                "/etc/sysconfig/clock", "^ZONE=.*", f'ZONE="{timezone}"'
            )
        elif "Suse" in __grains__["os_family"]:
            __salt__["file.sed"](
                "/etc/sysconfig/clock",
                "^TIMEZONE=.*",
                f'TIMEZONE="{timezone}"',
            )
        elif "Debian" in __grains__["os_family"]:
            if clock == "UTC":
                __salt__["file.sed"]("/etc/default/rcS", "^UTC=.*", "UTC=yes")
            elif clock == "localtime":
                __salt__["file.sed"]("/etc/default/rcS", "^UTC=.*", "UTC=no")
        elif "Gentoo" in __grains__["os_family"]:
            if clock not in ("UTC", "localtime"):
                raise SaltInvocationError("Only 'UTC' and 'localtime' are allowed")
            if clock == "localtime":
                clock = "local"
            __salt__["file.sed"]("/etc/conf.d/hwclock", "^clock=.*", f'clock="{clock}"')
        elif "Slackware" in os_family:
            if clock not in ("UTC", "localtime"):
                raise SaltInvocationError("Only 'UTC' and 'localtime' are allowed")
            __salt__["file.sed"]("/etc/hardwareclock", "^(UTC|localtime)", f"{clock}")

    return True
