# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
from os.path import join
from shutil import rmtree
from tempfile import mkdtemp

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
import tests.integration as integration
import salt.utils
import salt.utils.find


class TestUtils(TestCase):

    def test_safe_walk_symlink_recursion(self):
        tmp = mkdtemp(dir=integration.SYS_TMP_DIR)
        try:
            if os.stat(tmp).st_ino == 0:
                self.skipTest('inodes not supported in {0}'.format(tmp))
            os.mkdir(join(tmp, 'fax'))
            os.makedirs(join(tmp, 'foo/bar'))
            os.symlink('../..', join(tmp, 'foo/bar/baz'))
            os.symlink('foo', join(tmp, 'root'))
            expected = [
                (join(tmp, 'root'), ['bar'], []),
                (join(tmp, 'root/bar'), ['baz'], []),
                (join(tmp, 'root/bar/baz'), ['fax', 'foo', 'root'], []),
                (join(tmp, 'root/bar/baz/fax'), [], []),
            ]
            paths = []
            for root, dirs, names in salt.utils.safe_walk(join(tmp, 'root')):
                paths.append((root, sorted(dirs), names))
            if paths != expected:
                raise AssertionError(
                    '\n'.join(
                        ['got:'] + [repr(p) for p in paths] +
                        ['', 'expected:'] + [repr(p) for p in expected]
                    )
                )
        finally:
            rmtree(tmp)
