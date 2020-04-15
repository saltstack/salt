# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.states.virtualenv
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil

# Import Salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, skip_if_not_root
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
class VirtualenvTest(ModuleCase, SaltReturnAssertsMixin):
    @skipIf(salt.utils.platform.is_darwin(), "Test is flaky on macosx")
    @destructiveTest
    @skip_if_not_root
    def test_issue_1959_virtualenv_runas(self):
        user = "issue-1959"
        self.assertSaltTrueReturn(self.run_state("user.present", name=user))

        uinfo = self.run_function("user.info", [user])

        if salt.utils.platform.is_darwin():
            # MacOS does not support createhome with user.present
            self.assertSaltTrueReturn(
                self.run_state(
                    "file.directory",
                    name=uinfo["home"],
                    user=user,
                    group=uinfo["groups"][0],
                    dir_mode=755,
                )
            )

        venv_dir = os.path.join(RUNTIME_VARS.SYS_TMP_DIR, "issue-1959-virtualenv-runas")
        try:
            ret = self.run_function("state.sls", mods="issue-1959-virtualenv-runas")
            self.assertSaltTrueReturn(ret)

            # Lets check proper ownership
            statinfo = self.run_function("file.stats", [venv_dir])
            self.assertEqual(statinfo["user"], uinfo["name"])
            self.assertEqual(statinfo["uid"], uinfo["uid"])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)
            self.assertSaltTrueReturn(
                self.run_state("user.absent", name=user, purge=True)
            )

    @skipIf(salt.utils.platform.is_darwin(), "Test is flaky on macosx")
    def test_issue_2594_non_invalidated_cache(self):
        # Testing virtualenv directory
        venv_path = os.path.join(RUNTIME_VARS.TMP, "issue-2594-ve")
        if os.path.exists(venv_path):
            shutil.rmtree(venv_path)
        # Our virtualenv requirements file
        requirements_file_path = os.path.join(
            RUNTIME_VARS.TMP_STATE_TREE, "issue-2594-requirements.txt"
        )
        if os.path.exists(requirements_file_path):
            os.unlink(requirements_file_path)

        # Our state template
        template = [
            "{0}:".format(venv_path),
            "  virtualenv.managed:",
            "    - system_site_packages: False",
            "    - clear: false",
            "    - requirements: salt://issue-2594-requirements.txt",
        ]

        reqs = ["pep8==1.3.3", "zope.interface==4.7.1"]
        # Let's populate the requirements file, just pep-8 for now
        with salt.utils.files.fopen(requirements_file_path, "a") as fhw:
            fhw.write(reqs[0] + "\n")

        # Let's run our state!!!
        try:
            ret = self.run_function("state.template_str", ["\n".join(template)])

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment("Created new virtualenv", ret)
            self.assertSaltStateChangesEqual(ret, [reqs[0]], keys=("packages", "new"))
        except AssertionError:
            # Always clean up the tests temp files
            if os.path.exists(venv_path):
                shutil.rmtree(venv_path)
            if os.path.exists(requirements_file_path):
                os.unlink(requirements_file_path)
            raise

        # Let's make sure, it really got installed
        ret = self.run_function("pip.freeze", bin_env=venv_path)
        self.assertIn(reqs[0], ret)
        self.assertNotIn(reqs[1], ret)

        # Now let's update the requirements file, which is now cached.
        with salt.utils.files.fopen(requirements_file_path, "w") as fhw:
            fhw.write(reqs[1] + "\n")

        # Let's run our state!!!
        try:
            ret = self.run_function("state.template_str", ["\n".join(template)])

            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment("virtualenv exists", ret)
            self.assertSaltStateChangesEqual(ret, [reqs[1]], keys=("packages", "new"))
        except AssertionError:
            # Always clean up the tests temp files
            if os.path.exists(venv_path):
                shutil.rmtree(venv_path)
            if os.path.exists(requirements_file_path):
                os.unlink(requirements_file_path)
            raise

        # Let's make sure, it really got installed
        ret = self.run_function("pip.freeze", bin_env=venv_path)
        self.assertIn(reqs[0], ret)
        self.assertIn(reqs[1], ret)

        # If we reached this point no assertion failed, so, cleanup!
        if os.path.exists(venv_path):
            shutil.rmtree(venv_path)
        if os.path.exists(requirements_file_path):
            os.unlink(requirements_file_path)
