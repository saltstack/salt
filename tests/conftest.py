# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    tests.conftest
    ~~~~~~~~~~~~~~

    Prepare py.test for our test suite
"""
# pylint: disable=wrong-import-order,wrong-import-position,3rd-party-local-module-not-gated
# pylint: disable=redefined-outer-name,invalid-name

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
import logging
import os
import pprint
import shutil
import socket
import stat
import sys
import tempfile
import textwrap
from contextlib import contextmanager

import _pytest.logging
import _pytest.skipping

# Import 3rd-party libs
import psutil

# Import pytest libs
import pytest
import salt.config

# Import salt libs
import salt.loader
import salt.log.mixins
import salt.log.setup
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.win_functions
from _pytest.mark.evaluate import MarkEvaluator

# Import Pytest Salt libs
from pytestsalt.utils import cli_scripts
from salt.ext import six
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze

# Import test libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

TESTS_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))
CODE_DIR = os.path.dirname(TESTS_DIR)

# Change to code checkout directory
os.chdir(CODE_DIR)

# Make sure the current directory is the first item in sys.path
if CODE_DIR in sys.path:
    sys.path.remove(CODE_DIR)
sys.path.insert(0, CODE_DIR)


# Coverage
if "COVERAGE_PROCESS_START" in os.environ:
    MAYBE_RUN_COVERAGE = True
    COVERAGERC_FILE = os.environ["COVERAGE_PROCESS_START"]
else:
    COVERAGERC_FILE = os.path.join(CODE_DIR, ".coveragerc")
    MAYBE_RUN_COVERAGE = (
        sys.argv[0].endswith("pytest.py") or "_COVERAGE_RCFILE" in os.environ
    )
    if MAYBE_RUN_COVERAGE:
        # Flag coverage to track suprocesses by pointing it to the right .coveragerc file
        os.environ[str("COVERAGE_PROCESS_START")] = str(COVERAGERC_FILE)

# Define the pytest plugins we rely on
pytest_plugins = ["tempdir", "helpers_namespace", "salt-runtests-bridge"]

# Define where not to collect tests from
collect_ignore = ["setup.py"]


# Patch PyTest logging handlers
class LogCaptureHandler(
    salt.log.mixins.ExcInfoOnLogLevelFormatMixIn, _pytest.logging.LogCaptureHandler
):
    """
    Subclassing PyTest's LogCaptureHandler in order to add the
    exc_info_on_loglevel functionality.
    """


_pytest.logging.LogCaptureHandler = LogCaptureHandler


class LiveLoggingStreamHandler(
    salt.log.mixins.ExcInfoOnLogLevelFormatMixIn,
    _pytest.logging._LiveLoggingStreamHandler,
):
    """
    Subclassing PyTest's LiveLoggingStreamHandler in order to add the
    exc_info_on_loglevel functionality.
    """


_pytest.logging._LiveLoggingStreamHandler = LiveLoggingStreamHandler

# Reset logging root handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


# Reset the root logger to it's default level(because salt changed it)
logging.root.setLevel(logging.WARNING)

log = logging.getLogger("salt.testsuite")


# ----- PyTest Tempdir Plugin Hooks --------------------------------------------------------------------------------->
def pytest_tempdir_temproot():
    # Taken from https://github.com/saltstack/salt/blob/v2019.2.0/tests/support/paths.py
    # Avoid ${TMPDIR} and gettempdir() on MacOS as they yield a base path too long
    # for unix sockets: ``error: AF_UNIX path too long``
    # Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
    if not sys.platform.startswith("darwin"):
        tempdir = os.environ.get("TMPDIR") or tempfile.gettempdir()
    else:
        tempdir = "/tmp"
    return os.path.abspath(os.path.realpath(tempdir))


def pytest_tempdir_basename():
    """
    Return the temporary directory basename for the salt test suite.
    """
    return "salt-tests-tmpdir"


# <---- PyTest Tempdir Plugin Hooks ----------------------------------------------------------------------------------


# ----- CLI Options Setup ------------------------------------------------------------------------------------------->
def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    parser.addoption(
        "--sysinfo",
        default=False,
        action="store_true",
        help="Print some system information.",
    )
    parser.addoption(
        "--transport",
        default="zeromq",
        choices=("zeromq", "tcp"),
        help=(
            "Select which transport to run the integration tests with, "
            "zeromq or tcp. Default: %default"
        ),
    )
    test_selection_group = parser.getgroup("Tests Selection")
    test_selection_group.addoption(
        "--ssh",
        "--ssh-tests",
        dest="ssh",
        action="store_true",
        default=False,
        help="Run salt-ssh tests. These tests will spin up a temporary "
        "SSH server on your machine. In certain environments, this "
        "may be insecure! Default: False",
    )
    test_selection_group.addoption(
        "--proxy",
        "--proxy-tests",
        dest="proxy",
        action="store_true",
        default=False,
        help="Run proxy tests",
    )
    test_selection_group.addoption(
        "--run-destructive",
        action="store_true",
        default=False,
        help="Run destructive tests. These tests can include adding "
        "or removing users from your system for example. "
        "Default: False",
    )
    test_selection_group.addoption(
        "--run-expensive",
        action="store_true",
        default=False,
        help="Run expensive tests. These tests usually involve costs "
        "like for example bootstrapping a cloud VM. "
        "Default: False",
    )
    output_options_group = parser.getgroup("Output Options")
    output_options_group.addoption(
        "--output-columns",
        default=80,
        type=int,
        help="Number of maximum columns to use on the output",
    )
    output_options_group.addoption(
        "--no-colors",
        "--no-colours",
        default=False,
        action="store_true",
        help="Disable colour printing.",
    )

    # ----- Test Groups --------------------------------------------------------------------------------------------->
    # This will allow running the tests in chunks
    test_selection_group.addoption(
        "--test-group-count",
        dest="test-group-count",
        type=int,
        help="The number of groups to split the tests into",
    )
    test_selection_group.addoption(
        "--test-group",
        dest="test-group",
        type=int,
        help="The group of tests that should be executed",
    )
    # <---- Test Groups ----------------------------------------------------------------------------------------------


# <---- CLI Options Setup --------------------------------------------------------------------------------------------


# ----- Register Markers -------------------------------------------------------------------------------------------->
@pytest.mark.trylast
def pytest_configure(config):
    """
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    for dirname in os.listdir(CODE_DIR):
        if not os.path.isdir(dirname):
            continue
        if dirname != "tests":
            config.addinivalue_line("norecursedirs", os.path.join(CODE_DIR, dirname))

    config.addinivalue_line("norecursedirs", os.path.join(CODE_DIR, "templates"))
    config.addinivalue_line("norecursedirs", os.path.join(CODE_DIR, "tests/kitchen"))
    config.addinivalue_line("norecursedirs", os.path.join(CODE_DIR, "tests/support"))

    # Expose the markers we use to pytest CLI
    config.addinivalue_line(
        "markers",
        "destructive_test: Run destructive tests. These tests can include adding "
        "or removing users from your system for example.",
    )
    config.addinivalue_line(
        "markers", "skip_if_not_root: Skip if the current user is not `root`."
    )
    config.addinivalue_line(
        "markers",
        "skip_if_binaries_missing(*binaries, check_all=False, message=None): Skip if "
        "any of the passed binaries are not found in path. If 'check_all' is "
        "'True', then all binaries must be found.",
    )
    config.addinivalue_line(
        "markers",
        "requires_network(only_local_network=False): Skip if no networking is set up. "
        "If 'only_local_network' is 'True', only the local network is checked.",
    )
    config.addinivalue_line(
        "markers",
        "requires_salt_modules(*required_module_names): Skip if at least one module is not available. ",
    )
    # Make sure the test suite "knows" this is a pytest test run
    RUNTIME_VARS.PYTEST_SESSION = True


