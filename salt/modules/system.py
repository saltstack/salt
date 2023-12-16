"""
Support for reboot, shutdown, etc on POSIX-like systems.

.. note::

    If a wrapper such as ``molly-guard`` to intercept *interactive* shutdown
    commands is configured, calling :mod:`system.halt <salt.modules.system.halt>`,
    :mod:`system.poweroff <salt.modules.system.poweroff>`,
    :mod:`system.reboot <salt.modules.system.reboot>`, and
    :mod:`system.shutdown <salt.modules.system.shutdown>` with ``salt-call`` will
    hang indefinitely while the wrapper script waits for user input. Calling them
    with ``salt`` will work as expected.
"""

import os.path
import re
from datetime import datetime, timedelta, tzinfo

import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.decorators import depends

__virtualname__ = "system"


def __virtual__():
    """
    Only supported on POSIX-like systems
    Windows, Solaris, and OS X have their own modules
    """
    if salt.utils.platform.is_windows():
        return (False, "This module is not available on Windows")

    if salt.utils.platform.is_darwin():
        return (False, "This module is not available on Mac OS")

    if salt.utils.platform.is_sunos():
        return (False, "This module is not available on SunOS")

    return __virtualname__


def halt():
    """
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    """
    cmd = ["halt"]
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def init(runlevel):
    """
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    """
    cmd = ["init", f"{runlevel}"]
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def poweroff():
    """
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    """
    cmd = ["poweroff"]
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def reboot(at_time=None):
    """
    Reboot the system

    at_time
        The wait time in minutes before the system will be rebooted.

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
    """
    cmd = ["shutdown", "-r", (f"{at_time}" if at_time else "now")]
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def shutdown(at_time=None):
    """
    Shutdown a running system

    at_time
        The wait time in minutes before the system will be shutdown.

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown 5
    """
    if (
        salt.utils.platform.is_freebsd()
        or salt.utils.platform.is_netbsd()
        or salt.utils.platform.is_openbsd()
    ):
        # these platforms don't power off by default when halted
        flag = "-p"
    else:
        flag = "-h"

    cmd = ["shutdown", flag, (f"{at_time}" if at_time else "now")]
    ret = __salt__["cmd.run"](cmd, python_shell=False)
    return ret


def _date_bin_set_datetime(new_date):
    """
    set the system date/time using the date command

    Note using a strictly POSIX-compliant date binary we can only set the date
    up to the minute.
    """
    cmd = ["date"]

    # if there is a timezone in the datetime object use that offset
    # This will modify the new_date to be the equivalent time in UTC
    if new_date.utcoffset() is not None:
        new_date = new_date - new_date.utcoffset()
        new_date = new_date.replace(tzinfo=_FixedOffset(0))
        cmd.append("-u")

    # the date can be set in the following format:
    # Note that setting the time with a resolution of seconds
    # is not a posix feature, so we will attempt it and if it
    # fails we will try again only using posix features

    # date MMDDhhmm[[CC]YY[.ss]]
    non_posix = "{1:02}{2:02}{3:02}{4:02}{0:04}.{5:02}".format(*new_date.timetuple())
    non_posix_cmd = cmd + [non_posix]

    ret_non_posix = __salt__["cmd.run_all"](non_posix_cmd, python_shell=False)
    if ret_non_posix["retcode"] != 0:
        # We will now try the command again following posix
        # date MMDDhhmm[[CC]YY]
        posix = " {1:02}{2:02}{3:02}{4:02}{0:04}".format(*new_date.timetuple())
        posix_cmd = cmd + [posix]

        ret_posix = __salt__["cmd.run_all"](posix_cmd, python_shell=False)
        if ret_posix["retcode"] != 0:
            # if both fail it's likely an invalid date string
            # so we will give back the error from the first attempt
            msg = "date failed: {}".format(ret_non_posix["stderr"])
            raise CommandExecutionError(msg)
    return True


def has_settable_hwclock():
    """
    Returns ``True`` if the system has a hardware clock capable of being
    set from software.

    CLI Example:

    .. code-block:: bash

        salt '*' system.has_settable_hwclock
    """
    if salt.utils.path.which_bin(["hwclock"]) is not None:
        res = __salt__["cmd.run_all"](
            ["hwclock", "--test", "--systohc"],
            python_shell=False,
            output_loglevel="quiet",
            ignore_retcode=True,
        )
        return res["retcode"] == 0
    return False


