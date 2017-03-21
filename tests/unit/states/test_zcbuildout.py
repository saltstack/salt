# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.paths import FILES
from tests.support.unit import skipIf
from tests.support.helpers import requires_network

# Import Salt libs
import salt.utils
from tests.unit.modules.test_zcbuildout import Base, KNOWN_VIRTUALENV_BINARY_NAMES
import salt.modules.zcbuildout as modbuildout
import salt.states.zcbuildout as buildout
import salt.modules.cmdmod as cmd

ROOT = os.path.join(FILES, 'file/base/buildout')


@skipIf(salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES) is None,
        'The \'virtualenv\' packaged needs to be installed')
class BuildoutTestCase(Base):

    loader_module = buildout, modbuildout

    def loader_module_globals(self):
        return {
            '__env__': 'base',
            '__opts__': {'test': False},
            '__salt__': {
                'cmd.run_all': cmd.run_all,
                'cmd.run': cmd.run,
                'cmd.retcode': cmd.retcode,
                'buildout.buildout': modbuildout.buildout,
            }
        }

    @requires_network()
    def test_quiet(self):
        c_dir = os.path.join(self.tdir, 'c')
        cret = buildout.installed(c_dir, python=self.py_st, quiet=True)
        self.assertTrue(cret['result'])
        self.assertFalse('OUTPUT:' in cret['comment'])
        self.assertFalse('Log summary:' in cret['comment'])

    @requires_network()
    def test_error(self):
        b_dir = os.path.join(self.tdir, 'e')
        ret = buildout.installed(b_dir, python=self.py_st)
        self.assertTrue(
            'We did not get any expectable '
            'answer from buildout'
            in ret['comment'])
        self.assertTrue(
            'An internal error occurred due to a bug in'
            ' either zc.buildout '
            in ret['comment'])
        self.assertFalse(ret['result'])

    @requires_network()
    def test_installed(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir,
                                 python=self.py_st,
                                 onlyif='/bin/false')
        self.assertEqual(ret['comment'], '\nonlyif execution failed')
        self.assertEqual(ret['result'], True)
        self.assertTrue('/b' in ret['name'])
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir,
                                 python=self.py_st,
                                 unless='/bin/true')
        self.assertEqual(ret['comment'], '\nunless execution succeeded')
        self.assertEqual(ret['result'], True)
        self.assertTrue('/b' in ret['name'])
        ret = buildout.installed(b_dir, python=self.py_st)
        self.assertEqual(ret['result'], True)
        self.assertTrue('OUTPUT:' in ret['comment'])
        self.assertTrue('Log summary:' in ret['comment'])