# <---- Register Markers ---------------------------------------------------------------------------------------------


# ----- PyTest Tweaks ----------------------------------------------------------------------------------------------->
def set_max_open_files_limits(min_soft=3072, min_hard=4096):

    # Get current limits
    if salt.utils.platform.is_windows():
        import win32file

        prev_hard = win32file._getmaxstdio()
        prev_soft = 512
    else:
        import resource

        prev_soft, prev_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

    # Check minimum required limits
    set_limits = False
    if prev_soft < min_soft:
        soft = min_soft
        set_limits = True
    else:
        soft = prev_soft

    if prev_hard < min_hard:
        hard = min_hard
        set_limits = True
    else:
        hard = prev_hard

    # Increase limits
    if set_limits:
        log.debug(
            " * Max open files settings is too low (soft: %s, hard: %s) for running the tests. "
            "Trying to raise the limits to soft: %s, hard: %s",
            prev_soft,
            prev_hard,
            soft,
            hard,
        )
        try:
            if salt.utils.platform.is_windows():
                hard = 2048 if hard > 2048 else hard
                win32file._setmaxstdio(hard)
            else:
                resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
        except Exception as err:  # pylint: disable=broad-except
            log.error(
                "Failed to raise the max open files settings -> %s. Please issue the following command "
                "on your console: 'ulimit -u %s'",
                err,
                soft,
            )
            exit(1)
    return soft, hard


def pytest_report_header():
    soft, hard = set_max_open_files_limits()
    return "max open files; soft: {}; hard: {}".format(soft, hard)