def _swclock_to_hwclock():
    """
    Set hardware clock to value of software clock.
    """
    res = __salt__["cmd.run_all"](["hwclock", "--systohc"], python_shell=False)
    if res["retcode"] != 0:
        msg = "hwclock failed to set hardware clock from software clock: {}".format(
            res["stderr"]
        )
        raise CommandExecutionError(msg)
    return True


def _try_parse_datetime(time_str, fmts):
    """
    Attempts to parse the input ``time_str`` as a date.

    :param str time_str: A string representing the time
    :param list fmts: A list of date format strings.

    :return: Returns a datetime object if parsed properly. Otherwise ``None``
    :rtype: datetime
    """
    result = None
    for fmt in fmts:
        try:
            result = datetime.strptime(time_str, fmt)
            break
        except ValueError:
            pass
    return result


def _offset_to_min(utc_offset):
    """
    Helper function that converts the UTC offset string into number of minutes
    offset. Input is in form ``[+-]?HHMM``. Example valid inputs are ``+0500``
    ``-0300`` and ``0800``. These would return ``-300``, ``180``, ``480`` respectively.
    """
    match = re.match(r"^([+-])?(\d\d)(\d\d)$", utc_offset)
    if not match:
        raise SaltInvocationError("Invalid UTC offset")

    sign = -1 if match.group(1) == "-" else 1
    hours_offset = int(match.group(2))
    minutes_offset = int(match.group(3))
    total_offset = sign * (hours_offset * 60 + minutes_offset)
    return total_offset


def _get_offset_time(utc_offset):
    """
    Will return the current time adjusted using the input timezone offset.

    :rtype: datetime
    """
    if utc_offset is not None:
        minutes = _offset_to_min(utc_offset)
        offset = timedelta(minutes=minutes)
        offset_time = datetime.utcnow() + offset
        offset_time = offset_time.replace(tzinfo=_FixedOffset(minutes))
    else:
        offset_time = datetime.now()
    return offset_time


def get_system_time(utc_offset=None):
    """
    Get the system time.

    :param str utc_offset: The UTC offset in 4 digit (e.g. ``+0600``) format with an
        optional sign (``+``/``-``).  Will default to ``None`` which will use the local
        timezone. To set the time based off of UTC use ``+0000``. Note: If
        being passed through the command line will need to be quoted twice to
        allow negative offsets (e.g. ``"'+0000'"``).
    :return: Returns the system time in ``HH:MM:SS AM/PM`` format.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_time
    """
    offset_time = _get_offset_time(utc_offset)
    return datetime.strftime(offset_time, "%I:%M:%S %p")


def set_system_time(newtime, utc_offset=None):
    """
    Set the system time.

    :param str newtime:
        The time to set. Can be any of the following formats.

        - ``HH:MM:SS AM/PM``
        - ``HH:MM AM/PM``
        - ``HH:MM:SS`` (24 hour)
        - ``HH:MM`` (24 hour)

        Note that the Salt command line parser parses the date/time
        before we obtain the argument (preventing us from doing UTC)
        Therefore the argument must be passed in as a string.
        Meaning the text might have to be quoted twice on the command line.

    :param str utc_offset: The UTC offset in 4 digit (``+0600``) format with an
        optional sign (``+``/``-``).  Will default to ``None`` which will use the local
        timezone. To set the time based off of UTC use ``+0000``. Note: If
        being passed through the command line will need to be quoted twice to
        allow negative offsets (e.g. ``"'+0000'"``)
    :return: Returns ``True`` if successful. Otherwise ``False``.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_time "'11:20'"
    """
    fmts = ["%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"]
    dt_obj = _try_parse_datetime(newtime, fmts)
    if dt_obj is None:
        return False

    return set_system_date_time(
        hours=dt_obj.hour,
        minutes=dt_obj.minute,
        seconds=dt_obj.second,
        utc_offset=utc_offset,
    )


def get_system_date_time(utc_offset=None):
    """
    Get the system date/time.

    :param str utc_offset: The UTC offset in 4 digit (``+0600``) format with an
        optional sign (``+``/``-``).  Will default to ``None`` which will use the local
        timezone. To set the time based off of UTC use ``+0000``. Note: If
        being passed through the command line will need to be quoted twice to
        allow negative offsets (e.g. ``"'+0000'"``).
    :return: Returns the system time in ``YYYY-MM-DD hh:mm:ss`` format.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date_time "'-0500'"
    """
    offset_time = _get_offset_time(utc_offset)
    return datetime.strftime(offset_time, "%Y-%m-%d %H:%M:%S")


