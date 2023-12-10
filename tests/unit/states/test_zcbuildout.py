import os

import pytest

import salt.modules.cmdmod as cmd
import salt.modules.virtualenv_mod
import salt.modules.zcbuildout as modbuildout
import salt.states.zcbuildout as buildout
import salt.utils.path
from tests.support.runtests import RUNTIME_VARS
from tests.unit.modules.test_zcbuildout import KNOWN_VIRTUALENV_BINARY_NAMES, Base

pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
    pytest.mark.skip_on_windows(
        reason=(
            "Special steps are required for proper SSL validation because "
            "`easy_install` is too old(and deprecated)."
        )
    ),
]


@pytest.mark.skip_if_binaries_missing(*KNOWN_VIRTUALENV_BINARY_NAMES, check_all=False)
@pytest.mark.requires_network
class BuildoutTestCase(Base):
    def setup_loader_modules(self):
        module_globals = {
            "__env__": "base",
            "__opts__": {"test": False},
            "__salt__": {
                "cmd.run_all": cmd.run_all,
                "cmd.run": cmd.run,
                "cmd.retcode": cmd.retcode,
                "buildout.buildout": modbuildout.buildout,
            },
        }
        return {buildout: module_globals, modbuildout: module_globals}

    # I don't have the time to invest in learning more about buildout,
    # and given we don't have support yet, and there are other priorities
    # I'm going to punt on this for now - WW
    @pytest.mark.skip(reason="Buildout is still in beta. Test needs fixing.")
    def test_quiet(self):
        c_dir = os.path.join(self.tdir, "c")
        assert False, os.listdir(self.rdir)
        modbuildout.upgrade_bootstrap(c_dir)
        cret = buildout.installed(c_dir, python=self.py_st)
        self.assertFalse("OUTPUT:" in cret["comment"], cret["comment"])
        self.assertFalse("Log summary:" in cret["comment"], cret["comment"])
        self.assertTrue(cret["result"], cret["comment"])

    @pytest.mark.slow_test
    def test_error(self):
        b_dir = os.path.join(self.tdir, "e")
        ret = buildout.installed(b_dir, python=self.py_st)
        self.assertTrue("Unexpected response from buildout" in ret["comment"])
        self.assertFalse(ret["result"])

    @pytest.mark.slow_test
    def test_installed(self):
        if salt.modules.virtualenv_mod.virtualenv_ver(self.ppy_st) >= (20, 0, 0):
            self.skipTest(
                "Skiping until upstream resolved"
                " https://github.com/pypa/virtualenv/issues/1715"
            )
        b_dir = os.path.join(self.tdir, "b")
        ret = buildout.installed(
            b_dir, python=self.py_st, onlyif=RUNTIME_VARS.SHELL_FALSE_PATH
        )
        self.assertEqual(ret["comment"], "\nonlyif condition is false")
        self.assertEqual(ret["result"], True)
        self.assertTrue(os.sep + "b" in ret["name"])
        b_dir = os.path.join(self.tdir, "b")
        ret = buildout.installed(
            b_dir, python=self.py_st, unless=RUNTIME_VARS.SHELL_TRUE_PATH
        )
        self.assertEqual(ret["comment"], "\nunless condition is true")
        self.assertEqual(ret["result"], True)
        self.assertTrue(os.sep + "b" in ret["name"])
        ret = buildout.installed(b_dir, python=self.py_st)
        self.assertEqual(ret["result"], True)
        self.assertTrue("OUTPUT:" in ret["comment"])
        self.assertTrue("Log summary:" in ret["comment"])
