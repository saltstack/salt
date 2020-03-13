# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

import pytest

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf
from tests.unit.modules.test_zcbuildout import Base, KNOWN_VIRTUALENV_BINARY_NAMES

# Import Salt libs
import salt.utils.path
import salt.modules.zcbuildout as modbuildout
import salt.modules.virtualenv_mod
import salt.states.zcbuildout as buildout
import salt.modules.cmdmod as cmd


@skipIf(salt.utils.path.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES) is None,
        "The 'virtualenv' packaged needs to be installed")
class BuildoutTestCase(Base):

    def setup_loader_modules(self):
        module_globals = {
            '__env__': 'base',
            '__opts__': {'test': False},
            '__salt__': {
                'cmd.run_all': cmd.run_all,
                'cmd.run': cmd.run,
                'cmd.retcode': cmd.retcode,
                'buildout.buildout': modbuildout.buildout,
            }
        }
        return {buildout: module_globals, modbuildout: module_globals}

    # I don't have the time to invest in learning more about buildout,
    # and given we don't have support yet, and there are other priorities
    # I'm going to punt on this for now - WW
    @skipIf(True, "Buildout is still in beta. Test needs fixing.")
    @pytest.mark.requires_network
    def test_quiet(self):
        c_dir = os.path.join(self.tdir, 'c')
        assert False, os.listdir(self.rdir)
        modbuildout.upgrade_bootstrap(c_dir)
        cret = buildout.installed(c_dir, python=self.py_st)
        assert not ('OUTPUT:' in cret['comment']), cret['comment']
        assert not ('Log summary:' in cret['comment']), cret['comment']
        assert cret['result'], cret['comment']

    @pytest.mark.requires_network
    def test_error(self):
        b_dir = os.path.join(self.tdir, 'e')
        ret = buildout.installed(b_dir, python=self.py_st)
        assert 'We did not get any expectable answer from buildout' \
            in ret['comment']
        assert not ret['result']

    @pytest.mark.requires_network
    def test_installed(self):
        if salt.modules.virtualenv_mod.virtualenv_ver(self.ppy_st) >= (20, 0, 0):
            self.skipTest("Skiping until upstream resolved https://github.com/pypa/virtualenv/issues/1715")
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir,
                                 python=self.py_st,
                                 onlyif=RUNTIME_VARS.SHELL_FALSE_PATH)
        assert ret['comment'] == '\nonlyif condition is false'
        assert ret['result'] is True
        assert os.sep + 'b' in ret['name']
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir,
                                 python=self.py_st,
                                 unless=RUNTIME_VARS.SHELL_TRUE_PATH)
        assert ret['comment'] == '\nunless condition is true'
        assert ret['result'] is True
        assert os.sep + 'b' in ret['name']
        ret = buildout.installed(b_dir, python=self.py_st)
        assert ret['result'] is True
        assert 'OUTPUT:' in ret['comment']
        assert 'Log summary:' in ret['comment']
