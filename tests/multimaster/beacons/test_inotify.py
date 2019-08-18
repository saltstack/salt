# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import time
import tempfile
import shutil
import os
try:
    import pyinotify  # pylint: disable=unused-import
    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False

# Import Salt Testing libs
from tests.support.case import MultimasterModuleCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import skipIf

# Import salt libs
import salt.version
import salt.config


@skipIf(not HAS_PYINOTIFY, 'pyinotify is not available')
class TestBeaconsInotify(MultimasterModuleCase, AdaptedConfigurationTestCaseMixin):
    '''
    Validate the inotify beacon in multimaster environment
    '''
    def setUp(self):
        self.tmpdir = salt.utils.stringutils.to_unicode(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_beacons_duplicate_53344(self):
        # Also add a status beacon to use it for interval checks
        res = self.run_function(
                'beacons.add',
                ('inotify', [{'files': {self.tmpdir: {'mask': ['create']}}}]),
                master_tgt=0,
                )
        self.assertTrue(res.get('result'))
        res = self.run_function(
                'beacons.add',
                 ('status', [{'time': ['all']}]),
                master_tgt=0,
                )
        self.assertTrue(res.get('result'))

        # Ensure beacons are added.
        res = self.run_function(
                'beacons.list',
                (),
                return_yaml=False,
                master_tgt=0,
                )
        self.assertEqual({
            'inotify': [{
                'files': {
                    self.tmpdir: {
                        'mask': ['create']
                        }
                    }
                }],
            'status': [{
                'time': ['all']
                }]
            }, res)

        file_path = os.path.join(self.tmpdir, 'tmpfile')
        try:
            master_listener = salt.utils.event.get_event(
                    'master',
                    sock_dir=self.mm_master_opts['sock_dir'],
                    transport=self.mm_master_opts['transport'],
                    opts=self.mm_master_opts)
            sub_master_listener = salt.utils.event.get_event(
                    'master',
                    sock_dir=self.mm_sub_master_opts['sock_dir'],
                    transport=self.mm_sub_master_opts['transport'],
                    opts=self.mm_sub_master_opts)

            # We have to wait beacon first execution that would configure the inotify watch.
            # Since beacons will be executed both together waiting for the first status beacon event
            # which will mean the inotify beacon was executed too.
            start = time.time()
            stop_at = start + self.mm_minion_opts['loop_interval'] * 3 + 60
            event = sub_event = None
            while True:
                if time.time() > stop_at:
                    break
                if not event:
                    event = master_listener.get_event(
                            full=True,
                            wait=1,
                            tag='salt/beacon/minion/status',
                            match_type='startswith',
                            )
                if sub_event is None:
                    sub_event = sub_master_listener.get_event(
                            full=True,
                            wait=1,
                            tag='salt/beacon/minion/status',
                            match_type='startswith',
                            )
                if event and sub_event:
                    break

            with salt.utils.files.fopen(file_path, 'w') as f:
                pass

            start = time.time()
            # Now in successful case this test will get results at most in 2 loop intervals.
            # Waiting for 2 loops intervals + some seconds to the hardware stupidity.
            stop_at = start + self.mm_minion_opts['loop_interval'] * 2 + 60
            event = sub_event = None
            while True:
                if time.time() > stop_at:
                    break
                if not event:
                    event = master_listener.get_event(
                            full=True,
                            wait=1,
                            tag='salt/beacon/minion/inotify/' + self.tmpdir,
                            match_type='startswith',
                            )
                if sub_event is None:
                    sub_event = sub_master_listener.get_event(
                            full=True,
                            wait=1,
                            tag='salt/beacon/minion/inotify/' + self.tmpdir,
                            match_type='startswith',
                            )
                if event and sub_event:
                    break
        finally:
            self.assertTrue(self.run_function(
                'beacons.delete',
                ('inotify',),
                master_tgt=0,
                ))
            master_listener.destroy()
            sub_master_listener.destroy()

        # We can't determine the timestamp so remove it from results
        if event:
            del event['data']['_stamp']
        if sub_event:
            del sub_event['data']['_stamp']

        expected = {
                'data': {
                    'path': file_path,
                    'change': 'IN_CREATE',
                    'id': 'minion',
                    },
                'tag': salt.utils.stringutils.to_str('salt/beacon/minion/inotify/' + self.tmpdir),
                }

        # It's better to compare both at once to see both responses in the error log.
        self.assertEqual((expected, expected), (event, sub_event))
