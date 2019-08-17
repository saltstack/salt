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
        res = self.run_function(
                'beacons.add',
                ('inotify', [{'files': {self.tmpdir: {'mask': ['create']}}}]),
                master_tgt=0,
                )
        self.assertTrue(res.get('result'))

        # Ensure the beacon is added just for better diagnostic.
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
            # Waiting for 1 loop interval + some seconds to the hardware stupidity
            time.sleep(self.mm_minion_opts['loop_interval'] + 6)
            with salt.utils.files.fopen(file_path, 'w') as f:
                pass

            start = time.time()
            # Now in successful case this test will get results at most in 2 loop intervals.
            # Waiting for 2 loops intervals + some seconds to the hardware stupidity.
            stop_at = start + self.mm_minion_opts['loop_interval'] * 2 + 30
            event = sub_event = None
            while True:
                if time.time() > stop_at:
                    break
                if not event:
                    event = master_listener.get_event(
                            full=True,
                            no_block=True,
                            tag='salt/beacon/minion/inotify/' + self.tmpdir,
                            match_type='startswith',
                            )
                if sub_event is None:
                    sub_event = master_listener.get_event(
                            full=True,
                            no_block=True,
                            tag='salt/beacon/minion/inotify/' + self.tmpdir,
                            match_type='startswith',
                            )
                if not event or not sub_event:
                    time.sleep(1)
                if event and sub_event:
                    break
        finally:
            self.assertTrue(self.run_function(
                'beacons.delete',
                ('inotify',),
                master_tgt=0,
                ))

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
