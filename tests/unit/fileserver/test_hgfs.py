# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.fileserver.hgfs as hgfs

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


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
