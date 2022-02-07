"""
    tests.unit.test_test_module_name
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import fnmatch
import os

import salt.utils.path
import salt.utils.stringutils
from tests.support.paths import list_test_mods
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

EXCLUDED_DIRS = [
    os.path.join("tests", "integration", "cloud", "helpers"),
    os.path.join("tests", "integration", "files"),
    os.path.join("tests", "kitchen", "tests"),
    os.path.join("tests", "perf"),
    os.path.join("tests", "pkg"),
    os.path.join("tests", "support"),
    os.path.join("tests", "unit", "files"),
    os.path.join("tests", "unit", "modules", "inspectlib"),
    os.path.join("tests", "unit", "modules", "nxos"),
    os.path.join("tests", "unit", "modules", "zypp"),
    os.path.join("tests", "unit", "setup"),
    os.path.join("tests", "unit", "templates", "files"),
]
INCLUDED_DIRS = [
    os.path.join("tests", "kitchen", "tests", "*", "tests", "*"),
]
EXCLUDED_FILES = [
    os.path.join("tests", "buildpackage.py"),
    os.path.join("tests", "committer_parser.py"),
    os.path.join("tests", "consist.py"),
    os.path.join("tests", "eventlisten.py"),
    os.path.join("tests", "jenkins.py"),
    os.path.join("tests", "minionswarm.py"),
    os.path.join("tests", "modparser.py"),
    os.path.join("tests", "packdump.py"),
    os.path.join("tests", "runtests.py"),
    os.path.join("tests", "salt-tcpdump.py"),
    os.path.join("tests", "saltsh.py"),
    os.path.join("tests", "unit", "test_pytest_pass_fail.py"),
    os.path.join("tests", "unit", "transport", "mixins.py"),
    os.path.join("tests", "unit", "utils", "scheduler", "base.py"),
    os.path.join("tests", "virtualname.py"),
    os.path.join("tests", "wheeltest.py"),
    os.path.join("tests", "zypp_plugin.py"),
]


class BadTestModuleNamesTestCase(TestCase):
    """
    Unit test case for testing bad names for test modules
    """

    maxDiff = None

    def _match_dirs(self, reldir, matchdirs):
        return any(fnmatch.fnmatchcase(reldir, mdir) for mdir in matchdirs)

    def test_module_name(self):
        """
        Make sure all test modules conform to the test_*.py naming scheme
        """
        excluded_dirs, included_dirs = tuple(EXCLUDED_DIRS), tuple(INCLUDED_DIRS)
        tests_dir = os.path.join(RUNTIME_VARS.CODE_DIR, "tests")
        bad_names = []
        for root, _, files in salt.utils.path.os_walk(tests_dir):
            reldir = os.path.relpath(root, RUNTIME_VARS.CODE_DIR)
            if (
                reldir.startswith(excluded_dirs)
                and not self._match_dirs(reldir, included_dirs)
            ) or reldir.endswith("__pycache__"):
                continue
            for fname in files:
                if fname in ("__init__.py", "conftest.py") or not fname.endswith(".py"):
                    continue
                relpath = os.path.join(reldir, fname)
                if relpath in EXCLUDED_FILES:
                    continue
                if not fname.startswith("test_"):
                    bad_names.append(relpath)

        error_msg = "\n\nPlease rename the following files:\n"
        for path in bad_names:
            directory, filename = path.rsplit(os.sep, 1)
            filename, _ = os.path.splitext(filename)
            error_msg += "  {} -> {}/test_{}.py\n".format(
                path, directory, filename.split("_test")[0]
            )

        error_msg += (
            "\nIf you believe one of the entries above should be ignored, please add it to either\n"
            "'EXCLUDED_DIRS' or 'EXCLUDED_FILES' in 'tests/unit/test_module_names.py'.\n"
            "If it is a tests module, then please rename as suggested."
        )
        self.assertEqual([], bad_names, error_msg)

    def test_module_name_source_match(self):
        """
        Check all the test mods and check if they correspond to actual files in
        the codebase. If this test fails, then a test module is likely not
        named correctly, and should be adjusted.

        If a test module doesn't have a natural name match (as does this very
        file), then its should be included in the "ignore" tuple below.
        However, if there is no matching source code file, then you should
        consider mapping it to files manually via tests/filename_map.yml.
        """
        ignore = (
            "integration.cli.test_custom_module",
            "integration.cli.test_grains",
            "integration.client.test_kwarg",
            "integration.client.test_runner",
            "integration.client.test_standard",
            "integration.client.test_syndic",
            "integration.cloud.test_cloud",
            "integration.doc.test_man",
            "integration.externalapi.test_venafiapi",
            "integration.grains.test_custom",
            "integration.loader.test_ext_grains",
            "integration.loader.test_ext_modules",
            "integration.logging.handlers.test_logstash_mod",
            "integration.logging.test_jid_logging",
            "integration.master.test_clear_funcs",
            "integration.master.test_event_return",
            "integration.minion.test_executor",
            "integration.minion.test_minion_cache",
            "integration.minion.test_timeout",
            "integration.modules.test_decorators",
            "integration.modules.test_pkg",
            "integration.modules.test_service",
            "integration.modules.test_state_jinja_filters",
            "integration.modules.test_sysctl",
            "integration.netapi.rest_cherrypy.test_app_pam",
            "integration.netapi.rest_tornado.test_app",
            "integration.netapi.test_client",
            "integration.output.test_output",
            "integration.pillar.test_pillar_include",
            "integration.proxy.test_shell",
            "integration.proxy.test_simple",
            "integration.reactor.test_reactor",
            "integration.returners.test_noop_return",
            "integration.runners.test_runner_returns",
            "integration.shell.test_arguments",
            "integration.shell.test_auth",
            "integration.shell.test_call",
            "integration.shell.test_cloud",
            "integration.shell.test_cp",
            "integration.shell.test_enabled",
            "integration.shell.test_key",
            "integration.shell.test_master",
            "integration.shell.test_master_tops",
            "integration.shell.test_minion",
            "integration.shell.test_proxy",
            "integration.shell.test_runner",
            "integration.shell.test_saltcli",
            "integration.shell.test_spm",
            "integration.shell.test_syndic",
            "integration.spm.test_build",
            "integration.spm.test_files",
            "integration.spm.test_info",
            "integration.spm.test_install",
            "integration.spm.test_remove",
            "integration.spm.test_repo",
            "integration.ssh.test_deploy",
            "integration.ssh.test_grains",
            "integration.ssh.test_jinja_filters",
            "integration.ssh.test_master",
            "integration.ssh.test_mine",
            "integration.ssh.test_pillar",
            "integration.ssh.test_pre_flight",
            "integration.ssh.test_raw",
            "integration.ssh.test_saltcheck",
            "integration.ssh.test_state",
            "integration.states.test_compiler",
            "integration.states.test_handle_error",
            "integration.states.test_handle_iorder",
            "integration.states.test_match",
            "integration.states.test_renderers",
            "integration.wheel.test_client",
            "unit.cache.test_cache",
            "unit.serializers.test_serializers",
            "unit.setup.test_install",
            "unit.setup.test_man",
            "unit.states.test_postgres",
            "unit.test_doc",
            "unit.test_mock",
            "unit.test_module_names",
            "unit.test_proxy_minion",
            "unit.test_pytest_pass_fail",
            "unit.test_simple",
            "unit.test_virtualname",
            "unit.test_zypp_plugins",
            "unit.utils.scheduler.test_error",
            "unit.utils.scheduler.test_eval",
            "unit.utils.scheduler.test_helpers",
            "unit.utils.scheduler.test_maxrunning",
            "unit.utils.scheduler.test_postpone",
            "unit.utils.scheduler.test_run_job",
            "unit.utils.scheduler.test_schedule",
            "unit.utils.scheduler.test_skip",
            "unit.auth.test_auth",
        )
        errors = []

        def _format_errors(errors):
            msg = (
                "The following {} test module(s) could not be matched to a "
                "source code file:\n\n".format(len(errors))
            )
            msg += "".join(errors)
            return msg

        for mod_name in list_test_mods():
            if mod_name in ignore:
                # Test module is being ignored, skip it
                continue

            # Separate the test_foo away from the rest of the mod name, because
            # we'll need to remove the "test_" from the beginning and add .py
            stem, flower = mod_name.rsplit(".", 1)
            # Lop off the integration/unit from the beginning of the mod name
            try:
                stem = stem.split(".", 1)[1]
            except IndexError:
                # This test mod was in the root of the unit/integration dir
                stem = ""

            # The path from the root of the repo
            relpath = salt.utils.path.join(
                stem.replace(".", os.sep), ".".join((flower[5:], "py"))
            )

            # The full path to the file we expect to find
            abspath = salt.utils.path.join(RUNTIME_VARS.SALT_CODE_DIR, relpath)

            if not os.path.isfile(abspath):
                # Maybe this is in a dunder init?
                alt_relpath = salt.utils.path.join(relpath[:-3], "__init__.py")
                alt_abspath = salt.utils.path.join(abspath[:-3], "__init__.py")
                if os.path.isfile(alt_abspath):
                    # Yep, it is. Carry on!
                    continue

                errors.append("{} (expected: {})\n".format(mod_name, relpath))

        assert not errors, _format_errors(errors)
