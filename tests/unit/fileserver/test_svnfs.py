import salt.fileserver.svnfs as svnfs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class SvnfsFileTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {svnfs: {}}

    def test_env_is_exposed(self):
        """
        test _env_is_exposed method when
        base is in whitelist
        """
        with patch.dict(
            svnfs.__opts__,
            {"svnfs_saltenv_whitelist": "base", "svnfs_saltenv_blacklist": ""},
        ):
            assert svnfs._env_is_exposed("base")

    def test_env_is_exposed_blacklist(self):
        """
        test _env_is_exposed method when
        base is in blacklist
        """
        with patch.dict(
            svnfs.__opts__,
            {"svnfs_saltenv_whitelist": "", "svnfs_saltenv_blacklist": "base"},
        ):
            assert not svnfs._env_is_exposed("base")
