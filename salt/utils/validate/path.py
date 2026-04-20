"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.utils.validate.path
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Several path related validators
"""

import logging.handlers
import os
import pathlib
import stat
from urllib.parse import urlparse


def is_syslog_path(path):
    """
    Check if a given path is a syslog path.

    <file|udp|tcp>://<host|socketpath>:<port-if-required>/<log-facility>

    log-facility is optional; must be a valid syslog facility in upper case (e.g. "LOG_USER", "LOG_DAEMON", etc.)
    see https://docs.python.org/3/library/logging.handlers.html#logging.handlers.SysLogHandler

    :param path: The path to check
    :returns: True or False
    """

    parsed_log_path = urlparse(path)

    if parsed_log_path.scheme in ("tcp", "udp", "file"):
        if parsed_log_path.scheme == "file" and parsed_log_path.path:
            path = pathlib.Path(parsed_log_path.path)
            facility_name = path.name.upper()
            if facility_name.startswith("LOG_"):
                facility = getattr(logging.handlers.SysLogHandler, facility_name, None)
                if facility is None:
                    return False
                file_path = str(path.resolve().parent)
            else:
                file_path = str(path.resolve())

            # Check if file_path is a Unix socket
            if os.path.exists(file_path):
                mode = os.stat(file_path).st_mode
                if stat.S_ISSOCK(mode):
                    return os.access(file_path, os.W_OK)
                else:
                    return False
            else:
                return False

        elif parsed_log_path.path:
            # In case of udp or tcp with a facility specified
            path = pathlib.Path(parsed_log_path.path)
            facility_name = path.stem.upper()
            if not facility_name.startswith("LOG_"):
                return False

            facility = getattr(logging.handlers.SysLogHandler, facility_name, None)
            if facility is None:
                return False
            else:
                return True

        else:
            # This is the case of udp or tcp without a facility specified
            return True
    return False


def is_writeable(path, check_parent=False):
    """
    Check if a given path is writeable by the current user.

    :param path: The path to check
    :param check_parent: If the path to check does not exist, check for the
           ability to write to the parent directory instead
    :returns: True or False
    """

    if os.access(path, os.F_OK) and os.access(path, os.W_OK):
        # The path exists and is writeable
        return True

    if os.access(path, os.F_OK) and not os.access(path, os.W_OK):
        # The path exists and is not writeable
        return False

    # The path does not exists or is not writeable

    if check_parent is False:
        # We're not allowed to check the parent directory of the provided path
        return False

    # Lets get the parent directory of the provided path
    parent_dir = os.path.dirname(path)

    if not os.access(parent_dir, os.F_OK):
        # Parent directory does not exit
        return False

    # Finally, return if we're allowed to write in the parent directory of the
    # provided path
    return os.access(parent_dir, os.W_OK)


def is_readable(path):
    """
    Check if a given path is readable by the current user.

    :param path: The path to check
    :returns: True or False
    """

    if os.access(path, os.F_OK) and os.access(path, os.R_OK):
        # The path exists and is readable
        return True

    # The path does not exist
    return False


def is_executable(path):
    """
    Check if a given path is executable by the current user.

    :param path: The path to check
    :returns: True or False
    """

    return os.access(path, os.X_OK)
