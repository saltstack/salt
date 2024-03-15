import logging
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

import pytest

import salt.modules.cmdmod as cmd
import salt.modules.virtualenv_mod
import salt.modules.zcbuildout as buildout
import salt.utils.files
import salt.utils.path
import salt.utils.platform
from tests.support.helpers import patched_environ
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
    pytest.mark.skip_on_windows(
        reason=(
            "Special steps are required for proper SSL validation because "
            "`easy_install` is too old(and deprecated)."
        )
    ),
]

KNOWN_VIRTUALENV_BINARY_NAMES = (
    "virtualenv",
    "virtualenv2",
    "virtualenv-2.6",
    "virtualenv-2.7",
)

BOOT_INIT = {
    1: ["var/ver/1/bootstrap/bootstrap.py"],
    2: ["var/ver/2/bootstrap/bootstrap.py", "b/bootstrap.py"],
}

log = logging.getLogger(__name__)


def download_to(url, dest):
    req = urllib.request.Request(url)
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36",
    )
    with salt.utils.files.fopen(dest, "wb") as fic:
        fic.write(urllib.request.urlopen(req, timeout=10).read())


class Base(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            buildout: {
                "__salt__": {
                    "cmd.run_all": cmd.run_all,
                    "cmd.run": cmd.run,
                    "cmd.retcode": cmd.retcode,
                }
            }
        }

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

        cls.root = os.path.join(RUNTIME_VARS.BASE_FILES, "buildout")
        cls.rdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        cls.tdir = os.path.join(cls.rdir, "test")
        for idx, url in buildout._URL_VERSIONS.items():
            log.debug("Downloading bootstrap from %s", url)
            dest = os.path.join(cls.rdir, f"{idx}_bootstrap.py")
            try:
                download_to(url, dest)
            except urllib.error.URLError as exc:
                log.debug("Failed to download %s: %s", url, exc)
        # creating a new setuptools install
        cls.ppy_st = os.path.join(cls.rdir, "psetuptools")
        if salt.utils.platform.is_windows():
            cls.bin_st = os.path.join(cls.ppy_st, "Scripts")
            cls.py_st = os.path.join(cls.bin_st, "python")
        else:
            cls.bin_st = os.path.join(cls.ppy_st, "bin")
            cls.py_st = os.path.join(cls.bin_st, "python")
        # `--no-site-packages` has been deprecated
        # https://virtualenv.pypa.io/en/stable/reference/#cmdoption-no-site-packages
        subprocess.check_call(
            [salt.utils.path.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES), cls.ppy_st]
        )
        # Setuptools >=53.0.0 no longer has easy_install
        # Between 50.0.0 and 53.0.0 it has problems with salt, use an older version
        subprocess.check_call(
            [os.path.join(cls.bin_st, "pip"), "install", "-U", "setuptools<50.0.0"]
        )
        # distribute has been merged back in to setuptools as of v0.7. So, no
        # need to upgrade distribute, but this seems to be the only way to get
        # the binary in the right place
        # https://packaging.python.org/key_projects/#setuptools
        # Additionally, this part may fail if the certificate store is outdated
        # on Windows, as it would be in a fresh installation for example. The
        # following commands will fix that. This should be part of the golden
        # images. (https://github.com/saltstack/salt-jenkins/pull/1479)
        # certutil -generateSSTFromWU roots.sst
        # powershell "(Get-ChildItem -Path .\roots.sst) | Import-Certificate -CertStoreLocation Cert:\LocalMachine\Root"
        subprocess.check_call(
            [os.path.join(cls.bin_st, "easy_install"), "-U", "distribute"]
        )

    def setUp(self):
        if salt.utils.platform.is_darwin():
            self.patched_environ = patched_environ(__cleanup__=["__PYVENV_LAUNCHER__"])
            self.patched_environ.__enter__()  # pylint: disable=unnecessary-dunder-call
            self.addCleanup(self.patched_environ.__exit__)

        super().setUp()
        self._remove_dir()
        shutil.copytree(self.root, self.tdir)

        for idx in BOOT_INIT:
            path = os.path.join(self.rdir, f"{idx}_bootstrap.py")
            for fname in BOOT_INIT[idx]:
                shutil.copy2(path, os.path.join(self.tdir, fname))

    def tearDown(self):
        super().tearDown()
        self._remove_dir()

    def _remove_dir(self):
        if os.path.isdir(self.tdir):
            shutil.rmtree(self.tdir)


