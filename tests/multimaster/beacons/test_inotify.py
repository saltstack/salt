# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil
import tempfile
import time

import salt.config

# Import salt libs
import salt.version

# Import Salt Testing libs
from tests.support.case import MultimasterModuleCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import skipIf

try:
    import pyinotify  # pylint: disable=unused-import

    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False


log = logging.getLogger(__name__)


@skipIf(not HAS_PYINOTIFY, "pyinotify is not available")
class TestBeaconsInotify(MultimasterModuleCase, AdaptedConfigurationTestCaseMixin):
    """
    Validate the inotify beacon in multimaster environment
    """

    def setUp(self):
        self.tmpdir = salt.utils.stringutils.to_unicode(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_beacons_duplicate_53344(self):
        # Also add a status beacon to use it for interval checks
        res = self.run_function(
            "beacons.add",
            ("inotify", [{"files": {self.tmpdir: {"mask": ["create"]}}}]),
            master_tgt="mm-master",
        )
        log.debug("Inotify beacon add returned: %s", res)
        self.assertTrue(res.get("result"))
        self.addCleanup(
            self.run_function, "beacons.delete", ("inotify",), master_tgt="mm-master"
        )
        res = self.run_function(
            "beacons.add", ("status", [{"time": ["all"]}]), master_tgt="mm-master",
        )
        log.debug("Status beacon add returned: %s", res)
        self.assertTrue(res.get("result"))
        self.addCleanup(
            self.run_function, "beacons.delete", ("status",), master_tgt="mm-master"
        )

        # Ensure beacons are added.
        res = self.run_function(
            "beacons.list", (), return_yaml=False, master_tgt="mm-master",
        )
        log.debug("Beacons list: %s", res)
        self.assertEqual(
            {
                "inotify": [{"files": {self.tmpdir: {"mask": ["create"]}}}],
                "status": [{"time": ["all"]}],
            },
            res,
        )

        file_path = os.path.join(self.tmpdir, "tmpfile")
        master_listener = salt.utils.event.get_master_event(
            self.mm_master_opts, sock_dir=self.mm_master_opts["sock_dir"]
        )
        self.addCleanup(master_listener.destroy)
        sub_master_listener = salt.utils.event.get_master_event(
            self.mm_sub_master_opts, sock_dir=self.mm_sub_master_opts["sock_dir"]
        )
        self.addCleanup(sub_master_listener.destroy)

        # We have to wait beacon first execution that would configure the inotify watch.
        # Since beacons will be executed both together waiting for the first status beacon event
        # which will mean the inotify beacon was executed too.
        start = time.time()
        stop_at = start + self.mm_minion_opts["loop_interval"] * 2 + 60
        event = sub_event = None
        while True:
            if time.time() > stop_at:
                break
            if not event:
                event = master_listener.get_event(
                    full=True,
                    wait=1,
                    tag="salt/beacon/mm-minion/status",
                    match_type="startswith",
                )
            if sub_event is None:
                sub_event = sub_master_listener.get_event(
                    full=True,
                    wait=1,
                    tag="salt/beacon/mm-minion/status",
                    match_type="startswith",
                )
            if event and sub_event:
                break
        log.debug("Status events received: %s, %s", event, sub_event)

        if not event or not sub_event:
            self.fail("Failed to receive at least one of the status events")

        with salt.utils.files.fopen(file_path, "w") as f:
            pass

        start = time.time()
        # Now in successful case this test will get results at most in 2 loop intervals.
        # Waiting for 2 loops intervals + some seconds to the hardware stupidity.
        stop_at = start + self.mm_minion_opts["loop_interval"] * 3 + 60
        event = sub_event = None
        expected_tag = salt.utils.stringutils.to_str(
            "salt/beacon/mm-minion/inotify/{}".format(self.tmpdir)
        )
        while True:
            if time.time() > stop_at:
                break
            if not event:
                event = master_listener.get_event(
                    full=True, wait=1, tag=expected_tag, match_type="startswith"
                )
            if sub_event is None:
                sub_event = sub_master_listener.get_event(
                    full=True, wait=1, tag=expected_tag, match_type="startswith"
                )
            if event and sub_event:
                break
        log.debug("Inotify events received: %s, %s", event, sub_event)

        if not event or not sub_event:
            self.fail("Failed to receive at least one of the inotify events")

        # We can't determine the timestamp so remove it from results
        if event:
            del event["data"]["_stamp"]
        if sub_event:
            del sub_event["data"]["_stamp"]

        expected = {
            "data": {"path": file_path, "change": "IN_CREATE", "id": "mm-minion"},
            "tag": expected_tag,
        }

        # It's better to compare both at once to see both responses in the error log.
        self.assertEqual((expected, expected), (event, sub_event))
