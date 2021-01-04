#!/usr/bin/env python
"""
Discover all instances of unittest.TestCase in this directory.
"""
# pylint: disable=file-perms

import collections
import os
import sys
import time
import warnings

TESTS_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))
if os.name == "nt":
    TESTS_DIR = TESTS_DIR.replace("\\", "\\\\")
CODE_DIR = os.path.dirname(TESTS_DIR)

# Let's inject CODE_DIR so salt is importable if not there already
if "" in sys.path:
    sys.path.remove("")
if TESTS_DIR in sys.path:
    sys.path.remove(TESTS_DIR)
if CODE_DIR in sys.path and sys.path[0] != CODE_DIR:
    sys.path.remove(CODE_DIR)
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(1, TESTS_DIR)

try:
    import tests

    if not tests.__file__.startswith(CODE_DIR):
        print("Found tests module not from salt in {}".format(tests.__file__))
        sys.modules.pop("tests")
        module_dir = os.path.dirname(tests.__file__)
        if module_dir in sys.path:
            sys.path.remove(module_dir)
        del tests
except ImportError:
    pass

try:
    from tests.support.paths import TMP, SYS_TMP_DIR, INTEGRATION_TEST_DIR
    from tests.support.paths import CODE_DIR as SALT_ROOT
except ImportError as exc:
    try:
        import tests

        print("Found tests module not from salt in {}".format(tests.__file__))
    except ImportError:
        print("Unable to import salt test module")
        print("PYTHONPATH:", os.environ.get("PYTHONPATH"))
    print("Current sys.path:")
    import pprint

    pprint.pprint(sys.path)
    raise

from tests.integration import TestDaemon, TestDaemonStartFailed  # isort:skip
import salt.utils.platform  # isort:skip

if not salt.utils.platform.is_windows():
    import resource

from tests.support.parser import PNUM, print_header  # isort:skip
from tests.support.parser.cover import SaltCoverageTestingParser  # isort:skip

XML_OUTPUT_DIR = os.environ.get(
    "SALT_XML_TEST_REPORTS_DIR", os.path.join(TMP, "xml-test-reports")
)
HTML_OUTPUT_DIR = os.environ.get(
    "SALT_HTML_TEST_REPORTS_DIR", os.path.join(TMP, "html-test-reports")
)

TEST_DIR = os.path.dirname(INTEGRATION_TEST_DIR)
try:
    if SALT_ROOT:
        os.chdir(SALT_ROOT)
except OSError as err:
    print("Failed to change directory to salt's source: {}".format(err))

# Soft and hard limits on max open filehandles
MAX_OPEN_FILES = {
    "integration": {"soft_limit": 3072, "hard_limit": 4096},
    "unit": {"soft_limit": 1024, "hard_limit": 2048},
}