@pytest.mark.skip_if_binaries_missing(*KNOWN_VIRTUALENV_BINARY_NAMES, check_all=False)
@pytest.mark.requires_network
class BuildoutTestCase(Base):
    @pytest.mark.slow_test
    def test_onlyif_unless(self):
        b_dir = os.path.join(self.tdir, "b")
        ret = buildout.buildout(b_dir, onlyif=RUNTIME_VARS.SHELL_FALSE_PATH)
        self.assertTrue(ret["comment"] == "onlyif condition is false")
        self.assertTrue(ret["status"] is True)
        ret = buildout.buildout(b_dir, unless=RUNTIME_VARS.SHELL_TRUE_PATH)
        self.assertTrue(ret["comment"] == "unless condition is true")
        self.assertTrue(ret["status"] is True)

    @pytest.mark.slow_test
    def test_salt_callback(self):
        @buildout._salt_callback
        def callback1(a, b=1):
            for i in buildout.LOG.levels:
                getattr(buildout.LOG, i)(f"{i[0]}bar")
            return "foo"

        def callback2(a, b=1):
            raise Exception("foo")

        # pylint: disable=invalid-sequence-index
        ret1 = callback1(1, b=3)
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        # self.assertEqual(ret1['status'], True)
        # self.assertEqual(ret1['logs_by_level']['warn'], ['wbar'])
        # self.assertEqual(ret1['comment'], '')
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        # self.assertTrue(
        #     u''
        #     u'OUTPUT:\n'
        #     u'foo\n'
        #     u''
        #    in ret1['outlog']
        # )

        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        # self.assertTrue(u'Log summary:\n' in ret1['outlog'])
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        # self.assertTrue(
        #     u'INFO: ibar\n'
        #     u'WARN: wbar\n'
        #     u'DEBUG: dbar\n'
        #     u'ERROR: ebar\n'
        #    in ret1['outlog']
        # )
        # These lines are throwing pylint errors - disabling for now since we are skipping
        # these tests
        # self.assertTrue('by level' in ret1['outlog_by_level'])
        # self.assertEqual(ret1['out'], 'foo')
        ret2 = buildout._salt_callback(callback2)(2, b=6)
        self.assertEqual(ret2["status"], False)
        self.assertTrue(ret2["logs_by_level"]["error"][0].startswith("Traceback"))
        self.assertTrue("Unexpected response from buildout" in ret2["comment"])
        self.assertEqual(ret2["out"], None)
        for l in buildout.LOG.levels:
            self.assertTrue(0 == len(buildout.LOG.by_level[l]))
        # pylint: enable=invalid-sequence-index

    @pytest.mark.slow_test
    def test_get_bootstrap_url(self):
        for path in [
            os.path.join(self.tdir, "var/ver/1/dumppicked"),
            os.path.join(self.tdir, "var/ver/1/versions"),
        ]:
            self.assertEqual(
                buildout._URL_VERSIONS[1],
                buildout._get_bootstrap_url(path),
                f"b1 url for {path}",
            )
        for path in [
            os.path.join(self.tdir, "/non/existing"),
            os.path.join(self.tdir, "var/ver/2/versions"),
            os.path.join(self.tdir, "var/ver/2/default"),
        ]:
            self.assertEqual(
                buildout._URL_VERSIONS[2],
                buildout._get_bootstrap_url(path),
                f"b2 url for {path}",
            )

    @pytest.mark.slow_test
    def test_get_buildout_ver(self):
        for path in [
            os.path.join(self.tdir, "var/ver/1/dumppicked"),
            os.path.join(self.tdir, "var/ver/1/versions"),
        ]:
            self.assertEqual(1, buildout._get_buildout_ver(path), f"1 for {path}")
        for path in [
            os.path.join(self.tdir, "/non/existing"),
            os.path.join(self.tdir, "var/ver/2/versions"),
            os.path.join(self.tdir, "var/ver/2/default"),
        ]:
            self.assertEqual(2, buildout._get_buildout_ver(path), f"2 for {path}")

    @pytest.mark.slow_test
    def test_get_bootstrap_content(self):
        self.assertEqual(
            "",
            buildout._get_bootstrap_content(os.path.join(self.tdir, "non", "existing")),
        )
        self.assertEqual(
            "",
            buildout._get_bootstrap_content(os.path.join(self.tdir, "var", "tb", "1")),
        )

        if (
            salt.utils.platform.is_windows()
            and os.environ.get("GITHUB_ACTIONS_PIPELINE", "0") == "0"
        ):
            line_break = "\r\n"
        else:
            line_break = "\n"
        self.assertEqual(
            f"# pylint: skip-file{line_break}foo{line_break}",
            buildout._get_bootstrap_content(os.path.join(self.tdir, "var", "tb", "2")),
        )

    @pytest.mark.slow_test
    def test_logger_clean(self):
        buildout.LOG.clear()
        # nothing in there
        self.assertTrue(
            True
            not in [len(buildout.LOG.by_level[a]) > 0 for a in buildout.LOG.by_level]
        )
        buildout.LOG.info("foo")
        self.assertTrue(
            True in [len(buildout.LOG.by_level[a]) > 0 for a in buildout.LOG.by_level]
        )
        buildout.LOG.clear()
        self.assertTrue(
            True
            not in [len(buildout.LOG.by_level[a]) > 0 for a in buildout.LOG.by_level]
        )

    @pytest.mark.slow_test
    def test_logger_loggers(self):
        buildout.LOG.clear()
        # nothing in there
        for i in buildout.LOG.levels:
            getattr(buildout.LOG, i)("foo")
            getattr(buildout.LOG, i)("bar")
            getattr(buildout.LOG, i)("moo")
            self.assertTrue(len(buildout.LOG.by_level[i]) == 3)
            self.assertEqual(buildout.LOG.by_level[i][0], "foo")
            self.assertEqual(buildout.LOG.by_level[i][-1], "moo")

    @pytest.mark.slow_test
    def test__find_cfgs(self):
        result = sorted(
            a.replace(self.root, "") for a in buildout._find_cfgs(self.root)
        )
        assertlist = sorted(
            [
                os.path.join(os.sep, "buildout.cfg"),
                os.path.join(os.sep, "c", "buildout.cfg"),
                os.path.join(os.sep, "etc", "buildout.cfg"),
                os.path.join(os.sep, "e", "buildout.cfg"),
                os.path.join(os.sep, "b", "buildout.cfg"),
                os.path.join(os.sep, "b", "bdistribute", "buildout.cfg"),
                os.path.join(os.sep, "b", "b2", "buildout.cfg"),
                os.path.join(os.sep, "foo", "buildout.cfg"),
            ]
        )
        self.assertEqual(result, assertlist)

    def skip_test_upgrade_bootstrap(self):
        b_dir = os.path.join(self.tdir, "b")
        bpy = os.path.join(b_dir, "bootstrap.py")
        buildout.upgrade_bootstrap(b_dir)
        time1 = os.stat(bpy).st_mtime
        with salt.utils.files.fopen(bpy) as fic:
            data = fic.read()
        self.assertTrue("setdefaulttimeout(2)" in data)
        flag = os.path.join(b_dir, ".buildout", "2.updated_bootstrap")
        self.assertTrue(os.path.exists(flag))
        buildout.upgrade_bootstrap(b_dir, buildout_ver=1)
        time2 = os.stat(bpy).st_mtime
        with salt.utils.files.fopen(bpy) as fic:
            data = fic.read()
        self.assertTrue("setdefaulttimeout(2)" in data)
        flag = os.path.join(b_dir, ".buildout", "1.updated_bootstrap")
        self.assertTrue(os.path.exists(flag))
        buildout.upgrade_bootstrap(b_dir, buildout_ver=1)
        time3 = os.stat(bpy).st_mtime
        self.assertNotEqual(time2, time1)
        self.assertEqual(time2, time3)


