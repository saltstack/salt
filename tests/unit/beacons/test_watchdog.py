# coding: utf-8

# Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import tempfile
import time

# Salt libs
import salt.utils.files
import salt.utils.platform
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
@skipIf(salt.utils.platform.is_darwin(), 'Tests were being skipped pre macos under nox. Keep it like that for now.')
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
        # Create triggers a modify event along with the create event in Py3
        # So, let's do this before configuring the beacon
        create(path)

        config = [{'directories': {self.tmpdir: {'mask': ['modify']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        create(path, 'some content')

        ret = check_events(config)

        modified = False
        for event in ret:
            # "modified" requires special handling
            # A modification sometimes triggers 2 modified events depending on
            # the OS and the python version
            # When the "modified" event triggers on modify, it will have the
            # path to the temp file (path), other modified events will contain
            # the path minus "tmpfile" and will not match. That's how we'll
            # distinguish the two
            if event['change'] == 'modified':
                if event['path'] == path:
                    modified = True

        # Check results of the for loop to validate modified
        self.assertTrue(modified)

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
        config = [{'directories': {self.tmpdir: {'mask': ['create']}}}]
        self.assertValid(config)
        self.assertEqual(watchdog.beacon(config), [])

        path = os.path.join(self.tmpdir, 'tmpfile')
        create(path)

        ret = check_events(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]['path'], path)
        self.assertEqual(ret[0]['change'], 'created')

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

        # Give the events time to load into the queue
        time.sleep(1)

        ret = check_events(config)

        events = {'created': '',
                  'deleted': '',
                  'moved': ''}
        modified = False
        for event in ret:
            if event['change'] == 'created':
                self.assertEqual(event['path'], path)
                events.pop('created', '')
            if event['change'] == 'moved':
                self.assertEqual(event['path'], path)
                events.pop('moved', '')
            if event['change'] == 'deleted':
                self.assertEqual(event['path'], moved)
                events.pop('deleted', '')
            # "modified" requires special handling
            # All events [created, moved, deleted] also trigger a "modified"
            # event on Linux
            # Only the "created" event triggers a modified event on Py3 Windows
            # When the "modified" event triggers on modify, it will have the
            # path to the temp file (path), other modified events will contain
            # the path minus "tmpfile" and will not match. That's how we'll
            # distinguish the two
            if event['change'] == 'modified':
                if event['path'] == path:
                    modified = True

        # Check results of the for loop to validate modified
        self.assertTrue(modified)

        # Make sure all events were checked
        self.assertDictEqual(events, {})