def pytest_runtest_logstart(nodeid):
    """
    implements the runtest_setup/call/teardown protocol for
    the given test item, including capturing exceptions and calling
    reporting hooks.
    """
    log.debug(">>>>> START >>>>> %s", nodeid)


def pytest_runtest_logfinish(nodeid):
    """
    called after ``pytest_runtest_call``
    """
    log.debug("<<<<< END <<<<<<< %s", nodeid)


# <---- PyTest Tweaks ------------------------------------------------------------------------------------------------


# ----- Test Setup -------------------------------------------------------------------------------------------------->
def _has_unittest_attr(item, attr):
    # XXX: This is a hack while we support both runtests.py and PyTest
    if hasattr(item.obj, attr):
        return True
    if item.cls and hasattr(item.cls, attr):
        return True
    if item.parent and hasattr(item.parent.obj, attr):
        return True
    return False


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    destructive_tests_marker = item.get_closest_marker("destructive_test")
    if destructive_tests_marker is not None or _has_unittest_attr(
        item, "__destructive_test__"
    ):
        if item.config.getoption("--run-destructive") is False:
            item._skipped_by_mark = True
            pytest.skip("Destructive tests are disabled")
    os.environ[str("DESTRUCTIVE_TESTS")] = str(
        item.config.getoption("--run-destructive")
    )

    expensive_tests_marker = item.get_closest_marker("expensive_test")
    if expensive_tests_marker is not None or _has_unittest_attr(
        item, "__expensive_test__"
    ):
        if item.config.getoption("--run-expensive") is False:
            item._skipped_by_mark = True
            pytest.skip("Expensive tests are disabled")
    os.environ[str("EXPENSIVE_TESTS")] = str(item.config.getoption("--run-expensive"))

    skip_if_not_root_marker = item.get_closest_marker("skip_if_not_root")
    if skip_if_not_root_marker is not None or _has_unittest_attr(
        item, "__skip_if_not_root__"
    ):
        if not sys.platform.startswith("win"):
            if os.getuid() != 0:
                item._skipped_by_mark = True
                pytest.skip("You must be logged in as root to run this test")
        else:
            current_user = salt.utils.win_functions.get_current_user()
            if current_user != "SYSTEM":
                if not salt.utils.win_functions.is_admin(current_user):
                    item._skipped_by_mark = True
                    pytest.skip(
                        "You must be logged in as an Administrator to run this test"
                    )

    skip_if_binaries_missing_marker = item.get_closest_marker(
        "skip_if_binaries_missing"
    )
    if skip_if_binaries_missing_marker is not None:
        binaries = skip_if_binaries_missing_marker.args
        if len(binaries) == 1:
            if isinstance(binaries[0], (list, tuple, set, frozenset)):
                binaries = binaries[0]
        check_all = skip_if_binaries_missing_marker.kwargs.get("check_all", False)
        message = skip_if_binaries_missing_marker.kwargs.get("message", None)
        if check_all:
            for binary in binaries:
                if salt.utils.path.which(binary) is None:
                    item._skipped_by_mark = True
                    pytest.skip(
                        '{0}The "{1}" binary was not found'.format(
                            message and "{0}. ".format(message) or "", binary
                        )
                    )
        elif salt.utils.path.which_bin(binaries) is None:
            item._skipped_by_mark = True
            pytest.skip(
                "{0}None of the following binaries was found: {1}".format(
                    message and "{0}. ".format(message) or "", ", ".join(binaries)
                )
            )

    requires_network_marker = item.get_closest_marker("requires_network")
    if requires_network_marker is not None:
        only_local_network = requires_network_marker.kwargs.get(
            "only_local_network", False
        )
        has_local_network = False
        # First lets try if we have a local network. Inspired in verify_socket
        try:
            pubsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            retsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            pubsock.bind(("", 18000))
            pubsock.close()
            retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            retsock.bind(("", 18001))
            retsock.close()
            has_local_network = True
        except socket.error:
            # I wonder if we just have IPV6 support?
            try:
                pubsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                retsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                pubsock.bind(("", 18000))
                pubsock.close()
                retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                retsock.bind(("", 18001))
                retsock.close()
                has_local_network = True
            except socket.error:
                # Let's continue
                pass

        if only_local_network is True:
            if has_local_network is False:
                # Since we're only supposed to check local network, and no
                # local network was detected, skip the test
                item._skipped_by_mark = True
                pytest.skip("No local network was detected")

        # We are using the google.com DNS records as numerical IPs to avoid
        # DNS lookups which could greatly slow down this check
        for addr in (
            "173.194.41.198",
            "173.194.41.199",
            "173.194.41.200",
            "173.194.41.201",
            "173.194.41.206",
            "173.194.41.192",
            "173.194.41.193",
            "173.194.41.194",
            "173.194.41.195",
            "173.194.41.196",
            "173.194.41.197",
        ):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.25)
                sock.connect((addr, 80))
                sock.close()
                # We connected? Stop the loop
                break
            except socket.error:
                # Let's check the next IP
                continue
            else:
                item._skipped_by_mark = True
                pytest.skip("No internet network connection was detected")

    requires_salt_modules_marker = item.get_closest_marker("requires_salt_modules")
    if requires_salt_modules_marker is not None:
        required_salt_modules = requires_salt_modules_marker.args
        if len(required_salt_modules) == 1 and isinstance(
            required_salt_modules[0], (list, tuple, set)
        ):
            required_salt_modules = required_salt_modules[0]
        required_salt_modules = set(required_salt_modules)
        sminion = create_sminion()
        available_modules = list(sminion.functions)
        not_available_modules = set()
        try:
            cached_not_available_modules = sminion.__not_availiable_modules__
        except AttributeError:
            cached_not_available_modules = sminion.__not_availiable_modules__ = set()

        if cached_not_available_modules:
            for not_available_module in cached_not_available_modules:
                if not_available_module in required_salt_modules:
                    not_available_modules.add(not_available_module)
                    required_salt_modules.remove(not_available_module)

        for required_module_name in required_salt_modules:
            search_name = required_module_name
            if "." not in search_name:
                search_name += ".*"
                if not fnmatch.filter(available_modules, search_name):
                    not_available_modules.add(required_module_name)
                    cached_not_available_modules.add(required_module_name)

        if not_available_modules:
            item._skipped_by_mark = True
            if len(not_available_modules) == 1:
                pytest.skip(
                    "Salt module '{}' is not available".format(*not_available_modules)
                )
            pytest.skip(
                "Salt modules not available: {}".format(
                    ", ".join(not_available_modules)
                )
            )