@pytest.mark.skip_if_binaries_missing(*KNOWN_VIRTUALENV_BINARY_NAMES, check_all=False)
@pytest.mark.requires_network
class BuildoutOnlineTestCase(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ppy_dis = os.path.join(cls.rdir, "pdistribute")
        cls.ppy_blank = os.path.join(cls.rdir, "pblank")
        cls.py_dis = os.path.join(cls.ppy_dis, "bin", "python")
        cls.py_blank = os.path.join(cls.ppy_blank, "bin", "python")
        # creating a distribute based install
        try:
            # `--no-site-packages` has been deprecated
            # https://virtualenv.pypa.io/en/stable/reference/#cmdoption-no-site-packages
            subprocess.check_call(
                [
                    salt.utils.path.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    "--no-setuptools",
                    "--no-pip",
                    cls.ppy_dis,
                ]
            )
        except subprocess.CalledProcessError:
            subprocess.check_call(
                [salt.utils.path.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES), cls.ppy_dis]
            )

            url = (
                "https://pypi.python.org/packages/source"
                "/d/distribute/distribute-0.6.43.tar.gz"
            )
            download_to(
                url,
                os.path.join(cls.ppy_dis, "distribute-0.6.43.tar.gz"),
            )

            subprocess.check_call(
                [
                    "tar",
                    "-C",
                    cls.ppy_dis,
                    "-xzvf",
                    f"{cls.ppy_dis}/distribute-0.6.43.tar.gz",
                ]
            )

            subprocess.check_call(
                [
                    f"{cls.ppy_dis}/bin/python",
                    f"{cls.ppy_dis}/distribute-0.6.43/setup.py",
                    "install",
                ]
            )

        # creating a blank based install
        try:
            subprocess.check_call(
                [
                    salt.utils.path.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    "--no-setuptools",
                    "--no-pip",
                    cls.ppy_blank,
                ]
            )
        except subprocess.CalledProcessError:
            subprocess.check_call(
                [
                    salt.utils.path.which_bin(KNOWN_VIRTUALENV_BINARY_NAMES),
                    cls.ppy_blank,
                ]
            )

    @pytest.mark.skip(reason="TODO this test should probably be fixed")
    def test_buildout_bootstrap(self):
        b_dir = os.path.join(self.tdir, "b")
        bd_dir = os.path.join(self.tdir, "b", "bdistribute")
        b2_dir = os.path.join(self.tdir, "b", "b2")
        self.assertTrue(buildout._has_old_distribute(self.py_dis))
        # this is too hard to check as on debian & other where old
        # packages are present (virtualenv), we can't have
        # a clean site-packages
        # self.assertFalse(buildout._has_old_distribute(self.py_blank))
        self.assertFalse(buildout._has_old_distribute(self.py_st))
        self.assertFalse(buildout._has_setuptools7(self.py_dis))
        self.assertTrue(buildout._has_setuptools7(self.py_st))
        self.assertFalse(buildout._has_setuptools7(self.py_blank))

        ret = buildout.bootstrap(bd_dir, buildout_ver=1, python=self.py_dis)
        comment = ret["outlog"]
        self.assertTrue("--distribute" in comment)
        self.assertTrue("Generated script" in comment)

        ret = buildout.bootstrap(b_dir, buildout_ver=1, python=self.py_blank)
        comment = ret["outlog"]
        # as we may have old packages, this test the two
        # behaviors (failure with old setuptools/distribute)
        self.assertTrue(
            ("Got " in comment and "Generated script" in comment)
            or ("setuptools>=0.7" in comment)
        )

        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_blank)
        comment = ret["outlog"]
        self.assertTrue(
            ("setuptools" in comment and "Generated script" in comment)
            or ("setuptools>=0.7" in comment)
        )

        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_st)
        comment = ret["outlog"]
        self.assertTrue(
            ("setuptools" in comment and "Generated script" in comment)
            or ("setuptools>=0.7" in comment)
        )

        ret = buildout.bootstrap(b2_dir, buildout_ver=2, python=self.py_st)
        comment = ret["outlog"]
        self.assertTrue(
            ("setuptools" in comment and "Creating directory" in comment)
            or ("setuptools>=0.7" in comment)
        )

    @pytest.mark.slow_test
    def test_run_buildout(self):
        if salt.modules.virtualenv_mod.virtualenv_ver(self.ppy_st) >= (20, 0, 0):
            self.skipTest(
                "Skiping until upstream resolved"
                " https://github.com/pypa/virtualenv/issues/1715"
            )

        b_dir = os.path.join(self.tdir, "b")
        ret = buildout.bootstrap(b_dir, buildout_ver=2, python=self.py_st)
        self.assertTrue(ret["status"])
        ret = buildout.run_buildout(b_dir, parts=["a", "b"])
        out = ret["out"]
        self.assertTrue("Installing a" in out)
        self.assertTrue("Installing b" in out)

    @pytest.mark.slow_test
    def test_buildout(self):
        if salt.modules.virtualenv_mod.virtualenv_ver(self.ppy_st) >= (20, 0, 0):
            self.skipTest(
                "Skiping until upstream resolved"
                " https://github.com/pypa/virtualenv/issues/1715"
            )

        b_dir = os.path.join(self.tdir, "b")
        ret = buildout.buildout(b_dir, buildout_ver=2, python=self.py_st)
        self.assertTrue(ret["status"])
        out = ret["out"]
        comment = ret["comment"]
        self.assertTrue(ret["status"])
        self.assertIn("Creating directory", out)
        self.assertIn("Installing a.", out)
        self.assertTrue(f"{self.py_st} bootstrap.py" in comment)
        self.assertTrue("buildout -c buildout.cfg" in comment)
        ret = buildout.buildout(
            b_dir, parts=["a", "b", "c"], buildout_ver=2, python=self.py_st
        )
        outlog = ret["outlog"]
        out = ret["out"]
        comment = ret["comment"]
        self.assertIn("Installing single part: a", outlog)
        self.assertIn("buildout -c buildout.cfg -N install a", comment)
        self.assertIn("Installing b.", out)
        self.assertIn("Installing c.", out)
        ret = buildout.buildout(
            b_dir, parts=["a", "b", "c"], buildout_ver=2, newest=True, python=self.py_st
        )
        outlog = ret["outlog"]
        out = ret["out"]
        comment = ret["comment"]
        self.assertIn("buildout -c buildout.cfg -n install a", comment)


