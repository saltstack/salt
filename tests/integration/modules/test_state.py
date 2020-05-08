# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time

import pytest
import salt.utils.atomicfile
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.ext import six
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.case import ModuleCase
from tests.support.helpers import slowTest, with_tempdir
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


DEFAULT_ENDING = salt.utils.stringutils.to_bytes(os.linesep)


@pytest.mark.windows_whitelisted
class StateModuleTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the state module
    """

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        def _reline(path, ending=DEFAULT_ENDING):
            """
            Normalize the line endings of a file.
            """
            with salt.utils.files.fopen(path, "rb") as fhr:
                lines = fhr.read().splitlines()
            with salt.utils.atomicfile.atomic_open(path, "wb") as fhw:
                for line in lines:
                    fhw.write(line + ending)

        destpath = os.path.join(RUNTIME_VARS.BASE_FILES, "testappend", "firstif")
        _reline(destpath)
        destpath = os.path.join(RUNTIME_VARS.BASE_FILES, "testappend", "secondif")
        _reline(destpath)
        if salt.utils.platform.is_windows():
            cls.TIMEOUT = 600
            # Be sure to have everything sync'ed
            sminion = create_sminion()
            sminion.functions.saltutil.sync_all()
        else:
            cls.TIMEOUT = 10

    @slowTest
    def test_show_highstate(self):
        """
        state.show_highstate
        """
        high = self.run_function("state.show_highstate")
        destpath = os.path.join(RUNTIME_VARS.TMP, "testfile")
        self.assertTrue(isinstance(high, dict))
        self.assertTrue(destpath in high)
        self.assertEqual(high[destpath]["__env__"], "base")

    @slowTest
    def test_show_lowstate(self):
        """
        state.show_lowstate
        """
        low = self.run_function("state.show_lowstate")
        self.assertTrue(isinstance(low, list))
        self.assertTrue(isinstance(low[0], dict))

    @slowTest
    def test_show_states(self):
        """
        state.show_states
        """
        states = self.run_function("state.show_states")
        self.assertTrue(isinstance(states, list))
        self.assertTrue(isinstance(states[0], six.string_types))

        states = self.run_function("state.show_states", sorted=False)
        self.assertTrue(isinstance(states, list))
        self.assertTrue(isinstance(states[0], six.string_types))

    @slowTest
    def test_show_states_missing_sls(self):
        """
        Test state.show_states with a sls file
        defined in a top file is missing
        """
        topfile = os.path.join(RUNTIME_VARS.TMP_STATE_TREE, "top.sls")
        with salt.utils.files.fopen(topfile, "w") as top_file:
            top_file.write(
                textwrap.dedent(
                    """\
                                           base:
                                             '*':
                                               - doesnotexist
                                           """
                )
            )
        states = self.run_function("state.show_states")
        assert isinstance(states, list)
        assert states == ["No matching sls found for 'doesnotexist' in env 'base'"]

    @slowTest
    def test_catch_recurse(self):
        """
        state.show_sls used to catch a recursive ref
        """
        err = self.run_function("state.sls", mods="recurse_fail")
        self.assertIn("recursive", err[0])

    @slowTest
    def test_no_recurse(self):
        """
        verify that a sls structure is NOT a recursive ref
        """
        sls = self.run_function("state.show_sls", mods="recurse_ok")
        self.assertIn("snmpd", sls)

    @slowTest
    def test_no_recurse_two(self):
        """
        verify that a sls structure is NOT a recursive ref
        """
        sls = self.run_function("state.show_sls", mods="recurse_ok_two")
        self.assertIn("/etc/nagios/nrpe.cfg", sls)

    @slowTest
    def test_running_dictionary_consistency(self):
        """
        Test the structure of the running dictionary so we don't change it
        without deprecating/documenting the change
        """
        running_dict_fields = [
            "__id__",
            "__run_num__",
            "__sls__",
            "changes",
            "comment",
            "duration",
            "name",
            "result",
            "start_time",
        ]

        sls = self.run_function(
            "state.single", fun="test.succeed_with_changes", name="gndn"
        )

        for state, ret in sls.items():
            for field in running_dict_fields:
                self.assertIn(field, ret)

    @slowTest
    def test_running_dictionary_key_sls(self):
        """
        Ensure the __sls__ key is either null or a string
        """
        sls1 = self.run_function(
            "state.single", fun="test.succeed_with_changes", name="gndn"
        )

        sls2 = self.run_function("state.sls", mods="gndn")

        for state, ret in sls1.items():
            self.assertTrue(isinstance(ret["__sls__"], type(None)))

        for state, ret in sls2.items():
            self.assertTrue(isinstance(ret["__sls__"], six.string_types))

    def _remove_request_cache_file(self):
        """
        remove minion state request file
        """
        cache_file = os.path.join(self.get_config("minion")["cachedir"], "req_state.p")
        if os.path.exists(cache_file):
            os.remove(cache_file)

    @slowTest
    def test_request(self):
        """
        verify sending a state request to the minion(s)
        """
        self._remove_request_cache_file()

        ret = self.run_function("state.request", mods="modules.state.requested")
        result = ret["cmd_|-count_root_dir_contents_|-ls -a / | wc -l_|-run"]["result"]
        self.assertEqual(result, None)

    @slowTest
    def test_check_request(self):
        """
        verify checking a state request sent to the minion(s)
        """
        self._remove_request_cache_file()

        self.run_function("state.request", mods="modules.state.requested")
        ret = self.run_function("state.check_request")
        result = ret["default"]["test_run"][
            "cmd_|-count_root_dir_contents_|-ls -a / | wc -l_|-run"
        ]["result"]
        self.assertEqual(result, None)

    @slowTest
    def test_clear_request(self):
        """
        verify clearing a state request sent to the minion(s)
        """
        self._remove_request_cache_file()

        self.run_function("state.request", mods="modules.state.requested")
        ret = self.run_function("state.clear_request")
        self.assertTrue(ret)

    @slowTest
    def test_run_request_succeeded(self):
        """
        verify running a state request sent to the minion(s)
        """
        self._remove_request_cache_file()

        if salt.utils.platform.is_windows():
            self.run_function("state.request", mods="modules.state.requested_win")
        else:
            self.run_function("state.request", mods="modules.state.requested")

        ret = self.run_function("state.run_request")

        if salt.utils.platform.is_windows():
            key = "cmd_|-count_root_dir_contents_|-Get-ChildItem C:\\\\ | Measure-Object | %{$_.Count}_|-run"
        else:
            key = "cmd_|-count_root_dir_contents_|-ls -a / | wc -l_|-run"

        result = ret[key]["result"]
        self.assertTrue(result)

    @slowTest
    def test_run_request_failed_no_request_staged(self):
        """
        verify not running a state request sent to the minion(s)
        """
        self._remove_request_cache_file()

        self.run_function("state.request", mods="modules.state.requested")
        self.run_function("state.clear_request")
        ret = self.run_function("state.run_request")
        self.assertEqual(ret, {})

    @with_tempdir()
    @slowTest
    def test_issue_1896_file_append_source(self, base_dir):
        """
        Verify that we can append a file's contents
        """
        testfile = os.path.join(base_dir, "test.append")

        ret = self.run_state("file.touch", name=testfile)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "file.append", name=testfile, source="salt://testappend/firstif"
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "file.append", name=testfile, source="salt://testappend/secondif"
        )
        self.assertSaltTrueReturn(ret)

        with salt.utils.files.fopen(testfile, "r") as fp_:
            testfile_contents = salt.utils.stringutils.to_unicode(fp_.read())

        contents = textwrap.dedent(
            """\
            # set variable identifying the chroot you work in (used in the prompt below)
            if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
                debian_chroot=$(cat /etc/debian_chroot)
            fi

            # enable bash completion in interactive shells
            if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
                . /etc/bash_completion
            fi
            """
        )

        if salt.utils.platform.is_windows():
            new_contents = contents.splitlines()
            contents = os.linesep.join(new_contents)
            contents += os.linesep

        self.assertMultiLineEqual(contents, testfile_contents)

        ret = self.run_state(
            "file.append", name=testfile, source="salt://testappend/secondif"
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "file.append", name=testfile, source="salt://testappend/firstif"
        )
        self.assertSaltTrueReturn(ret)

        with salt.utils.files.fopen(testfile, "r") as fp_:
            testfile_contents = salt.utils.stringutils.to_unicode(fp_.read())

        self.assertMultiLineEqual(contents, testfile_contents)

    @slowTest
    def test_issue_1876_syntax_error(self):
        """
        verify that we catch the following syntax error::

            /tmp/salttest/issue-1876:

              file:
                - managed
                - source: salt://testfile

              file.append:
                - text: foo

        """
        testfile = os.path.join(RUNTIME_VARS.TMP, "issue-1876")

        sls = self.run_function("state.sls", mods="issue-1876")
        self.assertIn(
            "ID '{0}' in SLS 'issue-1876' contains multiple state "
            "declarations of the same type".format(testfile),
            sls,
        )

    @slowTest
    def test_issue_1879_too_simple_contains_check(self):
        expected = textwrap.dedent(
            """\
            # set variable identifying the chroot you work in (used in the prompt below)
            if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
                debian_chroot=$(cat /etc/debian_chroot)
            fi
            # enable bash completion in interactive shells
            if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
                . /etc/bash_completion
            fi
            """
        )

        if salt.utils.platform.is_windows():
            new_contents = expected.splitlines()
            expected = os.linesep.join(new_contents)
            expected += os.linesep

        testfile = os.path.join(RUNTIME_VARS.TMP, "issue-1879")
        # Delete if exiting
        if os.path.isfile(testfile):
            os.unlink(testfile)

        # Create the file
        ret = self.run_function("state.sls", mods="issue-1879", timeout=120)
        self.assertSaltTrueReturn(ret)

        # The first append
        ret = self.run_function("state.sls", mods="issue-1879.step-1", timeout=120)
        self.assertSaltTrueReturn(ret)

        # The second append
        ret = self.run_function("state.sls", mods="issue-1879.step-2", timeout=120)
        self.assertSaltTrueReturn(ret)

        # Does it match?
        try:
            with salt.utils.files.fopen(testfile, "r") as fp_:
                contents = salt.utils.stringutils.to_unicode(fp_.read())
            self.assertMultiLineEqual(expected, contents)
            # Make sure we don't re-append existing text
            ret = self.run_function("state.sls", mods="issue-1879.step-1", timeout=120)
            self.assertSaltTrueReturn(ret)

            ret = self.run_function("state.sls", mods="issue-1879.step-2", timeout=120)
            self.assertSaltTrueReturn(ret)

            with salt.utils.files.fopen(testfile, "r") as fp_:
                contents = salt.utils.stringutils.to_unicode(fp_.read())
            self.assertMultiLineEqual(expected, contents)
        except Exception:  # pylint: disable=broad-except
            if os.path.exists(testfile):
                shutil.copy(testfile, testfile + ".bak")
            raise
        finally:
            if os.path.exists(testfile):
                os.unlink(testfile)

    @slowTest
    def test_include(self):
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, tempdir, ignore_errors=True)
        pillar = {}
        for path in ("include-test", "to-include-test", "exclude-test"):
            pillar[path] = os.path.join(tempdir, path)
        ret = self.run_function("state.sls", mods="include-test", pillar=pillar)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(pillar["include-test"]))
        self.assertTrue(os.path.isfile(pillar["to-include-test"]))
        self.assertFalse(os.path.isfile(pillar["exclude-test"]))

    @slowTest
    def test_exclude(self):
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, tempdir, ignore_errors=True)
        pillar = {}
        for path in ("include-test", "exclude-test", "to-include-test"):
            pillar[path] = os.path.join(tempdir, path)
        ret = self.run_function("state.sls", mods="exclude-test", pillar=pillar)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(pillar["include-test"]))
        self.assertTrue(os.path.isfile(pillar["exclude-test"]))
        self.assertFalse(os.path.isfile(pillar["to-include-test"]))

    @skipIf(
        salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None,
        "virtualenv not installed",
    )
    @slowTest
    def test_issue_2068_template_str(self):
        venv_dir = os.path.join(RUNTIME_VARS.TMP, "issue-2068-template-str")

        try:
            ret = self.run_function(
                "state.sls", mods="issue-2068-template-str-no-dot", timeout=120
            )
            self.assertSaltTrueReturn(ret)
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Let's load the template from the filesystem. If running this state
        # with state.sls works, so should using state.template_str
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "files",
            "file",
            "base",
            "issue-2068-template-str-no-dot.sls",
        )

        with salt.utils.files.fopen(template_path, "r") as fp_:
            template = salt.utils.stringutils.to_unicode(fp_.read())
            ret = self.run_function("state.template_str", [template], timeout=120)
            self.assertSaltTrueReturn(ret)

        # Now using state.template
        ret = self.run_function("state.template", [template_path], timeout=120)
        self.assertSaltTrueReturn(ret)

        # Now the problematic #2068 including dot's
        ret = self.run_function(
            "state.sls", mods="issue-2068-template-str", timeout=120
        )
        self.assertSaltTrueReturn(ret)

        # Let's load the template from the filesystem. If running this state
        # with state.sls works, so should using state.template_str
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "files",
            "file",
            "base",
            "issue-2068-template-str.sls",
        )

        with salt.utils.files.fopen(template_path, "r") as fp_:
            template = salt.utils.stringutils.to_unicode(fp_.read())
        ret = self.run_function("state.template_str", [template], timeout=120)
        self.assertSaltTrueReturn(ret)

        # Now using state.template
        ret = self.run_function("state.template", [template_path], timeout=120)
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_template_invalid_items(self):
        TEMPLATE = textwrap.dedent(
            """\
            {0}:
              - issue-2068-template-str

            /tmp/test-template-invalid-items:
              file:
                - managed
                - source: salt://testfile
            """
        )
        for item in ("include", "exclude", "extends"):
            ret = self.run_function("state.template_str", [TEMPLATE.format(item)])
            self.assertTrue(isinstance(ret, list))
            self.assertNotEqual(ret, [])
            self.assertEqual(
                [
                    "The '{0}' declaration found on '<template-str>' is "
                    "invalid when rendering single templates".format(item)
                ],
                ret,
            )

    @slowTest
    def test_pydsl(self):
        """
        Test the basics of the pydsl
        """
        ret = self.run_function("state.sls", mods="pydsl-1")
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_issues_7905_and_8174_sls_syntax_error(self):
        """
        Call sls file with yaml syntax error.

        Ensure theses errors are detected and presented to the user without
        stack traces.
        """
        ret = self.run_function("state.sls", mods="syntax.badlist")
        self.assertEqual(
            ret, ["State 'A' in SLS 'syntax.badlist' is not formed as a list"]
        )
        ret = self.run_function("state.sls", mods="syntax.badlist2")
        self.assertEqual(
            ret, ["State 'C' in SLS 'syntax.badlist2' is not formed as a list"]
        )

    @slowTest
    def test_requisites_mixed_require_prereq_use(self):
        """
        Call sls file containing several requisites.
        """
        expected_simple_result = {
            "cmd_|-A_|-echo A_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo A" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo B" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo C" run',
                "result": True,
                "changes": True,
            },
        }
        expected_result = {
            "cmd_|-A_|-echo A fifth_|-run": {
                "__run_num__": 4,
                "comment": 'Command "echo A fifth" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B third_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo B third" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo C second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-D_|-echo D first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo D first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-E_|-echo E fourth_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo E fourth" run',
                "result": True,
                "changes": True,
            },
        }
        expected_req_use_result = {
            "cmd_|-A_|-echo A_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo A" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B_|-run": {
                "__run_num__": 4,
                "comment": 'Command "echo B" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo C" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-D_|-echo D_|-run": {
                "__run_num__": 5,
                "comment": 'Command "echo D" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-E_|-echo E_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo E" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-F_|-echo F_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo F" run',
                "result": True,
                "changes": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.mixed_simple")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_simple_result, result)

        # test Traceback recursion prereq+require #8785
        # TODO: this is actually failing badly
        # ret = self.run_function('state.sls', mods='requisites.prereq_require_recursion_error2')
        # self.assertEqual(
        #    ret,
        #    ['A recursive requisite was found, SLS "requisites.prereq_require_recursion_error2" ID "B" ID "A"']
        # )

        # test Infinite recursion prereq+require #8785 v2
        # TODO: this is actually failing badly
        # ret = self.run_function('state.sls', mods='requisites.prereq_require_recursion_error3')
        # self.assertEqual(
        #    ret,
        #    ['A recursive requisite was found, SLS "requisites.prereq_require_recursion_error2" ID "B" ID "A"']
        # )

        # test Infinite recursion prereq+require #8785 v3
        # TODO: this is actually failing badly, and expected result is maybe not a recursion
        # ret = self.run_function('state.sls', mods='requisites.prereq_require_recursion_error4')
        # self.assertEqual(
        #    ret,
        #    ['A recursive requisite was found, SLS "requisites.prereq_require_recursion_error2" ID "B" ID "A"']
        # )

        # undetected infinite loopS prevents this test from running...
        # TODO: this is actually failing badly
        # ret = self.run_function('state.sls', mods='requisites.mixed_complex1')
        # result = self.normalize_ret(ret)
        # self.assertEqual(expected_result, result)

    @slowTest
    def test_watch_in(self):
        """
        test watch_in requisite when there is a success
        """
        ret = self.run_function("state.sls", mods="requisites.watch_in")
        changes = "test_|-return_changes_|-return_changes_|-succeed_with_changes"
        watch = "test_|-watch_states_|-watch_states_|-succeed_without_changes"

        self.assertEqual(ret[changes]["__run_num__"], 0)
        self.assertEqual(ret[watch]["__run_num__"], 2)

        self.assertEqual("Watch statement fired.", ret[watch]["comment"])
        self.assertEqual(
            "Something pretended to change", ret[changes]["changes"]["testing"]["new"]
        )

    @slowTest
    def test_watch_in_failure(self):
        """
        test watch_in requisite when there is a failure
        """
        ret = self.run_function("state.sls", mods="requisites.watch_in_failure")
        fail = "test_|-return_changes_|-return_changes_|-fail_with_changes"
        watch = "test_|-watch_states_|-watch_states_|-succeed_without_changes"

        self.assertEqual(False, ret[fail]["result"])
        self.assertEqual(
            "One or more requisite failed: requisites.watch_in_failure.return_changes",
            ret[watch]["comment"],
        )

    def normalize_ret(self, ret):
        """
        Normalize the return to the format that we'll use for result checking
        """
        result = {}
        for item, descr in six.iteritems(ret):
            result[item] = {
                "__run_num__": descr["__run_num__"],
                "comment": descr["comment"],
                "result": descr["result"],
                "changes": descr["changes"] != {},  # whether there where any changes
            }
        return result

    @slowTest
    def test_requisites_require_ordering_and_errors(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        expected_result = {
            "cmd_|-A_|-echo A fifth_|-run": {
                "__run_num__": 4,
                "comment": 'Command "echo A fifth" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo B second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C third_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo C third" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-D_|-echo D first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo D first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-E_|-echo E fourth_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo E fourth" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-F_|-echo F_|-run": {
                "__run_num__": 5,
                "comment": "The following requisites were not found:\n"
                + "                   require:\n"
                + "                       foobar: A\n",
                "result": False,
                "changes": False,
            },
            "cmd_|-G_|-echo G_|-run": {
                "__run_num__": 6,
                "comment": "The following requisites were not found:\n"
                + "                   require:\n"
                + "                       cmd: Z\n",
                "result": False,
                "changes": False,
            },
            "cmd_|-H_|-echo H_|-run": {
                "__run_num__": 7,
                "comment": "The following requisites were not found:\n"
                + "                   require:\n"
                + "                       cmd: Z\n",
                "result": False,
                "changes": False,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.require")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

        ret = self.run_function("state.sls", mods="requisites.require_error1")
        self.assertEqual(
            ret,
            [
                "Cannot extend ID 'W' in 'base:requisites.require_error1'. It is not part of the high state.\nThis is likely due to a missing include statement or an incorrectly typed ID.\nEnsure that a state with an ID of 'W' is available\nin environment 'base' and to SLS 'requisites.require_error1'"
            ],
        )

        # issue #8235
        # FIXME: Why is require enforcing list syntax while require_in does not?
        # And why preventing it?
        # Currently this state fails, should return C/B/A
        result = {}
        ret = self.run_function("state.sls", mods="requisites.require_simple_nolist")
        self.assertEqual(
            ret,
            [
                "The require statement in state 'B' in SLS "
                + "'requisites.require_simple_nolist' needs to be formed as a list"
            ],
        )

        # commented until a fix is made for issue #8772
        # TODO: this test actually fails
        # ret = self.run_function('state.sls', mods='requisites.require_error2')
        # self.assertEqual(ret, [
        #    'Cannot extend state foobar for ID A in "base:requisites.require_error2".'
        #    + ' It is not part of the high state.'
        # ])

        ret = self.run_function("state.sls", mods="requisites.require_recursion_error1")
        self.assertEqual(
            ret,
            [
                'A recursive requisite was found, SLS "requisites.require_recursion_error1" ID "B" ID "A"'
            ],
        )

    @slowTest
    def test_requisites_require_any(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        expected_result = {
            "cmd_|-A_|-echo A_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo A" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo B" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-$(which false)_|-run": {
                "__run_num__": 1,
                "comment": 'Command "$(which false)" run',
                "result": False,
                "changes": True,
            },
            "cmd_|-D_|-echo D_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo D" run',
                "result": True,
                "changes": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.require_any")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

    @slowTest
    def test_requisites_require_any_fail(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        ret = self.run_function("state.sls", mods="requisites.require_any_fail")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertIn(
            "One or more requisite failed", result["cmd_|-D_|-echo D_|-run"]["comment"]
        )

    @slowTest
    def test_requisites_watch_any(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        if salt.utils.platform.is_windows():
            cmd_true = "exit"
            cmd_false = "exit /B 1"
        else:
            cmd_true = "true"
            cmd_false = "false"
        expected_result = {
            "cmd_|-A_|-{0}_|-wait".format(cmd_true): {
                "__run_num__": 4,
                "comment": 'Command "{0}" run'.format(cmd_true),
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-{0}_|-run".format(cmd_true): {
                "__run_num__": 0,
                "comment": 'Command "{0}" run'.format(cmd_true),
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-{0}_|-run".format(cmd_false): {
                "__run_num__": 1,
                "comment": 'Command "{0}" run'.format(cmd_false),
                "result": False,
                "changes": True,
            },
            "cmd_|-D_|-{0}_|-run".format(cmd_true): {
                "__run_num__": 2,
                "comment": 'Command "{0}" run'.format(cmd_true),
                "result": True,
                "changes": True,
            },
            "cmd_|-E_|-{0}_|-wait".format(cmd_true): {
                "__run_num__": 9,
                "comment": 'Command "{0}" run'.format(cmd_true),
                "result": True,
                "changes": True,
            },
            "cmd_|-F_|-{0}_|-run".format(cmd_true): {
                "__run_num__": 5,
                "comment": 'Command "{0}" run'.format(cmd_true),
                "result": True,
                "changes": True,
            },
            "cmd_|-G_|-{0}_|-run".format(cmd_false): {
                "__run_num__": 6,
                "comment": 'Command "{0}" run'.format(cmd_false),
                "result": False,
                "changes": True,
            },
            "cmd_|-H_|-{0}_|-run".format(cmd_false): {
                "__run_num__": 7,
                "comment": 'Command "{0}" run'.format(cmd_false),
                "result": False,
                "changes": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.watch_any")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

    @slowTest
    def test_requisites_watch_any_fail(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        ret = self.run_function("state.sls", mods="requisites.watch_any_fail")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertIn(
            "One or more requisite failed", result["cmd_|-A_|-true_|-wait"]["comment"]
        )

    @slowTest
    def test_requisites_onchanges_any(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        expected_result = {
            'cmd_|-another_changing_state_|-echo "Changed!"_|-run': {
                "__run_num__": 1,
                "changes": True,
                "comment": 'Command "echo "Changed!"" run',
                "result": True,
            },
            'cmd_|-changing_state_|-echo "Changed!"_|-run': {
                "__run_num__": 0,
                "changes": True,
                "comment": 'Command "echo "Changed!"" run',
                "result": True,
            },
            'cmd_|-test_one_changing_states_|-echo "Success!"_|-run': {
                "__run_num__": 4,
                "changes": True,
                "comment": 'Command "echo "Success!"" run',
                "result": True,
            },
            'cmd_|-test_two_non_changing_states_|-echo "Should not run"_|-run': {
                "__run_num__": 5,
                "changes": False,
                "comment": "State was not run because none of the onchanges reqs changed",
                "result": True,
            },
            "pip_|-another_non_changing_state_|-mock_|-installed": {
                "__run_num__": 3,
                "changes": False,
                "comment": "Python package mock was already installed\nAll specified packages are already installed",
                "result": True,
            },
            "pip_|-non_changing_state_|-mock_|-installed": {
                "__run_num__": 2,
                "changes": False,
                "comment": "Python package mock was already installed\nAll specified packages are already installed",
                "result": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.onchanges_any")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

    @slowTest
    def test_requisites_onfail_any(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        expected_result = {
            "cmd_|-a_|-exit 0_|-run": {
                "__run_num__": 0,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-b_|-exit 1_|-run": {
                "__run_num__": 1,
                "changes": True,
                "comment": 'Command "exit 1" run',
                "result": False,
            },
            "cmd_|-c_|-exit 0_|-run": {
                "__run_num__": 2,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-d_|-echo itworked_|-run": {
                "__run_num__": 3,
                "changes": True,
                "comment": 'Command "echo itworked" run',
                "result": True,
            },
            "cmd_|-e_|-exit 0_|-run": {
                "__run_num__": 4,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-f_|-exit 0_|-run": {
                "__run_num__": 5,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-g_|-exit 0_|-run": {
                "__run_num__": 6,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-h_|-echo itworked_|-run": {
                "__run_num__": 7,
                "changes": False,
                "comment": "State was not run because onfail req did not change",
                "result": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.onfail_any")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

    @slowTest
    def test_requisites_onfail_all(self):
        """
        Call sls file containing several onfail-all

        Ensure that some of them are failing and that the order is right.
        """
        expected_result = {
            "cmd_|-a_|-exit 0_|-run": {
                "__run_num__": 0,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-b_|-exit 0_|-run": {
                "__run_num__": 1,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-c_|-exit 0_|-run": {
                "__run_num__": 2,
                "changes": True,
                "comment": 'Command "exit 0" run',
                "result": True,
            },
            "cmd_|-d_|-exit 1_|-run": {
                "__run_num__": 3,
                "changes": True,
                "comment": 'Command "exit 1" run',
                "result": False,
            },
            "cmd_|-e_|-exit 1_|-run": {
                "__run_num__": 4,
                "changes": True,
                "comment": 'Command "exit 1" run',
                "result": False,
            },
            "cmd_|-f_|-exit 1_|-run": {
                "__run_num__": 5,
                "changes": True,
                "comment": 'Command "exit 1" run',
                "result": False,
            },
            "cmd_|-reqs also met_|-echo itonfailed_|-run": {
                "__run_num__": 9,
                "changes": True,
                "comment": 'Command "echo itonfailed" run',
                "result": True,
            },
            "cmd_|-reqs also not met_|-echo italsodidnonfail_|-run": {
                "__run_num__": 7,
                "changes": False,
                "comment": "State was not run because onfail req did not change",
                "result": True,
            },
            "cmd_|-reqs met_|-echo itonfailed_|-run": {
                "__run_num__": 8,
                "changes": True,
                "comment": 'Command "echo itonfailed" run',
                "result": True,
            },
            "cmd_|-reqs not met_|-echo itdidntonfail_|-run": {
                "__run_num__": 6,
                "changes": False,
                "comment": "State was not run because onfail req did not change",
                "result": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.onfail_all")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

    @slowTest
    def test_requisites_full_sls(self):
        """
        Teste the sls special command in requisites
        """
        expected_result = {
            "cmd_|-A_|-echo A_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo A" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo B" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo C" run',
                "result": True,
                "changes": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.fullsls_require")
        self.assertReturnNonEmptySaltType(ret)
        result = self.normalize_ret(ret)
        self.assertEqual(expected_result, result)

        # issue #8233: traceback on prereq sls
        # TODO: not done
        # ret = self.run_function('state.sls', mods='requisites.fullsls_prereq')
        # self.assertEqual(['sls command can only be used with require requisite'], ret)

    @slowTest
    def test_requisites_require_no_state_module(self):
        """
        Call sls file containing several require_in and require.

        Ensure that some of them are failing and that the order is right.
        """
        expected_result = {
            "cmd_|-A_|-echo A fifth_|-run": {
                "__run_num__": 4,
                "comment": 'Command "echo A fifth" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo B second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C third_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo C third" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-D_|-echo D first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo D first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-E_|-echo E fourth_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo E fourth" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-G_|-echo G_|-run": {
                "__run_num__": 5,
                "comment": "The following requisites were not found:\n"
                + "                   require:\n"
                + "                       id: Z\n",
                "result": False,
                "changes": False,
            },
            "cmd_|-H_|-echo H_|-run": {
                "__run_num__": 6,
                "comment": "The following requisites were not found:\n"
                + "                   require:\n"
                + "                       id: Z\n",
                "result": False,
                "changes": False,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.require_no_state_module")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result, result)

    @slowTest
    def test_requisites_prereq_simple_ordering_and_errors(self):
        """
        Call sls file containing several prereq_in and prereq.

        Ensure that some of them are failing and that the order is right.
        """
        expected_result_simple = {
            "cmd_|-A_|-echo A third_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo A third" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo B first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo C second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-I_|-echo I_|-run": {
                "__run_num__": 3,
                "comment": "The following requisites were not found:\n"
                + "                   prereq:\n"
                + "                       cmd: Z\n",
                "result": False,
                "changes": False,
            },
            "cmd_|-J_|-echo J_|-run": {
                "__run_num__": 4,
                "comment": "The following requisites were not found:\n"
                + "                   prereq:\n"
                + "                       foobar: A\n",
                "result": False,
                "changes": False,
            },
        }
        expected_result_simple_no_state_module = {
            "cmd_|-A_|-echo A third_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo A third" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo B first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo C second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-I_|-echo I_|-run": {
                "__run_num__": 3,
                "comment": "The following requisites were not found:\n"
                + "                   prereq:\n"
                + "                       id: Z\n",
                "result": False,
                "changes": False,
            },
        }
        expected_result_simple2 = {
            "cmd_|-A_|-echo A_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo A" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo B" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo C" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-D_|-echo D_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo D" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-E_|-echo E_|-run": {
                "__run_num__": 4,
                "comment": 'Command "echo E" run',
                "result": True,
                "changes": True,
            },
        }
        expected_result_simple3 = {
            "cmd_|-A_|-echo A first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo A first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo B second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C third_|-wait": {
                "__run_num__": 2,
                "comment": "",
                "result": True,
                "changes": False,
            },
        }
        expected_result_complex = {
            "cmd_|-A_|-echo A fourth_|-run": {
                "__run_num__": 3,
                "comment": 'Command "echo A fourth" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-B_|-echo B first_|-run": {
                "__run_num__": 0,
                "comment": 'Command "echo B first" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-C_|-echo C second_|-run": {
                "__run_num__": 1,
                "comment": 'Command "echo C second" run',
                "result": True,
                "changes": True,
            },
            "cmd_|-D_|-echo D third_|-run": {
                "__run_num__": 2,
                "comment": 'Command "echo D third" run',
                "result": True,
                "changes": True,
            },
        }
        ret = self.run_function("state.sls", mods="requisites.prereq_simple")
        self.assertReturnNonEmptySaltType(ret)
        result = self.normalize_ret(ret)
        self.assertEqual(expected_result_simple, result)

        # same test, but not using lists in yaml syntax
        # TODO: issue #8235, prereq ignored when not used in list syntax
        # Currently fails badly with :
        # TypeError encountered executing state.sls: string indices must be integers, not str.
        # expected_result_simple.pop('cmd_|-I_|-echo I_|-run')
        # expected_result_simple.pop('cmd_|-J_|-echo J_|-run')
        # ret = self.run_function('state.sls', mods='requisites.prereq_simple_nolist')
        # result = self.normalize_ret(ret)
        # self.assertEqual(expected_result_simple, result)

        ret = self.run_function("state.sls", mods="requisites.prereq_simple2")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result_simple2, result)

        ret = self.run_function("state.sls", mods="requisites.prereq_simple3")
        result = self.normalize_ret(ret)
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(expected_result_simple3, result)

        # ret = self.run_function('state.sls', mods='requisites.prereq_error_nolist')
        # self.assertEqual(
        #    ret,
        #    ['Cannot extend ID Z in "base:requisites.prereq_error_nolist".'
        #    + ' It is not part of the high state.']
        # )

        ret = self.run_function("state.sls", mods="requisites.prereq_compile_error1")
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(
            ret["cmd_|-B_|-echo B_|-run"]["comment"],
            "The following requisites were not found:\n"
            + "                   prereq:\n"
            + "                       foobar: A\n",
        )

        ret = self.run_function("state.sls", mods="requisites.prereq_compile_error2")
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual(
            ret["cmd_|-B_|-echo B_|-run"]["comment"],
            "The following requisites were not found:\n"
            + "                   prereq:\n"
            + "                       foobar: C\n",
        )

        ret = self.run_function("state.sls", mods="requisites.prereq_complex")
        result = self.normalize_ret(ret)
        self.assertEqual(expected_result_complex, result)

        # issue #8210 : prereq recursion undetected
        # TODO: this test fails
        # ret = self.run_function('state.sls', mods='requisites.prereq_recursion_error')
        # self.assertEqual(
        #    ret,
        #    ['A recursive requisite was found, SLS "requisites.prereq_recursion_error" ID "B" ID "A"']
        # )

        ret = self.run_function(
            "state.sls", mods="requisites.prereq_simple_no_state_module"
        )
        result = self.normalize_ret(ret)
        self.assertEqual(expected_result_simple_no_state_module, result)

    @slowTest
    def test_infinite_recursion_sls_prereq(self):
        ret = self.run_function(
            "state.sls", mods="requisites.prereq_sls_infinite_recursion"
        )
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_requisites_use(self):
        """
        Call sls file containing several use_in and use.

        """
        # TODO issue #8235 & #8774 some examples are still commented in the test file
        ret = self.run_function("state.sls", mods="requisites.use")
        self.assertReturnNonEmptySaltType(ret)
        for item, descr in six.iteritems(ret):
            self.assertEqual(descr["comment"], "onlyif condition is false")

        # TODO: issue #8802 : use recursions undetected
        # issue is closed as use does not actually inherit requisites
        # if chain-use is added after #8774 resolution theses tests would maybe become useful
        # ret = self.run_function('state.sls', mods='requisites.use_recursion')
        # self.assertEqual(ret, [
        #    'A recursive requisite was found, SLS "requisites.use_recursion"'
        #    + ' ID "B" ID "A"'
        # ])

        # ret = self.run_function('state.sls', mods='requisites.use_recursion2')
        # self.assertEqual(ret, [
        #    'A recursive requisite was found, SLS "requisites.use_recursion2"'
        #    + ' ID "C" ID "A"'
        # ])

        # ret = self.run_function('state.sls', mods='requisites.use_auto_recursion')
        # self.assertEqual(ret, [
        #    'A recursive requisite was found, SLS "requisites.use_recursion"'
        #    + ' ID "A" ID "A"'
        # ])

    @slowTest
    def test_requisites_use_no_state_module(self):
        """
        Call sls file containing several use_in and use.

        """
        ret = self.run_function("state.sls", mods="requisites.use_no_state_module")
        self.assertReturnNonEmptySaltType(ret)
        for item, descr in six.iteritems(ret):
            self.assertEqual(descr["comment"], "onlyif condition is false")

    @slowTest
    def test_onlyif_req(self):
        ret = self.run_function(
            "state.single",
            fun="test.succeed_with_changes",
            name="onlyif test",
            onlyif=[{}],
        )["test_|-onlyif test_|-onlyif test_|-succeed_with_changes"]
        self.assertTrue(ret["result"])
        self.assertEqual(ret["comment"], "Success!")
        ret = self.run_function(
            "state.single",
            fun="test.fail_with_changes",
            name="onlyif test",
            onlyif=[{"fun": "test.false"}],
        )["test_|-onlyif test_|-onlyif test_|-fail_with_changes"]
        self.assertTrue(ret["result"])
        self.assertFalse(ret["changes"])
        self.assertEqual(ret["comment"], "onlyif condition is false")
        ret = self.run_function(
            "state.single",
            fun="test.fail_with_changes",
            name="onlyif test",
            onlyif=[{"fun": "test.true"}],
        )["test_|-onlyif test_|-onlyif test_|-fail_with_changes"]
        self.assertFalse(ret["result"])
        self.assertTrue(ret["changes"])
        self.assertEqual(ret["comment"], "Failure!")
        ret = self.run_function(
            "state.single",
            fun="test.succeed_without_changes",
            name="onlyif test",
            onlyif=[{"fun": "test.true"}],
        )["test_|-onlyif test_|-onlyif test_|-succeed_without_changes"]
        self.assertTrue(ret["result"])
        self.assertFalse(ret["changes"])
        self.assertEqual(ret["comment"], "Success!")

    @slowTest
    def test_onlyif_req_retcode(self):
        ret = self.run_function(
            "state.single",
            fun="test.succeed_with_changes",
            name="onlyif test",
            onlyif=[{"fun": "test.retcode"}],
        )["test_|-onlyif test_|-onlyif test_|-succeed_with_changes"]
        self.assertTrue(ret["result"])
        self.assertFalse(ret["changes"])
        self.assertEqual(ret["comment"], "onlyif condition is false")
        ret = self.run_function(
            "state.single",
            fun="test.succeed_with_changes",
            name="onlyif test",
            onlyif=[{"fun": "test.retcode", "code": 0}],
        )["test_|-onlyif test_|-onlyif test_|-succeed_with_changes"]
        self.assertTrue(ret["result"])
        self.assertTrue(ret["changes"])
        self.assertEqual(ret["comment"], "Success!")

    @slowTest
    def test_unless_req(self):
        ret = self.run_function(
            "state.single",
            fun="test.succeed_with_changes",
            name="unless test",
            unless=[{}],
        )["test_|-unless test_|-unless test_|-succeed_with_changes"]
        self.assertTrue(ret["result"])
        self.assertEqual(ret["comment"], "Success!")
        ret = self.run_function(
            "state.single",
            fun="test.fail_with_changes",
            name="unless test",
            unless=[{"fun": "test.true"}],
        )["test_|-unless test_|-unless test_|-fail_with_changes"]
        self.assertTrue(ret["result"])
        self.assertFalse(ret["changes"])
        self.assertEqual(ret["comment"], "unless condition is true")
        ret = self.run_function(
            "state.single",
            fun="test.fail_with_changes",
            name="unless test",
            unless=[{"fun": "test.false"}],
        )["test_|-unless test_|-unless test_|-fail_with_changes"]
        self.assertFalse(ret["result"])
        self.assertTrue(ret["changes"])
        self.assertEqual(ret["comment"], "Failure!")
        ret = self.run_function(
            "state.single",
            fun="test.succeed_without_changes",
            name="unless test",
            unless=[{"fun": "test.false"}],
        )["test_|-unless test_|-unless test_|-succeed_without_changes"]
        self.assertTrue(ret["result"])
        self.assertFalse(ret["changes"])
        self.assertEqual(ret["comment"], "Success!")

    @slowTest
    def test_unless_req_retcode(self):
        ret = self.run_function(
            "state.single",
            fun="test.succeed_with_changes",
            name="unless test",
            unless=[{"fun": "test.retcode"}],
        )["test_|-unless test_|-unless test_|-succeed_with_changes"]
        self.assertTrue(ret["result"])
        self.assertTrue(ret["changes"])
        self.assertEqual(ret["comment"], "Success!")
        ret = self.run_function(
            "state.single",
            fun="test.succeed_with_changes",
            name="unless test",
            unless=[{"fun": "test.retcode", "code": 0}],
        )["test_|-unless test_|-unless test_|-succeed_with_changes"]
        self.assertTrue(ret["result"])
        self.assertFalse(ret["changes"])
        self.assertEqual(ret["comment"], "unless condition is true")

    @slowTest
    def test_get_file_from_env_in_top_match(self):
        tgt = os.path.join(RUNTIME_VARS.TMP, "prod-cheese-file")
        try:
            ret = self.run_function("state.highstate", minion_tgt="sub_minion")
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(tgt))
            with salt.utils.files.fopen(tgt, "r") as cheese:
                data = salt.utils.stringutils.to_unicode(cheese.read())
            self.assertIn("Gromit", data)
            self.assertIn("Comte", data)
        finally:
            if os.path.islink(tgt):
                os.unlink(tgt)

    # onchanges tests

    @slowTest
    def test_onchanges_requisite(self):
        """
        Tests a simple state using the onchanges requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.onchanges_simple")

        # First, test the result of the state run when changes are expected to happen
        test_data = state_run['cmd_|-test_changing_state_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

        # Then, test the result of the state run when changes are not expected to happen
        test_data = state_run[
            'cmd_|-test_non_changing_state_|-echo "Should not run"_|-run'
        ]["comment"]
        expected_result = "State was not run because none of the onchanges reqs changed"
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_onchanges_requisite_multiple(self):
        """
        Tests a simple state using the onchanges requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.onchanges_multiple")

        # First, test the result of the state run when two changes are expected to happen
        test_data = state_run['cmd_|-test_two_changing_states_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

        # Then, test the result of the state run when two changes are not expected to happen
        test_data = state_run[
            'cmd_|-test_two_non_changing_states_|-echo "Should not run"_|-run'
        ]["comment"]
        expected_result = "State was not run because none of the onchanges reqs changed"
        self.assertIn(expected_result, test_data)

        # Finally, test the result of the state run when only one of the onchanges requisites changes.
        test_data = state_run['cmd_|-test_one_changing_state_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_onchanges_in_requisite(self):
        """
        Tests a simple state using the onchanges_in requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function(
            "state.sls", mods="requisites.onchanges_in_simple"
        )

        # First, test the result of the state run of when changes are expected to happen
        test_data = state_run['cmd_|-test_changes_expected_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

        # Then, test the result of the state run when changes are not expected to happen
        test_data = state_run[
            'cmd_|-test_changes_not_expected_|-echo "Should not run"_|-run'
        ]["comment"]
        expected_result = "State was not run because none of the onchanges reqs changed"
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_onchanges_requisite_no_state_module(self):
        """
        Tests a simple state using the onchanges requisite without state modules
        """
        # Only run the state once and keep the return data
        state_run = self.run_function(
            "state.sls", mods="requisites.onchanges_simple_no_state_module"
        )
        test_data = state_run['cmd_|-test_changing_state_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_onchanges_requisite_with_duration(self):
        """
        Tests a simple state using the onchanges requisite
        the state will not run but results will include duration
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.onchanges_simple")

        # Then, test the result of the state run when changes are not expected to happen
        # and ensure duration is included in the results
        test_data = state_run[
            'cmd_|-test_non_changing_state_|-echo "Should not run"_|-run'
        ]
        self.assertIn("duration", test_data)

    # onfail tests

    @slowTest
    def test_onfail_requisite(self):
        """
        Tests a simple state using the onfail requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.onfail_simple")

        # First, test the result of the state run when a failure is expected to happen
        test_data = state_run['cmd_|-test_failing_state_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

        # Then, test the result of the state run when a failure is not expected to happen
        test_data = state_run[
            'cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'
        ]["comment"]
        expected_result = "State was not run because onfail req did not change"
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_multiple_onfail_requisite(self):
        """
        test to ensure state is run even if only one
        of the onfails fails. This is a test for the issue:
        https://github.com/saltstack/salt/issues/22370
        """

        state_run = self.run_function(
            "state.sls", mods="requisites.onfail_multiple", timeout=self.TIMEOUT
        )

        retcode = state_run["cmd_|-c_|-echo itworked_|-run"]["changes"]["retcode"]
        self.assertEqual(retcode, 0)

        stdout = state_run["cmd_|-c_|-echo itworked_|-run"]["changes"]["stdout"]
        self.assertEqual(stdout, "itworked")

    @slowTest
    def test_onfail_in_requisite(self):
        """
        Tests a simple state using the onfail_in requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.onfail_in_simple")

        # First, test the result of the state run when a failure is expected to happen
        test_data = state_run['cmd_|-test_failing_state_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

        # Then, test the result of the state run when a failure is not expected to happen
        test_data = state_run[
            'cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'
        ]["comment"]
        expected_result = "State was not run because onfail req did not change"
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_onfail_requisite_no_state_module(self):
        """
        Tests a simple state using the onfail requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function(
            "state.sls", mods="requisites.onfail_simple_no_state_module"
        )

        # First, test the result of the state run when a failure is expected to happen
        test_data = state_run['cmd_|-test_failing_state_|-echo "Success!"_|-run'][
            "comment"
        ]
        expected_result = 'Command "echo "Success!"" run'
        self.assertIn(expected_result, test_data)

        # Then, test the result of the state run when a failure is not expected to happen
        test_data = state_run[
            'cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'
        ]["comment"]
        expected_result = "State was not run because onfail req did not change"
        self.assertIn(expected_result, test_data)

    @slowTest
    def test_onfail_requisite_with_duration(self):
        """
        Tests a simple state using the onfail requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.onfail_simple")

        # Then, test the result of the state run when a failure is not expected to happen
        test_data = state_run[
            'cmd_|-test_non_failing_state_|-echo "Should not run"_|-run'
        ]
        self.assertIn("duration", test_data)

    @slowTest
    def test_multiple_onfail_requisite_with_required(self):
        """
        test to ensure multiple states are run
        when specified as onfails for a single state.
        This is a test for the issue:
        https://github.com/saltstack/salt/issues/46552
        """

        state_run = self.run_function(
            "state.sls", mods="requisites.onfail_multiple_required"
        )

        retcode = state_run["cmd_|-b_|-echo b_|-run"]["changes"]["retcode"]
        self.assertEqual(retcode, 0)

        retcode = state_run["cmd_|-c_|-echo c_|-run"]["changes"]["retcode"]
        self.assertEqual(retcode, 0)

        retcode = state_run["cmd_|-d_|-echo d_|-run"]["changes"]["retcode"]
        self.assertEqual(retcode, 0)

        stdout = state_run["cmd_|-b_|-echo b_|-run"]["changes"]["stdout"]
        self.assertEqual(stdout, "b")

        stdout = state_run["cmd_|-c_|-echo c_|-run"]["changes"]["stdout"]
        self.assertEqual(stdout, "c")

        stdout = state_run["cmd_|-d_|-echo d_|-run"]["changes"]["stdout"]
        self.assertEqual(stdout, "d")

        comment = state_run["cmd_|-e_|-echo e_|-run"]["comment"]
        self.assertEqual(comment, "State was not run because onfail req did not change")

        stdout = state_run["cmd_|-f_|-echo f_|-run"]["changes"]["stdout"]
        self.assertEqual(stdout, "f")

    @slowTest
    def test_multiple_onfail_requisite_with_required_no_run(self):
        """
        test to ensure multiple states are not run
        when specified as onfails for a single state
        which fails.
        This is a test for the issue:
        https://github.com/saltstack/salt/issues/46552
        """

        state_run = self.run_function(
            "state.sls", mods="requisites.onfail_multiple_required_no_run"
        )

        expected = "State was not run because onfail req did not change"

        stdout = state_run["cmd_|-b_|-echo b_|-run"]["comment"]
        self.assertEqual(stdout, expected)

        stdout = state_run["cmd_|-c_|-echo c_|-run"]["comment"]
        self.assertEqual(stdout, expected)

        stdout = state_run["cmd_|-d_|-echo d_|-run"]["comment"]
        self.assertEqual(stdout, expected)

    # listen tests

    @slowTest
    def test_listen_requisite(self):
        """
        Tests a simple state using the listen requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.listen_simple")

        # First, test the result of the state run when a listener is expected to trigger
        listener_state = 'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch'
        self.assertIn(listener_state, state_run)

        # Then, test the result of the state run when a listener should not trigger
        absent_state = 'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run once"_|-mod_watch'
        self.assertNotIn(absent_state, state_run)

    @slowTest
    def test_listen_in_requisite(self):
        """
        Tests a simple state using the listen_in requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.listen_in_simple")

        # First, test the result of the state run when a listener is expected to trigger
        listener_state = 'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch'
        self.assertIn(listener_state, state_run)

        # Then, test the result of the state run when a listener should not trigger
        absent_state = 'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run once"_|-mod_watch'
        self.assertNotIn(absent_state, state_run)

    @slowTest
    def test_listen_in_requisite_resolution(self):
        """
        Verify listen_in requisite lookups use ID declaration to check for changes
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.listen_in_simple")

        # Test the result of the state run when a listener is expected to trigger
        listener_state = 'cmd_|-listener_test_listen_in_resolution_|-echo "Successful listen_in resolution"_|-mod_watch'
        self.assertIn(listener_state, state_run)

    @slowTest
    def test_listen_requisite_resolution(self):
        """
        Verify listen requisite lookups use ID declaration to check for changes
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.listen_simple")

        # Both listeners are expected to trigger
        listener_state = 'cmd_|-listener_test_listening_resolution_one_|-echo "Successful listen resolution"_|-mod_watch'
        self.assertIn(listener_state, state_run)

        listener_state = 'cmd_|-listener_test_listening_resolution_two_|-echo "Successful listen resolution"_|-mod_watch'
        self.assertIn(listener_state, state_run)

    @slowTest
    def test_listen_requisite_no_state_module(self):
        """
        Tests a simple state using the listen requisite
        """

        # Only run the state once and keep the return data
        state_run = self.run_function(
            "state.sls", mods="requisites.listen_simple_no_state_module"
        )
        # First, test the result of the state run when a listener is expected to trigger
        listener_state = 'cmd_|-listener_test_listening_change_state_|-echo "Listening State"_|-mod_watch'
        self.assertIn(listener_state, state_run)

        # Then, test the result of the state run when a listener should not trigger
        absent_state = 'cmd_|-listener_test_listening_non_changing_state_|-echo "Only run once"_|-mod_watch'
        self.assertNotIn(absent_state, state_run)

    @slowTest
    def test_listen_in_requisite_resolution_names(self):
        """
        Verify listen_in requisite lookups use ID declaration to check for changes
        and resolves magic names state variable
        """

        # Only run the state once and keep the return data
        state_run = self.run_function("state.sls", mods="requisites.listen_in_names")
        self.assertIn("test_|-listener_service_|-nginx_|-mod_watch", state_run)
        self.assertIn("test_|-listener_service_|-crond_|-mod_watch", state_run)

    @slowTest
    def test_listen_requisite_resolution_names(self):
        """
        Verify listen requisite lookups use ID declaration to check for changes
        and resolves magic names state variable
        """

        # Only run the state once and keep the return data
        state_run = self.run_function(
            "state.sls", mods="requisites.listen_names", timeout=self.TIMEOUT
        )
        self.assertIn("test_|-listener_service_|-nginx_|-mod_watch", state_run)
        self.assertIn("test_|-listener_service_|-crond_|-mod_watch", state_run)

    @slowTest
    def test_issue_30820_requisite_in_match_by_name(self):
        """
        This tests the case where a requisite_in matches by name instead of ID

        See https://github.com/saltstack/salt/issues/30820 for more info
        """
        state_run = self.run_function(
            "state.sls", mods="requisites.requisite_in_match_by_name"
        )
        bar_state = "cmd_|-bar state_|-echo bar_|-wait"

        self.assertIn(bar_state, state_run)
        self.assertEqual(state_run[bar_state]["comment"], 'Command "echo bar" run')

    @slowTest
    def test_retry_option_defaults(self):
        """
        test the retry option on a simple state with defaults
        ensure comment is as expected
        ensure state duration is greater than default retry_interval (30 seconds)
        """
        state_run = self.run_function("state.sls", mods="retry.retry_defaults")
        retry_state = "file_|-file_test_|-/path/to/a/non-existent/file.txt_|-exists"
        expected_comment = (
            'Attempt 1: Returned a result of "False", with the following '
            'comment: "Specified path /path/to/a/non-existent/file.txt does not exist"\n'
            "Specified path /path/to/a/non-existent/file.txt does not exist"
        )
        self.assertEqual(state_run[retry_state]["comment"], expected_comment)
        self.assertTrue(state_run[retry_state]["duration"] > 30)
        self.assertEqual(state_run[retry_state]["result"], False)

    @slowTest
    def test_retry_option_custom(self):
        """
        test the retry option on a simple state with custom retry values
        ensure comment is as expected
        ensure state duration is greater than custom defined interval * (retries - 1)
        """
        state_run = self.run_function("state.sls", mods="retry.retry_custom")
        retry_state = "file_|-file_test_|-/path/to/a/non-existent/file.txt_|-exists"
        expected_comment = (
            'Attempt 1: Returned a result of "False", with the following '
            'comment: "Specified path /path/to/a/non-existent/file.txt does not exist"\n'
            'Attempt 2: Returned a result of "False", with the following comment: "Specified'
            ' path /path/to/a/non-existent/file.txt does not exist"\nAttempt 3: Returned'
            ' a result of "False", with the following comment: "Specified path'
            ' /path/to/a/non-existent/file.txt does not exist"\nAttempt 4: Returned a'
            ' result of "False", with the following comment: "Specified path'
            ' /path/to/a/non-existent/file.txt does not exist"\nSpecified path'
            " /path/to/a/non-existent/file.txt does not exist"
        )
        self.assertEqual(state_run[retry_state]["comment"], expected_comment)
        self.assertTrue(state_run[retry_state]["duration"] > 40)
        self.assertEqual(state_run[retry_state]["result"], False)

    @slowTest
    def test_retry_option_success(self):
        """
        test a state with the retry option that should return True immedietly (i.e. no retries)
        """
        testfile = os.path.join(RUNTIME_VARS.TMP, "retry_file_option_success")
        state_run = self.run_function("state.sls", mods="retry.retry_success")
        os.unlink(testfile)
        retry_state = "file_|-file_test_|-{0}_|-exists".format(testfile)
        self.assertNotIn("Attempt", state_run[retry_state]["comment"])

    def run_create(self, testfile):
        """
        helper function to wait 30 seconds and then create the temp retry file
        """
        # Wait for the requisite stae 'file_test_a' to complete before creating
        # test_file
        while True:
            if os.path.exists(testfile + "_a"):
                break
            time.sleep(1)
        time.sleep(30)
        with salt.utils.files.fopen(testfile, "a"):
            pass

    @slowTest
    def test_retry_option_eventual_success(self):
        """
        test a state with the retry option that should return True after at least 4 retry attmempt
        but never run 15 attempts
        """
        testfile = os.path.join(RUNTIME_VARS.TMP, "retry_file_eventual_success")
        assert not os.path.exists(testfile + "_a")
        assert not os.path.exists(testfile)
        create_thread = threading.Thread(target=self.run_create, args=(testfile,))
        create_thread.start()
        state_run = self.run_function("state.sls", mods="retry.retry_success2")
        retry_state = "file_|-file_test_b_|-{0}_|-exists".format(testfile)
        self.assertIn("Attempt 1:", state_run[retry_state]["comment"])
        self.assertIn("Attempt 2:", state_run[retry_state]["comment"])
        self.assertIn("Attempt 3:", state_run[retry_state]["comment"])
        self.assertIn("Attempt 4:", state_run[retry_state]["comment"])
        self.assertNotIn("Attempt 15:", state_run[retry_state]["comment"])
        self.assertEqual(state_run[retry_state]["result"], True)

    @slowTest
    def test_issue_38683_require_order_failhard_combination(self):
        """
        This tests the case where require, order, and failhard are all used together in a state definition.

        Previously, the order option, which used in tandem with require and failhard, would cause the state
        compiler to stacktrace. This exposed a logic error in the ``check_failhard`` function of the state
        compiler. With the logic error resolved, this test should now pass.

        See https://github.com/saltstack/salt/issues/38683 for more information.
        """
        state_run = self.run_function(
            "state.sls", mods="requisites.require_order_failhard_combo"
        )
        state_id = "test_|-b_|-b_|-fail_with_changes"

        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]["comment"], "Failure!")
        self.assertFalse(state_run[state_id]["result"])

    @slowTest
    def test_issue_46762_prereqs_on_a_state_with_unfulfilled_requirements(self):
        """
        This tests the case where state C requires state A, which fails.
        State C is a pre-required state for State B.
        Since state A fails, state C will not run because the requisite failed,
        therefore state B will not run because state C failed to run.

        See https://github.com/saltstack/salt/issues/46762 for
        more information.
        """
        state_run = self.run_function("state.sls", mods="issue-46762")

        state_id = "test_|-a_|-a_|-fail_without_changes"
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]["comment"], "Failure!")
        self.assertFalse(state_run[state_id]["result"])

        state_id = "test_|-b_|-b_|-nop"
        self.assertIn(state_id, state_run)
        self.assertEqual(
            state_run[state_id]["comment"],
            "One or more requisite failed: issue-46762.c",
        )
        self.assertFalse(state_run[state_id]["result"])

        state_id = "test_|-c_|-c_|-nop"
        self.assertIn(state_id, state_run)
        self.assertEqual(
            state_run[state_id]["comment"],
            "One or more requisite failed: issue-46762.a",
        )
        self.assertFalse(state_run[state_id]["result"])

    @slowTest
    def test_state_nonbase_environment(self):
        """
        test state.sls with saltenv using a nonbase environment
        with a salt source
        """
        filename = os.path.join(RUNTIME_VARS.TMP, "nonbase_env")
        try:
            ret = self.run_function("state.sls", mods="non-base-env", saltenv="prod")
            ret = ret[next(iter(ret))]
            assert ret["result"]
            assert ret["comment"] == "File {0} updated".format(filename)
            assert os.path.isfile(filename)
        finally:
            try:
                os.remove(filename)
            except OSError:
                pass

    @skipIf(
        sys.platform.startswith("win"),
        "Skipped until parallel states can be fixed on Windows",
    )
    @skipIf(
        salt.utils.platform.is_darwin() and six.PY2, "This test hangs on OS X on Py2"
    )
    @slowTest
    def test_parallel_state_with_long_tag(self):
        """
        This tests the case where the state being executed has a long ID dec or
        name and states are being run in parallel. The filenames used for the
        parallel state cache were previously based on the tag for each chunk,
        and longer ID decs or name params can cause the cache file to be longer
        than the operating system's max file name length. To counter this we
        instead generate a SHA1 hash of the chunk's tag to use as the cache
        filename. This test will ensure that long tags don't cause caching
        failures.

        See https://github.com/saltstack/salt/issues/49738 for more info.
        """
        short_command = "helloworld"
        long_command = short_command * 25

        ret = self.run_function(
            "state.sls",
            mods="issue-49738",
            pillar={"short_command": short_command, "long_command": long_command},
        )
        comments = sorted([x["comment"] for x in six.itervalues(ret)])
        expected = sorted(
            ['Command "{0}" run'.format(x) for x in (short_command, long_command)]
        )
        assert comments == expected, "{0} != {1}".format(comments, expected)

    def _add_runtime_pillar(self, pillar):
        """
        helper class to add pillar data at runtime
        """
        import salt.utils.yaml

        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "pillar.sls"), "w"
        ) as fp:
            salt.utils.yaml.safe_dump(pillar, fp)

        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"), "w"
        ) as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     base:
                       '*':
                         - pillar
                     """
                )
            )

        self.run_function("saltutil.refresh_pillar")
        self.run_function("test.sleep", [5])

    @slowTest
    def test_state_sls_id_test(self):
        """
        test state.sls_id when test is set
        to true in pillar data
        """
        self._add_runtime_pillar(pillar={"test": True})
        testfile = os.path.join(RUNTIME_VARS.TMP, "testfile")
        comment = "The file {0} is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.".format(
            testfile
        )
        ret = self.run_function("state.sls", ["core"])

        for key, val in ret.items():
            self.assertEqual(val["comment"], comment)
            self.assertEqual(val["changes"], {"newfile": testfile})

    @slowTest
    def test_state_sls_id_test_state_test_post_run(self):
        """
        test state.sls_id when test is set to
        true post the state already being run previously
        """
        file_name = os.path.join(RUNTIME_VARS.TMP, "testfile")
        ret = self.run_function("state.sls", ["core"])
        for key, val in ret.items():
            self.assertEqual(val["comment"], "File {0} updated".format(file_name))
            self.assertEqual(val["changes"]["diff"], "New file")

        self._add_runtime_pillar(pillar={"test": True})
        ret = self.run_function("state.sls", ["core"])

        for key, val in ret.items():
            self.assertEqual(
                val["comment"], "The file {0} is in the correct state".format(file_name)
            )
            self.assertEqual(val["changes"], {})

    @slowTest
    def test_state_sls_id_test_true(self):
        """
        test state.sls_id when test=True is passed as arg
        """
        file_name = os.path.join(RUNTIME_VARS.TMP, "testfile")
        ret = self.run_function("state.sls", ["core"], test=True)
        for key, val in ret.items():
            self.assertEqual(
                val["comment"],
                "The file {0} is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.".format(
                    file_name
                ),
            )
            self.assertEqual(val["changes"], {"newfile": file_name})

    @slowTest
    def test_state_sls_id_test_true_post_run(self):
        """
        test state.sls_id when test is set to true as an
        arg post the state already being run previously
        """
        file_name = os.path.join(RUNTIME_VARS.TMP, "testfile")
        ret = self.run_function("state.sls", ["core"])
        for key, val in ret.items():
            self.assertEqual(val["comment"], "File {0} updated".format(file_name))
            self.assertEqual(val["changes"]["diff"], "New file")

        ret = self.run_function("state.sls", ["core"], test=True)

        for key, val in ret.items():
            self.assertEqual(
                val["comment"], "The file {0} is in the correct state".format(file_name)
            )
            self.assertEqual(val["changes"], {})

    @slowTest
    def test_state_sls_id_test_false_pillar_true(self):
        """
        test state.sls_id when test is set to false as an
        arg and minion_state_test is set to True. Should
        return test=False.
        """
        file_name = os.path.join(RUNTIME_VARS.TMP, "testfile")
        self._add_runtime_pillar(pillar={"test": True})
        ret = self.run_function("state.sls", ["core"], test=False)

        for key, val in ret.items():
            self.assertEqual(val["comment"], "File {0} updated".format(file_name))
            self.assertEqual(val["changes"]["diff"], "New file")

    def test_state_test_pillar_false(self):
        """
        test state.test forces test kwarg to True even when pillar is set to False
        """
        self._add_runtime_pillar(pillar={"test": False})
        testfile = os.path.join(RUNTIME_VARS.TMP, "testfile")
        comment = "The file {0} is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.".format(
            testfile
        )
        ret = self.run_function("state.test", ["core"])
        self.assertIsInstance(ret, dict)

        for key, val in ret.items():
            self.assertEqual(val["comment"], comment)
            self.assertEqual(val["changes"], {"newfile": testfile})

    def test_state_test_test_false_pillar_false(self):
        """
        test state.test forces test kwarg to True even when pillar and kwarg are set
        to False
        """
        self._add_runtime_pillar(pillar={"test": False})
        testfile = os.path.join(RUNTIME_VARS.TMP, "testfile")
        comment = "The file {0} is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.".format(
            testfile
        )
        ret = self.run_function("state.test", ["core"], test=False)

        for key, val in ret.items():
            self.assertEqual(val["comment"], comment)
            self.assertEqual(val["changes"], {"newfile": testfile})

    @skipIf(
        six.PY3 and salt.utils.platform.is_darwin(), "Test is broken on macosx and PY3"
    )
    @slowTest
    def test_issue_30161_unless_and_onlyif_together(self):
        """
        test cmd.run using multiple unless options where the first cmd in the
        list will pass, but the second will fail. This tests the fix for issue
        #35384. (The fix is in PR #35545.)
        """
        sls = self.run_function("state.sls", mods="issue-30161")
        self.assertSaltTrueReturn(sls)
        # We must assert against the comment here to make sure the comment reads that the
        # command "echo "hello"" was run. This ensures that we made it to the last unless
        # command in the state. If the comment reads "unless condition is true", or similar,
        # then the unless state run bailed out after the first unless command succeeded,
        # which is the bug we're regression testing for.
        _expected = {
            "file_|-unless_false_onlyif_false_|-{0}{1}test.txt_|-managed".format(
                RUNTIME_VARS.TMP, os.path.sep
            ): {
                "comment": "onlyif condition is false\nunless condition is false",
                "name": "{0}{1}test.txt".format(RUNTIME_VARS.TMP, os.path.sep),
                "skip_watch": True,
                "changes": {},
                "result": True,
            },
            "file_|-unless_false_onlyif_true_|-{0}{1}test.txt_|-managed".format(
                RUNTIME_VARS.TMP, os.path.sep
            ): {
                "comment": "Empty file",
                "pchanges": {},
                "name": "{0}{1}test.txt".format(RUNTIME_VARS.TMP, os.path.sep),
                "start_time": "18:10:20.341753",
                "result": True,
                "changes": {
                    "new": "file {0}{1}test.txt created".format(
                        RUNTIME_VARS.TMP, os.path.sep
                    )
                },
            },
            "file_|-unless_true_onlyif_false_|-{0}{1}test.txt_|-managed".format(
                RUNTIME_VARS.TMP, os.path.sep
            ): {
                "comment": "onlyif condition is false\nunless condition is true",
                "name": "{0}{1}test.txt".format(RUNTIME_VARS.TMP, os.path.sep),
                "start_time": "18:10:22.936446",
                "skip_watch": True,
                "changes": {},
                "result": True,
            },
            "file_|-unless_true_onlyif_true_|-{0}{1}test.txt_|-managed".format(
                RUNTIME_VARS.TMP, os.path.sep
            ): {
                "comment": "onlyif condition is true\nunless condition is true",
                "name": "{0}{1}test.txt".format(RUNTIME_VARS.TMP, os.path.sep),
                "skip_watch": True,
                "changes": {},
                "result": True,
            },
        }
        for id in _expected:
            self.assertEqual(sls[id]["comment"], _expected[id]["comment"])

    @skipIf(
        six.PY3 and salt.utils.platform.is_darwin(), "Test is broken on macosx and PY3"
    )
    @slowTest
    def test_state_sls_unicode_characters(self):
        """
        test state.sls when state file contains non-ascii characters
        """
        ret = self.run_function("state.sls", ["issue-46672"])
        log.debug("== ret %s ==", type(ret))

        _expected = "cmd_|-echo1_|-echo 'This is Æ test!'_|-run"
        self.assertIn(_expected, ret)

    @skipIf(
        six.PY3 and salt.utils.platform.is_darwin(), "Test is broken on macosx and PY3"
    )
    @slowTest
    def test_state_sls_unicode_characters_cmd_output(self):
        """
        test the output from running and echo command with non-ascii
        characters.
        """
        ret = self.run_function("state.sls", ["issue-46672-a"], timeout=60)
        key = list(ret.keys())[0]
        log.debug("== ret %s ==", type(ret))
        _expected = "This is Æ test!"
        if salt.utils.platform.is_windows():
            # Windows cmd.exe will mangle the output using cmd's codepage.
            if six.PY2:
                _expected = "'This is A+ test!'"
            else:
                _expected = "'This is ’ test!'"
        self.assertEqual(_expected, ret[key]["changes"]["stdout"])

    def tearDown(self):
        rm_files = [
            os.path.join(RUNTIME_VARS.TMP, "nonbase_env"),
            os.path.join(RUNTIME_VARS.TMP, "testfile"),
            os.path.join(RUNTIME_VARS.TMP, "test.txt"),
            os.path.join(RUNTIME_VARS.TMP_STATE_TREE, "top.sls"),
        ]

        for file_ in rm_files:
            if os.path.isfile(file_):
                os.remove(file_)

        # remove old pillar data
        for filename in os.listdir(RUNTIME_VARS.TMP_PILLAR_TREE):
            os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, filename))
        self.run_function("saltutil.refresh_pillar")
        self.run_function("test.sleep", [5])

    @slowTest
    def test_state_sls_integer_name(self):
        """
        This tests the case where the state file is named
        only with integers
        """
        state_run = self.run_function("state.sls", mods="12345")

        state_id = "test_|-always-passes_|-always-passes_|-succeed_without_changes"
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]["comment"], "Success!")
        self.assertTrue(state_run[state_id]["result"])

    @slowTest
    def test_state_sls_lazyloader_allows_recursion(self):
        """
        This tests that referencing dunders like __salt__ work
        context: https://github.com/saltstack/salt/pull/51499
        """
        state_run = self.run_function("state.sls", mods="issue-51499")

        state_id = "test_|-always-passes_|-foo_|-succeed_without_changes"
        self.assertIn(state_id, state_run)
        self.assertEqual(state_run[state_id]["comment"], "Success!")
        self.assertTrue(state_run[state_id]["result"])

    @slowTest
    def test_issue_56131(self):
        module_path = os.path.join(RUNTIME_VARS.CODE_DIR, "pip.py")
        if six.PY3:
            modulec_path = os.path.join(RUNTIME_VARS.CODE_DIR, "__pycache__", "pip.pyc")
        else:
            modulec_path = os.path.join(RUNTIME_VARS.CODE_DIR, "pip.pyc")
        unzip_path = os.path.join(RUNTIME_VARS.TMP, "issue-56131.txt")

        def clean_paths(paths):
            for path in paths:
                try:
                    os.remove(path)
                except OSError:
                    log.warn("Path not found: %s", path)

        with salt.utils.files.fopen(module_path, "w") as fp:
            fp.write('raise ImportError("No module named pip")')
        self.addCleanup(clean_paths, [unzip_path, module_path, modulec_path])
        assert not os.path.exists(unzip_path)
        state_run = self.run_function(
            "state.sls",
            mods="issue-56131",
            pillar={"unzip_to": RUNTIME_VARS.TMP},
            timeout=30,
        )
        assert state_run is not False
        assert os.path.exists(unzip_path)

    @slowTest
    def test_jinja_renderer_argline(self):
        """
        This is a test case for https://github.com/saltstack/salt/issues/55124

        Renderer for this is in tests/integration/files/file/base/_renderers/issue55124.py
        """
        result = self.run_function("state.sls", mods="issue-55124")
        assert isinstance(result, dict), result
        result = result[next(iter(result))]
        assert result["result"], result
