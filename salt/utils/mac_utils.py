# -*- coding: utf-8 -*-
"""
Helper functions for use by mac modules
.. versionadded:: 2016.3.0
"""
from __future__ import absolute_import, unicode_literals

# Import Python Libraries
import logging
import os
import plistlib
import subprocess
import time
import xml.parsers.expat

import salt.grains.extra

# Import Salt Libs
import salt.modules.cmdmod
import salt.utils.args
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.timed_subprocess
from salt.exceptions import (
    CommandExecutionError,
    SaltInvocationError,
    TimedProcTimeoutError,
)
from salt.ext import six

# Import Third Party Libs
from salt.ext.six.moves import range

try:
    import pwd
except ImportError:
    # The pwd module is not available on all platforms
    pass


DEFAULT_SHELL = salt.grains.extra.shell()["shell"]

# Set up logging
log = logging.getLogger(__name__)

__virtualname__ = "mac_utils"

__salt__ = {
    "cmd.run_all": salt.modules.cmdmod._run_all_quiet,
    "cmd.run": salt.modules.cmdmod._run_quiet,
}

if six.PY2:

    class InvalidFileException(Exception):
        pass

    plistlib.InvalidFileException = InvalidFileException


def __virtual__():
    """
    Load only on Mac OS
    """
    if not salt.utils.platform.is_darwin():
        return (
            False,
            "The mac_utils utility could not be loaded: "
            "utility only works on MacOS systems.",
        )

    return __virtualname__


def _run_all(cmd):
    """

    Args:
        cmd:

    Returns:

    """
    if not isinstance(cmd, list):
        cmd = salt.utils.args.shlex_split(cmd, posix=False)

    for idx, item in enumerate(cmd):
        if not isinstance(cmd[idx], six.string_types):
            cmd[idx] = six.text_type(cmd[idx])

    cmd = " ".join(cmd)

    run_env = os.environ.copy()

    kwargs = {
        "cwd": None,
        "shell": DEFAULT_SHELL,
        "env": run_env,
        "stdin": None,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "with_communicate": True,
        "timeout": None,
        "bg": False,
    }

    try:
        proc = salt.utils.timed_subprocess.TimedProc(cmd, **kwargs)

    except (OSError, IOError) as exc:
        raise CommandExecutionError(
            "Unable to run command '{0}' with the context '{1}', "
            "reason: {2}".format(cmd, kwargs, exc)
        )

    ret = {}

    try:
        proc.run()
    except TimedProcTimeoutError as exc:
        ret["stdout"] = six.text_type(exc)
        ret["stderr"] = ""
        ret["retcode"] = 1
        ret["pid"] = proc.process.pid
        return ret

    out, err = proc.stdout, proc.stderr

    if out is not None:
        out = salt.utils.stringutils.to_str(out).rstrip()
    if err is not None:
        err = salt.utils.stringutils.to_str(err).rstrip()

    ret["pid"] = proc.process.pid
    ret["retcode"] = proc.process.returncode
    ret["stdout"] = out
    ret["stderr"] = err

    return ret


def _check_launchctl_stderr(ret):
    """
    helper class to check the launchctl stderr.
    launchctl does not always return bad exit code
    if there is a failure
    """
    err = ret["stderr"].lower()
    if "service is disabled" in err:
        return True
    return False


def execute_return_success(cmd):
    """
    Executes the passed command. Returns True if successful

    :param str cmd: The command to run

    :return: True if successful, otherwise False
    :rtype: bool

    :raises: Error if command fails or is not supported
    """

    ret = _run_all(cmd)
    log.debug("Execute return success %s: %r", cmd, ret)

    if ret["retcode"] != 0 or "not supported" in ret["stdout"].lower():
        msg = "Command Failed: {0}\n".format(cmd)
        msg += "Return Code: {0}\n".format(ret["retcode"])
        msg += "Output: {0}\n".format(ret["stdout"])
        msg += "Error: {0}\n".format(ret["stderr"])
        raise CommandExecutionError(msg)

    return True


def execute_return_result(cmd):
    """
    Executes the passed command. Returns the standard out if successful

    :param str cmd: The command to run

    :return: The standard out of the command if successful, otherwise returns
    an error
    :rtype: str

    :raises: Error if command fails or is not supported
    """
    ret = _run_all(cmd)

    if ret["retcode"] != 0 or "not supported" in ret["stdout"].lower():
        msg = "Command Failed: {0}\n".format(cmd)
        msg += "Return Code: {0}\n".format(ret["retcode"])
        msg += "Output: {0}\n".format(ret["stdout"])
        msg += "Error: {0}\n".format(ret["stderr"])
        raise CommandExecutionError(msg)

    return ret["stdout"]


