# pylint: disable=wrong-import-order,wrong-import-position,3rd-party-local-module-not-gated
# pylint: disable=redefined-outer-name,invalid-name,3rd-party-module-not-gated


import logging
import os
import pathlib
import re
import shutil
import stat
import sys
from functools import lru_cache
from unittest import TestCase  # pylint: disable=blacklisted-module

import _pytest.logging
import _pytest.skipping
import more_itertools
import pytest

import salt
import salt._logging
import salt._logging.mixins
import salt.config
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.win_functions
from salt.serializers import yaml
from salt.utils.immutabletypes import freeze
from tests.support.helpers import (
    PRE_PYTEST_SKIP_OR_NOT,
    PRE_PYTEST_SKIP_REASON,
    get_virtualenv_binary_path,
)
from tests.support.pytest.helpers import *  # pylint: disable=unused-wildcard-import,wildcard-import
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import check_required_sminion_attributes, create_sminion

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PYTESTS_DIR = TESTS_DIR / "pytests"
CODE_DIR = TESTS_DIR.parent

# Change to code checkout directory
os.chdir(str(CODE_DIR))

# Make sure the current directory is the first item in sys.path
if str(CODE_DIR) in sys.path:
    sys.path.remove(str(CODE_DIR))
if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
    sys.path.insert(0, str(CODE_DIR))

os.environ["REPO_ROOT_DIR"] = str(CODE_DIR)

# Coverage
if "COVERAGE_PROCESS_START" in os.environ:
    MAYBE_RUN_COVERAGE = True
    COVERAGERC_FILE = os.environ["COVERAGE_PROCESS_START"]
else:
    COVERAGERC_FILE = str(CODE_DIR / ".coveragerc")
    MAYBE_RUN_COVERAGE = (
        sys.argv[0].endswith("pytest.py") or "_COVERAGE_RCFILE" in os.environ
    )
    if MAYBE_RUN_COVERAGE:
        # Flag coverage to track suprocesses by pointing it to the right .coveragerc file
        os.environ["COVERAGE_PROCESS_START"] = str(COVERAGERC_FILE)

# Variable defining a FIPS test run or not
FIPS_TESTRUN = os.environ.get("FIPS_TESTRUN", "0") == "1"

# Define the pytest plugins we rely on
pytest_plugins = ["helpers_namespace"]

# Define where not to collect tests from
collect_ignore = ["setup.py"]


# Patch PyTest logging handlers
class LogCaptureHandler(
    salt._logging.mixins.ExcInfoOnLogLevelFormatMixin, _pytest.logging.LogCaptureHandler
):
    """
    Subclassing PyTest's LogCaptureHandler in order to add the
    exc_info_on_loglevel functionality and actually make it a NullHandler,
    it's only used to print log messages emmited during tests, which we
    have explicitly disabled in pytest.ini
    """


_pytest.logging.LogCaptureHandler = LogCaptureHandler


