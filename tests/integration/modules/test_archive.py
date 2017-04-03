# -*- coding: utf-8 -*-
'''
Tests for the archive state
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.paths import TMP
from tests.support.helpers import destructiveTest

# Import salt libs
import salt.utils

# Import 3rd party libs
try:
    import zipfile  # pylint: disable=W0611
    HAS_ZIPFILE = True
except ImportError:
    HAS_ZIPFILE = False


@destructiveTest
class ArchiveTest(ModuleCase):
    '''
    Validate the archive module
    '''
    # Base path used for test artifacts
    base_path = os.path.join(TMP, 'modules', 'archive')

    def _set_artifact_paths(self, arch_fmt):
        '''
        Define the paths for the source, archive, and destination files

        :param str arch_fmt: The archive format used in the test
        '''
        self.src = os.path.join(self.base_path, '{0}_src_dir'.format(arch_fmt))
        self.src_file = os.path.join(self.src, 'file')
        self.arch = os.path.join(self.base_path, 'archive.{0}'.format(arch_fmt))
        self.dst = os.path.join(self.base_path, '{0}_dst_dir'.format(arch_fmt))

    def _set_up(self, arch_fmt):
        '''
        Create source file tree and destination directory

        :param str arch_fmt: The archive format used in the test
        '''
        # Setup artifact paths
        self._set_artifact_paths(arch_fmt)

        # Remove the artifacts if any present
        if any([os.path.exists(f) for f in (self.src, self.arch, self.dst)]):
            self._tear_down()

        # Create source
        os.makedirs(self.src)
        with salt.utils.fopen(os.path.join(self.src, 'file'), 'w') as theorem:
            theorem.write(textwrap.dedent(r'''\
                Compression theorem of computational complexity theory:

                Given a Gödel numbering $φ$ of the computable functions and a
                Blum complexity measure $Φ$ where a complexity class for a
                boundary function $f$ is defined as
                
                    $\mathrm C(f) := \{φ_i ∈ \mathbb R^{(1)} | (∀^∞ x) Φ_i(x) ≤ f(x)\}$.
                
                Then there exists a total computable function $f$ so that for
                all $i$
                
                    $\mathrm{Dom}(φ_i) = \mathrm{Dom}(φ_{f(i)})$
                
                and
                
                    $\mathrm C(φ_i) ⊊ \mathrm{C}(φ_{f(i)})$.
            '''))

        # Create destination
        os.makedirs(self.dst)

    def _tear_down(self):
        '''
        Remove source file tree, archive, and destination file tree
        '''
        for f in (self.src, self.arch, self.dst):
            if os.path.exists(f):
                if os.path.isdir(f):
                    shutil.rmtree(f, ignore_errors=True)
                else:
                    os.remove(f)
        del self.dst
        del self.src
        del self.arch
        del self.src_file

    def _assert_artifacts_in_ret(self, ret, file_only=False):
        '''
        Assert that the artifact source files are printed in the source command
        output
        '''
        # Try to find source directory and file in output lines
        dir_in_ret = None
        file_in_ret = None
        for line in ret:
            if self.src.lstrip('/') in line \
            and not self.src_file.lstrip('/') in line:
                dir_in_ret = True
            if self.src_file.lstrip('/') in line:
                file_in_ret = True

        # Assert number of lines, reporting of source directory and file
        self.assertTrue(len(ret) >= 1 if file_only else 2)
        if not file_only:
            self.assertTrue(dir_in_ret)
        self.assertTrue(file_in_ret)

    @skipIf(not salt.utils.which('tar'), 'Cannot find tar executable')
    def test_tar_pack(self):
        '''
        Validate using the tar function to create archives
        '''
        self._set_up(arch_fmt='tar')

        # Test create archive
        ret = self.run_function('archive.tar', ['-cvf', self.arch], sources=self.src)
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not salt.utils.which('tar'), 'Cannot find tar executable')
    def test_tar_unpack(self):
        '''
        Validate using the tar function to extract archives
        '''
        self._set_up(arch_fmt='tar')
        self.run_function('archive.tar', ['-cvf', self.arch], sources=self.src)

        # Test extract archive
        ret = self.run_function('archive.tar', ['-xvf', self.arch], dest=self.dst)
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not salt.utils.which('gzip'), 'Cannot find gzip executable')
    def test_gzip(self):
        '''
        Validate using the gzip function
        '''
        self._set_up(arch_fmt='gz')

        # Test create archive
        ret = self.run_function('archive.gzip', [self.src_file], options='-v')
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret, file_only=True)

        self._tear_down()

    @skipIf(not salt.utils.which('gzip'), 'Cannot find gzip executable')
    @skipIf(not salt.utils.which('gunzip'), 'Cannot find gunzip executable')
    def test_gunzip(self):
        '''
        Validate using the gunzip function
        '''
        self._set_up(arch_fmt='gz')
        self.run_function('archive.gzip', [self.src_file], options='-v')

        # Test extract archive
        ret = self.run_function('archive.gunzip', [self.src_file + '.gz'], options='-v')
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret, file_only=True)

        self._tear_down()

    @skipIf(not salt.utils.which('zip'), 'Cannot find zip executable')
    def test_cmd_zip(self):
        '''
        Validate using the cmd_zip function
        '''
        self._set_up(arch_fmt='zip')

        # Test create archive
        ret = self.run_function('archive.cmd_zip', [self.arch, self.src])
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not salt.utils.which('zip'), 'Cannot find zip executable')
    @skipIf(not salt.utils.which('unzip'), 'Cannot find unzip executable')
    def test_cmd_unzip(self):
        '''
        Validate using the cmd_unzip function
        '''
        self._set_up(arch_fmt='zip')
        self.run_function('archive.cmd_zip', [self.arch, self.src])

        # Test create archive
        ret = self.run_function('archive.cmd_unzip', [self.arch, self.dst])
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not HAS_ZIPFILE, 'Cannot find zipfile python module')
    def test_zip(self):
        '''
        Validate using the zip function
        '''
        self._set_up(arch_fmt='zip')

        # Test create archive
        ret = self.run_function('archive.zip', [self.arch, self.src])
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not HAS_ZIPFILE, 'Cannot find zipfile python module')
    def test_unzip(self):
        '''
        Validate using the unzip function
        '''
        self._set_up(arch_fmt='zip')
        self.run_function('archive.zip', [self.arch, self.src])

        # Test create archive
        ret = self.run_function('archive.unzip', [self.arch, self.dst])
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not salt.utils.which('rar'), 'Cannot find rar executable')
    def test_rar(self):
        '''
        Validate using the rar function
        '''
        self._set_up(arch_fmt='rar')

        # Test create archive
        ret = self.run_function('archive.rar', [self.arch, self.src])
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()

    @skipIf(not salt.utils.which('rar'), 'Cannot find rar executable')
    @skipIf(not salt.utils.which('unrar'), 'Cannot find unrar executable')
    def test_unrar(self):
        '''
        Validate using the unrar function
        '''
        self._set_up(arch_fmt='rar')
        self.run_function('archive.rar', [self.arch, self.src])

        # Test create archive
        ret = self.run_function('archive.unrar', [self.arch, self.dst])
        self.assertTrue(isinstance(ret, list), str(ret))
        self._assert_artifacts_in_ret(ret)

        self._tear_down()
