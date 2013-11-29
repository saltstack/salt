# -*- coding: utf-8 -*-

'''
Test the buildout module
'''
# Import Salt Testing libs
import shutil
import os
import tempfile
from distutils.dir_util import copy_tree

from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
import integration
from salt.modules import zcbuildout as buildout
from salt.modules import cmdmod as cmd

ROOT = os.path.join(os.path.dirname(integration.__file__),
                    'files/file/base/buildout')

buildout.__salt__ = {'cmd': cmd}

@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.which', lambda exe: exe)
class Base(integration.ModuleCase):

    def setUp(self):
        super(Base, self).setUp()
        self.tdir = tempfile.mkdtemp()
        copy_tree(ROOT, self.tdir)

    def tearDown(self):
        super(Base, self).tearDown()
        if os.path.isdir(self.tdir):
            shutil.rmtree(self.tdir)


class BuildoutModuleTest(Base):
    '''
    Test the buildout module
    '''

    def test_buildout_bootstrap(self):
        b_dir = os.path.join(self.tdir, 'b')
        ret = self.run_function(
            'buildout.bootstrap', [],
            b_dir, distribute=True, buildout_ver=1)
        import pdb;pdb.set_trace()  ## Breakpoint ##


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BuildoutModuleTest)