def parse_return(data):
    """
    Returns the data portion of a string that is colon separated.

    :param str data: The string that contains the data to be parsed. Usually the
    standard out from a command

    For example:
    ``Time Zone: America/Denver``
    will return:
    ``America/Denver``
    """

    if ": " in data:
        return data.split(": ")[1]
    if ":\n" in data:
        return data.split(":\n")[1]
    else:
        return data


def validate_enabled(enabled):
    """
    Helper function to validate the enabled parameter. Boolean values are
    converted to "on" and "off". String values are checked to make sure they are
    either "on" or "off"/"yes" or "no". Integer ``0`` will return "off". All
    other integers will return "on"

    :param enabled: Enabled can be boolean True or False, Integers, or string
    values "on" and "off"/"yes" and "no".
    :type: str, int, bool

    :return: "on" or "off" or errors
    :rtype: str
    """
    if isinstance(enabled, six.string_types):
        if enabled.lower() not in ["on", "off", "yes", "no"]:
            msg = (
                "\nMac Power: Invalid String Value for Enabled.\n"
                "String values must be 'on' or 'off'/'yes' or 'no'.\n"
                "Passed: {0}".format(enabled)
            )
            raise SaltInvocationError(msg)

        return "on" if enabled.lower() in ["on", "yes"] else "off"

    return "on" if bool(enabled) else "off"


def confirm_updated(value, check_fun, normalize_ret=False, wait=5):
    """
    Wait up to ``wait`` seconds for a system parameter to be changed before
    deciding it hasn't changed.

    :param str value: The value indicating a successful change

    :param function check_fun: The function whose return is compared with
        ``value``

    :param bool normalize_ret: Whether to normalize the return from
        ``check_fun`` with ``validate_enabled``

    :param int wait: The maximum amount of seconds to wait for a system
        parameter to change
    """
    for i in range(wait):
        state = validate_enabled(check_fun()) if normalize_ret else check_fun()
        log.debug(
            "Confirm update try: %d func:%r state:%s value:%s",
            i,
            check_fun,
            state,
            value,
        )
        if value in state:
            return True
        time.sleep(1)
    return False


def launchctl(sub_cmd, *args, **kwargs):
    """
    Run a launchctl command and raise an error if it fails

    Args: additional args are passed to launchctl
        sub_cmd (str): Sub command supplied to launchctl

    Kwargs: passed to ``cmd.run_all``
        return_stdout (bool): A keyword argument. If true return the stdout of
            the launchctl command

    Returns:
        bool: ``True`` if successful
        str: The stdout of the launchctl command if requested

    Raises:
        CommandExecutionError: If command fails

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.launchctl('debug', 'org.cups.cupsd')
    """
    # Get return type
    return_stdout = kwargs.pop("return_stdout", False)

    # Construct command
    cmd = ["launchctl", sub_cmd]
    cmd.extend(args)

    # Run command
    kwargs["python_shell"] = False
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    ret = __salt__["cmd.run_all"](cmd, **kwargs)
    error = _check_launchctl_stderr(ret)

    # Raise an error or return successful result
    if ret["retcode"] or error:
        out = "Failed to {0} service:\n".format(sub_cmd)
        out += "stdout: {0}\n".format(ret["stdout"])
        out += "stderr: {0}\n".format(ret["stderr"])
        out += "retcode: {0}".format(ret["retcode"])
        raise CommandExecutionError(out)
    else:
        return ret["stdout"] if return_stdout else True


