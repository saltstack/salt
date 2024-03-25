"""
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
"""

import copy
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile

import jinja2
import pytest

import salt.exceptions
import salt.utils.hashutils
import salt.utils.json
import salt.utils.platform
import salt.utils.stringutils
from salt.utils import thin
from salt.utils.stringutils import to_bytes as bts
from tests.support.helpers import TstSuiteLoggingHandler, VirtualEnv
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


def patch_if(condition, *args, **kwargs):
    """
    Return a patch decorator if the provided condition is met
    """
    if condition:
        return patch(*args, **kwargs)

    def inner(func):
        return func

    return inner


class SSHThinTestCase(TestCase):
    """
    TestCase for SaltSSH-related parts.
    """

    def setUp(self):
        self.jinja_fp = os.path.dirname(jinja2.__file__)

        self.ext_conf = {
            "test": {
                "py-version": [2, 7],
                "path": RUNTIME_VARS.SALT_CODE_DIR,
                "dependencies": {"jinja2": self.jinja_fp},
            }
        }
        self.tops = copy.deepcopy(self.ext_conf)
        self.tops["test"]["dependencies"] = [self.jinja_fp]
        self.tar = self._tarfile(None).open()
        self.digest = salt.utils.hashutils.DigestCollector()
        self.exp_files = [
            os.path.join("salt", "payload.py"),
            os.path.join("jinja2", "__init__.py"),
        ]
        lib_root = os.path.join(RUNTIME_VARS.TMP, "fake-libs")
        self.fake_libs = {
            "distro": os.path.join(lib_root, "distro"),
            "jinja2": os.path.join(lib_root, "jinja2"),
            "yaml": os.path.join(lib_root, "yaml"),
            "tornado": os.path.join(lib_root, "tornado"),
            "msgpack": os.path.join(lib_root, "msgpack"),
        }

        code_dir = pathlib.Path(RUNTIME_VARS.CODE_DIR).resolve()
        self.exp_ret = {
            "distro": str(code_dir / "distro.py"),
            "jinja2": str(code_dir / "jinja2"),
            "yaml": str(code_dir / "yaml"),
            "tornado": str(code_dir / "tornado"),
            "msgpack": str(code_dir / "msgpack"),
            "certifi": str(code_dir / "certifi"),
            "singledispatch": str(code_dir / "singledispatch.py"),
            "looseversion": str(code_dir / "looseversion.py"),
            "packaging": str(code_dir / "packaging"),
        }
        self.exc_libs = ["jinja2", "yaml"]

    def tearDown(self):
        for lib, fp in self.fake_libs.items():
            if os.path.exists(fp):
                shutil.rmtree(fp)
        self.exc_libs = None
        self.jinja_fp = None
        self.ext_conf = None
        self.tops = None
        self.tar = None
        self.digest = None
        self.exp_files = None
        self.fake_libs = None
        self.exp_ret = None

    def _popen(self, return_value=None, side_effect=None, returncode=0):
        """
        Fake subprocess.Popen

        :return:
        """

        proc = MagicMock()
        proc.communicate = MagicMock(return_value=return_value, side_effect=side_effect)
        proc.returncode = returncode
        popen = MagicMock(return_value=proc)

        return popen

    @staticmethod
    def _version_info(major=None, minor=None):
        """
        Fake version info.

        :param major:
        :param minor:
        :return:
        """

        class VersionInfo(tuple):
            pass

        vi = VersionInfo([major, minor])
        vi.major = major or sys.version_info.major
        vi.minor = minor or sys.version_info.minor

        return vi

    def _tarfile(self, getinfo=False):
        """
        Fake tarfile handler.

        :return:
        """
        spec = ["add", "close"]
        if getinfo:
            spec.append("getinfo")

        tf = MagicMock()
        tf.open = MagicMock(return_value=MagicMock(spec=spec))

        return tf

    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=False))
    def test_get_ext_tops_cfg_missing_dependencies(self):
        """
        Test thin.get_ext_tops contains all required dependencies.

        :return:
        """
        cfg = {"namespace": {"py-version": [0, 0], "path": "/foo", "dependencies": []}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        self.assertIn("Missing dependencies", str(err.value))
        self.assertTrue(thin.log.error.called)
        self.assertIn("Missing dependencies", thin.log.error.call_args[0][0])
        self.assertIn("jinja2, yaml, tornado, msgpack", thin.log.error.call_args[0][0])

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=False))
    def test_get_ext_tops_cfg_missing_interpreter(self):
        """
        Test thin.get_ext_tops contains interpreter configuration.

        :return:
        """
        cfg = {"namespace": {"path": "/foo", "dependencies": []}}
        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        self.assertIn("missing specific locked Python version", str(err.value))

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=False))
    def test_get_ext_tops_cfg_wrong_interpreter(self):
        """
        Test thin.get_ext_tops contains correct interpreter configuration.

        :return:
        """
        cfg = {"namespace": {"path": "/foo", "py-version": 2, "dependencies": []}}

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)
        self.assertIn(
            "specific locked Python version should be a list of major/minor version",
            str(err.value),
        )

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=False))
    def test_get_ext_tops_cfg_interpreter(self):
        """
        Test thin.get_ext_tops interpreter configuration.

        :return:
        """
        cfg = {
            "namespace": {
                "path": "/foo",
                "py-version": [2, 6],
                "dependencies": {
                    "jinja2": "",
                    "yaml": "",
                    "tornado": "",
                    "msgpack": "",
                },
            }
        }

        with pytest.raises(salt.exceptions.SaltSystemExit):
            thin.get_ext_tops(cfg)
        assert len(thin.log.warning.mock_calls) == 4
        assert sorted(x[1][1] for x in thin.log.warning.mock_calls) == [
            "jinja2",
            "msgpack",
            "tornado",
            "yaml",
        ]
        assert (
            "Module test has missing configuration"
            == thin.log.warning.mock_calls[0][1][0] % "test"
        )

    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=False))
    def test_get_ext_tops_dependency_config_check(self):
        """
        Test thin.get_ext_tops dependencies are importable

        :return:
        """
        cfg = {
            "namespace": {
                "path": "/foo",
                "py-version": [2, 6],
                "dependencies": {
                    "jinja2": "/jinja/foo.py",
                    "yaml": "/yaml/",
                    "tornado": "/tornado/wrong.rb",
                    "msgpack": "msgpack.sh",
                },
            }
        }

        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.get_ext_tops(cfg)

        self.assertIn(
            "Missing dependencies for the alternative version in the "
            "external configuration",
            str(err.value),
        )

        messages = {}
        for cl in thin.log.warning.mock_calls:
            messages[cl[1][1]] = cl[1][0] % (cl[1][1], cl[1][2])
        for mod in ["tornado", "yaml", "msgpack"]:
            self.assertIn("not a Python importable module", messages[mod])
        self.assertIn(
            "configured with not a file or does not exist", messages["jinja2"]
        )

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.path.isfile", MagicMock(return_value=True))
    def test_get_ext_tops_config_pass(self):
        """
        Test thin.get_ext_tops configuration

        :return:
        """
        cfg = {
            "namespace": {
                "path": "/foo",
                "py-version": [2, 6],
                "dependencies": {
                    "jinja2": "/jinja/foo.py",
                    "yaml": "/yaml/",
                    "tornado": "/tornado/tornado.py",
                    "msgpack": "msgpack.py",
                    "distro": "distro.py",
                },
            }
        }
        out = thin.get_ext_tops(cfg)
        assert out["namespace"]["py-version"] == cfg["namespace"]["py-version"]
        assert out["namespace"]["path"] == cfg["namespace"]["path"]
        assert sorted(out["namespace"]["dependencies"]) == sorted(
            [
                "/tornado/tornado.py",
                "/jinja/foo.py",
                "/yaml/",
                "msgpack.py",
                "distro.py",
            ]
        )

    @patch("salt.utils.thin.sys.argv", [None, '{"foo": "bar"}'])
    @patch("salt.utils.thin.get_tops", lambda **kw: kw)
    def test_gte(self):
        """
        Test thin.gte external call for processing the info about tops per interpreter.

        :return:
        """
        assert salt.utils.json.loads(thin.gte()).get("foo") == "bar"

    def test_add_dep_path(self):
        """
        Test thin._add_dependency function to setup dependency paths
        :return:
        """
        container = []
        for pth in ["/foo/bar.py", "/something/else/__init__.py"]:
            thin._add_dependency(container, type("obj", (), {"__file__": pth})())
        assert "__init__" not in container[1]
        assert container == ["/foo/bar.py", "/something/else"]

    def test_thin_path(self):
        """
        Test thin.thin_path returns the expected path.

        :return:
        """
        path = os.sep + os.path.join("path", "to")
        expected = os.path.join(path, "thin", "thin.tgz")
        self.assertEqual(thin.thin_path(path), expected)

    def test_get_salt_call_script(self):
        """
        Test get salt-call script rendered.

        :return:
        """
        out = thin._get_salt_call("foo", "bar", py26=[2, 6], py27=[2, 7], py34=[3, 4])
        for line in salt.utils.stringutils.to_str(out).split(os.linesep):
            if line.startswith("namespaces = {"):
                data = salt.utils.json.loads(line.replace("namespaces = ", "").strip())
                assert data.get("py26") == [2, 6]
                assert data.get("py27") == [2, 7]
                assert data.get("py34") == [3, 4]
            if line.startswith("syspaths = "):
                data = salt.utils.json.loads(line.replace("syspaths = ", ""))
                assert data == ["foo", "bar"]

    def test_get_ext_namespaces_empty(self):
        """
        Test thin._get_ext_namespaces function returns an empty dictionary on nothing
        :return:
        """
        for obj in [None, {}, []]:
            assert thin._get_ext_namespaces(obj) == {}

    def test_get_ext_namespaces(self):
        """
        Test thin._get_ext_namespaces function returns namespaces properly out of the config.
        :return:
        """
        cfg = {"ns": {"py-version": [2, 7]}}
        assert thin._get_ext_namespaces(cfg).get("ns") == (
            2,
            7,
        )
        assert isinstance(thin._get_ext_namespaces(cfg).get("ns"), tuple)

    def test_get_ext_namespaces_failure(self):
        """
        Test thin._get_ext_namespaces function raises an exception
        if python major/minor version is not configured.
        :return:
        """
        with pytest.raises(salt.exceptions.SaltSystemExit):
            thin._get_ext_namespaces({"ns": {}})

    @patch(
        "salt.utils.thin.distro",
        type("distro", (), {"__file__": "/site-packages/distro"}),
    )
    @patch(
        "salt.utils.thin.salt",
        type("salt", (), {"__file__": "/site-packages/salt"}),
    )
    @patch(
        "salt.utils.thin.jinja2",
        type("jinja2", (), {"__file__": "/site-packages/jinja2"}),
    )
    @patch(
        "salt.utils.thin.yaml",
        type("yaml", (), {"__file__": "/site-packages/yaml"}),
    )
    @patch(
        "salt.utils.thin.tornado",
        type("tornado", (), {"__file__": "/site-packages/tornado"}),
    )
    @patch(
        "salt.utils.thin.msgpack",
        type("msgpack", (), {"__file__": "/site-packages/msgpack"}),
    )
    @patch(
        "salt.utils.thin.certifi",
        type("certifi", (), {"__file__": "/site-packages/certifi"}),
    )
    @patch(
        "salt.utils.thin.singledispatch",
        type("singledispatch", (), {"__file__": "/site-packages/sdp"}),
    )
    @patch(
        "salt.utils.thin.singledispatch_helpers",
        type("singledispatch_helpers", (), {"__file__": "/site-packages/sdp_hlp"}),
    )
    @patch(
        "salt.utils.thin.ssl_match_hostname",
        type("ssl_match_hostname", (), {"__file__": "/site-packages/ssl_mh"}),
    )
    @patch(
        "salt.utils.thin.markupsafe",
        type("markupsafe", (), {"__file__": "/site-packages/markupsafe"}),
    )
    @patch(
        "salt.utils.thin.backports_abc",
        type("backports_abc", (), {"__file__": "/site-packages/backports_abc"}),
    )
    @patch(
        "salt.utils.thin.concurrent",
        type("concurrent", (), {"__file__": "/site-packages/concurrent"}),
    )
    @patch(
        "salt.utils.thin.py_contextvars",
        type("contextvars", (), {"__file__": "/site-packages/contextvars"}),
    )
    @patch(
        "salt.utils.thin.packaging",
        type("packaging", (), {"__file__": "/site-packages/packaging"}),
    )
    @patch(
        "salt.utils.thin.looseversion",
        type("looseversion", (), {"__file__": "/site-packages/looseversion"}),
    )
    @patch_if(
        salt.utils.thin.has_immutables,
        "salt.utils.thin.immutables",
        type("immutables", (), {"__file__": "/site-packages/immutables"}),
    )
    @patch("salt.utils.thin.log", MagicMock())
    def test_get_tops(self):
        """
        Test thin.get_tops to get top directories, based on the interpreter.
        :return:
        """
        base_tops = [
            "distro",
            "salt",
            "jinja2",
            "yaml",
            "tornado",
            "msgpack",
            "certifi",
            "sdp",
            "sdp_hlp",
            "ssl_mh",
            "markupsafe",
            "backports_abc",
            "concurrent",
            "contextvars",
            "looseversion",
            "packaging",
        ]
        if salt.utils.thin.has_immutables:
            base_tops.extend(["immutables"])
        tops = []
        for top in thin.get_tops(extra_mods="foo,bar"):
            if top.find("/") != -1:
                spl = "/"
            else:
                spl = os.sep
            tops.append(top.rsplit(spl, 1)[-1])
        assert len(tops) == len(base_tops)
        assert sorted(tops) == sorted(base_tops), sorted(tops)

    @patch(
        "salt.utils.thin.distro",
        type("distro", (), {"__file__": "/site-packages/distro"}),
    )
    @patch(
        "salt.utils.thin.salt",
        type("salt", (), {"__file__": "/site-packages/salt"}),
    )
    @patch(
        "salt.utils.thin.jinja2",
        type("jinja2", (), {"__file__": "/site-packages/jinja2"}),
    )
    @patch(
        "salt.utils.thin.yaml",
        type("yaml", (), {"__file__": "/site-packages/yaml"}),
    )
    @patch(
        "salt.utils.thin.tornado",
        type("tornado", (), {"__file__": "/site-packages/tornado"}),
    )
    @patch(
        "salt.utils.thin.msgpack",
        type("msgpack", (), {"__file__": "/site-packages/msgpack"}),
    )
    @patch(
        "salt.utils.thin.certifi",
        type("certifi", (), {"__file__": "/site-packages/certifi"}),
    )
    @patch(
        "salt.utils.thin.singledispatch",
        type("singledispatch", (), {"__file__": "/site-packages/sdp"}),
    )
    @patch(
        "salt.utils.thin.singledispatch_helpers",
        type("singledispatch_helpers", (), {"__file__": "/site-packages/sdp_hlp"}),
    )
    @patch(
        "salt.utils.thin.ssl_match_hostname",
        type("ssl_match_hostname", (), {"__file__": "/site-packages/ssl_mh"}),
    )
    @patch(
        "salt.utils.thin.markupsafe",
        type("markupsafe", (), {"__file__": "/site-packages/markupsafe"}),
    )
    @patch(
        "salt.utils.thin.backports_abc",
        type("backports_abc", (), {"__file__": "/site-packages/backports_abc"}),
    )
    @patch(
        "salt.utils.thin.concurrent",
        type("concurrent", (), {"__file__": "/site-packages/concurrent"}),
    )
    @patch(
        "salt.utils.thin.py_contextvars",
        type("contextvars", (), {"__file__": "/site-packages/contextvars"}),
    )
    @patch(
        "salt.utils.thin.packaging",
        type("packaging", (), {"__file__": "/site-packages/packaging"}),
    )
    @patch(
        "salt.utils.thin.looseversion",
        type("looseversion", (), {"__file__": "/site-packages/looseversion"}),
    )
    @patch_if(
        salt.utils.thin.has_immutables,
        "salt.utils.thin.immutables",
        type("immutables", (), {"__file__": "/site-packages/immutables"}),
    )
    @patch("salt.utils.thin.log", MagicMock())
    def test_get_tops_extra_mods(self):
        """
        Test thin.get_tops to get extra-modules alongside the top directories, based on the interpreter.
        :return:
        """
        base_tops = [
            "distro",
            "salt",
            "jinja2",
            "yaml",
            "tornado",
            "msgpack",
            "certifi",
            "sdp",
            "sdp_hlp",
            "ssl_mh",
            "concurrent",
            "markupsafe",
            "backports_abc",
            "contextvars",
            "looseversion",
            "packaging",
            "foo",
            "bar.py",
        ]
        if salt.utils.thin.has_immutables:
            base_tops.extend(["immutables"])
        libs = salt.utils.thin.find_site_modules("contextvars")
        foo = {"__file__": os.sep + os.path.join("custom", "foo", "__init__.py")}
        bar = {"__file__": os.sep + os.path.join("custom", "bar")}
        with patch("salt.utils.thin.find_site_modules", MagicMock(side_effect=[libs])):
            with patch(
                "builtins.__import__",
                MagicMock(side_effect=[type("foo", (), foo), type("bar", (), bar)]),
            ):
                tops = []
                for top in thin.get_tops(extra_mods="foo,bar"):
                    if top.find("/") != -1:
                        spl = "/"
                    else:
                        spl = os.sep
                    tops.append(top.rsplit(spl, 1)[-1])
        self.assertEqual(len(tops), len(base_tops))
        self.assertListEqual(sorted(tops), sorted(base_tops))

    @patch(
        "salt.utils.thin.distro",
        type("distro", (), {"__file__": "/site-packages/distro"}),
    )
    @patch(
        "salt.utils.thin.salt",
        type("salt", (), {"__file__": "/site-packages/salt"}),
    )
    @patch(
        "salt.utils.thin.jinja2",
        type("jinja2", (), {"__file__": "/site-packages/jinja2"}),
    )
    @patch(
        "salt.utils.thin.yaml",
        type("yaml", (), {"__file__": "/site-packages/yaml"}),
    )
    @patch(
        "salt.utils.thin.tornado",
        type("tornado", (), {"__file__": "/site-packages/tornado"}),
    )
    @patch(
        "salt.utils.thin.msgpack",
        type("msgpack", (), {"__file__": "/site-packages/msgpack"}),
    )
    @patch(
        "salt.utils.thin.certifi",
        type("certifi", (), {"__file__": "/site-packages/certifi"}),
    )
    @patch(
        "salt.utils.thin.singledispatch",
        type("singledispatch", (), {"__file__": "/site-packages/sdp"}),
    )
    @patch(
        "salt.utils.thin.singledispatch_helpers",
        type("singledispatch_helpers", (), {"__file__": "/site-packages/sdp_hlp"}),
    )
    @patch(
        "salt.utils.thin.ssl_match_hostname",
        type("ssl_match_hostname", (), {"__file__": "/site-packages/ssl_mh"}),
    )
    @patch(
        "salt.utils.thin.markupsafe",
        type("markupsafe", (), {"__file__": "/site-packages/markupsafe"}),
    )
    @patch(
        "salt.utils.thin.backports_abc",
        type("backports_abc", (), {"__file__": "/site-packages/backports_abc"}),
    )
    @patch(
        "salt.utils.thin.concurrent",
        type("concurrent", (), {"__file__": "/site-packages/concurrent"}),
    )
    @patch(
        "salt.utils.thin.py_contextvars",
        type("contextvars", (), {"__file__": "/site-packages/contextvars"}),
    )
    @patch(
        "salt.utils.thin.packaging",
        type("packaging", (), {"__file__": "/site-packages/packaging"}),
    )
    @patch(
        "salt.utils.thin.looseversion",
        type("looseversion", (), {"__file__": "/site-packages/looseversion"}),
    )
    @patch_if(
        salt.utils.thin.has_immutables,
        "salt.utils.thin.immutables",
        type("immutables", (), {"__file__": "/site-packages/immutables"}),
    )
    @patch("salt.utils.thin.log", MagicMock())
    def test_get_tops_so_mods(self):
        """
        Test thin.get_tops to get extra-modules alongside the top directories, based on the interpreter.
        :return:
        """
        base_tops = [
            "distro",
            "salt",
            "jinja2",
            "yaml",
            "tornado",
            "msgpack",
            "certifi",
            "sdp",
            "sdp_hlp",
            "ssl_mh",
            "concurrent",
            "markupsafe",
            "backports_abc",
            "contextvars",
            "looseversion",
            "packaging",
            "foo.so",
            "bar.so",
        ]
        if salt.utils.thin.has_immutables:
            base_tops.extend(["immutables"])
        libs = salt.utils.thin.find_site_modules("contextvars")
        with patch("salt.utils.thin.find_site_modules", MagicMock(side_effect=[libs])):
            with patch(
                "builtins.__import__",
                MagicMock(
                    side_effect=[
                        type("salt", (), {"__file__": "/custom/foo.so"}),
                        type("salt", (), {"__file__": "/custom/bar.so"}),
                    ]
                ),
            ):
                tops = []
                for top in thin.get_tops(so_mods="foo,bar"):
                    if top.find("/") != -1:
                        spl = "/"
                    else:
                        spl = os.sep
                    tops.append(top.rsplit(spl, 1)[-1])
        assert len(tops) == len(base_tops)
        assert sorted(tops) == sorted(base_tops)

    @patch("salt.utils.thin.gen_thin", MagicMock(return_value="/path/to/thin/thin.tgz"))
    @patch("salt.utils.hashutils.get_hash", MagicMock(return_value=12345))
    def test_thin_sum(self):
        """
        Test thin.thin_sum function.

        :return:
        """
        assert thin.thin_sum("/cachedir", form="sha256")[1] == 12345
        thin.salt.utils.hashutils.get_hash.assert_called()
        assert thin.salt.utils.hashutils.get_hash.call_count == 1

        path, form = thin.salt.utils.hashutils.get_hash.call_args[0]
        assert path == "/path/to/thin/thin.tgz"
        assert form == "sha256"

    @patch("salt.utils.thin.gen_min", MagicMock(return_value="/path/to/thin/min.tgz"))
    @patch("salt.utils.hashutils.get_hash", MagicMock(return_value=12345))
    def test_min_sum(self):
        """
        Test thin.thin_sum function.

        :return:
        """
        assert thin.min_sum("/cachedir", form="sha256") == 12345
        thin.salt.utils.hashutils.get_hash.assert_called()
        assert thin.salt.utils.hashutils.get_hash.call_count == 1

        path, form = thin.salt.utils.hashutils.get_hash.call_args[0]
        assert path == "/path/to/thin/min.tgz"
        assert form == "sha256"

    @patch("salt.utils.thin.sys.version_info", (2, 5))
    @patch("salt.exceptions.SaltSystemExit", Exception)
    def test_gen_thin_fails_ancient_python_version(self):
        """
        Test thin.gen_thin function raises an exception
        if Python major/minor version is lower than 2.6

        :return:
        """
        with pytest.raises(salt.exceptions.SaltSystemExit) as err:
            thin.sys.exc_clear = lambda: None
            thin.gen_thin("")
        self.assertIn(
            'The minimum required python version to run salt-ssh is "3"',
            str(err.value),
        )

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.makedirs", MagicMock())
    @patch("salt.utils.files.fopen", MagicMock())
    @patch("salt.utils.thin._get_salt_call", MagicMock())
    @patch("salt.utils.thin._get_ext_namespaces", MagicMock())
    @patch("salt.utils.thin.get_tops", MagicMock(return_value=["/foo3", "/bar3"]))
    @patch("salt.utils.thin.get_ext_tops", MagicMock(return_value={}))
    @patch("salt.utils.thin.os.path.isfile", MagicMock())
    @patch("salt.utils.thin.os.path.isdir", MagicMock(return_value=True))
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.remove", MagicMock())
    @patch("salt.utils.thin.os.path.exists", MagicMock())
    @patch("salt.utils.path.os_walk", MagicMock(return_value=[]))
    @patch(
        "salt.utils.thin.subprocess.Popen",
        _popen(
            None,
            side_effect=[(bts("2.7"), bts("")), (bts('["/foo27", "/bar27"]'), bts(""))],
        ),
    )
    @patch("salt.utils.thin.tarfile", MagicMock())
    @patch("salt.utils.thin.zipfile", MagicMock())
    @patch("salt.utils.thin.os.getcwd", MagicMock())
    @patch("salt.utils.thin.os.access", MagicMock(return_value=True))
    @patch("salt.utils.thin.os.chdir", MagicMock())
    @patch("salt.utils.thin.os.close", MagicMock())
    @patch("salt.utils.thin.tempfile.mkdtemp", MagicMock())
    @patch(
        "salt.utils.thin.tempfile.mkstemp", MagicMock(return_value=(3, ".temporary"))
    )
    @patch("salt.utils.thin.shutil", MagicMock())
    @patch("salt.utils.thin.sys.version_info", _version_info(3, 6))
    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/python"))
    def test_gen_thin_compression_fallback_py3(self):
        """
        Test thin.gen_thin function if fallbacks to the gzip compression, once setup wrong.
        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        """
        thin.gen_thin("", compress="arj")
        thin.log.warning.assert_called()
        pt, msg = thin.log.warning.mock_calls[0][1]
        assert (
            pt % msg
            == 'Unknown compression type: "arj". Falling back to "gzip" compression.'
        )
        thin.zipfile.ZipFile.assert_not_called()
        thin.tarfile.open.assert_called()

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.makedirs", MagicMock())
    @patch("salt.utils.files.fopen", MagicMock())
    @patch("salt.utils.thin._get_salt_call", MagicMock())
    @patch("salt.utils.thin._get_ext_namespaces", MagicMock())
    @patch("salt.utils.thin.get_tops", MagicMock(return_value=["/foo3", "/bar3"]))
    @patch("salt.utils.thin.get_ext_tops", MagicMock(return_value={}))
    @patch("salt.utils.thin.os.path.isfile", MagicMock())
    @patch("salt.utils.thin.os.path.isdir", MagicMock(return_value=False))
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.remove", MagicMock())
    @patch("salt.utils.thin.os.path.exists", MagicMock())
    @patch("salt.utils.path.os_walk", MagicMock(return_value=[]))
    @patch(
        "salt.utils.thin.subprocess.Popen",
        _popen(
            None,
            side_effect=[(bts("2.7"), bts("")), (bts('["/foo27", "/bar27"]'), bts(""))],
        ),
    )
    @patch("salt.utils.thin.tarfile", MagicMock())
    @patch("salt.utils.thin.zipfile", MagicMock())
    @patch("salt.utils.thin.os.getcwd", MagicMock())
    @patch("salt.utils.thin.os.access", MagicMock(return_value=True))
    @patch("salt.utils.thin.os.chdir", MagicMock())
    @patch("salt.utils.thin.os.close", MagicMock())
    @patch("salt.utils.thin.tempfile.mkdtemp", MagicMock(return_value=""))
    @patch(
        "salt.utils.thin.tempfile.mkstemp", MagicMock(return_value=(3, ".temporary"))
    )
    @patch("salt.utils.thin.shutil", MagicMock())
    @patch("salt.utils.thin.sys.version_info", _version_info(3, 6))
    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/python"))
    def test_gen_thin_control_files_written_py3(self):
        """
        Test thin.gen_thin function if control files are written (version, salt-call etc).
        :return:
        """
        thin.gen_thin("")
        arc_name, arc_mode = thin.tarfile.method_calls[0][1]
        self.assertEqual(arc_name, ".temporary")
        self.assertEqual(arc_mode, "w:gz")
        for idx, fname in enumerate(
            ["version", ".thin-gen-py-version", "salt-call", "supported-versions"]
        ):
            name = thin.tarfile.open().method_calls[idx + 2][1][0]
            self.assertEqual(name, fname)
        thin.tarfile.open().close.assert_called()

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.makedirs", MagicMock())
    @patch("salt.utils.files.fopen", MagicMock())
    @patch("salt.utils.thin._get_salt_call", MagicMock())
    @patch("salt.utils.thin._get_ext_namespaces", MagicMock())
    @patch("salt.utils.thin.get_tops", MagicMock(return_value=["/salt", "/bar3"]))
    @patch("salt.utils.thin.get_ext_tops", MagicMock(return_value={}))
    @patch("salt.utils.thin.os.path.isfile", MagicMock())
    @patch("salt.utils.thin.os.path.isdir", MagicMock(return_value=True))
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.remove", MagicMock())
    @patch("salt.utils.thin.os.path.exists", MagicMock())
    @patch(
        "salt.utils.path.os_walk",
        MagicMock(
            return_value=(
                ("root", [], ["r1", "r2", "r3"]),
                ("root2", [], ["r4", "r5", "r6"]),
            )
        ),
    )
    @patch("salt.utils.thin.tarfile", _tarfile(None))
    @patch("salt.utils.thin.zipfile", MagicMock())
    @patch(
        "salt.utils.thin.os.getcwd",
        MagicMock(return_value=os.path.join(RUNTIME_VARS.TMP, "fake-cwd")),
    )
    @patch("salt.utils.thin.os.chdir", MagicMock())
    @patch("salt.utils.thin.os.close", MagicMock())
    @patch("salt.utils.thin.tempfile.mkdtemp", MagicMock(return_value=""))
    @patch(
        "salt.utils.thin.tempfile.mkstemp", MagicMock(return_value=(3, ".temporary"))
    )
    @patch("salt.utils.thin.shutil", MagicMock())
    @patch("salt.utils.thin.sys.version_info", _version_info(3, 6))
    @patch("salt.utils.hashutils.DigestCollector", MagicMock())
    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/python"))
    def test_gen_thin_main_content_files_written_py3(self):
        """
        Test thin.gen_thin function if main content files are written.
        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        """
        thin.gen_thin("")
        files = []
        for py in ("py3", "pyall"):
            for i in range(1, 4):
                files.append(os.path.join(py, "root", f"r{i}"))
            for i in range(4, 7):
                files.append(os.path.join(py, "root2", f"r{i}"))
        for cl in thin.tarfile.open().method_calls[:-6]:
            arcname = cl[2].get("arcname")
            self.assertIn(arcname, files)
            files.pop(files.index(arcname))
        self.assertFalse(files)

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.makedirs", MagicMock())
    @patch("salt.utils.files.fopen", MagicMock())
    @patch("salt.utils.thin._get_salt_call", MagicMock())
    @patch("salt.utils.thin._get_ext_namespaces", MagicMock())
    @patch("salt.utils.thin.get_tops", MagicMock(return_value=[]))
    @patch(
        "salt.utils.thin.get_ext_tops",
        MagicMock(
            return_value={
                "namespace": {
                    "py-version": [3, 0],
                    "path": "/opt/2015.8/salt",
                    "dependencies": ["/opt/certifi", "/opt/whatever"],
                }
            }
        ),
    )
    @patch("salt.utils.thin.os.path.isfile", MagicMock())
    @patch("salt.utils.thin.os.path.isdir", MagicMock(return_value=True))
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.remove", MagicMock())
    @patch("salt.utils.thin.os.path.exists", MagicMock())
    @patch(
        "salt.utils.path.os_walk",
        MagicMock(
            return_value=(
                ("root", [], ["r1", "r2", "r3"]),
                ("root2", [], ["r4", "r5", "r6"]),
            )
        ),
    )
    @patch("salt.utils.thin.tarfile", _tarfile(None))
    @patch("salt.utils.thin.zipfile", MagicMock())
    @patch(
        "salt.utils.thin.os.getcwd",
        MagicMock(return_value=os.path.join(RUNTIME_VARS.TMP, "fake-cwd")),
    )
    @patch("salt.utils.thin.os.chdir", MagicMock())
    @patch("salt.utils.thin.os.close", MagicMock())
    @patch("salt.utils.thin.tempfile.mkdtemp", MagicMock(return_value=""))
    @patch(
        "salt.utils.thin.tempfile.mkstemp", MagicMock(return_value=(3, ".temporary"))
    )
    @patch("salt.utils.thin.shutil", MagicMock())
    @patch("salt.utils.thin.sys.version_info", _version_info(3, 6))
    @patch("salt.utils.hashutils.DigestCollector", MagicMock())
    @patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/python"))
    def test_gen_thin_ext_alternative_content_files_written_py3(self):
        """
        Test thin.gen_thin function if external alternative content files are written.
        :return:
        """
        ext_conf = {
            "namespace": {
                "py-version": [3, 0],
                "path": "/opt/2015.8/salt",
                "dependencies": {
                    "certifi": "/opt/certifi",
                    "whatever": "/opt/whatever",
                },
            }
        }

        thin.gen_thin("", extended_cfg=ext_conf)
        files = []
        for py in ("pyall", "pyall", "py3"):
            for i in range(1, 4):
                files.append(os.path.join("namespace", py, "root", f"r{i}"))
            for i in range(4, 7):
                files.append(os.path.join("namespace", py, "root2", f"r{i}"))

        for idx, cl in enumerate(thin.tarfile.open().method_calls[:-6]):
            arcname = cl[2].get("arcname")
            self.assertIn(arcname, files)
            files.pop(files.index(arcname))
        self.assertFalse(files)

    def test_get_supported_py_config_typecheck(self):
        """
        Test collecting proper py-versions. Should return bytes type.
        :return:
        """
        tops = {}
        ext_cfg = {}
        out = thin._get_supported_py_config(tops=tops, extended_cfg=ext_cfg)
        assert type(salt.utils.stringutils.to_bytes("")) == type(out)

    def test_get_supported_py_config_base_tops(self):
        """
        Test collecting proper py-versions. Should return proper base tops.
        :return:
        """
        tops = {"3": ["/groundkeepers", "/stole"], "2": ["/the-root", "/password"]}
        ext_cfg = {}
        out = (
            salt.utils.stringutils.to_str(
                thin._get_supported_py_config(tops=tops, extended_cfg=ext_cfg)
            )
            .strip()
            .split(os.linesep)
        )
        self.assertEqual(len(out), 2)
        for t_line in ["py3:3:0", "py2:2:7"]:
            self.assertIn(t_line, out)

    def test_get_supported_py_config_ext_tops(self):
        """
        Test collecting proper py-versions. Should return proper ext conf tops.
        :return:
        """
        tops = {}
        ext_cfg = {
            "solar-interference": {"py-version": [2, 6]},
            "second-system-effect": {"py-version": [2, 7]},
        }
        out = (
            salt.utils.stringutils.to_str(
                thin._get_supported_py_config(tops=tops, extended_cfg=ext_cfg)
            )
            .strip()
            .split(os.linesep)
        )
        for t_line in ["second-system-effect:2:7", "solar-interference:2:6"]:
            self.assertIn(t_line, out)

    @patch("salt.exceptions.SaltSystemExit", Exception)
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.makedirs", MagicMock())
    @patch("salt.utils.files.fopen", MagicMock())
    @patch("salt.utils.thin._get_salt_call", MagicMock())
    @patch("salt.utils.thin._get_ext_namespaces", MagicMock())
    @patch("salt.utils.thin.get_tops", MagicMock(return_value=["/foo3", "/bar3"]))
    @patch("salt.utils.thin.get_ext_tops", MagicMock(return_value={}))
    @patch("salt.utils.thin.os.path.isfile", MagicMock())
    @patch("salt.utils.thin.os.path.isdir", MagicMock(return_value=False))
    @patch("salt.utils.thin.log", MagicMock())
    @patch("salt.utils.thin.os.remove", MagicMock())
    @patch("salt.utils.thin.os.path.exists", MagicMock())
    @patch("salt.utils.path.os_walk", MagicMock(return_value=[]))
    @patch(
        "salt.utils.thin.subprocess.Popen",
        _popen(
            None,
            side_effect=[(bts("2.7"), bts("")), (bts('["/foo27", "/bar27"]'), bts(""))],
        ),
    )
    @patch("salt.utils.thin.tarfile", MagicMock())
    @patch("salt.utils.thin.zipfile", MagicMock())
    @patch("salt.utils.thin.os.getcwd", MagicMock())
    @patch("salt.utils.thin.os.access", MagicMock(return_value=False))
    @patch("salt.utils.thin.os.chdir", MagicMock())
    @patch("salt.utils.thin.os.close", MagicMock())
    @patch("salt.utils.thin.tempfile.mkdtemp", MagicMock(return_value=""))
    @patch(
        "salt.utils.thin.tempfile.mkstemp", MagicMock(return_value=(3, ".temporary"))
    )
    @patch("salt.utils.thin.shutil", MagicMock())
    @patch("salt.utils.thin.sys.version_info", _version_info(3, 6))
    def test_gen_thin_control_files_written_access_denied_cwd(self):
        """
        Test thin.gen_thin function if control files are written (version, salt-call etc)
        when the current working directory is inaccessible, eg. Salt is configured to run as
        a non-root user but the command is executed in a directory that the user does not
        have permissions to.  Issue #54317.

        NOTE: Py2 version of this test is not required, as code shares the same spot across the versions.

        :return:
        """
        thin.gen_thin("")
        arc_name, arc_mode = thin.tarfile.method_calls[0][1]
        self.assertEqual(arc_name, ".temporary")
        self.assertEqual(arc_mode, "w:gz")
        for idx, fname in enumerate(
            ["version", ".thin-gen-py-version", "salt-call", "supported-versions"]
        ):
            name = thin.tarfile.open().method_calls[idx + 2][1][0]
            self.assertEqual(name, fname)
        thin.tarfile.open().close.assert_called()

    def test_get_tops_python(self):
        """
        test get_tops_python
        """
        patch_proc = patch(
            "salt.utils.thin.subprocess.Popen",
            self._popen(
                None,
                side_effect=[
                    (bts("jinja2/__init__.py"), bts("")),
                    (bts("yaml/__init__.py"), bts("")),
                    (bts("tornado/__init__.py"), bts("")),
                    (bts("msgpack/__init__.py"), bts("")),
                    (bts("certifi/__init__.py"), bts("")),
                    (bts("singledispatch.py"), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts("looseversion.py"), bts("")),
                    (bts("packaging/__init__.py"), bts("")),
                    (bts("distro.py"), bts("")),
                ],
            ),
        )

        patch_os = patch("os.path.exists", return_value=True)
        patch_which = patch("salt.utils.path.which", return_value=True)
        with patch_proc, patch_os, patch_which:
            with TstSuiteLoggingHandler() as log_handler:
                exp_ret = copy.deepcopy(self.exp_ret)
                ret = thin.get_tops_python("python3.7", ext_py_ver=[3, 7])
                if salt.utils.platform.is_windows():
                    for key, value in ret.items():
                        ret[key] = str(pathlib.Path(value).resolve(strict=False))
                    for key, value in exp_ret.items():
                        exp_ret[key] = str(pathlib.Path(value).resolve(strict=False))
                assert ret == exp_ret
                assert (
                    "ERROR:Could not auto detect file location for module concurrent"
                    " for python version python3.7" in log_handler.messages
                )

    def test_get_tops_python_exclude(self):
        """
        test get_tops_python when excluding modules
        """
        patch_proc = patch(
            "salt.utils.thin.subprocess.Popen",
            self._popen(
                None,
                side_effect=[
                    (bts("tornado/__init__.py"), bts("")),
                    (bts("msgpack/__init__.py"), bts("")),
                    (bts("certifi/__init__.py"), bts("")),
                    (bts("singledispatch.py"), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts("looseversion.py"), bts("")),
                    (bts("packaging/__init__.py"), bts("")),
                    (bts("distro.py"), bts("")),
                ],
            ),
        )
        exp_ret = copy.deepcopy(self.exp_ret)
        for lib in self.exc_libs:
            exp_ret.pop(lib)

        patch_os = patch("os.path.exists", return_value=True)
        patch_which = patch("salt.utils.path.which", return_value=True)
        with patch_proc, patch_os, patch_which:
            ret = thin.get_tops_python(
                "python3.7", exclude=self.exc_libs, ext_py_ver=[3, 7]
            )
            if salt.utils.platform.is_windows():
                for key, value in ret.items():
                    ret[key] = str(pathlib.Path(value).resolve(strict=False))
                for key, value in exp_ret.items():
                    exp_ret[key] = str(pathlib.Path(value).resolve(strict=False))
            assert ret == exp_ret

    def test_pack_alternatives_exclude(self):
        """
        test pack_alternatives when mixing
        manually set dependencies and auto
        detecting other modules.
        """
        patch_proc = patch(
            "salt.utils.thin.subprocess.Popen",
            self._popen(
                None,
                side_effect=[
                    (bts(self.fake_libs["distro"]), bts("")),
                    (bts(self.fake_libs["yaml"]), bts("")),
                    (bts(self.fake_libs["tornado"]), bts("")),
                    (bts(self.fake_libs["msgpack"]), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts(""), bts("")),
                    (bts("looseversion.py"), bts("")),
                    (bts("packaging/__init__.py"), bts("")),
                ],
            ),
        )

        patch_os = patch("os.path.exists", return_value=True)
        ext_conf = copy.deepcopy(self.ext_conf)
        ext_conf["test"]["auto_detect"] = True

        for lib in self.fake_libs.values():
            os.makedirs(lib)
            with salt.utils.files.fopen(os.path.join(lib, "__init__.py"), "w+") as fp_:
                fp_.write("test")

        exp_files = self.exp_files.copy()
        exp_files.extend(
            [
                os.path.join("yaml", "__init__.py"),
                os.path.join("tornado", "__init__.py"),
                os.path.join("msgpack", "__init__.py"),
            ]
        )

        patch_which = patch("salt.utils.path.which", return_value=True)

        with patch_os, patch_proc, patch_which:
            thin._pack_alternative(ext_conf, self.digest, self.tar)
            calls = self.tar.mock_calls
            for _file in exp_files:
                assert [x for x in calls if f"{_file}" in x[-2]]

    def test_pack_alternatives(self):
        """
        test thin._pack_alternatives
        """
        with patch("salt.utils.thin.get_ext_tops", MagicMock(return_value=self.tops)):
            thin._pack_alternative(self.ext_conf, self.digest, self.tar)
            calls = self.tar.mock_calls
            for _file in self.exp_files:
                assert [x for x in calls if f"{_file}" in x[-2]]
                assert [
                    x
                    for x in calls
                    if os.path.join("test", "pyall", _file) in x[-1]["arcname"]
                ]

    def test_pack_alternatives_not_normalized(self):
        """
        test thin._pack_alternatives when the path
        is not normalized
        """
        tops = copy.deepcopy(self.tops)
        tops["test"]["dependencies"] = [self.jinja_fp + "/"]
        with patch("salt.utils.thin.get_ext_tops", MagicMock(return_value=tops)):
            thin._pack_alternative(self.ext_conf, self.digest, self.tar)
            calls = self.tar.mock_calls
            for _file in self.exp_files:
                assert [x for x in calls if f"{_file}" in x[-2]]
                assert [
                    x
                    for x in calls
                    if os.path.join("test", "pyall", _file) in x[-1]["arcname"]
                ]

    def test_pack_alternatives_path_doesnot_exist(self):
        """
        test thin._pack_alternatives when the path
        doesnt exist. Check error log message
        and expect that because the directory
        does not exist jinja2 does not get
        added to the tar
        """
        bad_path = os.path.join(tempfile.gettempdir(), "doesnotexisthere")
        tops = copy.deepcopy(self.tops)
        tops["test"]["dependencies"] = [bad_path]
        with patch("salt.utils.thin.get_ext_tops", MagicMock(return_value=tops)):
            with TstSuiteLoggingHandler() as log_handler:
                thin._pack_alternative(self.ext_conf, self.digest, self.tar)
                msg = "ERROR:File path {} does not exist. Unable to add to salt-ssh thin".format(
                    bad_path
                )
                assert msg in log_handler.messages
        calls = self.tar.mock_calls
        for _file in self.exp_files:
            arg = [x for x in calls if f"{_file}" in x[-2]]
            kwargs = [
                x
                for x in calls
                if os.path.join("test", "pyall", _file) in x[-1]["arcname"]
            ]
            if "jinja2" in _file:
                assert not arg
                assert not kwargs
            else:
                assert arg
                assert kwargs

    def test_pack_alternatives_auto_detect(self):
        """
        test thin._pack_alternatives when auto_detect
        is enabled
        """
        ext_conf = copy.deepcopy(self.ext_conf)
        ext_conf["test"]["auto_detect"] = True

        for lib in self.fake_libs.values():
            os.makedirs(lib)
            with salt.utils.files.fopen(os.path.join(lib, "__init__.py"), "w+") as fp_:
                fp_.write("test")

        patch_tops_py = patch(
            "salt.utils.thin.get_tops_python", return_value=self.fake_libs
        )

        exp_files = self.exp_files.copy()
        exp_files.extend(
            [
                os.path.join("yaml", "__init__.py"),
                os.path.join("tornado", "__init__.py"),
                os.path.join("msgpack", "__init__.py"),
            ]
        )
        with patch_tops_py:
            thin._pack_alternative(ext_conf, self.digest, self.tar)
            calls = self.tar.mock_calls
            for _file in exp_files:
                assert [x for x in calls if f"{_file}" in x[-2]]

    def test_pack_alternatives_empty_dependencies(self):
        """
        test _pack_alternatives when dependencies is not
        set in the config.
        """
        ext_conf = copy.deepcopy(self.ext_conf)
        ext_conf["test"]["auto_detect"] = True
        ext_conf["test"].pop("dependencies")

        for lib in self.fake_libs.values():
            os.makedirs(lib)
            with salt.utils.files.fopen(os.path.join(lib, "__init__.py"), "w+") as fp_:
                fp_.write("test")

        patch_tops_py = patch(
            "salt.utils.thin.get_tops_python", return_value=self.fake_libs
        )

        exp_files = self.exp_files.copy()
        exp_files.extend(
            [
                os.path.join("yaml", "__init__.py"),
                os.path.join("tornado", "__init__.py"),
                os.path.join("msgpack", "__init__.py"),
            ]
        )
        with patch_tops_py:
            thin._pack_alternative(ext_conf, self.digest, self.tar)
            calls = self.tar.mock_calls
            for _file in exp_files:
                assert [x for x in calls if f"{_file}" in x[-2]]

    @pytest.mark.slow_test
    @pytest.mark.skip_on_windows(reason="salt-ssh does not deploy to/from windows")
    def test_thin_dir(self):
        """
        Test the thin dir to make sure salt-call can run

        Run salt call via a python in a new virtual environment to ensure
        salt-call has all dependencies needed.
        """
        # This was previously an integration test and is now here, as a unit test.
        # Should actually be a functional test
        with VirtualEnv() as venv:
            salt.utils.thin.gen_thin(str(venv.venv_dir))
            thin_dir = venv.venv_dir / "thin"
            thin_archive = thin_dir / "thin.tgz"
            tar = tarfile.open(str(thin_archive))
            tar.extractall(str(thin_dir))  # nosec
            tar.close()
            ret = venv.run(
                venv.venv_python,
                str(thin_dir / "salt-call"),
                "--version",
                check=False,
            )
            assert ret.returncode == 0, ret