# Combine info from command line options and test suite directories.  A test
# suite is a python package of test modules relative to the tests directory.
TEST_SUITES_UNORDERED = {
    "unit": {"display_name": "Unit", "path": "unit"},
    "kitchen": {"display_name": "Kitchen", "path": "kitchen"},
    "multimaster": {"display_name": "Multimaster", "path": "multimaster"},
    "module": {"display_name": "Module", "path": "integration/modules"},
    "state": {"display_name": "State", "path": "integration/states"},
    "cli": {"display_name": "CLI", "path": "integration/cli"},
    "client": {"display_name": "Client", "path": "integration/client"},
    "doc": {"display_name": "Documentation", "path": "integration/doc"},
    "ext_pillar": {"display_name": "External Pillar", "path": "integration/pillar"},
    "grains": {"display_name": "Grains", "path": "integration/grains"},
    "shell": {"display_name": "Shell", "path": "integration/shell"},
    "runners": {"display_name": "Runners", "path": "integration/runners"},
    "renderers": {"display_name": "Renderers", "path": "integration/renderers"},
    "returners": {"display_name": "Returners", "path": "integration/returners"},
    "ssh-int": {"display_name": "SSH Integration", "path": "integration/ssh"},
    "spm": {"display_name": "SPM", "path": "integration/spm"},
    "loader": {"display_name": "Loader", "path": "integration/loader"},
    "outputter": {"display_name": "Outputter", "path": "integration/output"},
    "fileserver": {"display_name": "Fileserver", "path": "integration/fileserver"},
    "wheel": {"display_name": "Wheel", "path": "integration/wheel"},
    "api": {"display_name": "NetAPI", "path": "integration/netapi"},
    "cloud_provider": {
        "display_name": "Cloud Provider",
        "path": "integration/cloud/clouds",
    },
    "minion": {"display_name": "Minion", "path": "integration/minion"},
    "reactor": {"display_name": "Reactor", "path": "integration/reactor"},
    "proxy": {"display_name": "Proxy", "path": "integration/proxy"},
    "external_api": {"display_name": "ExternalAPIs", "path": "integration/externalapi"},
    "daemons": {"display_name": "Daemon", "path": "integration/daemons"},
    "sdb": {"display_name": "Sdb", "path": "integration/sdb"},
    "logging": {"display_name": "Logging", "path": "integration/logging"},
}

TEST_SUITES = collections.OrderedDict(
    sorted(TEST_SUITES_UNORDERED.items(), key=lambda x: x[0])
)


