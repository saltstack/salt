# -*- coding: utf-8 -*-
import os
import tempfile
import textwrap

from distutils.dir_util import copy_tree

# Import third party libs
import yaml

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import (
    ensure_in_syspath,
    requires_network,
)
from salttesting.mock import MagicMock

ensure_in_syspath('../../')
import integration
import shutil

# Import Salt libs
from unit.modules.zcbuildout_test import Base
from salt.modules import zcbuildout as modbuildout
from salt.states import zcbuildout as buildout
from salt.modules import cmdmod as cmd
from salt.exceptions import CommandExecutionError, SaltInvocationError

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


class BuildoutTestCase(Base):

    @requires_network()
    def test_quiet(self):
        c_dir = os.path.join(self.tdir, 'c')
        cret = buildout.installed(c_dir, quiet=True)
        self.assertTrue(cret['result'])
        self.assertFalse('OUTPUT:' in cret['comment'])
        self.assertFalse('Log summary:' in cret['comment'])

    @requires_network()
    def test_error(self):
        b_dir = os.path.join(self.tdir, 'e')
        ret = buildout.installed(b_dir)
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
        ret = buildout.installed(b_dir, onlyif='/bin/false')
        self.assertEqual(ret['comment'], '\nonlyif execution failed')
        self.assertEqual(ret['result'], True)
        self.assertTrue('/b' in ret['name'])
        b_dir = os.path.join(self.tdir, 'b')
        ret = buildout.installed(b_dir, unless='/bin/true')
        self.assertEqual(ret['comment'], '\nunless execution succeeded')
        self.assertEqual(ret['result'], True)
        self.assertTrue('/b' in ret['name'])
        ret = buildout.installed(b_dir)
        self.assertEqual(ret['result'], True)
        self.assertTrue('OUTPUT:' in ret['comment'])
        self.assertTrue('Log summary:' in ret['comment'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BuildoutTestCase, needs_daemon=False)