# <---- Test Setup ---------------------------------------------------------------------------------------------------


# ----- Test Groups Selection --------------------------------------------------------------------------------------->
def get_group_size(total_items, total_groups):
    """
    Return the group size.
    """
    return int(total_items / total_groups)


def get_group(items, group_count, group_size, group_id):
    """
    Get the items from the passed in group based on group size.
    """
    start = group_size * (group_id - 1)
    end = start + group_size
    total_items = len(items)

    if start >= total_items:
        pytest.fail(
            "Invalid test-group argument. start({})>=total_items({})".format(
                start, total_items
            )
        )
    elif start < 0:
        pytest.fail("Invalid test-group argument. Start({})<0".format(start))

    if group_count == group_id and end < total_items:
        # If this is the last group and there are still items to test
        # which don't fit in this group based on the group items count
        # add them anyway
        end = total_items

    return items[start:end]


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_modifyitems(config, items):
    # Let PyTest or other plugins handle the initial collection
    yield

    group_count = config.getoption("test-group-count")
    group_id = config.getoption("test-group")

    if not group_count or not group_id:
        # We're not selection tests using groups, don't do any filtering
        return

    total_items = len(items)

    group_size = get_group_size(total_items, group_count)
    tests_in_group = get_group(items, group_count, group_size, group_id)
    # Replace all items in the list
    items[:] = tests_in_group

    terminal_reporter = config.pluginmanager.get_plugin("terminalreporter")
    terminal_reporter.write(
        "Running test group #{0} ({1} tests)\n".format(group_id, len(items)),
        yellow=True,
    )


# <---- Test Groups Selection ----------------------------------------------------------------------------------------


