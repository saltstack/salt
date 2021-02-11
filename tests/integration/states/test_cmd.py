"""
Tests for the file state
"""

import errno
import os
import tempfile
import textwrap
import time

import pytest
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS


class CMDTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the cmd state
    """

    @classmethod
    def setUpClass(cls):
        cls.__cmd = "dir" if salt.utils.platform.is_windows() else "ls"

    def test_run_simple(self):
        """
        cmd.run
        """
        ret = self.run_state("cmd.run", name=self.__cmd, cwd=tempfile.gettempdir())
        self.assertSaltTrueReturn(ret)

    def test_run_output_loglevel(self):
        """
        cmd.run with output_loglevel=quiet
        """
        ret = self.run_state(
            "cmd.run",
            name=self.__cmd,
            cwd=tempfile.gettempdir(),
            output_loglevel="quiet",
        )
        self.assertSaltTrueReturn(ret)

    def test_run_simple_test_true(self):
        """
        cmd.run test interface
        """
        ret = self.run_state(
            "cmd.run", name=self.__cmd, cwd=tempfile.gettempdir(), test=True
        )
        self.assertSaltNoneReturn(ret)

    def test_run_hide_output(self):
        """
        cmd.run with output hidden
        """
        ret = self.run_state("cmd.run", name=self.__cmd, hide_output=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        self.assertEqual(ret["changes"]["stdout"], "")
        self.assertEqual(ret["changes"]["stderr"], "")


class CMDRunRedirectTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the cmd state of run_redirect
    """

    def setUp(self):
        self.state_name = "run_redirect"
        state_filename = self.state_name + ".sls"
        self.state_file = os.path.join(RUNTIME_VARS.TMP_STATE_TREE, state_filename)

        # Create the testfile and release the handle
        fd, self.test_file = tempfile.mkstemp()
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise

        # Create the testfile and release the handle
        fd, self.test_tmp_path = tempfile.mkstemp()
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise

        super().setUp()

    def tearDown(self):
        time.sleep(1)
        for path in (self.state_file, self.test_tmp_path, self.test_file):
            try:
                os.remove(path)
            except OSError:
                # Not all of the tests leave files around that we want to remove
                # As some of the tests create the sls files in the test itself,
                # And some are using files in the integration test file state tree.
                pass
        super().tearDown()

    @pytest.mark.slow_test
    def test_run_unless(self):
        """
        test cmd.run unless
        """
        state_key = "cmd_|-{0}_|-{0}_|-run".format(self.test_tmp_path)
        with salt.utils.files.fopen(self.state_file, "w") as fb_:
            fb_.write(
                salt.utils.stringutils.to_str(
                    textwrap.dedent(
                        """
                {}:
                  cmd.run:
                    - unless: echo cheese > {}
                """.format(
                            self.test_tmp_path, self.test_file
                        )
                    )
                )
            )

        ret = self.run_function("state.sls", [self.state_name])
        self.assertTrue(ret[state_key]["result"])

    @pytest.mark.slow_test
    @pytest.mark.windows_whitelisted
    def test_run_unless_multiple_cmds(self):
        """
        test cmd.run using multiple unless options where the first cmd in the
        list will pass, but the second will fail. This tests the fix for issue
        #35384. (The fix is in PR #35545.)
        """
        sls = self.run_function("state.sls", mods="issue-35384")
        self.assertSaltTrueReturn(sls)
        # We must assert against the comment here to make sure the comment reads that the
        # command "echo "hello"" was run. This ensures that we made it to the last unless
        # command in the state. If the comment reads "unless condition is true", or similar,
        # then the unless state run bailed out after the first unless command succeeded,
        # which is the bug we're regression testing for.
        self.assertEqual(
            sls['cmd_|-cmd_run_unless_multiple_|-echo "hello"_|-run']["comment"],
            'Command "echo "hello"" run',
        )

    @pytest.mark.slow_test
    def test_run_creates_exists(self):
        """
        test cmd.run creates already there
        """
        state_key = "cmd_|-echo >> {0}_|-echo >> {0}_|-run".format(self.test_file)
        with salt.utils.files.fopen(self.state_file, "w") as fb_:
            fb_.write(
                salt.utils.stringutils.to_str(
                    textwrap.dedent(
                        """
                echo >> {0}:
                  cmd.run:
                    - creates: {0}
                """.format(
                            self.test_file
                        )
                    )
                )
            )

        ret = self.run_function("state.sls", [self.state_name])
        self.assertTrue(ret[state_key]["result"])
        self.assertEqual(len(ret[state_key]["changes"]), 0)

    @pytest.mark.slow_test
    def test_run_creates_new(self):
        """
        test cmd.run creates not there
        """
        os.remove(self.test_file)
        state_key = "cmd_|-echo >> {0}_|-echo >> {0}_|-run".format(self.test_file)
        with salt.utils.files.fopen(self.state_file, "w") as fb_:
            fb_.write(
                salt.utils.stringutils.to_str(
                    textwrap.dedent(
                        """
                echo >> {0}:
                  cmd.run:
                    - creates: {0}
                """.format(
                            self.test_file
                        )
                    )
                )
            )

        ret = self.run_function("state.sls", [self.state_name])
        self.assertTrue(ret[state_key]["result"])
        self.assertEqual(len(ret[state_key]["changes"]), 4)

    @pytest.mark.slow_test
    def test_run_redirect(self):
        """
        test cmd.run with shell redirect
        """
        state_key = "cmd_|-echo test > {0}_|-echo test > {0}_|-run".format(
            self.test_file
        )
        with salt.utils.files.fopen(self.state_file, "w") as fb_:
            fb_.write(
                salt.utils.stringutils.to_str(
                    textwrap.dedent(
                        """
                echo test > {}:
                  cmd.run
                """.format(
                            self.test_file
                        )
                    )
                )
            )

        ret = self.run_function("state.sls", [self.state_name])
        self.assertTrue(ret[state_key]["result"])


class CMDRunWatchTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the cmd state of run_watch
    """

    def setUp(self):
        self.state_name = "run_watch"
        state_filename = self.state_name + ".sls"
        self.state_file = os.path.join(RUNTIME_VARS.TMP_STATE_TREE, state_filename)
        super().setUp()

    def tearDown(self):
        os.remove(self.state_file)
        super().tearDown()

    def test_run_watch(self):
        """
        test cmd.run watch
        """
        saltines_key = "cmd_|-saltines_|-echo changed=true_|-run"
        biscuits_key = "cmd_|-biscuits_|-echo biscuits_|-wait"

        with salt.utils.files.fopen(self.state_file, "w") as fb_:
            fb_.write(
                salt.utils.stringutils.to_str(
                    textwrap.dedent(
                        """
                saltines:
                  cmd.run:
                    - name: echo changed=true
                    - cwd: /
                    - stateful: True

                biscuits:
                  cmd.wait:
                    - name: echo biscuits
                    - cwd: /
                    - watch:
                        - cmd: saltines
                """
                    )
                )
            )

        ret = self.run_function("state.sls", [self.state_name])
        self.assertTrue(ret[saltines_key]["result"])
        self.assertTrue(ret[biscuits_key]["result"])
