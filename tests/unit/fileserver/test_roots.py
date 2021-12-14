"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import copy
import os
import pathlib
import shutil
import tempfile
import textwrap

import salt.fileclient
import salt.fileserver.roots as roots
import salt.utils.files
import salt.utils.hashutils
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mixins import (
    AdaptedConfigurationTestCaseMixin,
    LoaderModuleMockMixin,
)
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

UNICODE_FILENAME = "питон.txt"
UNICODE_DIRNAME = UNICODE_ENVNAME = "соль"


class RootsTest(TestCase, AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        config_overrides = {"file_roots": {"base": [str(self.tmp_state_tree)]}}
        self.opts = self.get_temp_config("master", **config_overrides)
        return {roots: {"__opts__": self.opts}}

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = pathlib.Path(tempfile.mkdtemp(dir=RUNTIME_VARS.TMP))
        cls.tmp_state_tree = pathlib.Path(tempfile.mkdtemp(dir=RUNTIME_VARS.TMP))
        full_path_to_file = os.path.join(RUNTIME_VARS.BASE_FILES, "testfile")
        shutil.copyfile(full_path_to_file, str(cls.tmp_dir / "testfile"))
        shutil.copyfile(full_path_to_file, str(cls.tmp_state_tree / "testfile"))
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.BASE_FILES, UNICODE_FILENAME),
            str(cls.tmp_state_tree / UNICODE_FILENAME),
        )
        shutil.copytree(
            os.path.join(RUNTIME_VARS.BASE_FILES, UNICODE_DIRNAME),
            str(cls.tmp_state_tree / UNICODE_DIRNAME),
        )

    @classmethod
    def tearDownClass(cls):
        salt.utils.files.rm_rf(str(cls.tmp_dir))
        salt.utils.files.rm_rf(str(cls.tmp_state_tree))

    def tearDown(self):
        del self.opts

    def test_file_list(self):
        ret = roots.file_list({"saltenv": "base"})
        self.assertIn("testfile", ret)
        self.assertIn(UNICODE_FILENAME, ret)

    def test_find_file(self):
        ret = roots.find_file("testfile")
        self.assertEqual("testfile", ret["rel"])

        full_path_to_file = str(self.tmp_state_tree / "testfile")
        self.assertEqual(full_path_to_file, ret["path"])

    def test_serve_file(self):
        with patch.dict(roots.__opts__, {"file_buffer_size": 262144}):
            load = {
                "saltenv": "base",
                "path": str(self.tmp_dir / "testfile"),
                "loc": 0,
            }
            fnd = {"path": str(self.tmp_dir / "testfile"), "rel": "testfile"}
            ret = roots.serve_file(load, fnd)

            with salt.utils.files.fopen(
                os.path.join(RUNTIME_VARS.BASE_FILES, "testfile"), "rb"
            ) as fp_:
                data = fp_.read()

            self.assertDictEqual(ret, {"data": data, "dest": "testfile"})

    def test_envs(self):
        opts = {"file_roots": copy.copy(self.opts["file_roots"])}
        opts["file_roots"][UNICODE_ENVNAME] = opts["file_roots"]["base"]
        with patch.dict(roots.__opts__, opts):
            ret = roots.envs()
        self.assertIn("base", ret)
        self.assertIn(UNICODE_ENVNAME, ret)

    def test_file_hash(self):
        load = {
            "saltenv": "base",
            "path": str(self.tmp_dir / "testfile"),
        }
        fnd = {"path": str(self.tmp_dir / "testfile"), "rel": "testfile"}
        ret = roots.file_hash(load, fnd)

        # Hashes are different in Windows. May be how git translates line
        # endings
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.BASE_FILES, "testfile"), "rb"
        ) as fp_:
            hsum = salt.utils.hashutils.sha256_digest(fp_.read())

        self.assertDictEqual(ret, {"hsum": hsum, "hash_type": "sha256"})

    def test_file_list_emptydirs(self):
        empty_dir = self.tmp_state_tree / "empty_dir"
        if not empty_dir.is_dir():
            empty_dir.mkdir()
        self.addCleanup(salt.utils.files.rm_rf, str(empty_dir))
        ret = roots.file_list_emptydirs({"saltenv": "base"})
        self.assertIn("empty_dir", ret)

    def test_file_list_with_slash(self):
        opts = {"file_roots": copy.copy(self.opts["file_roots"])}
        opts["file_roots"]["foo/bar"] = opts["file_roots"]["base"]
        load = {
            "saltenv": "foo/bar",
        }
        with patch.dict(roots.__opts__, opts):
            ret = roots.file_list(load)
        self.assertIn("testfile", ret)
        self.assertIn(UNICODE_FILENAME, ret)

    def test_dir_list(self):
        empty_dir = self.tmp_state_tree / "empty_dir"
        if not empty_dir.is_dir():
            empty_dir.mkdir()
        self.addCleanup(salt.utils.files.rm_rf, str(empty_dir))
        ret = roots.dir_list({"saltenv": "base"})
        self.assertIn("empty_dir", ret)
        self.assertIn(UNICODE_DIRNAME, ret)

    def test_symlink_list(self):
        source_sym = self.tmp_state_tree / "source_sym"
        source_sym.write_text("")
        dest_sym = self.tmp_state_tree / "dest_sym"
        dest_sym.symlink_to(str(source_sym))
        self.addCleanup(dest_sym.unlink)
        self.addCleanup(source_sym.unlink)
        ret = roots.symlink_list({"saltenv": "base"})
        self.assertDictEqual(ret, {"dest_sym": str(source_sym)})

    def test_dynamic_file_roots(self):
        dyn_root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        top_sls = os.path.join(dyn_root_dir, "top.sls")
        with salt.utils.files.fopen(top_sls, "w") as fp_:
            fp_.write("{{saltenv}}:\n  '*':\n    - dynamo\n")
        dynamo_sls = os.path.join(dyn_root_dir, "dynamo.sls")
        with salt.utils.files.fopen(dynamo_sls, "w") as fp_:
            fp_.write("foo:\n  test.nop\n")
        opts = {"file_roots": copy.copy(self.opts["file_roots"])}
        opts["file_roots"]["__env__"] = [dyn_root_dir]
        with patch.dict(roots.__opts__, opts):
            ret1 = roots.find_file("dynamo.sls", "dyn")
            ret2 = roots.file_list({"saltenv": "dyn"})
        self.assertEqual("dynamo.sls", ret1["rel"])
        self.assertIn("top.sls", ret2)
        self.assertIn("dynamo.sls", ret2)

    @skipIf(
        salt.utils.platform.is_windows(),
        "Windows does not support this master function",
    )
    def test_update_no_change(self):
        # process all changes that have happen
        # changes will always take place the first time during testing
        ret = roots.update()
        self.assertTrue(ret["changed"])

        # check if no changes took place
        ret = roots.update()
        self.assertFalse(ret["changed"])
        self.assertEqual(ret["files"]["changed"], [])
        self.assertEqual(ret["files"]["removed"], [])
        self.assertEqual(ret["files"]["added"], [])

    def test_update_mtime_map(self):
        """
        Test that files with colons in the filename are properly handled in the
        mtime_map, and that they are properly identified as having changed.
        """
        mtime_map_path = os.path.join(self.opts["cachedir"], "roots", "mtime_map")
        mtime_map_mock = mock_open(
            read_data={
                mtime_map_path: textwrap.dedent(
                    """\
                    /srv/salt/kleine_Datei.txt:1594263154.0469685
                    /srv/salt/große:Datei.txt:1594263160.9336357
                    """
                ),
            }
        )
        new_mtime_map = {
            "/srv/salt/kleine_Datei.txt": 1594263154.0469685,
            "/srv/salt/große:Datei.txt": 1594263261.0616212,
        }

        with patch(
            "salt.fileserver.reap_fileserver_cache_dir", MagicMock(return_value=True)
        ), patch(
            "salt.fileserver.generate_mtime_map", MagicMock(return_value=new_mtime_map)
        ), patch.dict(
            roots.__opts__, {"fileserver_events": False}
        ), patch(
            "salt.utils.files.fopen", mtime_map_mock
        ):
            ret = roots.update()

        # Confirm the expected return from the function
        assert ret == {
            "changed": True,
            "files": {
                "changed": ["/srv/salt/große:Datei.txt"],
                "removed": [],
                "added": [],
            },
            "backend": "roots",
        }, ret

        # Confirm that the new values were written to the mtime_map. Sort both
        # lists of lines to account for variances in dictionary iteration order
        # between Python releases.
        lines_written = sorted(mtime_map_mock.write_calls())
        expected = sorted(
            [
                salt.utils.stringutils.to_bytes(
                    "{key}:{val}\n".format(key=key, val=val)
                )
                for key, val in new_mtime_map.items()
            ]
        )
        assert lines_written == expected, lines_written

    def test_update_mtime_map_unicode_error(self):
        """
        Test that a malformed mtime_map (which causes an UnicodeDecodeError
        exception) is handled properly.
        """
        new_mtime_map = {
            "/srv/salt/große:Datei.txt": 1594263261.0616212,
        }
        with tempfile.TemporaryDirectory() as tmpdirname:
            mtime_map_path = os.path.join(tmpdirname, "roots", "mtime_map")
            os.makedirs(os.path.dirname(mtime_map_path))
            with salt.utils.files.fopen(mtime_map_path, "wb") as fp:
                fp.write(b"\x9c")

            with patch(
                "salt.fileserver.reap_fileserver_cache_dir",
                MagicMock(return_value=True),
            ), patch(
                "salt.fileserver.generate_mtime_map",
                MagicMock(return_value=new_mtime_map),
            ), patch.dict(
                roots.__opts__,
                {"fileserver_events": False, "cachedir": tmpdirname},
            ):
                ret = roots.update()

        assert ret == {
            "changed": True,
            "files": {
                "changed": [],
                "removed": [],
                "added": ["/srv/salt/große:Datei.txt"],
            },
            "backend": "roots",
        }, ret