# ----- Pytest Helpers ---------------------------------------------------------------------------------------------->
if six.PY2:
    # backport mock_open from the python 3 unittest.mock library so that we can
    # mock read, readline, readlines, and file iteration properly

    file_spec = None

    def _iterate_read_data(read_data):
        # Helper for mock_open:
        # Retrieve lines from read_data via a generator so that separate calls to
        # readline, read, and readlines are properly interleaved
        data_as_list = ["{0}\n".format(l) for l in read_data.split("\n")]

        if data_as_list[-1] == "\n":
            # If the last line ended in a newline, the list comprehension will have an
            # extra entry that's just a newline.  Remove this.
            data_as_list = data_as_list[:-1]
        else:
            # If there wasn't an extra newline by itself, then the file being
            # emulated doesn't have a newline to end the last line  remove the
            # newline that our naive format() added
            data_as_list[-1] = data_as_list[-1][:-1]

        for line in data_as_list:
            yield line

    @pytest.helpers.mock.register
    def mock_open(mock=None, read_data=""):
        """
        A helper function to create a mock to replace the use of `open`. It works
        for `open` called directly or used as a context manager.

        The `mock` argument is the mock object to configure. If `None` (the
        default) then a `MagicMock` will be created for you, with the API limited
        to methods or attributes available on standard file handles.

        `read_data` is a string for the `read` methoddline`, and `readlines` of the
        file handle to return.  This is an empty string by default.
        """
        _mock = pytest.importorskip("mock", minversion="2.0.0")

        def _readlines_side_effect(*args, **kwargs):
            if handle.readlines.return_value is not None:
                return handle.readlines.return_value
            return list(_data)

        def _read_side_effect(*args, **kwargs):
            if handle.read.return_value is not None:
                return handle.read.return_value
            return "".join(_data)

        def _readline_side_effect():
            if handle.readline.return_value is not None:
                while True:
                    yield handle.readline.return_value
            for line in _data:
                yield line

        global file_spec
        if file_spec is None:
            file_spec = file  # pylint: disable=undefined-variable

        if mock is None:
            mock = _mock.MagicMock(name="open", spec=open)

        handle = _mock.MagicMock(spec=file_spec)
        handle.__enter__.return_value = handle

        _data = _iterate_read_data(read_data)

        handle.write.return_value = None
        handle.read.return_value = None
        handle.readline.return_value = None
        handle.readlines.return_value = None

        handle.read.side_effect = _read_side_effect
        handle.readline.side_effect = _readline_side_effect()
        handle.readlines.side_effect = _readlines_side_effect

        mock.return_value = handle
        return mock


else:

    @pytest.helpers.mock.register
    def mock_open(mock=None, read_data=""):
        _mock = pytest.importorskip("mock", minversion="2.0.0")
        return _mock.mock_open(mock=mock, read_data=read_data)


@pytest.helpers.register
@contextmanager
def temp_directory(name=None):
    if name is not None:
        directory_path = os.path.join(RUNTIME_VARS.TMP, name)
    else:
        directory_path = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    yield directory_path

    shutil.rmtree(directory_path, ignore_errors=True)


@pytest.helpers.register
@contextmanager
def temp_file(name, contents=None, directory=None, strip_first_newline=True):
    if directory is None:
        directory = RUNTIME_VARS.TMP

    file_path = os.path.join(directory, name)
    file_directory = os.path.dirname(file_path)
    if contents is not None:
        if contents:
            if contents.startswith("\n") and strip_first_newline:
                contents = contents[1:]
            file_contents = textwrap.dedent(contents)
        else:
            file_contents = contents

    try:
        if not os.path.isdir(file_directory):
            os.makedirs(file_directory)
        if contents is not None:
            with salt.utils.files.fopen(file_path, "w") as wfh:
                wfh.write(file_contents)

        yield file_path

    finally:
        try:
            os.unlink(file_path)
        except OSError:
            # Already deleted
            pass


@pytest.helpers.register
def temp_state_file(name, contents, saltenv="base", strip_first_newline=True):

    if saltenv == "base":
        directory = RUNTIME_VARS.TMP_STATE_TREE
    elif saltenv == "prod":
        directory = RUNTIME_VARS.TMP_PRODENV_STATE_TREE
    else:
        raise RuntimeError(
            '"saltenv" can only be "base" or "prod", not "{}"'.format(saltenv)
        )
    return temp_file(
        name, contents, directory=directory, strip_first_newline=strip_first_newline
    )


# <---- Pytest Helpers -----------------------------------------------------------------------------------------------


# ----- Fixtures Overrides ------------------------------------------------------------------------------------------>
# ----- Generate CLI Scripts ---------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def cli_master_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_master.py"


@pytest.fixture(scope="session")
def cli_minion_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_minion.py"


@pytest.fixture(scope="session")
def cli_salt_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt.py"


@pytest.fixture(scope="session")
def cli_run_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_run.py"


@pytest.fixture(scope="session")
def cli_key_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_key.py"


@pytest.fixture(scope="session")
def cli_call_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_call.py"


@pytest.fixture(scope="session")
def cli_syndic_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_syndic.py"


@pytest.fixture(scope="session")
def cli_ssh_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_ssh.py"


@pytest.fixture(scope="session")
def cli_proxy_script_name():
    """
    Return the CLI script basename
    """
    return "cli_salt_proxy.py"