class SaltTestsuiteParser(SaltCoverageTestingParser):
    support_docker_execution = True
    support_destructive_tests_selection = True
    support_expensive_tests_selection = True
    source_code_basedir = SALT_ROOT

    def _get_suites(
        self,
        include_unit=False,
        include_cloud_provider=False,
        include_proxy=False,
        include_kitchen=False,
        include_multimaster=False,
    ):
        """
        Return a set of all test suites except unit and cloud provider tests
        unless requested
        """
        suites = set(TEST_SUITES.keys())
        if not include_unit:
            suites -= {"unit"}
        if not include_cloud_provider:
            suites -= {"cloud_provider"}
        if not include_proxy:
            suites -= {"proxy"}
        if not include_kitchen:
            suites -= {"kitchen"}
        # Multimaster tests now run under PyTest
        suites -= {"multimaster"}

        return suites

    def _check_enabled_suites(
        self,
        include_unit=False,
        include_cloud_provider=False,
        include_proxy=False,
        include_kitchen=False,
        include_multimaster=False,
    ):
        """
        Query whether test suites have been enabled
        """
        suites = self._get_suites(
            include_unit=include_unit,
            include_cloud_provider=include_cloud_provider,
            include_proxy=include_proxy,
            include_kitchen=include_kitchen,
            include_multimaster=include_multimaster,
        )

        return any([getattr(self.options, suite) for suite in suites])

    def _enable_suites(
        self,
        include_unit=False,
        include_cloud_provider=False,
        include_proxy=False,
        include_kitchen=False,
        include_multimaster=False,
    ):
        """
        Enable test suites for current test run
        """
        suites = self._get_suites(
            include_unit=include_unit,
            include_cloud_provider=include_cloud_provider,
            include_proxy=include_proxy,
            include_kitchen=include_kitchen,
            include_multimaster=include_multimaster,
        )

        for suite in suites:
            setattr(self.options, suite, True)

    def setup_additional_options(self):
        self.add_option(
            "--sysinfo",
            default=False,
            action="store_true",
            help="Print some system information.",
        )
        self.add_option(
            "--transport",
            default="zeromq",
            choices=("zeromq", "tcp"),
            help=(
                "Select which transport to run the integration tests with, "
                "zeromq or tcp. Default: %default"
            ),
        )
        self.add_option(
            "--interactive",
            default=False,
            action="store_true",
            help="Do not run any tests. Simply start the daemons.",
        )
        self.output_options_group.add_option(
            "--no-colors",
            "--no-colours",
            default=False,
            action="store_true",
            help="Disable colour printing.",
        )

        self.test_selection_group.add_option(
            "-m",
            "--module",
            "--module-tests",
            dest="module",
            default=False,
            action="store_true",
            help="Run tests for modules",
        )
        self.test_selection_group.add_option(
            "-S",
            "--state",
            "--state-tests",
            dest="state",
            default=False,
            action="store_true",
            help="Run tests for states",
        )
        self.test_selection_group.add_option(
            "-C",
            "--cli",
            "--cli-tests",
            dest="cli",
            default=False,
            action="store_true",
            help="Run tests for cli",
        )
        self.test_selection_group.add_option(
            "-c",
            "--client",
            "--client-tests",
            dest="client",
            default=False,
            action="store_true",
            help="Run tests for client",
        )
        self.test_selection_group.add_option(
            "-d",
            "--doc",
            "--doc-tests",
            dest="doc",
            default=False,
            action="store_true",
            help="Run tests for documentation",
        )
        self.test_selection_group.add_option(
            "-I",
            "--ext-pillar",
            "--ext-pillar-tests",
            dest="ext_pillar",
            default=False,
            action="store_true",
            help="Run ext_pillar tests",
        )
        self.test_selection_group.add_option(
            "-G",
            "--grains",
            "--grains-tests",
            dest="grains",
            default=False,
            action="store_true",
            help="Run tests for grains",
        )
        self.test_selection_group.add_option(
            "-s",
            "--shell",
            "--shell-tests",
            dest="shell",
            default=False,
            action="store_true",
            help="Run shell tests",
        )
        self.test_selection_group.add_option(
            "-r",
            "--runners",
            "--runner-tests",
            dest="runners",
            default=False,
            action="store_true",
            help="Run salt/runners/*.py tests",
        )
        self.test_selection_group.add_option(
            "-R",
            "--renderers",
            "--renderer-tests",
            dest="renderers",
            default=False,
            action="store_true",
            help="Run salt/renderers/*.py tests",
        )
        self.test_selection_group.add_option(
            "--reactor",
            dest="reactor",
            default=False,
            action="store_true",
            help="Run salt/reactor/*.py tests",
        )
        self.test_selection_group.add_option(
            "--minion",
            "--minion-tests",
            dest="minion",
            default=False,
            action="store_true",
            help="Run tests for minion",
        )
        self.test_selection_group.add_option(
            "--returners",
            dest="returners",
            default=False,
            action="store_true",
            help="Run salt/returners/*.py tests",
        )
        self.test_selection_group.add_option(
            "--spm",
            dest="spm",
            default=False,
            action="store_true",
            help="Run spm integration tests",
        )
        self.test_selection_group.add_option(
            "--setup",
            dest="setup",
            default=False,
            action="store_true",
            help="Run setup integration tests",
        )
        self.test_selection_group.add_option(
            "-l",
            "--loader",
            "--loader-tests",
            dest="loader",
            default=False,
            action="store_true",
            help="Run loader tests",
        )
        self.test_selection_group.add_option(
            "-u",
            "--unit",
            "--unit-tests",
            dest="unit",
            default=False,
            action="store_true",
            help="Run unit tests",
        )
        self.test_selection_group.add_option(
            "-k",
            "--kitchen",
            "--kitchen-tests",
            dest="kitchen",
            default=False,
            action="store_true",
            help="Run kitchen tests",
        )
        self.test_selection_group.add_option(
            "--fileserver",
            "--fileserver-tests",
            dest="fileserver",
            default=False,
            action="store_true",
            help="Run Fileserver tests",
        )
        self.test_selection_group.add_option(
            "-w",
            "--wheel",
            "--wheel-tests",
            dest="wheel",
            action="store_true",
            default=False,
            help="Run wheel tests",
        )
        self.test_selection_group.add_option(
            "-o",
            "--outputter",
            "--outputter-tests",
            dest="outputter",
            action="store_true",
            default=False,
            help="Run outputter tests",
        )
        self.test_selection_group.add_option(
            "--cloud-provider",
            "--cloud-provider-tests",
            dest="cloud_provider",
            action="store_true",
            default=False,
            help=(
                "Run cloud provider tests. These tests create and delete "
                "instances on cloud providers. Must provide valid credentials "
                "in salt/tests/integration/files/conf/cloud.*.d to run tests."
            ),
        )
        self.test_selection_group.add_option(
            "--ssh",
            "--ssh-tests",
            dest="ssh",
            action="store_true",
            default=False,
            help="Run salt-ssh tests. These tests will spin up a temporary "
            "SSH server on your machine. In certain environments, this "
            "may be insecure! Default: False",
        )
        self.test_selection_group.add_option(
            "--ssh-int",
            dest="ssh-int",
            action="store_true",
            default=False,
            help="Run salt-ssh integration tests. Requires to be run with --ssh"
            "to spin up the SSH server on your machine.",
        )
        self.test_selection_group.add_option(
            "-A",
            "--api",
            "--api-tests",
            dest="api",
            action="store_true",
            default=False,
            help="Run salt-api tests",
        )
        self.test_selection_group.add_option(
            "--sdb",
            "--sdb-tests",
            dest="sdb",
            action="store_true",
            default=False,
            help="Run sdb tests",
        )
        self.test_selection_group.add_option(
            "-P",
            "--proxy",
            "--proxy-tests",
            dest="proxy",
            action="store_true",
            default=False,
            help="Run salt-proxy tests",
        )
        self.test_selection_group.add_option(
            "--external",
            "--external-api",
            "--external-api-tests",
            dest="external_api",
            action="store_true",
            default=False,
            help="Run venafi runner tests",
        )
        self.test_selection_group.add_option(
            "--daemons",
            "--daemon-tests",
            dest="daemons",
            action="store_true",
            default=False,
            help="Run salt/daemons/*.py tests",
        )
        self.test_selection_group.add_option(
            "--scheduler",
            dest="scheduler",
            action="store_true",
            default=False,
            help="Run scheduler integration tests",
        )
        self.test_selection_group.add_option(
            "--logging",
            dest="logging",
            action="store_true",
            default=False,
            help="Run logging integration tests",
        )
        self.test_selection_group.add_option(
            "--multimaster",
            dest="multimaster",
            action="store_true",
            default=False,
            help="Start multimaster daemons and run multimaster integration tests",
        )

    def validate_options(self):
        if self.options.cloud_provider or self.options.external_api:
            # Turn on expensive tests execution
            os.environ["EXPENSIVE_TESTS"] = "True"

        # This fails even with salt.utils.platform imported in the global
        # scope, unless we import it again here.
        import salt.utils.platform

        if salt.utils.platform.is_windows():
            import salt.utils.win_functions

            current_user = salt.utils.win_functions.get_current_user()
            if current_user == "SYSTEM":
                is_admin = True
            else:
                is_admin = salt.utils.win_functions.is_admin(current_user)
            if (
                self.options.coverage
                and any(
                    (self.options.name, not is_admin, not self.options.run_destructive)
                )
                and self._check_enabled_suites(include_unit=True)
            ):
                warnings.warn("Test suite not running with elevated priviledges")
        else:
            is_admin = os.geteuid() == 0

            if (
                self.options.coverage
                and any(
                    (self.options.name, not is_admin, not self.options.run_destructive)
                )
                and self._check_enabled_suites(include_unit=True)
            ):
                self.error(
                    "No sense in generating the tests coverage report when "
                    "not running the full test suite, including the "
                    "destructive tests, as 'root'. It would only produce "
                    "incorrect results."
                )

        # When no tests are specifically enumerated on the command line, setup
        # a default run: +unit -cloud_provider
        if not self.options.name and not self._check_enabled_suites(
            include_unit=True,
            include_cloud_provider=True,
            include_proxy=True,
            include_kitchen=True,
            include_multimaster=True,
        ):
            self._enable_suites(include_unit=True, include_multimaster=True)

        self.start_coverage(
            branch=True, source=[os.path.join(SALT_ROOT, "salt")],
        )

        # Print out which version of python this test suite is running on
        print(" * Python Version: {}".format(" ".join(sys.version.split())))

        # Transplant configuration
        TestDaemon.transplant_configs(transport=self.options.transport)

    def post_execution_cleanup(self):
        SaltCoverageTestingParser.post_execution_cleanup(self)
        if self.options.clean:
            TestDaemon.clean()

    def run_integration_suite(self, path="", display_name=""):
        """
        Run an integration test suite
        """
        full_path = os.path.join(TEST_DIR, path)
        return self.run_suite(
            full_path, display_name, suffix="test_*.py", failfast=self.options.failfast,
        )

    def start_daemons_only(self):
        if not salt.utils.platform.is_windows():
            self.set_filehandle_limits("integration")
        try:
            print_header(
                " * Setting up Salt daemons for interactive use",
                top=False,
                width=getattr(self.options, "output_columns", PNUM),
            )
        except TypeError:
            print_header(" * Setting up Salt daemons for interactive use", top=False)

        try:
            with TestDaemon(self):
                print_header(" * Salt daemons started")
                master_conf = TestDaemon.config("master")
                minion_conf = TestDaemon.config("minion")
                proxy_conf = TestDaemon.config("proxy")
                sub_minion_conf = TestDaemon.config("sub_minion")
                syndic_conf = TestDaemon.config("syndic")
                syndic_master_conf = TestDaemon.config("syndic_master")

                print_header(" * Syndic master configuration values (MoM)", top=False)
                print("interface: {}".format(syndic_master_conf["interface"]))
                print("publish port: {}".format(syndic_master_conf["publish_port"]))
                print("return port: {}".format(syndic_master_conf["ret_port"]))
                print("\n")

                print_header(" * Syndic configuration values", top=True)
                print("interface: {}".format(syndic_conf["interface"]))
                print("syndic master: {}".format(syndic_conf["syndic_master"]))
                print(
                    "syndic master port: {}".format(syndic_conf["syndic_master_port"])
                )
                print("\n")

                print_header(" * Master configuration values", top=True)
                print("interface: {}".format(master_conf["interface"]))
                print("publish port: {}".format(master_conf["publish_port"]))
                print("return port: {}".format(master_conf["ret_port"]))
                print("\n")

                print_header(" * Minion configuration values", top=True)
                print("interface: {}".format(minion_conf["interface"]))
                print("master: {}".format(minion_conf["master"]))
                print("master port: {}".format(minion_conf["master_port"]))
                if minion_conf["ipc_mode"] == "tcp":
                    print("tcp pub port: {}".format(minion_conf["tcp_pub_port"]))
                    print("tcp pull port: {}".format(minion_conf["tcp_pull_port"]))
                print("\n")

                print_header(" * Sub Minion configuration values", top=True)
                print("interface: {}".format(sub_minion_conf["interface"]))
                print("master: {}".format(sub_minion_conf["master"]))
                print("master port: {}".format(sub_minion_conf["master_port"]))
                if sub_minion_conf["ipc_mode"] == "tcp":
                    print("tcp pub port: {}".format(sub_minion_conf["tcp_pub_port"]))
                    print("tcp pull port: {}".format(sub_minion_conf["tcp_pull_port"]))
                print("\n")

                print_header(" * Proxy Minion configuration values", top=True)
                print("interface: {}".format(proxy_conf["interface"]))
                print("master: {}".format(proxy_conf["master"]))
                print("master port: {}".format(proxy_conf["master_port"]))
                if minion_conf["ipc_mode"] == "tcp":
                    print("tcp pub port: {}".format(proxy_conf["tcp_pub_port"]))
                    print("tcp pull port: {}".format(proxy_conf["tcp_pull_port"]))
                print("\n")

                print_header(
                    " Your client configuration is at {}".format(
                        TestDaemon.config_location()
                    )
                )
                print(
                    "To access the minion: salt -c {} minion test.ping".format(
                        TestDaemon.config_location()
                    )
                )

                while True:
                    time.sleep(1)
        except TestDaemonStartFailed:
            self.exit(status=2)

    def set_filehandle_limits(self, limits="integration"):
        """
        Set soft and hard limits on open file handles at required thresholds
        for integration tests or unit tests
        """
        # Get current limits
        if salt.utils.platform.is_windows():
            import win32file

            prev_hard = win32file._getmaxstdio()
            prev_soft = 512
        else:
            prev_soft, prev_hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        # Get required limits
        min_soft = MAX_OPEN_FILES[limits]["soft_limit"]
        min_hard = MAX_OPEN_FILES[limits]["hard_limit"]

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
            print(
                " * Max open files settings is too low (soft: {}, hard: {}) "
                "for running the tests".format(prev_soft, prev_hard)
            )
            print(
                " * Trying to raise the limits to soft: "
                "{}, hard: {}".format(soft, hard)
            )
            try:
                if salt.utils.platform.is_windows():
                    hard = 2048 if hard > 2048 else hard
                    win32file._setmaxstdio(hard)
                else:
                    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
            except Exception as err:  # pylint: disable=broad-except
                print(
                    "ERROR: Failed to raise the max open files settings -> "
                    "{}".format(err)
                )
                print("Please issue the following command on your console:")
                print("  ulimit -n {}".format(soft))
                self.exit()
            finally:
                print("~" * getattr(self.options, "output_columns", PNUM))

    def run_integration_tests(self):
        """
        Execute the integration tests suite
        """
        named_tests = []
        named_unit_test = []

        if self.options.name:
            for test in self.options.name:
                if test.startswith(
                    (
                        "tests.unit.",
                        "unit.",
                        "test.kitchen.",
                        "kitchen.",
                        "test.multimaster.",
                        "multimaster.",
                    )
                ):
                    named_unit_test.append(test)
                    continue
                named_tests.append(test)

        if (
            (
                self.options.unit
                or self.options.kitchen
                or self.options.multimaster
                or named_unit_test
            )
            and not named_tests
            and (
                self.options.from_filenames
                or not self._check_enabled_suites(include_cloud_provider=True)
            )
        ):
            # We're either not running any integration test suites, or we're
            # only running unit tests by passing --unit or by passing only
            # `unit.<whatever>` to --name.  We don't need the tests daemon
            # running
            return [True]

        if not salt.utils.platform.is_windows():
            self.set_filehandle_limits("integration")

        try:
            print_header(
                " * Setting up Salt daemons to execute tests",
                top=False,
                width=getattr(self.options, "output_columns", PNUM),
            )
        except TypeError:
            print_header(" * Setting up Salt daemons to execute tests", top=False)

        status = []
        # Return an empty status if no tests have been enabled
        if (
            not self._check_enabled_suites(
                include_cloud_provider=True, include_proxy=True
            )
            and not self.options.name
        ):
            return status

        try:
            with TestDaemon(self):
                if self.options.name:
                    for name in self.options.name:
                        name = name.strip()
                        if not name:
                            continue
                        if os.path.isfile(name):
                            if not name.endswith(".py"):
                                continue
                            if name.startswith(
                                (
                                    os.path.join("tests", "unit"),
                                    os.path.join("tests", "multimaster"),
                                )
                            ):
                                continue
                            results = self.run_suite(
                                os.path.dirname(name),
                                name,
                                suffix=os.path.basename(name),
                                failfast=self.options.failfast,
                                load_from_name=False,
                            )
                            status.append(results)
                            continue
                        if name.startswith(
                            (
                                "tests.unit.",
                                "unit.",
                                "tests.multimaster.",
                                "multimaster.",
                            )
                        ):
                            continue
                        results = self.run_suite(
                            "",
                            name,
                            suffix="test_*.py",
                            load_from_name=True,
                            failfast=self.options.failfast,
                        )
                        status.append(results)
                    return status
                for suite in TEST_SUITES:
                    if (
                        suite != "unit"
                        and suite != "multimaster"
                        and getattr(self.options, suite)
                    ):
                        status.append(self.run_integration_suite(**TEST_SUITES[suite]))
            return status
        except TestDaemonStartFailed:
            self.exit(status=2)

    def run_unit_tests(self):
        """
        Execute the unit tests
        """
        named_unit_test = []
        if self.options.name:
            for test in self.options.name:
                if not test.startswith(("tests.unit.", "unit.")):
                    continue
                named_unit_test.append(test)

        if not named_unit_test and (
            self.options.from_filenames or not self.options.unit
        ):
            # We are not explicitly running the unit tests and none of the
            # names passed to --name (or derived via --from-filenames) is a
            # unit test.
            return [True]

        status = []
        if self.options.unit:
            # MacOS needs more open filehandles for running unit test suite
            self.set_filehandle_limits("unit")

            results = self.run_suite(
                os.path.join(TEST_DIR, "unit"),
                "Unit",
                suffix="test_*.py",
                failfast=self.options.failfast,
            )
            status.append(results)
            # We executed ALL unittests, we can skip running unittests by name
            # below
            return status

        for name in named_unit_test:
            results = self.run_suite(
                os.path.join(TEST_DIR, "unit"),
                name,
                suffix="test_*.py",
                load_from_name=True,
                failfast=self.options.failfast,
            )
            status.append(results)
        return status

    def run_kitchen_tests(self):
        """
        Execute the kitchen tests
        """
        named_kitchen_test = []
        if self.options.name:
            for test in self.options.name:
                if not test.startswith(("tests.kitchen.", "kitchen.")):
                    continue
                named_kitchen_test.append(test)

        if not self.options.kitchen and not named_kitchen_test:
            # We are not explicitly running the unit tests and none of the
            # names passed to --name is a unit test.
            return [True]

        status = []
        if self.options.kitchen:
            results = self.run_suite(
                os.path.join(TEST_DIR, "kitchen"), "Kitchen", suffix="test_*.py"
            )
            status.append(results)
            # We executed ALL unittests, we can skip running unittests by name
            # below
            return status

        for name in named_kitchen_test:
            results = self.run_suite(
                os.path.join(TEST_DIR, "kitchen"),
                name,
                suffix="test_*.py",
                load_from_name=True,
            )
            status.append(results)
        return status


def main(**kwargs):
    """
    Parse command line options for running specific tests
    """
    try:
        parser = SaltTestsuiteParser(
            TEST_DIR,
            xml_output_dir=XML_OUTPUT_DIR,
            tests_logfile=os.path.join(SYS_TMP_DIR, "salt-runtests.log"),
        )
        parser.parse_args()

        # Override parser options (helpful when importing runtests.py and
        # running from within a REPL). Using kwargs.items() to avoid importing
        # six, as this feature will rarely be used.
        for key, val in kwargs.items():
            setattr(parser.options, key, val)

        overall_status = []
        if parser.options.interactive:
            if parser.options.multimaster:
                print(
                    "Multimaster tests now run under PyTest",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                parser.start_daemons_only()
        status = parser.run_integration_tests()
        overall_status.extend(status)
        status = parser.run_unit_tests()
        overall_status.extend(status)
        status = parser.run_kitchen_tests()
        overall_status.extend(status)
        false_count = overall_status.count(False)

        if false_count > 0:
            parser.finalize(1)
        parser.finalize(0)
    except KeyboardInterrupt:
        print("\nCaught keyboard interrupt. Exiting.\n")
        exit(0)


if __name__ == "__main__":
    main()
