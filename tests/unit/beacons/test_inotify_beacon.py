# coding: utf-8

# Python libs
from __future__ import absolute_import
import os
import shutil
import tempfile

# Salt libs
from salt.beacons import inotify

# Salt testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import destructiveTest, ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON

# Third-party libs
try:
    import pyinotify  # pylint: disable=unused-import
    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False


ensure_in_syspath('../../')


@skipIf(not HAS_PYINOTIFY, 'pyinotify is not available')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class INotifyBeaconTestCase(TestCase):
    '''
    Test case for salt.beacons.inotify
    '''
    def setUp(self):
        inotify.__context__ = {}

    def test_empty_config(self, *args, **kwargs):
        config = {}
        ret = inotify.beacon(config)
        self.assertEqual(ret, [])

    def test_file_open(self, *args, **kwargs):
        path = os.path.realpath(__file__)
        config = {path: {'mask': ['open']}}
        ret = inotify.beacon(config)
        self.assertEqual(ret, [])

        with open(path, 'r') as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'IN_OPEN')

    @destructiveTest
    def test_dir_no_auto_add(self, *args, **kwargs):
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            config = {tmpdir: {'mask': ['create']}}
            ret = inotify.beacon(config)
            self.assertEqual(ret, [])
            fp = os.path.join(tmpdir, 'tmpfile')
            with open(fp, 'w') as f:
                pass
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 1)
            self.assertEqual(ret[0]['path'], fp)
            self.assertEqual(ret[0]['change'], 'IN_CREATE')
            with open(fp, 'r') as f:
                pass
            ret = inotify.beacon(config)
            self.assertEqual(ret, [])

        finally:
            if tmpdir:
                shutil.rmtree(tmpdir)

    @destructiveTest
    def test_dir_auto_add(self, *args, **kwargs):
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            config = {tmpdir: {'mask': ['create', 'open'], 'auto_add': True}}
            ret = inotify.beacon(config)
            self.assertEqual(ret, [])
            fp = os.path.join(tmpdir, 'tmpfile')
            with open(fp, 'w') as f:
                pass
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 2)
            self.assertEqual(ret[0]['path'], fp)
            self.assertEqual(ret[0]['change'], 'IN_CREATE')
            self.assertEqual(ret[1]['path'], fp)
            self.assertEqual(ret[1]['change'], 'IN_OPEN')
            with open(fp, 'r') as f:
                pass
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 1)
            self.assertEqual(ret[0]['path'], fp)
            self.assertEqual(ret[0]['change'], 'IN_OPEN')

        finally:
            if tmpdir:
                shutil.rmtree(tmpdir)

    @destructiveTest
    def test_dir_recurse(self, *args, **kwargs):
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            dp1 = os.path.join(tmpdir, 'subdir1')
            os.mkdir(dp1)
            dp2 = os.path.join(dp1, 'subdir2')
            os.mkdir(dp2)
            fp = os.path.join(dp2, 'tmpfile')
            with open(fp, 'w') as f:
                pass
            config = {tmpdir: {'mask': ['open'], 'recurse': True}}
            ret = inotify.beacon(config)
            self.assertEqual(ret, [])
            with open(fp) as f:
                pass
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 3)
            self.assertEqual(ret[0]['path'], dp1)
            self.assertEqual(ret[0]['change'], 'IN_OPEN|IN_ISDIR')
            self.assertEqual(ret[1]['path'], dp2)
            self.assertEqual(ret[1]['change'], 'IN_OPEN|IN_ISDIR')
            self.assertEqual(ret[2]['path'], fp)
            self.assertEqual(ret[2]['change'], 'IN_OPEN')

        finally:
            if tmpdir:
                shutil.rmtree(tmpdir)

    @destructiveTest
    def test_dir_recurse_auto_add(self, *args, **kwargs):
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            dp1 = os.path.join(tmpdir, 'subdir1')
            os.mkdir(dp1)
            config = {tmpdir: {'mask': ['create', 'delete'],
                               'recurse': True,
                               'auto_add': True}}
            ret = inotify.beacon(config)
            self.assertEqual(ret, [])
            dp2 = os.path.join(dp1, 'subdir2')
            os.mkdir(dp2)
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 1)
            self.assertEqual(ret[0]['path'], dp2)
            self.assertEqual(ret[0]['change'], 'IN_CREATE|IN_ISDIR')
            fp = os.path.join(dp2, 'tmpfile')
            with open(fp, 'w') as f:
                pass
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 1)
            self.assertEqual(ret[0]['path'], fp)
            self.assertEqual(ret[0]['change'], 'IN_CREATE')
            os.remove(fp)
            ret = inotify.beacon(config)
            self.assertEqual(len(ret), 1)
            self.assertEqual(ret[0]['path'], fp)
            self.assertEqual(ret[0]['change'], 'IN_DELETE')

        finally:
            if tmpdir:
                shutil.rmtree(tmpdir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(INotifyBeaconTestCase, needs_daemon=False)