@pytest.fixture(scope="session")
def cli_bin_dir(
    tempdir,
    request,
    python_executable_path,
    cli_master_script_name,
    cli_minion_script_name,
    cli_salt_script_name,
    cli_call_script_name,
    cli_key_script_name,
    cli_run_script_name,
    cli_ssh_script_name,
    cli_syndic_script_name,
    cli_proxy_script_name,
):
    """
    Return the path to the CLI script directory to use
    """
    tmp_cli_scripts_dir = tempdir.join("cli-scrips-bin")
    # Make sure we re-write the scripts every time we start the tests
    shutil.rmtree(tmp_cli_scripts_dir.strpath, ignore_errors=True)
    tmp_cli_scripts_dir.ensure(dir=True)
    cli_bin_dir_path = tmp_cli_scripts_dir.strpath

    # Now that we have the CLI directory created, lets generate the required CLI scripts to run salt's test suite
    for script_name in (
        cli_master_script_name,
        cli_minion_script_name,
        cli_call_script_name,
        cli_key_script_name,
        cli_run_script_name,
        cli_salt_script_name,
        cli_ssh_script_name,
        cli_syndic_script_name,
        cli_proxy_script_name,
    ):
        original_script_name = (
            os.path.splitext(script_name)[0].split("cli_")[-1].replace("_", "-")
        )
        cli_scripts.generate_script(
            bin_dir=cli_bin_dir_path,
            script_name=original_script_name,
            executable=sys.executable,
            code_dir=CODE_DIR,
            inject_sitecustomize=MAYBE_RUN_COVERAGE,
        )

    # Return the CLI bin dir value
    return cli_bin_dir_path


# <---- Generate CLI Scripts -----------------------------------------------------------------------------------------


# ----- Salt Configuration ------------------------------------------------------------------------------------------>
@pytest.fixture(scope="session")
def session_master_of_masters_id():
    """
    Returns the master of masters id
    """
    return "syndic_master"


@pytest.fixture(scope="session")
def session_master_id():
    """
    Returns the session scoped master id
    """
    return "master"


@pytest.fixture(scope="session")
def session_minion_id():
    """
    Returns the session scoped minion id
    """
    return "minion"


@pytest.fixture(scope="session")
def session_secondary_minion_id():
    """
    Returns the session scoped secondary minion id
    """
    return "sub_minion"


@pytest.fixture(scope="session")
def session_syndic_id():
    """
    Returns the session scoped syndic id
    """
    return "syndic"


@pytest.fixture(scope="session")
def session_proxy_id():
    """
    Returns the session scoped proxy id
    """
    return "proxytest"


@pytest.fixture(scope="session")
def salt_fail_hard():
    """
    Return the salt fail hard value
    """
    return True


