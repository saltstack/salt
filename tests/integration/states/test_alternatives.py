"""
Integration tests for the alternatives state module
"""

import os

import pytest
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

NO_ALTERNATIVES = False
if not os.path.exists("/etc/alternatives"):
    NO_ALTERNATIVES = True


@skipIf(NO_ALTERNATIVES, "/etc/alternatives does not exist on the system")
class AlterantivesStateTest(ModuleCase, SaltReturnAssertsMixin):
    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_install_set_and_remove(self):
        ret = self.run_state(
            "alternatives.set", name="alt-test", path=RUNTIME_VARS.SHELL_TRUE_PATH
        )
        self.assertSaltFalseReturn(ret)

        ret = self.run_state(
            "alternatives.install",
            name="alt-test",
            link="/usr/local/bin/alt-test",
            path=RUNTIME_VARS.SHELL_TRUE_PATH,
            priority=50,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret, RUNTIME_VARS.SHELL_TRUE_PATH, keys=["path"]
        )

        ret = self.run_state(
            "alternatives.install",
            name="alt-test",
            link="/usr/local/bin/alt-test",
            path=RUNTIME_VARS.SHELL_TRUE_PATH,
            priority=50,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state(
            "alternatives.install",
            name="alt-test",
            link="/usr/local/bin/alt-test",
            path=RUNTIME_VARS.SHELL_FALSE_PATH,
            priority=90,
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret, RUNTIME_VARS.SHELL_FALSE_PATH, keys=["path"]
        )

        ret = self.run_state(
            "alternatives.set", name="alt-test", path=RUNTIME_VARS.SHELL_FALSE_PATH
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state(
            "alternatives.set", name="alt-test", path=RUNTIME_VARS.SHELL_TRUE_PATH
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(
            ret, RUNTIME_VARS.SHELL_TRUE_PATH, keys=["path"]
        )

        ret = self.run_state(
            "alternatives.set", name="alt-test", path=RUNTIME_VARS.SHELL_TRUE_PATH
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state(
            "alternatives.remove", name="alt-test", path=RUNTIME_VARS.SHELL_TRUE_PATH
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_state(
            "alternatives.remove", name="alt-test", path=RUNTIME_VARS.SHELL_FALSE_PATH
        )
        self.assertSaltTrueReturn(ret)
