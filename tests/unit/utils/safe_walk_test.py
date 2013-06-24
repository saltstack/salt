# Import python libs
import os
from os.path import join
from shutil import rmtree
from tempfile import mkdtemp

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration

import salt.utils
import salt.utils.find

# Import Salt Testing libs
from salttesting import TestCase, skipIf


class TestUtils(TestCase):

    def test_safe_walk_symlink_recursion(self):
        tmp = mkdtemp()
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestUtils, needs_daemon=False)