@pytest.fixture(scope="session")
def session_master_default_options(request, session_root_dir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        opts = yaml.deserialize(rfh.read())

        tests_known_hosts_file = session_root_dir.join("salt_ssh_known_hosts").strpath
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

        opts["known_hosts_file"] = tests_known_hosts_file
        opts["syndic_master"] = "localhost"
        opts["transport"] = request.config.getoption("--transport")

        # Config settings to test `event_return`
        if "returner_dirs" not in opts:
            opts["returner_dirs"] = []
        opts["returner_dirs"].append(os.path.join(RUNTIME_VARS.FILES, "returners"))
        opts["event_return"] = "runtests_noop"

        return opts


@pytest.fixture(scope="session")
def session_master_config_overrides(session_root_dir):
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {
                "cmd_yaml": "type {0}".format(
                    os.path.join(RUNTIME_VARS.FILES, "ext.yaml")
                )
            }
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {0}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    ext_pillar.append(
        {
            "file_tree": {
                "root_dir": os.path.join(RUNTIME_VARS.PILLAR_DIR, "base", "file_tree"),
                "follow_dir_links": False,
                "keep_newline": True,
            }
        }
    )

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = session_root_dir.join("extension_modules").strpath
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = session_root_dir.join("autosign_file").strpath
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    pytest_stop_sending_events_file = session_root_dir.join(
        "pytest_stop_sending_events_file"
    ).strpath
    with salt.utils.files.fopen(pytest_stop_sending_events_file, "w") as wfh:
        wfh.write("")

    return {
        "pillar_opts": True,
        "ext_pillar": ext_pillar,
        "extension_modules": extension_modules_path,
        "file_roots": {
            "base": [os.path.join(RUNTIME_VARS.FILES, "file", "base")],
            # Alternate root to test __env__ choices
            "prod": [os.path.join(RUNTIME_VARS.FILES, "file", "prod")],
        },
        "pillar_roots": {"base": [os.path.join(RUNTIME_VARS.FILES, "pillar", "base")]},
        "reactor": [
            {
                "salt/minion/*/start": [
                    os.path.join(RUNTIME_VARS.FILES, "reactor-sync-minion.sls")
                ],
            },
            {
                "salt/test/reactor": [
                    os.path.join(RUNTIME_VARS.FILES, "reactor-test.sls")
                ],
            },
        ],
        "pytest_stop_sending_events_file": pytest_stop_sending_events_file,
    }


@pytest.fixture(scope="session")
def session_minion_default_options(request, tempdir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = tempdir.join("hosts").strpath
        opts["aliases.file"] = tempdir.join("aliases").strpath
        opts["transport"] = request.config.getoption("--transport")

        return opts


def _get_virtualenv_binary_path():
    try:
        return _get_virtualenv_binary_path.__virtualenv_binary__
    except AttributeError:
        # Under windows we can't seem to properly create a virtualenv off of another
        # virtualenv, we can on linux but we will still point to the virtualenv binary
        # outside the virtualenv running the test suite, if that's the case.
        try:
            real_prefix = sys.real_prefix
            # The above attribute exists, this is a virtualenv
            if salt.utils.platform.is_windows():
                virtualenv_binary = os.path.join(
                    real_prefix, "Scripts", "virtualenv.exe"
                )
            else:
                # We need to remove the virtualenv from PATH or we'll get the virtualenv binary
                # from within the virtualenv, we don't want that
                path = os.environ.get("PATH")
                if path is not None:
                    path_items = path.split(os.pathsep)
                    for item in path_items[:]:
                        if item.startswith(sys.base_prefix):
                            path_items.remove(item)
                    os.environ["PATH"] = os.pathsep.join(path_items)
                virtualenv_binary = salt.utils.path.which("virtualenv")
                if path is not None:
                    # Restore previous environ PATH
                    os.environ["PATH"] = path
                if not virtualenv_binary.startswith(real_prefix):
                    virtualenv_binary = None
            if virtualenv_binary and not os.path.exists(virtualenv_binary):
                # It doesn't exist?!
                virtualenv_binary = None
        except AttributeError:
            # We're not running inside a virtualenv
            virtualenv_binary = None
        _get_virtualenv_binary_path.__virtualenv_binary__ = virtualenv_binary
        return virtualenv_binary


@pytest.fixture(scope="session")
def session_minion_config_overrides():
    opts = {
        "file_roots": {
            "base": [os.path.join(RUNTIME_VARS.FILES, "file", "base")],
            # Alternate root to test __env__ choices
            "prod": [os.path.join(RUNTIME_VARS.FILES, "file", "prod")],
        },
        "pillar_roots": {"base": [os.path.join(RUNTIME_VARS.FILES, "pillar", "base")]},
    }
    virtualenv_binary = _get_virtualenv_binary_path()
    if virtualenv_binary:
        opts["venv_bin"] = virtualenv_binary
    return opts


@pytest.fixture(scope="session")
def session_secondary_minion_default_options(request, tempdir):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = tempdir.join("hosts").strpath
        opts["aliases.file"] = tempdir.join("aliases").strpath
        opts["transport"] = request.config.getoption("--transport")

        return opts


@pytest.fixture(scope="session")
def session_seconary_minion_config_overrides():
    opts = {}
    virtualenv_binary = _get_virtualenv_binary_path()
    if virtualenv_binary:
        opts["venv_bin"] = virtualenv_binary
    return opts


@pytest.fixture(scope="session")
def session_master_of_masters_default_options(request, tempdir):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "syndic_master")
    ) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = tempdir.join("hosts").strpath
        opts["aliases.file"] = tempdir.join("aliases").strpath
        opts["transport"] = request.config.getoption("--transport")

        return opts


@pytest.fixture(scope="session")
def session_master_of_masters_config_overrides(session_master_of_masters_root_dir):
    if salt.utils.platform.is_windows():
        ext_pillar = {
            "cmd_yaml": "type {0}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))
        }
    else:
        ext_pillar = {
            "cmd_yaml": "cat {0}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))
        }

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = session_master_of_masters_root_dir.join(
        "extension_modules"
    ).strpath
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = session_master_of_masters_root_dir.join(
        "autosign_file"
    ).strpath
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    pytest_stop_sending_events_file = session_master_of_masters_root_dir.join(
        "pytest_stop_sending_events_file"
    ).strpath
    with salt.utils.files.fopen(pytest_stop_sending_events_file, "w") as wfh:
        wfh.write("")

    return {
        "ext_pillar": [ext_pillar],
        "extension_modules": extension_modules_path,
        "file_roots": {
            "base": [os.path.join(RUNTIME_VARS.FILES, "file", "base")],
            # Alternate root to test __env__ choices
            "prod": [os.path.join(RUNTIME_VARS.FILES, "file", "prod")],
        },
        "pillar_roots": {"base": [os.path.join(RUNTIME_VARS.FILES, "pillar", "base")]},
        "pytest_stop_sending_events_file": pytest_stop_sending_events_file,
    }


@pytest.fixture(scope="session")
def session_syndic_master_default_options(request, tempdir):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "syndic_master")
    ) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = tempdir.join("hosts").strpath
        opts["aliases.file"] = tempdir.join("aliases").strpath
        opts["transport"] = request.config.getoption("--transport")

        return opts


