# Python libs

import logging
import os
import shutil
import tempfile

# Salt libs
import salt.utils.files
from salt.beacons import inotify
from tests.support.mixins import LoaderModuleMockMixin

# Salt testing libs
from tests.support.unit import TestCase, skipIf

# Third-party libs
try:
    import pyinotify  # pylint: disable=unused-import

    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False


log = logging.getLogger(__name__)


@skipIf(not HAS_PYINOTIFY, "pyinotify is not available")
class INotifyBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.inotify
    """

    def setup_loader_modules(self):
        return {inotify: {}}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_non_list_config(self):
        config = {}

        ret = inotify.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for inotify beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]
        ret = inotify.validate(config)
        _expected = (False, "Configuration for inotify beacon must include files.")
        self.assertEqual(ret, _expected)

    def test_files_none_config(self):
        config = [{"files": None}]
        ret = inotify.validate(config)
        _expected = (
            False,
            "Configuration for inotify beacon invalid, files must be a dict.",
        )
        self.assertEqual(ret, _expected)

    def test_files_list_config(self):
        config = [{"files": [{"/importantfile": {"mask": ["modify"]}}]}]
        ret = inotify.validate(config)
        _expected = (
            False,
            "Configuration for inotify beacon invalid, files must be a dict.",
        )
        self.assertEqual(ret, _expected)

    @skipIf(
        salt.utils.platform.is_freebsd(),
        "Skip on FreeBSD - does not yet have full inotify/watchdog support",
    )
    def test_file_open(self):
        path = os.path.realpath(__file__)
        config = [{"files": {path: {"mask": ["open"]}}}]
        ret = inotify.validate(config)
        self.assertEqual(ret, (True, "Valid beacon configuration"))

        ret = inotify.beacon(config)
        self.assertEqual(ret, [])

        with salt.utils.files.fopen(path, "r") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], path)
        self.assertEqual(ret[0]["change"], "IN_OPEN")

    @skipIf(
        salt.utils.platform.is_freebsd(),
        "Skip on FreeBSD - does not yet have full inotify/watchdog support",
    )
    def test_dir_no_auto_add(self):
        config = [{"files": {self.tmpdir: {"mask": ["create"]}}}]
        ret = inotify.validate(config)
        self.assertEqual(ret, (True, "Valid beacon configuration"))

        ret = inotify.beacon(config)
        self.assertEqual(ret, [])
        fp = os.path.join(self.tmpdir, "tmpfile")
        with salt.utils.files.fopen(fp, "w") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_CREATE")
        with salt.utils.files.fopen(fp, "r") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(ret, [])

    @skipIf(
        salt.utils.platform.is_freebsd(),
        "Skip on FreeBSD - does not yet have full inotify/watchdog support",
    )
    def test_dir_auto_add(self):
        config = [
            {"files": {self.tmpdir: {"mask": ["create", "open"], "auto_add": True}}}
        ]
        ret = inotify.validate(config)
        self.assertEqual(ret, (True, "Valid beacon configuration"))

        ret = inotify.beacon(config)
        self.assertEqual(ret, [])
        fp = os.path.join(self.tmpdir, "tmpfile")
        with salt.utils.files.fopen(fp, "w") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 2)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_CREATE")
        self.assertEqual(ret[1]["path"], fp)
        self.assertEqual(ret[1]["change"], "IN_OPEN")
        with salt.utils.files.fopen(fp, "r") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_OPEN")

    @skipIf(
        salt.utils.platform.is_freebsd(),
        "Skip on FreeBSD - does not yet have full inotify/watchdog support",
    )
    def test_dir_recurse(self):
        dp1 = os.path.join(self.tmpdir, "subdir1")
        os.mkdir(dp1)
        dp2 = os.path.join(dp1, "subdir2")
        os.mkdir(dp2)
        fp = os.path.join(dp2, "tmpfile")
        with salt.utils.files.fopen(fp, "w") as f:
            pass
        config = [{"files": {self.tmpdir: {"mask": ["open"], "recurse": True}}}]
        ret = inotify.validate(config)
        self.assertEqual(ret, (True, "Valid beacon configuration"))

        ret = inotify.beacon(config)
        self.assertEqual(ret, [])
        with salt.utils.files.fopen(fp) as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 3)
        self.assertEqual(ret[0]["path"], dp1)
        self.assertEqual(ret[0]["change"], "IN_OPEN|IN_ISDIR")
        self.assertEqual(ret[1]["path"], dp2)
        self.assertEqual(ret[1]["change"], "IN_OPEN|IN_ISDIR")
        self.assertEqual(ret[2]["path"], fp)
        self.assertEqual(ret[2]["change"], "IN_OPEN")

    @skipIf(
        salt.utils.platform.is_freebsd(),
        "Skip on FreeBSD - does not yet have full inotify/watchdog support",
    )
    def test_dir_recurse_auto_add(self):
        dp1 = os.path.join(self.tmpdir, "subdir1")
        os.mkdir(dp1)
        config = [
            {
                "files": {
                    self.tmpdir: {
                        "mask": ["create", "delete"],
                        "recurse": True,
                        "auto_add": True,
                    }
                }
            }
        ]
        ret = inotify.validate(config)
        self.assertEqual(ret, (True, "Valid beacon configuration"))

        ret = inotify.beacon(config)
        self.assertEqual(ret, [])
        dp2 = os.path.join(dp1, "subdir2")
        os.mkdir(dp2)
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], dp2)
        self.assertEqual(ret[0]["change"], "IN_CREATE|IN_ISDIR")
        fp = os.path.join(dp2, "tmpfile")
        with salt.utils.files.fopen(fp, "w") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_CREATE")
        os.remove(fp)
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_DELETE")

    @skipIf(
        salt.utils.platform.is_freebsd(),
        "Skip on FreeBSD - does not yet have full inotify/watchdog support",
    )
    def test_multi_files_exclude(self):
        dp1 = os.path.join(self.tmpdir, "subdir1")
        dp2 = os.path.join(self.tmpdir, "subdir2")
        os.mkdir(dp1)
        os.mkdir(dp2)
        _exclude1 = "{}/subdir1/*tmpfile*$".format(self.tmpdir)
        _exclude2 = "{}/subdir2/*filetmp*$".format(self.tmpdir)
        config = [
            {
                "files": {
                    dp1: {
                        "mask": ["create", "delete"],
                        "recurse": True,
                        "exclude": [{_exclude1: {"regex": True}}],
                        "auto_add": True,
                    }
                }
            },
            {
                "files": {
                    dp2: {
                        "mask": ["create", "delete"],
                        "recurse": True,
                        "exclude": [{_exclude2: {"regex": True}}],
                        "auto_add": True,
                    }
                }
            },
        ]
        ret = inotify.validate(config)
        self.assertEqual(ret, (True, "Valid beacon configuration"))

        fp = os.path.join(dp1, "tmpfile")
        with salt.utils.files.fopen(fp, "w") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 0)
        os.remove(fp)
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 0)

        fp = os.path.join(dp2, "tmpfile")
        with salt.utils.files.fopen(fp, "w") as f:
            pass
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_CREATE")
        os.remove(fp)
        ret = inotify.beacon(config)
        self.assertEqual(len(ret), 1)
        self.assertEqual(ret[0]["path"], fp)
        self.assertEqual(ret[0]["change"], "IN_DELETE")

    # Check __get_notifier and ensure that the right bits are in __context__
    # including a beacon_name specific notifier is found.
    def test__get_notifier(self):
        config = {
            "files": {
                "/tmp/httpd/vhost.d": {
                    "mask": ["delete", "modify"],
                    "recurse": True,
                    "auto_add": True,
                    "exclude": [
                        {"/tmp/httpd/vhost.d/.+?\\.sw[px]*$|4913|~$": {"regex": True}}
                    ],
                },
                "/tmp/httpd/conf.d": {
                    "mask": ["delete", "modify"],
                    "recurse": True,
                    "auto_add": True,
                    "exclude": [
                        {"/tmp/httpd/vhost.d/.+?\\.sw[px]*$|4913|~$": {"regex": True}}
                    ],
                },
                "/tmp/httpd/conf": {
                    "mask": ["delete", "modify"],
                    "recurse": True,
                    "auto_add": True,
                    "exclude": [
                        {"/tmp/httpd/vhost.d/.+?\\.sw[px]*$|4913|~$": {"regex": True}}
                    ],
                },
            },
            "coalesce": True,
            "beacon_module": "inotify",
            "_beacon_name": "httpd.inotify",
        }

        ret = inotify._get_notifier(config)
        self.assertIn("inotify.queue", inotify.__context__)
        self.assertIn("httpd.inotify.notifier", inotify.__context__)
