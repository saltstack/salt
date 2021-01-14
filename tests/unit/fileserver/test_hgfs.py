import salt.fileserver.hgfs as hgfs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class HgfsFileTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {hgfs: {}}

    def test_env_is_exposed(self):
        """
        test _env_is_exposed method when
        base is in whitelist
        """
        with patch.dict(
            hgfs.__opts__,
            {"hgfs_saltenv_whitelist": "base", "hgfs_saltenv_blacklist": ""},
        ):
            assert hgfs._env_is_exposed("base")

    def test_env_is_exposed_blacklist(self):
        """
        test _env_is_exposed method when
        base is in blacklist
        """
        with patch.dict(
            hgfs.__opts__,
            {"hgfs_saltenv_whitelist": "", "hgfs_saltenv_blacklist": "base"},
        ):
            assert not hgfs._env_is_exposed("base")

    @skipIf(not hgfs.HAS_HG, "hglib needs to be installed")
    def test_fix_58852(self):
        """
        test to make sure python 3 can init hgfs
        """
        with patch.dict(
            hgfs.__opts__,
            {
                "cachedir": "/tmp/barf",
                "hgfs_base": "fnord",
                "hgfs_branch_method": "fnord",
                "hgfs_mountpoint": "fnord",
                "hgfs_root": "fnord",
                "hgfs_remotes": "fnord",
            },
        ):
            self.assertIsInstance(hgfs.init(), list)