# TODO: Is this test even still needed?
class BuildoutAPITestCase(TestCase):
    def test_merge(self):
        buildout.LOG.clear()
        buildout.LOG.info("àé")
        buildout.LOG.info("àé")
        buildout.LOG.error("àé")
        buildout.LOG.error("àé")
        ret1 = buildout._set_status({}, out="éà")
        uret1 = buildout._set_status({}, out="éà")
        buildout.LOG.clear()
        buildout.LOG.info("ççàé")
        buildout.LOG.info("ççàé")
        buildout.LOG.error("ççàé")
        buildout.LOG.error("ççàé")
        ret2 = buildout._set_status({}, out="çéà")
        uret2 = buildout._set_status({}, out="çéà")
        uretm = buildout._merge_statuses([ret1, uret1, ret2, uret2])
        for ret in ret1, uret1, ret2, uret2:
            out = ret["out"]
            if not isinstance(ret["out"], str):
                out = ret["out"].decode("utf-8")

        for out in ["àé", "ççàé"]:
            self.assertIn(out, uretm["logs_by_level"]["info"])
            self.assertIn(out, uretm["outlog_by_level"])

    def test_setup(self):
        buildout.LOG.clear()
        buildout.LOG.info("àé")
        buildout.LOG.info("àé")
        buildout.LOG.error("àé")
        buildout.LOG.error("àé")
        ret = buildout._set_status({}, out="éà")
        uret = buildout._set_status({}, out="éà")
        self.assertTrue(ret["outlog"] == uret["outlog"])
        self.assertTrue("àé" in uret["outlog_by_level"])