def set_system_date_time(
    years=None,
    months=None,
    days=None,
    hours=None,
    minutes=None,
    seconds=None,
    utc_offset=None,
):
    """
    Set the system date and time. Each argument is an element of the date, but
    not required. If an element is not passed, the current system value for
    that element will be used. For example, if the year is not passed, the
    current system year will be used. (Used by
    :mod:`system.set_system_date <salt.modules.system.set_system_date>` and
    :mod:`system.set_system_time <salt.modules.system.set_system_time>`)

    Updates hardware clock, if present, in addition to software
    (kernel) clock.

    :param int years: Years digit, e.g.: ``2015``
    :param int months: Months digit: ``1``-``12``
    :param int days: Days digit: ``1``-``31``
    :param int hours: Hours digit: ``0``-``23``
    :param int minutes: Minutes digit: ``0``-``59``
    :param int seconds: Seconds digit: ``0``-``59``
    :param str utc_offset: The UTC offset in 4 digit (``+0600``) format with an
        optional sign (``+``/``-``).  Will default to ``None`` which will use the local
        timezone. To set the time based off of UTC use ``+0000``. Note: If
        being passed through the command line will need to be quoted twice to
        allow negative offsets (e.g. ``"'+0000'"``).
    :return: ``True`` if successful. Otherwise ``False``.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date_time 2015 5 12 11 37 53 "'-0500'"
    """
    # Get the current date/time
    date_time = _get_offset_time(utc_offset)

    # Check for passed values. If not passed, use current values
    if years is None:
        years = date_time.year
    if months is None:
        months = date_time.month
    if days is None:
        days = date_time.day
    if hours is None:
        hours = date_time.hour
    if minutes is None:
        minutes = date_time.minute
    if seconds is None:
        seconds = date_time.second

    try:
        new_datetime = datetime(
            years, months, days, hours, minutes, seconds, 0, date_time.tzinfo
        )
    except ValueError as err:
        raise SaltInvocationError(err.message)

    if not _date_bin_set_datetime(new_datetime):
        return False

    if has_settable_hwclock():
        # Now that we've successfully set the software clock, we should
        # update hardware clock for time to persist though reboot.
        return _swclock_to_hwclock()

    return True


def get_system_date(utc_offset=None):
    """
    Get the system date

    :param str utc_offset: The UTC offset in 4 digit (``+0600``) format with an
        optional sign (``+``/``-``).  Will default to ``None`` which will use the local
        timezone. To set the time based off of UTC use ``+0000``. Note: If
        being passed through the command line will need to be quoted twice to
        allow negative offsets (e.g. ``"'+0000'"``).
    :return: Returns the system date.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_system_date
    """
    offset_time = _get_offset_time(utc_offset)
    return datetime.strftime(offset_time, "%a %m/%d/%Y")


def set_system_date(newdate, utc_offset=None):
    """
    Set the system date. Use ``<mm-dd-yy>`` format for the date.

    :param str newdate:
        The date to set. Can be any of the following formats:

        - ``YYYY-MM-DD``
        - ``MM-DD-YYYY``
        - ``MM-DD-YY``
        - ``MM/DD/YYYY``
        - ``MM/DD/YY``
        - ``YYYY/MM/DD``

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_system_date '03-28-13'
    """
    fmts = ["%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"]

    # Get date/time object from newdate
    dt_obj = _try_parse_datetime(newdate, fmts)
    if dt_obj is None:
        raise SaltInvocationError("Invalid date format")

    # Set time using set_system_date_time()
    return set_system_date_time(
        years=dt_obj.year, months=dt_obj.month, days=dt_obj.day, utc_offset=utc_offset
    )


# Class from: <https://docs.python.org/2.7/library/datetime.html>

# A class building tzinfo objects for fixed-offset time zones.
# Note that _FixedOffset(0) is a way to build a UTC tzinfo object.


class _FixedOffset(tzinfo):
    """
    Fixed offset in minutes east from UTC.
    """

    def __init__(self, offset):
        super().__init__()
        self.__offset = timedelta(minutes=offset)

    def utcoffset(self, dt):  # pylint: disable=W0613
        return self.__offset

    def tzname(self, dt):  # pylint: disable=W0613
        return None

    def dst(self, dt):  # pylint: disable=W0613
        return timedelta(0)


def _strip_quotes(str_q):
    """
    Helper function to strip off the ``'`` or ``"`` off of a string
    """
    if str_q[0] == str_q[-1] and str_q.startswith(("'", '"')):
        return str_q[1:-1]
    return str_q