class LiveLoggingStreamHandler(
    salt._logging.mixins.ExcInfoOnLogLevelFormatMixin,
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
    handler.close()


# Reset the root logger to its default level(because salt changed it)
logging.root.setLevel(logging.WARNING)

log = logging.getLogger("salt.testsuite")


# ----- CLI Options Setup ------------------------------------------------------------------------------------------->
def pytest_addoption(parser):
    """
    register argparse-style options and ini-style config values.
    """
    test_selection_group = parser.getgroup("Tests Selection")
    test_selection_group.addoption(
        "--from-filenames",
        default=None,
        help=(
            "Pass a comma-separated list of file paths, and any test module which"
            " corresponds to the specified file(s) will run. For example, if 'setup.py'"
            " was passed, then the corresponding test files defined in"
            " 'tests/filename_map.yml' would run. Absolute paths are assumed to be"
            " files containing relative paths, one per line. Providing the paths in a"
            " file can help get around shell character limits when the list of files is"
            " long."
        ),
    )
    # Add deprecated CLI flag until we completely switch to PyTest
    test_selection_group.addoption(
        "--names-file", default=None, help="Deprecated option"
    )
    test_selection_group.addoption(
        "--transport",
        default="zeromq",
        choices=("zeromq", "tcp"),
        help=(
            "Select which transport to run the integration tests with, zeromq or tcp."
            " Default: %(default)s"
        ),
    )
    test_selection_group.addoption(
        "--ssh",
        "--ssh-tests",
        dest="ssh",
        action="store_true",
        default=False,
        help=(
            "Run salt-ssh tests. These tests will spin up a temporary "
            "SSH server on your machine. In certain environments, this "
            "may be insecure! Default: False"
        ),
    )
    test_selection_group.addoption(
        "--no-fast",
        "--no-fast-tests",
        dest="fast",
        action="store_true",
        default=False,
        help="Don't run salt-fast tests. Default: %(default)s",
    )
    test_selection_group.addoption(
        "--run-slow",
        "--slow",
        "--slow-tests",
        dest="slow",
        action="store_true",
        default=False,
        help="Run slow tests. Default: %(default)s",
    )
    test_selection_group.addoption(
        "--core",
        "--core-tests",
        dest="core",
        action="store_true",
        default=False,
        help=(
            "Run salt-core tests. These tests test the engine of salt! "
            "Default: %(default)s"
        ),
    )
    test_selection_group.addoption(
        "--flaky",
        "--flaky-jail",
        dest="flaky",
        action="store_true",
        default=False,
        help=(
            "Run salt-flaky jail tests. These tests are in jail for being flaky! "
            "One day they will be made not flaky."
            "Default: %(default)s"
        ),
    )
    test_selection_group.addoption(
        "--proxy",
        "--proxy-tests",
        dest="proxy",
        action="store_true",
        default=False,
        help="Run proxy tests (DEPRECATED)",
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
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """
    called after command line options have been parsed
    and all plugins and initial conftest files been loaded.
    """
    try:
        assert config._onedir_check_complete
        return
    except AttributeError:
        if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
            if pathlib.Path(salt.__file__).parent == CODE_DIR / "salt":
                raise pytest.UsageError(
                    "Apparently running the test suite against the onedir build "
                    "of salt, however, the imported salt package is pointing to "
                    "the respository checkout instead of the onedir package.\n\n"
                    f"  * sys.path: {sys.path}"
                )
        config._onedir_check_complete = True

    for dirname in CODE_DIR.iterdir():
        if not dirname.is_dir():
            continue
        if dirname != TESTS_DIR:
            config.addinivalue_line("norecursedirs", str(CODE_DIR / dirname))
    config.addinivalue_line(
        "norecursedirs",
        str(TESTS_DIR / "unit" / "modules" / "inspectlib" / "tree_test"),
    )

    # Expose the markers we use to pytest CLI
    config.addinivalue_line(
        "markers",
        "requires_salt_modules(*required_module_names): Skip if at least one module is"
        " not available.",
    )
    config.addinivalue_line(
        "markers",
        "requires_salt_states(*required_state_names): Skip if at least one state module"
        " is not available.",
    )
    config.addinivalue_line(
        "markers", "windows_whitelisted: Mark test as whitelisted to run under Windows"
    )
    config.addinivalue_line(
        "markers", "requires_sshd_server: Mark test that require an SSH server running"
    )
    config.addinivalue_line(
        "markers",
        "slow_test: Mark test as being slow. These tests are skipped by default unless"
        " `--run-slow` is passed",
    )
    config.addinivalue_line(
        "markers",
        "core_test: Mark test as being core. These tests are skipped by default unless"
        " `--core-tests` is passed",
    )
    config.addinivalue_line(
        "markers",
        "flaky_jail: Mark test as being jlaky. These tests are skipped by default unless"
        " `--flaky-jail` is passed",
    )
    config.addinivalue_line(
        "markers",
        "async_timeout: Timeout, in seconds, for asynchronous test functions(`async def`)",
    )
    config.addinivalue_line(
        "markers",
        "requires_random_entropy(minimum={}, timeout={}, skip=True): Mark test as "
        "requiring a minimum value of random entropy. In the case where the value is lower "
        "than the provided 'minimum', an attempt will be made to raise that value up until "
        "the provided 'timeout' minutes have passed, at which time, depending on the value "
        "of 'skip' the test will skip or fail.  For entropy poolsizes of 256 bits, the min "
        "is adjusted to 192.".format(
            EntropyGenerator.minimum_entropy, EntropyGenerator.max_minutes
        ),
    )
    config.addinivalue_line(
        "markers",
        "skip_initial_gh_actions_failure(skip=<boolean or callable, reason=None): Skip known test failures "
        "under the new GH Actions setup if the environment variable SKIP_INITIAL_GH_ACTIONS_FAILURES "
        "is equal to '1' and the 'skip' keyword argument is either `True` or it's a callable that "
        "when called returns `True`. If `skip` is a callable, it should accept a single argument "
        "'grains', which is the grains dictionary.",
    )
    config.addinivalue_line(
        "markers",
        "skip_initial_onedir_failure(skip=<boolean or callable, reason=None): Skip known test failures "
        "under the new onedir builds if the environment variable SKIP_INITIAL_ONEDIR_FAILURES "
        "is equal to '1' and the 'skip' keyword argument is either `True` or it's a callable that "
        "when called returns `True`. If `skip` is a callable, it should accept a single argument "
        "'grains', which is the grains dictionary.",
    )
    config.addinivalue_line(
        "markers",
        "timeout_unless_on_windows(*args, **kwargs): Apply the 'timeout' marker unless running "
        "on Windows.",
    )
    # "Flag" the slowTest decorator if we're skipping slow tests or not
    os.environ["SLOW_TESTS"] = str(config.getoption("--run-slow"))


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
            " * Max open files settings is too low (soft: %s, hard: %s) for running the"
            " tests. Trying to raise the limits to soft: %s, hard: %s",
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
                "Failed to raise the max open files settings -> %s. Please issue the"
                " following command on your console: 'ulimit -u %s'",
                err,
                soft,
            )
            exit(1)
    return soft, hard


def pytest_report_header(config):
    soft, hard = set_max_open_files_limits()
    transport = config.getoption("--transport")
    return f"max open files: soft={soft}; hard={hard}\nsalt-transport: {transport}"


def pytest_itemcollected(item):
    """We just collected a test item."""
    try:
        pathlib.Path(item.fspath.strpath).resolve().relative_to(PYTESTS_DIR)
        # Test is under tests/pytests
        if item.cls and issubclass(item.cls, TestCase):
            pytest.fail(
                "The tests under {0!r} MUST NOT use unittest's TestCase class or a"
                " subclass of it. Please move {1!r} outside of {0!r}".format(
                    str(PYTESTS_DIR.relative_to(CODE_DIR)), item.nodeid
                )
            )
    except ValueError:
        # Test is not under tests/pytests
        if not item.cls or (item.cls and not issubclass(item.cls, TestCase)):
            pytest.fail(
                "The test {!r} appears to be written for pytest but it's not under"
                " {!r}. Please move it there.".format(
                    item.nodeid, str(PYTESTS_DIR.relative_to(CODE_DIR)), pytrace=False
                )
            )


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_collection_modifyitems(config, items):
    """
    called after collection has been performed, may filter or re-order
    the items in-place.

    :param _pytest.main.Session session: the pytest session object
    :param _pytest.config.Config config: pytest config object
    :param List[_pytest.nodes.Item] items: list of item objects
    """
    # Let PyTest or other plugins handle the initial collection
    yield
    groups_collection_modifyitems(config, items)
    from_filenames_collection_modifyitems(config, items)

    timeout_marker_tests_paths = (
        str(PYTESTS_DIR / "pkg"),
        str(PYTESTS_DIR / "scenarios"),
    )
    for item in items:
        marker = item.get_closest_marker("timeout_unless_on_windows")
        if marker is not None:
            if not salt.utils.platform.is_windows():
                # Apply the marker since we're not on windows
                marker_kwargs = marker.kwargs.copy()
                if "func_only" not in marker_kwargs:
                    # Default to counting only the test execution for the timeouts, ie,
                    # withough including the fixtures setup time towards the timeout.
                    marker_kwargs["func_only"] = True
                item.add_marker(pytest.mark.timeout(*marker.args, **marker_kwargs))
        else:
            if (
                not salt.utils.platform.is_windows()
                and not str(pathlib.Path(item.fspath).resolve()).startswith(
                    timeout_marker_tests_paths
                )
                and not item.get_closest_marker("timeout")
            ):
                # Let's apply the timeout marker on the test, if the marker
                # is not already applied
                # Default to counting only the test execution for the timeouts, ie,
                # withough including the fixtures setup time towards the timeout.
                item.add_marker(pytest.mark.timeout(90, func_only=True))


def pytest_markeval_namespace(config):
    """
    Called when constructing the globals dictionary used for evaluating string conditions in xfail/skipif markers.

    This is useful when the condition for a marker requires objects that are expensive or impossible to obtain during
    collection time, which is required by normal boolean conditions.

    :param config: The pytest config object.
    :returns: A dictionary of additional globals to add.
    """
    return {"grains": _grains_for_marker()}


# <---- PyTest Tweaks ------------------------------------------------------------------------------------------------


# ----- Test Setup -------------------------------------------------------------------------------------------------->
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """
    Fixtures injection based on markers or test skips based on CLI arguments
    """
    integration_utils_tests_path = str(TESTS_DIR / "integration" / "utils")
    if (
        str(item.fspath).startswith(integration_utils_tests_path)
        and PRE_PYTEST_SKIP_OR_NOT is True
    ):
        item._skipped_by_mark = True
        pytest.skip(PRE_PYTEST_SKIP_REASON)
    test_group_count = sum(
        bool(item.get_closest_marker(group))
        for group in ("core_test", "slow_test", "flaky_jail")
    )
    if item.get_closest_marker("core_test") and item.get_closest_marker("slow_test"):
        raise pytest.UsageError(
            "Tests can only be in one test group. ('core_test', 'slow_test')"
        )

    if item.get_closest_marker("flaky_jail"):
        if not item.config.getoption("--flaky-jail"):
            raise pytest.skip.Exception(
                "flaky jail tests are disabled, pass '--flaky-jail' to enable them.",
                _use_item_location=True,
            )
    else:
        if item.get_closest_marker("core_test"):
            if not item.config.getoption("--core-tests"):
                raise pytest.skip.Exception(
                    "Core tests are disabled, pass '--core-tests' to enable them.",
                    _use_item_location=True,
                )
        if item.get_closest_marker("slow_test"):
            if not item.config.getoption("--slow-tests"):
                raise pytest.skip.Exception(
                    "Slow tests are disabled, pass '--run-slow' to enable them.",
                    _use_item_location=True,
                )
        if test_group_count == 0 and item.config.getoption("--no-fast-tests"):
            raise pytest.skip.Exception(
                "Fast tests have been disabled by '--no-fast-tests'.",
                _use_item_location=True,
            )

    requires_sshd_server_marker = item.get_closest_marker("requires_sshd_server")
    if requires_sshd_server_marker is not None:
        if not item.config.getoption("--ssh-tests"):
            item._skipped_by_mark = True
            pytest.skip("SSH tests are disabled, pass '--ssh-tests' to enable them.")
        item.fixturenames.append("sshd_server")
        item.fixturenames.append("salt_ssh_roster_file")

    requires_salt_modules_marker = item.get_closest_marker("requires_salt_modules")
    if requires_salt_modules_marker is not None:
        required_salt_modules = requires_salt_modules_marker.args
        if len(required_salt_modules) == 1 and isinstance(
            required_salt_modules[0], (list, tuple, set)
        ):
            required_salt_modules = required_salt_modules[0]
        required_salt_modules = set(required_salt_modules)
        not_available_modules = check_required_sminion_attributes(
            "functions", required_salt_modules
        )

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

    requires_salt_states_marker = item.get_closest_marker("requires_salt_states")
    if requires_salt_states_marker is not None:
        required_salt_states = requires_salt_states_marker.args
        if len(required_salt_states) == 1 and isinstance(
            required_salt_states[0], (list, tuple, set)
        ):
            required_salt_states = required_salt_states[0]
        required_salt_states = set(required_salt_states)
        not_available_states = check_required_sminion_attributes(
            "states", required_salt_states
        )

        if not_available_states:
            item._skipped_by_mark = True
            if len(not_available_states) == 1:
                pytest.skip(
                    "Salt state module '{}' is not available".format(
                        *not_available_states
                    )
                )
            pytest.skip(
                "Salt state modules not available: {}".format(
                    ", ".join(not_available_states)
                )
            )

    skip_initial_gh_actions_failures_env_set = (
        os.environ.get("SKIP_INITIAL_GH_ACTIONS_FAILURES", "0") == "1"
    )
    skip_initial_gh_actions_failure_marker = item.get_closest_marker(
        "skip_initial_gh_actions_failure"
    )
    if (
        skip_initial_gh_actions_failure_marker is not None
        and skip_initial_gh_actions_failures_env_set
    ):
        if skip_initial_gh_actions_failure_marker.args:
            raise pytest.UsageError(
                "'skip_initial_gh_actions_failure' marker does not accept any arguments "
                "only keyword arguments."
            )
        kwargs = skip_initial_gh_actions_failure_marker.kwargs.copy()
        skip = kwargs.pop("skip", True)
        if skip and not callable(skip) and not isinstance(skip, bool):
            raise pytest.UsageError(
                "The 'skip' keyword argument to the 'skip_initial_gh_actions_failure' marker "
                "requires a boolean or callable, not '{}'.".format(type(skip))
            )
        reason = kwargs.pop("reason", None)
        if reason is None:
            reason = "Test skipped because it's a know GH Actions initial failure that needs to be fixed"
        if kwargs:
            raise pytest.UsageError(
                "'skip_initial_gh_actions_failure' marker does not accept any keyword arguments "
                "except 'skip' and 'reason'."
            )
        if skip and callable(skip):
            grains = _grains_for_marker()
            skip = skip(grains)

        if skip:
            raise pytest.skip.Exception(reason, _use_item_location=True)

    skip_initial_onedir_failures_env_set = (
        os.environ.get("SKIP_INITIAL_ONEDIR_FAILURES", "0") == "1"
    )
    skip_initial_onedir_failure_marker = item.get_closest_marker(
        "skip_initial_onedir_failure"
    )
    if (
        skip_initial_onedir_failure_marker is not None
        and skip_initial_onedir_failures_env_set
    ):
        if skip_initial_onedir_failure_marker.args:
            raise pytest.UsageError(
                "'skip_initial_onedir_failure' marker does not accept any arguments "
                "only keyword arguments."
            )
        kwargs = skip_initial_onedir_failure_marker.kwargs.copy()
        skip = kwargs.pop("skip", True)
        if skip and not callable(skip) and not isinstance(skip, bool):
            raise pytest.UsageError(
                "The 'skip' keyword argument to the 'skip_initial_onedir_failure' marker "
                "requires a boolean or callable, not '{}'.".format(type(skip))
            )
        reason = kwargs.pop("reason", None)
        if reason is None:
            reason = "Test skipped because it's a know GH Actions initial failure that needs to be fixed"
        if kwargs:
            raise pytest.UsageError(
                "'skip_initial_onedir_failure' marker does not accept any keyword arguments "
                "except 'skip' and 'reason'."
            )
        if skip and callable(skip):
            grains = _grains_for_marker()
            skip = skip(grains)

        if skip:
            raise pytest.skip.Exception(reason, _use_item_location=True)

    requires_random_entropy_marker = item.get_closest_marker("requires_random_entropy")
    if requires_random_entropy_marker is not None:
        if requires_random_entropy_marker.args:
            raise pytest.UsageError(
                "'requires_random_entropy' marker does not accept any arguments "
                "only keyword arguments."
            )
        kwargs = requires_random_entropy_marker.kwargs.copy()
        skip = kwargs.pop("skip", None)
        if skip and not isinstance(skip, bool):
            raise pytest.UsageError(
                "The 'skip' keyword argument to the 'requires_random_entropy' marker "
                "requires a boolean not '{}'.".format(type(skip))
            )
        minimum_entropy = kwargs.pop("minimum", None)
        if minimum_entropy is not None:
            if not isinstance(minimum_entropy, int):
                raise pytest.UsageError(
                    "The 'minimum' keyword argument to the 'requires_random_entropy' marker "
                    "must be an integer not '{}'.".format(type(minimum_entropy))
                )
            if minimum_entropy <= 0:
                raise pytest.UsageError(
                    "The 'minimum' keyword argument to the 'requires_random_entropy' marker "
                    "must be an positive integer not '{}'.".format(minimum_entropy)
                )
        max_minutes = kwargs.pop("timeout", None)
        if max_minutes is not None:
            if not isinstance(max_minutes, int):
                raise pytest.UsageError(
                    "The 'timeout' keyword argument to the 'requires_random_entropy' marker "
                    "must be an integer not '{}'.".format(type(max_minutes))
                )
            if max_minutes <= 0:
                raise pytest.UsageError(
                    "The 'timeout' keyword argument to the 'requires_random_entropy' marker "
                    "must be an positive integer not '{}'.".format(max_minutes)
                )
        if kwargs:
            raise pytest.UsageError(
                "Unsupported keyword arguments passed to the 'requires_random_entropy' "
                "marker: {}".format(", ".join(list(kwargs)))
            )
        entropy_generator = EntropyGenerator(
            minimum_entropy=minimum_entropy, max_minutes=max_minutes, skip=skip
        )
        entropy_generator.generate_entropy()

    if salt.utils.platform.is_windows():
        auto_whitelisted_paths = (
            str(TESTS_DIR / "unit"),
            str(PYTESTS_DIR / "unit"),
            str(PYTESTS_DIR / "pkg"),
        )
        if not str(pathlib.Path(item.fspath).resolve()).startswith(
            auto_whitelisted_paths
        ):
            # Unit tests are whitelisted on windows by default, so, we're only
            # after all other tests
            windows_whitelisted_marker = item.get_closest_marker("windows_whitelisted")
            if windows_whitelisted_marker is None:
                item._skipped_by_mark = True
                pytest.skip("Test is not whitelisted for Windows")


# <---- Test Setup ---------------------------------------------------------------------------------------------------


# ----- Test Groups Selection --------------------------------------------------------------------------------------->
def groups_collection_modifyitems(config, items):
    group_count = config.getoption("test-group-count")
    group_id = config.getoption("test-group")

    if not group_count or not group_id:
        # We're not selection tests using groups, don't do any filtering
        return

    if group_count == 1:
        # Just one group, don't do any filtering
        return

    terminal_reporter = config.pluginmanager.get_plugin("terminalreporter")

    if config.getoption("--last-failed") or config.getoption("--failed-first"):
        # This is a test failure rerun, applying test groups would break this
        terminal_reporter.write(
            "\nNot splitting collected tests into chunks since --lf/--last-failed or "
            "-ff/--failed-first was passed on the CLI.\n",
            yellow=True,
        )
        return

    total_items = len(items)

    # Devide into test groups
    test_groups = more_itertools.divide(group_count, items)
    # Pick the right group
    tests_in_group = list(test_groups.pop(group_id - 1))
    # The rest are deselected tests
    deselected = list(more_itertools.collapse(test_groups))
    # Sanity check
    assert len(tests_in_group) + len(deselected) == total_items
    # Replace all items in the list
    items[:] = tests_in_group
    if deselected:
        config.hook.pytest_deselected(items=deselected)

    terminal_reporter.write(
        f"Running test group #{group_id}(out of #{group_count}) ({len(items)} out of {total_items} tests)\n",
        yellow=True,
    )


# <---- Test Groups Selection ----------------------------------------------------------------------------------------


# ----- Fixtures Overrides ------------------------------------------------------------------------------------------>
@pytest.fixture(scope="session")
def salt_factories_default_root_dir(salt_factories_default_root_dir):
    """
    The root directory from where to base all salt-factories paths.

    For example, in a salt system installation, this would be ``/``.

    .. admonition:: Attention

        If `root_dir` is returned on the `salt_factories_config()` fixture
        dictionary, then that's the value used, and not the one returned by
        this fixture.
    """
    return salt_factories_default_root_dir / "stsuite"


@pytest.fixture(scope="session")
def salt_factories_config():
    """
    Return a dictionary with the keyworkd arguments for FactoriesManager
    """
    if os.environ.get("JENKINS_URL") or os.environ.get("CI"):
        start_timeout = 120
    else:
        start_timeout = 60

    if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
        code_dir = None
    else:
        code_dir = str(CODE_DIR)

    kwargs = {
        "code_dir": code_dir,
        "start_timeout": start_timeout,
        "inject_sitecustomize": MAYBE_RUN_COVERAGE,
    }
    if MAYBE_RUN_COVERAGE:
        kwargs["coverage_rc_path"] = str(COVERAGERC_FILE)
    else:
        kwargs["coverage_rc_path"] = None
    kwargs["coverage_db_path"] = os.environ.get("COVERAGE_FILE")
    return kwargs


@pytest.fixture
def tmpdir(tmpdir):
    raise pytest.UsageError(
        "The `tmpdir` fixture uses Pytest's `pypath` implementation which "
        "is getting deprecated in favor of `pathlib`. Please use the "
        "`tmp_path` fixture instead."
    )


# <---- Fixtures Overrides -------------------------------------------------------------------------------------------


# ----- Salt Factories ---------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def integration_files_dir(salt_factories):
    """
    Fixture which returns the salt integration files directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = salt_factories.root_dir / "integration-files"
    dirname.mkdir(exist_ok=True)
    for child in (PYTESTS_DIR / "integration" / "files").iterdir():
        destpath = dirname / child.name
        if child.is_dir():
            shutil.copytree(str(child), str(destpath), dirs_exist_ok=True)
        else:
            shutil.copyfile(str(child), str(destpath))
    return dirname


@pytest.fixture(scope="module")
def functional_files_dir(salt_factories):
    """
    Fixture which returns the salt functional files directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = salt_factories.root_dir / "functional-files"
    dirname.mkdir(exist_ok=True)
    for child in (PYTESTS_DIR / "functional" / "files").iterdir():
        if child.is_dir():
            shutil.copytree(str(child), str(dirname / child.name))
        else:
            shutil.copyfile(str(child), str(dirname / child.name))
    return dirname


@pytest.fixture(scope="session")
def state_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt state tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "state-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def pillar_tree_root_dir(integration_files_dir):
    """
    Fixture which returns the salt pillar tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "pillar-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def base_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt base environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir / "base"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_STATE_TREE = str(dirname.resolve())
    RUNTIME_VARS.TMP_BASEENV_STATE_TREE = RUNTIME_VARS.TMP_STATE_TREE
    return dirname


@pytest.fixture(scope="session")
def prod_env_state_tree_root_dir(state_tree_root_dir):
    """
    Fixture which returns the salt prod environment state tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = state_tree_root_dir / "prod"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_STATE_TREE = str(dirname.resolve())
    return dirname


@pytest.fixture(scope="session")
def base_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt base environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "base"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PILLAR_TREE = str(dirname.resolve())
    RUNTIME_VARS.TMP_BASEENV_PILLAR_TREE = RUNTIME_VARS.TMP_PILLAR_TREE
    return dirname


@pytest.fixture(scope="session")
def ext_pillar_file_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt pillar file tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "file-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="session")
def prod_env_pillar_tree_root_dir(pillar_tree_root_dir):
    """
    Fixture which returns the salt prod environment pillar tree directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = pillar_tree_root_dir / "prod"
    dirname.mkdir(exist_ok=True)
    RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE = str(dirname.resolve())
    return dirname


@pytest.fixture(scope="session")
def salt_syndic_master_factory(
    request,
    salt_factories,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
):
    root_dir = salt_factories.get_root_dir_for_daemon("syndic_master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "syndic_master")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = request.config.getoption("--transport")

    config_overrides = {
        "log_level_logfile": "quiet",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    str(base_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    str(prod_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    str(base_env_pillar_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [str(prod_env_pillar_tree_root_dir)],
            },
        }
    )

    factory = salt_factories.salt_master_daemon(
        "syndic_master",
        order_masters=True,
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_syndic_factory(salt_factories, salt_syndic_master_factory):
    config_defaults = {"master": None, "minion": None, "syndic": None}
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "syndic")) as rfh:
        opts = yaml.deserialize(rfh.read())

        opts["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
        opts["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
        opts["transport"] = salt_syndic_master_factory.config["transport"]
        config_defaults["syndic"] = opts
    config_overrides = {"log_level_logfile": "quiet"}
    factory = salt_syndic_master_factory.salt_syndic_daemon(
        "syndic",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_master_factory(
    salt_factories,
    salt_syndic_master_factory,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    ext_pillar_file_tree_root_dir,
    salt_api_account_factory,
):
    root_dir = salt_factories.get_root_dir_for_daemon("master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

        tests_known_hosts_file = str(root_dir / "salt_ssh_known_hosts")
        with salt.utils.files.fopen(tests_known_hosts_file, "w") as known_hosts:
            known_hosts.write("")

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["known_hosts_file"] = tests_known_hosts_file
    config_defaults["syndic_master"] = "localhost"
    config_defaults["transport"] = salt_syndic_master_factory.config["transport"]

    config_overrides = {
        "log_level_logfile": "quiet",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    ext_pillar = []
    if salt.utils.platform.is_windows():
        ext_pillar.append(
            {"cmd_yaml": "type {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    else:
        ext_pillar.append(
            {"cmd_yaml": "cat {}".format(os.path.join(RUNTIME_VARS.FILES, "ext.yaml"))}
        )
    ext_pillar.append(
        {
            "file_tree": {
                "root_dir": str(ext_pillar_file_tree_root_dir),
                "follow_dir_links": False,
                "keep_newline": True,
            }
        }
    )
    config_overrides["pillar_opts"] = True
    config_overrides["external_auth"] = {
        "auto": {
            salt_api_account_factory.username: [
                "@wheel",
                "@runner",
                "test.*",
                "grains.*",
            ],
        }
    }

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "ext_pillar": ext_pillar,
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    str(base_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
                # Alternate root to test __env__ choices
                "prod": [
                    str(prod_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "prod"),
                ],
            },
            "pillar_roots": {
                "base": [
                    str(base_env_pillar_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
                "prod": [str(prod_env_pillar_tree_root_dir)],
            },
        }
    )

    # Let's copy over the test cloud config files and directories into the running master config directory
    for entry in os.listdir(RUNTIME_VARS.CONF_DIR):
        if not entry.startswith("cloud"):
            continue
        source = os.path.join(RUNTIME_VARS.CONF_DIR, entry)
        dest = str(conf_dir / entry)
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            shutil.copyfile(source, dest)

    factory = salt_syndic_master_factory.salt_master_daemon(
        "master",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    return factory


@pytest.fixture(scope="session")
def salt_minion_factory(salt_master_factory):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "log_level_logfile": "quiet",
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        "minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_sub_minion_factory(salt_master_factory):
    with salt.utils.files.fopen(
        os.path.join(RUNTIME_VARS.CONF_DIR, "sub_minion")
    ) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "log_level_logfile": "quiet",
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary
    factory = salt_master_factory.salt_minion_daemon(
        "sub_minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )
    return factory


@pytest.fixture(scope="session")
def salt_cli(salt_master_factory):
    return salt_master_factory.salt_cli()


@pytest.fixture(scope="session")
def salt_cp_cli(salt_master_factory):
    return salt_master_factory.salt_cp_cli()


@pytest.fixture(scope="session")
def salt_key_cli(salt_master_factory):
    return salt_master_factory.salt_key_cli()


@pytest.fixture(scope="session")
def salt_run_cli(salt_master_factory):
    return salt_master_factory.salt_run_cli()


@pytest.fixture(scope="session")
def salt_call_cli(salt_minion_factory):
    return salt_minion_factory.salt_call_cli()


@pytest.fixture(scope="session", autouse=True)
def bridge_pytest_and_runtests(
    salt_factories,
    salt_syndic_master_factory,
    salt_syndic_factory,
    salt_master_factory,
    salt_minion_factory,
    salt_sub_minion_factory,
    sshd_config_dir,
):
    # Make sure unittest2 uses the pytest generated configuration
    RUNTIME_VARS.RUNTIME_CONFIGS["master"] = freeze(salt_master_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["minion"] = freeze(salt_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["sub_minion"] = freeze(salt_sub_minion_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic_master"] = freeze(
        salt_syndic_master_factory.config
    )
    RUNTIME_VARS.RUNTIME_CONFIGS["syndic"] = freeze(salt_syndic_factory.config)
    RUNTIME_VARS.RUNTIME_CONFIGS["client_config"] = freeze(
        salt.config.client_config(salt_master_factory.config["conf_file"])
    )

    # Make sure unittest2 classes know their paths
    RUNTIME_VARS.TMP_ROOT_DIR = str(salt_factories.root_dir.resolve())
    RUNTIME_VARS.TMP_CONF_DIR = os.path.dirname(salt_master_factory.config["conf_file"])
    RUNTIME_VARS.TMP_MINION_CONF_DIR = os.path.dirname(
        salt_minion_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR = os.path.dirname(
        salt_sub_minion_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR = os.path.dirname(
        salt_syndic_master_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR = os.path.dirname(
        salt_syndic_factory.config["conf_file"]
    )
    RUNTIME_VARS.TMP_SSH_CONF_DIR = str(sshd_config_dir)
    with reap_stray_processes():
        yield


@pytest.fixture(scope="session")
def sshd_config_dir(salt_factories):
    config_dir = salt_factories.get_root_dir_for_daemon("sshd")
    yield config_dir
    shutil.rmtree(str(config_dir), ignore_errors=True)


@pytest.fixture(scope="module")
def sshd_server(salt_factories, sshd_config_dir, salt_master, grains):
    sshd_config_dict = {
        "Protocol": "2",
        # Turn strict modes off so that we can operate in /tmp
        "StrictModes": "no",
        # Logging
        "SyslogFacility": "AUTH",
        "LogLevel": "INFO",
        # Authentication:
        "LoginGraceTime": "120",
        "PermitRootLogin": "without-password",
        "PubkeyAuthentication": "yes",
        # Don't read the user's ~/.rhosts and ~/.shosts files
        "IgnoreRhosts": "yes",
        "HostbasedAuthentication": "no",
        # To enable empty passwords, change to yes (NOT RECOMMENDED)
        "PermitEmptyPasswords": "no",
        # Change to yes to enable challenge-response passwords (beware issues with
        # some PAM modules and threads)
        "ChallengeResponseAuthentication": "no",
        # Change to no to disable tunnelled clear text passwords
        "PasswordAuthentication": "no",
        "X11Forwarding": "no",
        "X11DisplayOffset": "10",
        "PrintMotd": "no",
        "PrintLastLog": "yes",
        "TCPKeepAlive": "yes",
        "AcceptEnv": "LANG LC_*",
        "UsePAM": "yes",
    }
    sftp_server_paths = [
        # Common
        "/usr/lib/openssh/sftp-server",
        # CentOS Stream 9
        "/usr/libexec/openssh/sftp-server",
        # Arch Linux
        "/usr/lib/ssh/sftp-server",
        # Photon OS 5
        "/usr/libexec/sftp-server",
    ]
    sftp_server_path = None
    for path in sftp_server_paths:
        if os.path.exists(path):
            sftp_server_path = path
    if sftp_server_path is None:
        pytest.fail(f"Failed to find 'sftp-server'. Searched: {sftp_server_paths}")
    else:
        sshd_config_dict["Subsystem"] = f"sftp {sftp_server_path}"
    factory = salt_factories.get_sshd_daemon(
        sshd_config_dict=sshd_config_dict,
        config_dir=sshd_config_dir,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def known_hosts_file(sshd_server, salt_master, salt_factories):
    with pytest.helpers.temp_file(
        "ssh-known-hosts",
        "\n".join(sshd_server.get_host_keys()),
        salt_factories.tmp_root_dir,
    ) as known_hosts_file, pytest.helpers.temp_file(
        "master.d/ssh-known-hosts.conf",
        f"known_hosts_file: {known_hosts_file}",
        salt_master.config_dir,
    ):
        yield known_hosts_file


@pytest.fixture(scope="module")
def salt_ssh_roster_file(sshd_server, salt_master, known_hosts_file):
    roster_contents = """
    localhost:
      host: 127.0.0.1
      port: {}
      user: {}
      mine_functions:
        test.arg: ['itworked']
    """.format(
        sshd_server.listen_port, RUNTIME_VARS.RUNNING_TESTS_USER
    )
    if salt.utils.platform.is_darwin():
        roster_contents += "  set_path: $PATH:/usr/local/bin/\n"

    with pytest.helpers.temp_file(
        "roster", roster_contents, salt_master.config_dir
    ) as roster_file:
        yield roster_file


# <---- Salt Factories -----------------------------------------------------------------------------------------------


# ----- From Filenames Test Selection ------------------------------------------------------------------------------->
def _match_to_test_file(match):
    parts = match.split(".")
    test_module_path = TESTS_DIR.joinpath(*parts)
    if test_module_path.exists():
        return test_module_path
    parts[-1] += ".py"
    return TESTS_DIR.joinpath(*parts).relative_to(CODE_DIR)


def from_filenames_collection_modifyitems(config, items):
    from_filenames = config.getoption("--from-filenames")
    if not from_filenames:
        # Don't do anything
        return

    terminal_reporter = config.pluginmanager.getplugin("terminalreporter")
    terminal_reporter.ensure_newline()
    terminal_reporter.section(
        "From Filenames(--from-filenames) Test Selection", sep=">"
    )
    errors = []
    test_module_selections = []
    changed_files_selections = []
    from_filenames_paths = set()
    for path in [path.strip() for path in from_filenames.split(",")]:
        # Make sure that, no matter what kind of path we're passed, Windows or Posix path,
        # we resolve it to the platform slash separator
        properly_slashed_path = pathlib.Path(
            path.replace("\\", os.sep).replace("/", os.sep)
        )
        if not properly_slashed_path.exists():
            errors.append(f"{properly_slashed_path}: Does not exist")
            continue
        if (
            properly_slashed_path.name == "testrun-changed-files.txt"
            or properly_slashed_path.is_absolute()
        ):
            # In this case, this path is considered to be a file containing a line separated list
            # of files to consider
            contents = properly_slashed_path.read_text(encoding="utf-8")
            for sep in ("\r\n", "\\r\\n", "\\n"):
                contents = contents.replace(sep, "\n")
            for line in contents.split("\n"):
                line_path = pathlib.Path(
                    line.strip().replace("\\", os.sep).replace("/", os.sep)
                )
                if not line_path.exists():
                    errors.append(
                        "{}: Does not exist. Source {}".format(
                            line_path, properly_slashed_path
                        )
                    )
                    continue
                changed_files_selections.append(
                    f"{line_path}: Source {properly_slashed_path}"
                )
                from_filenames_paths.add(line_path)
            continue
        changed_files_selections.append(
            f"{properly_slashed_path}: Source --from-filenames"
        )
        from_filenames_paths.add(properly_slashed_path)

    # Let's start collecting test modules
    test_module_paths = set()

    filename_map = yaml.deserialize((TESTS_DIR / "filename_map.yml").read_text())
    # Let's add the match all rule
    for rule, matches in filename_map.items():
        if rule == "*":
            for match in matches:
                test_module_paths.add(_match_to_test_file(match))
            break

    # Let's now go through the list of files gathered
    for path in from_filenames_paths:
        if path.as_posix().startswith("tests/"):
            if path.name == "conftest.py":
                # This is not a test module, but consider any test_*.py files in child directories
                for match in path.parent.rglob("test_*.py"):
                    test_module_selections.append(
                        "{}: Source '{}/test_*.py' recursive glob match because '{}' was modified".format(
                            match, path.parent, path
                        )
                    )
                    test_module_paths.add(match)
                continue
            # Tests in the listing don't require additional matching and will be added to the
            # list of tests to run
            test_module_selections.append(f"{path}: Source --from-filenames")
            test_module_paths.add(path)
            continue
        if path.name == "setup.py" or path.as_posix().startswith("salt/"):
            if path.name == "__init__.py":
                # No direct matching
                continue

            # Let's try a direct match between the passed file and possible test modules
            glob_patterns = (
                # salt/version.py ->
                #    tests/unit/test_version.py
                #    tests/pytests/unit/test_version.py
                f"**/test_{path.name}",
                # salt/modules/grains.py ->
                #    tests/pytests/integration/modules/grains/tests_*.py
                # salt/modules/saltutil.py ->
                #    tests/pytests/integration/modules/saltutil/test_*.py
                f"**/{path.stem}/test_*.py",
                # salt/modules/config.py ->
                #    tests/unit/modules/test_config.py
                #    tests/integration/modules/test_config.py
                #    tests/pytests/unit/modules/test_config.py
                #    tests/pytests/integration/modules/test_config.py
                f"**/{path.parent.name}/test_{path.name}",
            )
            for pattern in glob_patterns:
                for match in TESTS_DIR.rglob(pattern):
                    relative_path = match.relative_to(CODE_DIR)
                    test_module_selections.append(
                        "{}: Source '{}' glob pattern match".format(
                            relative_path, pattern
                        )
                    )
                    test_module_paths.add(relative_path)

            # Do we have an entry in tests/filename_map.yml
            for rule, matches in filename_map.items():
                if rule == "*":
                    continue
                elif "|" in rule:
                    # This is regex
                    if re.match(rule, path.as_posix()):
                        for match in matches:
                            test_module_paths.add(_match_to_test_file(match))
                            test_module_selections.append(
                                "{}: Source '{}' regex match from 'tests/filename_map.yml'".format(
                                    match, rule
                                )
                            )
                elif "*" in rule or "\\" in rule:
                    # Glob matching
                    for filerule in CODE_DIR.glob(rule):
                        if not filerule.exists():
                            continue
                        filerule = filerule.relative_to(CODE_DIR)
                        if filerule != path:
                            continue
                        for match in matches:
                            match_path = _match_to_test_file(match)
                            test_module_selections.append(
                                "{}: Source '{}' file rule from 'tests/filename_map.yml'".format(
                                    match_path, filerule
                                )
                            )
                            test_module_paths.add(match_path)
                else:
                    if path.as_posix() != rule:
                        continue
                    # Direct file paths as rules
                    filerule = pathlib.Path(rule)
                    if not filerule.exists():
                        continue
                    for match in matches:
                        match_path = _match_to_test_file(match)
                        test_module_selections.append(
                            "{}: Source '{}' direct file rule from 'tests/filename_map.yml'".format(
                                match_path, filerule
                            )
                        )
                        test_module_paths.add(match_path)
            continue
        else:
            errors.append(f"{path}: Don't know what to do with this path")

    if errors:
        terminal_reporter.write("Errors:\n", bold=True)
        for error in errors:
            terminal_reporter.write(f" * {error}\n")
    if changed_files_selections:
        terminal_reporter.write("Changed files collected:\n", bold=True)
        for selection in changed_files_selections:
            terminal_reporter.write(f" * {selection}\n")
    if test_module_selections:
        terminal_reporter.write("Selected test modules:\n", bold=True)
        for selection in test_module_selections:
            terminal_reporter.write(f" * {selection}\n")
    terminal_reporter.section(
        "From Filenames(--from-filenames) Test Selection", sep="<"
    )
    terminal_reporter.ensure_newline()

    selected = []
    deselected = []
    for item in items:
        itempath = pathlib.Path(str(item.fspath)).resolve().relative_to(CODE_DIR)
        if itempath in test_module_paths:
            selected.append(item)
        else:
            deselected.append(item)

    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)


# <---- From Filenames Test Selection --------------------------------------------------------------------------------


# ----- Custom Fixtures --------------------------------------------------------------------------------------------->
@pytest.fixture(scope="session")
def sminion():
    return create_sminion()


@pytest.fixture(scope="session")
def grains(sminion):
    return sminion.opts["grains"].copy()


@lru_cache(maxsize=1)
def _grains_for_marker():
    return create_sminion().opts["grains"]


@pytest.fixture(scope="session", autouse=True)
def _disable_salt_logging():
    # This fixture is used to set logging to a configuration that salt expects,
    # however, no logging is actually configured since pytest's logging will be
    # logging what we need.
    logging_config = {
        # Undocumented, on purpose, at least for now, options.
        "configure_ext_handlers": False,
        "configure_file_logger": False,
        "configure_console_logger": False,
        "configure_granular_levels": False,
    }
    salt._logging.set_logging_options_dict(logging_config)
    # Run the test suite
    yield


@pytest.fixture(scope="session")
def salt_api_account_factory():
    return TestAccount(username="saltdev_api", password="saltdev")


# <---- Custom Fixtures ----------------------------------------------------------------------------------------------