@pytest.fixture(scope="session")
def session_syndic_default_options(request, tempdir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "syndic")) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = tempdir.join("hosts").strpath
        opts["aliases.file"] = tempdir.join("aliases").strpath
        opts["transport"] = request.config.getoption("--transport")

        return opts


@pytest.fixture(scope="session")
def session_proxy_default_options(request, tempdir):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "proxy")) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = tempdir.join("hosts").strpath
        opts["aliases.file"] = tempdir.join("aliases").strpath
        opts["transport"] = request.config.getoption("--transport")

        return opts


@pytest.fixture(scope="session", autouse=True)
def bridge_pytest_and_runtests(
    reap_stray_processes,
    session_root_dir,
    session_conf_dir,
    session_secondary_conf_dir,
    session_syndic_conf_dir,
    session_master_of_masters_conf_dir,
    session_base_env_pillar_tree_root_dir,
    session_base_env_state_tree_root_dir,
    session_prod_env_state_tree_root_dir,
    session_master_config,
    session_minion_config,
    session_secondary_minion_config,
    session_master_of_masters_config,
    session_syndic_config,
):

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = session_root_dir.realpath().strpath
    RUNTIME_VARS.TMP_CONF_DIR = session_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = session_secondary_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = (
        session_master_of_masters_conf_dir.realpath().strpath
    )
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = session_syndic_conf_dir.realpath().strpath
    RUNTIME_VARS.TMP_PILLAR_TREE = (
        session_base_env_pillar_tree_root_dir.realpath().strpath
    )
    RUNTIME_VARS.TMP_STATE_TREE = (
        session_base_env_state_tree_root_dir.realpath().strpath
    )
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = (
        session_prod_env_state_tree_root_dir.realpath().strpath
    )

    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(session_master_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(session_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(session_secondary_minion_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic_master"] = freeze(
        session_master_of_masters_config
    )
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic"] = freeze(session_syndic_config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(session_conf_dir.join("master").strpath)
    )

    # Copy configuration files and directories which are not automatically generated
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if entry in (
            "master",
            "minion",
            "sub_minion",
            "syndic",
            "syndic_master",
            "proxy",
        ):
            # These have runtime computed values and are handled by pytest-salt fixtures
            continue
        entry_path = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        if os.path.isfile(entry_path):
            shutil.copy(entry_path, os.path.join(RUNTIME_VARS.TMP_CONF_DIR, entry))
        elif os.path.isdir(entry_path):
            shutil.copytree(entry_path, os.path.join(RUNTIME_VARS.TMP_CONF_DIR, entry))


# <---- Salt Configuration -------------------------------------------------------------------------------------------
# <---- Fixtures Overrides -------------------------------------------------------------------------------------------


# ----- Custom Grains Mark Evaluator -------------------------------------------------------------------------------->
class GrainsMarkEvaluator(MarkEvaluator):
    _cached_grains = None

    def _getglobals(self):
        item_globals = super(GrainsMarkEvaluator, self)._getglobals()
        if GrainsMarkEvaluator._cached_grains is None:
            sminion = create_sminion()
            GrainsMarkEvaluator._cached_grains = sminion.opts["grains"].copy()
        item_globals["grains"] = GrainsMarkEvaluator._cached_grains.copy()
        return item_globals


# Patch PyTest's skipping MarkEvaluator to use our GrainsMarkEvaluator
_pytest.skipping.MarkEvaluator = GrainsMarkEvaluator
# <---- Custom Grains Mark Evaluator ---------------------------------------------------------------------------------


# ----- Custom Fixtures --------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def reap_stray_processes():
    # Run tests
    yield

    children = psutil.Process(os.getpid()).children(recursive=True)
    if not children:
        log.info("No astray processes found")
        return

    def on_terminate(proc):
        log.debug("Process %s terminated with exit code %s", proc, proc.returncode)

    if children:
        # Reverse the order, sublings first, parents after
        children.reverse()
        log.warning(
            "Test suite left %d astray processes running. Killing those processes:\n%s",
            len(children),
            pprint.pformat(children),
        )

        _, alive = psutil.wait_procs(children, timeout=3, callback=on_terminate)
        for child in alive:
            child.kill()

        _, alive = psutil.wait_procs(alive, timeout=3, callback=on_terminate)
        if alive:
            # Give up
            for child in alive:
                log.warning(
                    "Process %s survived SIGKILL, giving up:\n%s",
                    child,
                    pprint.pformat(child.as_dict()),
                )


@pytest.fixture(scope="session")
def grains(request):
    sminion = create_sminion()
    return sminion.opts["grains"].copy()


# <---- Custom Fixtures ----------------------------------------------------------------------------------------------