def _read_plist_file(root, file_name):
    """
    :param root: The root path of the plist file
    :param file_name: The name of the plist file
    :return:  An empty dictionary if the plist file was invalid, otherwise, a dictionary with plist data
    """
    file_path = os.path.join(root, file_name)
    log.debug("read_plist: Gathering service info for {}".format(file_path))

    # Must be a plist file
    if not file_path.lower().endswith(".plist"):
        log.debug("read_plist: Not a plist file: {}".format(file_path))
        return {}

    # ignore broken symlinks
    if not os.path.exists(os.path.realpath(file_path)):
        log.warning("read_plist: Ignoring broken symlink: {}".format(file_path))
        return {}

    try:
        if six.PY2:
            # py2 plistlib can't read binary plists, and
            # uses a different API than py3.
            plist = plistlib.readPlist(file_path)
        else:
            with salt.utils.files.fopen(file_path, "rb") as handle:
                plist = plistlib.load(handle)

    except plistlib.InvalidFileException:
        # Raised in python3 if the file is not XML.
        # There's nothing we can do; move on to the next one.
        log.warning(
            'read_plist: Unable to parse "{}" as it is invalid XML: InvalidFileException.'.format(
                file_path
            )
        )
        return {}

    except xml.parsers.expat.ExpatError:
        # Raised by py2 for all errors.
        # Raised by py3 if the file is XML, but with errors.
        if six.PY3:
            # There's an error in the XML, so move on.
            log.warning(
                'read_plist: Unable to parse "{}" as it is invalid XML: xml.parsers.expat.ExpatError.'.format(
                    file_path
                )
            )
            return {}

        # Use the system provided plutil program to attempt
        # conversion from binary.
        cmd = '/usr/bin/plutil -convert xml1 -o - -- "{0}"'.format(file_path)
        try:
            plist_xml = __salt__["cmd.run"](cmd)
            plist = plistlib.readPlistFromString(plist_xml)
        except xml.parsers.expat.ExpatError:
            # There's still an error in the XML, so move on.
            log.warning(
                'read_plist: Unable to parse "{}" as it is invalid XML: xml.parsers.expat.ExpatError.'.format(
                    file_path
                )
            )
            return {}

    if "Label" not in plist:
        # not all launchd plists contain a Label key
        log.debug(
            "read_plist: Service does not contain a Label key. Skipping {}.".format(
                file_path
            )
        )
        return {}

    return {
        "file_name": file_name,
        "file_path": file_path,
        "plist": plist,
    }


def _available_services(refresh=False):
    """
    This is a helper function for getting the available macOS services.

    The strategy is to look through the known system locations for
    launchd plist files, parse them, and use their information for
    populating the list of services. Services can run without a plist
    file present, but normally services which have an automated startup
    will have a plist file, so this is a minor compromise.
    """
    if "available_services" in __context__ and not refresh:
        log.debug("Found context for available services.")
        __context__["using_cached_services"] = True
        return __context__["available_services"]

    launchd_paths = {
        "/Library/LaunchAgents",
        "/Library/LaunchDaemons",
        "/System/Library/LaunchAgents",
        "/System/Library/LaunchDaemons",
    }

    agent_path = "/Users/{}/Library/LaunchAgents"
    launchd_paths.update(
        {
            agent_path.format(user)
            for user in os.listdir("/Users/")
            if os.path.isdir(agent_path.format(user))
        }
    )

    result = {}
    for launch_dir in launchd_paths:
        for root, dirs, files in salt.utils.path.os_walk(launch_dir):
            for file_name in files:
                data = _read_plist_file(root, file_name)
                if data:
                    result[data["plist"]["Label"].lower()] = data

    # put this in __context__ as this is a time consuming function.
    # a fix for this issue. https://github.com/saltstack/salt/issues/48414
    __context__["available_services"] = result
    # this is a fresh gathering of services, set cached to false
    __context__["using_cached_services"] = False

    return result


def available_services(refresh=False):
    """
    Return a dictionary of all available services on the system

    :param bool refresh: If you wish to refresh the available services
    as this data is cached on the first run.

    Returns:
        dict: All available services

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.available_services()
    """
    log.debug("Loading available services")
    return _available_services(refresh)


def console_user(username=False):
    """
    Gets the UID or Username of the current console user.

    :return: The uid or username of the console user.

    :param bool username: Whether to return the username of the console
    user instead of the UID. Defaults to False

    :rtype: Interger of the UID, or a string of the username.

    Raises:
        CommandExecutionError: If we fail to get the UID.

    CLI Example:

    .. code-block:: bash

        import salt.utils.mac_service
        salt.utils.mac_service.console_user()
    """
    try:
        # returns the 'st_uid' stat from the /dev/console file.
        uid = os.stat("/dev/console")[4]
    except (OSError, IndexError):
        # we should never get here but raise an error if so
        raise CommandExecutionError("Failed to get a UID for the console user.")

    if username:
        return pwd.getpwuid(uid)[0]

    return uid
