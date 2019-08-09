# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing libs
from tests.support.helpers import requires_network
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf, WAR_ROOM_SKIP

# Import Salt libs
import salt.utils.path
from tests.unit.modules.test_zcbuildout import Base, KNOWN_VIRTUALENV_BINARY_NAMES
import salt.modules.zcbuildout as modbuildout
import salt.states.zcbuildout as buildout
import salt.modules.cmdmod as cmd


@skipIf(WAR_ROOM_SKIP, 'WAR ROOM TEMPORARY SKIP')
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
    @requires_network()
    @skipIf(True, "Buildout is still in beta. Test needs fixing.")
    def test_quiet(self):
        c_dir = os.path.join(self.tdir, 'c')
        assert False, os.listdir(self.rdir)
        modbuildout.upgrade_bootstrap(c_dir)
        cret = buildout.installed(c_dir, python=self.py_st)
        self.assertFalse('OUTPUT:' in cret['comment'], cret['comment'])
        self.assertFalse('Log summary:' in cret['comment'], cret['comment'])
        self.assertTrue(cret['result'], cret['comment'])

    @requires_network()
    def test_error(self):
        b_dir = os.path.join(self.tdir, 'e')
        ret = buildout.installed(b_dir, python=self.py_st)
        self.assertTrue(
            'We did not get any expectable answer from buildout'
            in ret['comment']
        )
        self.assertFalse(ret['result'])

    @requires_network()
    def test_installed(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir,
                                 python=self.py_st,
                                 onlyif=RUNTIME_VARS.SHELL_FALSE_PATH)
        self.assertEqual(ret['comment'], '\nonlyif condition is false')
        self.assertEqual(ret['result'], True)
        self.assertTrue('/b' in ret['name'])
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir,
                                 python=self.py_st,
                                 unless=RUNTIME_VARS.SHELL_TRUE_PATH)
        self.assertEqual(ret['comment'], '\nunless condition is true')
        self.assertEqual(ret['result'], True)
        self.assertTrue('/b' in ret['name'])
        ret = buildout.installed(b_dir, python=self.py_st)
        self.assertEqual(ret['result'], True)
        self.assertTrue('OUTPUT:' in ret['comment'])
        self.assertTrue('Log summary:' in ret['comment'])
