"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    runtests_helpers.py
    ~~~~~~~~~~~~~~~~~~~
"""

import logging
import os
import sys
import tempfile

import salt.utils.platform

try:
    from tests.support.runtests import RUNTIME_VARS
except ImportError:
    # Salt SSH Tests
    SYS_TMP_DIR = os.path.realpath(
        # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
        # for unix sockets: ``error: AF_UNIX path too long``
        # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
        os.environ.get("TMPDIR", tempfile.gettempdir())
        if not salt.utils.platform.is_darwin()
        else "/tmp"
    )
    # This tempdir path is defined on tests.integration.__init__
    TMP = os.path.join(SYS_TMP_DIR, "salt-tests-tmpdir")

    class RUNTIME_VARS:
        TMP = TMP
        SYS_TMP_DIR = SYS_TMP_DIR


log = logging.getLogger(__name__)


def get_salt_temp_dir():
    return RUNTIME_VARS.TMP


def get_salt_temp_dir_for_path(*path):
    return os.path.join(RUNTIME_VARS.TMP, *path)


def get_sys_temp_dir_for_path(*path):
    return os.path.join(RUNTIME_VARS.SYS_TMP_DIR, *path)


def nonzero_retcode_return_true():
    """
    Sets a nonzero retcode before returning. Designed to test orchestration.
    """
    __context__["retcode"] = 1
    return True


def nonzero_retcode_return_false():
    """
    Sets a nonzero retcode before returning. Designed to test orchestration.
    """
    __context__["retcode"] = 1
    return False


def fail_function(*args, **kwargs):  # pylint: disable=unused-argument
    """
    Return False no matter what is passed to it
    """
    return False


def get_python_executable():
    """
    Return the path to the python executable.

    This is particularly important when running the test suite within a virtualenv, while trying
    to create virtualenvs on windows.
    """
    try:
        if salt.utils.platform.is_windows():
            python_binary = os.path.join(
                sys.real_prefix, os.path.basename(sys.executable)
            )
        else:
            python_binary = os.path.join(
                sys.real_prefix, "bin", os.path.basename(sys.executable)
            )
            if not os.path.exists(python_binary):
                if not python_binary[-1].isdigit():
                    versioned_python_binary = "{}{}".format(
                        python_binary, *sys.version_info
                    )
                    log.info(
                        "Python binary could not be found at %s. Trying %s",
                        python_binary,
                        versioned_python_binary,
                    )
                    if os.path.exists(versioned_python_binary):
                        python_binary = versioned_python_binary
        if not os.path.exists(python_binary):
            log.warning("Python binary could not be found at %s", python_binary)
            python_binary = None
    except AttributeError:
        # We're not running inside a virtualenv
        python_binary = sys.executable
    return python_binary
