# coding: utf-8

# Python libs
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import os
import shutil
import tempfile
import time

# Salt libs
import salt.utils.files
from salt.beacons import watchdog
from salt.ext.six.moves import range

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mixins import LoaderModuleMockMixin


def check_events(config):
    total_delay = 1
    delay_per_loop = 20e-3

    for _ in range(int(total_delay / delay_per_loop)):
        events = watchdog.beacon(config)

        if events:
            return events

        time.sleep(delay_per_loop)

    return []


def create(path, content=None):
    with salt.utils.files.fopen(path, 'w') as f:
        if content:
            f.write(content)
        os.fsync(f)


@skipIf(not watchdog.HAS_WATCHDOG, 'watchdog is not available')
class IWatchdogBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.watchdog
    '''

    def setup_loader_modules(self):
        return {watchdog: {}}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        watchdog.close({})
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def assertValid(self, config):
        ret = watchdog.validate(config)
        self.assertEqual(ret, (True, 'Valid beacon configuration'))

    def test_empty_config(self):
        config = [{}]
        ret = watchdog.beacon(config)
        self.assertEqual(ret, [])

    def test_file_create(self):
        path = os.path.join(self.tmpdir, 'tmpfile')

        config = [{'directories': {self.tmpdir: {'mask': ['create']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        create(path)

        ret = check_events(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'created')

    def test_file_modified(self):
        path = os.path.join(self.tmpdir, 'tmpfile')

        config = [{'directories': {self.tmpdir: {'mask': ['modify']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        create(path, 'some content')

        ret = check_events(config)
        self.assertEqual(len(ret), 2)
        self.assertEqual(ret[0]['path'], os.path.dirname(path))
        self.assertEqual(ret[0]['change'], 'modified')
        self.assertEqual(ret[1]['path'], path)
        self.assertEqual(ret[1]['change'], 'modified')

    def test_file_deleted(self):
        path = os.path.join(self.tmpdir, 'tmpfile')
        create(path)

        config = [{'directories': {self.tmpdir: {'mask': ['delete']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        os.remove(path)

        ret = check_events(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'deleted')

    def test_file_moved(self):
        path = os.path.join(self.tmpdir, 'tmpfile')
        create(path)

        config = [{'directories': {self.tmpdir: {'mask': ['move']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        os.rename(path, path + '_moved')

        ret = check_events(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'moved')

    def test_file_create_in_directory(self):
        config = [{'directories': {self.tmpdir: {'mask': ['create', 'modify']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        path = os.path.join(self.tmpdir, 'tmpfile')
        create(path)

        ret = check_events(config)
        self.assertEqual(len(ret), 2)
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'created')
        self.assertEqual(ret[1]['path'], self.tmpdir)
        self.assertEqual(ret[1]['change'], 'modified')

    def test_trigger_all_possible_events(self):
        path = os.path.join(self.tmpdir, 'tmpfile')
        moved = path + '_moved'

        config = [{'directories': {
            self.tmpdir: {},
        }}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        # create
        create(path)
        # modify
        create(path, 'modified content')
        # move
        os.rename(path, moved)
        # delete
        os.remove(moved)

        ret = check_events(config)

        self.assertEqual(len(ret), 8)

        # create
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'created')
        self.assertEqual(ret[1]['path'], self.tmpdir)
        self.assertEqual(ret[1]['change'], 'modified')

        # modify
        self.assertEqual(ret[2]['path'], path)
        self.assertEqual(ret[2]['change'], 'modified')
        self.assertEqual(ret[3]['path'], path)
        self.assertEqual(ret[3]['change'], 'modified')

        # move
        self.assertEqual(ret[4]['path'], path)
        self.assertEqual(ret[4]['change'], 'moved')
        self.assertEqual(ret[5]['path'], self.tmpdir)
        self.assertEqual(ret[5]['change'], 'modified')

        # delete
        self.assertEqual(ret[6]['path'], moved)
        self.assertEqual(ret[6]['change'], 'deleted')
        self.assertEqual(ret[7]['path'], self.tmpdir)
        self.assertEqual(ret[7]['change'], 'modified')