def get_computer_desc():
    """
    Get ``PRETTY_HOSTNAME`` value stored in ``/etc/machine-info``
    If this file doesn't exist or the variable doesn't exist
    return ``False``.

    :return: Value of ``PRETTY_HOSTNAME`` in ``/etc/machine-info``.
        If file/variable does not exist ``False``.
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_computer_desc
    """
    hostname_cmd = salt.utils.path.which("hostnamectl")
    if hostname_cmd:
        desc = __salt__["cmd.run"](
            [hostname_cmd, "status", "--pretty"], python_shell=False
        )
    else:
        desc = None
        pattern = re.compile(r"^\s*PRETTY_HOSTNAME=(.*)$")
        try:
            with salt.utils.files.fopen("/etc/machine-info", "r") as mach_info:
                for line in mach_info.readlines():
                    line = salt.utils.stringutils.to_unicode(line)
                    match = pattern.match(line)
                    if match:
                        # get rid of whitespace then strip off quotes
                        desc = _strip_quotes(match.group(1).strip())
                        # no break so we get the last occurance
        except OSError:
            pass

        if desc is None:
            return False

    return (
        desc.replace(r"\\", "\\")
        .replace(r"\"", r'"')
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
    )


def set_computer_desc(desc):
    """
    Set ``PRETTY_HOSTNAME`` value stored in ``/etc/machine-info``
    This will create the file if it does not exist. If
    it is unable to create or modify this file, ``False`` is returned.

    :param str desc: The computer description
    :return: ``False`` on failure. ``True`` if successful.

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_computer_desc "Michael's laptop"
    """
    desc = (
        salt.utils.stringutils.to_unicode(desc)
        .replace('"', r"\"")
        .replace("\n", r"\n")
        .replace("\t", r"\t")
    )

    hostname_cmd = salt.utils.path.which("hostnamectl")
    if hostname_cmd:
        result = __salt__["cmd.retcode"](
            [hostname_cmd, "set-hostname", "--pretty", desc], python_shell=False
        )
        return True if result == 0 else False

    if not os.path.isfile("/etc/machine-info"):
        with salt.utils.files.fopen("/etc/machine-info", "w"):
            pass

    pattern = re.compile(r"^\s*PRETTY_HOSTNAME=(.*)$")
    new_line = salt.utils.stringutils.to_str(f'PRETTY_HOSTNAME="{desc}"')
    try:
        with salt.utils.files.fopen("/etc/machine-info", "r+") as mach_info:
            lines = mach_info.readlines()
            for i, line in enumerate(lines):
                if pattern.match(salt.utils.stringutils.to_unicode(line)):
                    lines[i] = new_line
                    break
            else:
                # PRETTY_HOSTNAME line was not found, add it to the end
                lines.append(new_line)
            # time to write our changes to the file
            mach_info.seek(0, 0)
            mach_info.truncate()
            mach_info.writelines(lines)
            return True
    except OSError:
        return False


def set_computer_name(hostname):
    """
    Modify hostname.

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_computer_name master.saltstack.com
    """
    return __salt__["network.mod_hostname"](hostname)


def get_computer_name():
    """
    Get hostname.

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_hostname
    """
    return __salt__["network.get_hostname"]()


def _is_nilrt_family():
    """
    Determine whether the minion is running on NI Linux RT
    """
    return __grains__.get("os_family") == "NILinuxRT"


NILRT_REBOOT_WITNESS_PATH = "/var/volatile/tmp/salt/reboot_witnessed"


@depends("_is_nilrt_family")
def set_reboot_required_witnessed():
    """
    .. note::

        This only applies to Minions running on NI Linux RT

    This function is used to remember that an event indicating that a reboot is
    required was witnessed. This function writes to a temporary filesystem so
    the event gets cleared upon reboot.

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' system.set_reboot_required_witnessed
    """
    errcode = -1
    dir_path = os.path.dirname(NILRT_REBOOT_WITNESS_PATH)
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
        except OSError as ex:
            raise SaltInvocationError(
                f"Error creating {dir_path} (-{ex.errno}): {ex.strerror}"
            )

        rdict = __salt__["cmd.run_all"](f"touch {NILRT_REBOOT_WITNESS_PATH}")
        errcode = rdict["retcode"]

    return errcode == 0


@depends("_is_nilrt_family")
def get_reboot_required_witnessed():
    """
    .. note::

        This only applies to Minions running on NI Linux RT

    Determine if at any time during the current boot session the salt minion
    witnessed an event indicating that a reboot is required.

    Returns:
        bool: ``True`` if the a reboot request was witnessed, ``False`` otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_reboot_required_witnessed
    """
    return os.path.exists(NILRT_REBOOT_WITNESS_PATH)
