# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.unit import skipIf
from tests.support.helpers import requires_network
import tests.integration as integration

# Import Salt libs
import salt.utils
from tests.unit.modules.test_zcbuildout import Base, KNOWN_VIRTUALENV_BINARY_NAMES
from salt.modules import zcbuildout as modbuildout
from salt.states import zcbuildout as buildout
from salt.modules import cmdmod as cmd

ROOT = os.path.join(os.path.dirname(integration.__file__),
                    'files/file/base/buildout')


modbuildout.__env__ = 'base'
modbuildout.__opts__ = {'test': False}
modbuildout.__salt__ = {
    'cmd.run_all': cmd.run_all,
    'cmd.run': cmd.run,
    'cmd.retcode': cmd.retcode,
    'buildout.buildout': modbuildout.buildout,
}
buildout.__env__ = 'base'
buildout.__opts__ = {'test': False}
buildout.__salt__ = {
    'cmd.run_all': cmd.run_all,
    'cmd.run': cmd.run,
    'cmd.retcode': cmd.retcode,
    'buildout.buildout': modbuildout.buildout,
}


@skipIf(salt.utils.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES) is None,
        'The \'virtualenv\' packaged needs to be installed')
class BuildoutTestCase(Base):

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
