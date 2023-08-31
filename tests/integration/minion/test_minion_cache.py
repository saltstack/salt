import os

import salt.loader
import salt.minion
import salt.utils.yaml
from salt.utils.files import fopen
from tests.support.case import ModuleCase
from tests.support.helpers import with_tempdir
from tests.support.mock import patch


class BasePillarTest(ModuleCase):
    @with_tempdir()
    def test_minion_cache_should_cache_files(self, tempdir):
        pillar = {"this": {"is": {"some": "pillar data"}}}
        opts = {
            "file_client": "remote",
            "minion_pillar_cache": "true",
            "master_type": "local",
            "discovery": False,
            "master": "local",
            "__role": "",
            "id": "test",
            "saltenv": "base",
            "pillar_cache": True,
            "pillar_cache_backend": "disk",
            "pillar_cache_ttl": 3600,
            "cachedir": tempdir,
            "state_top": "top.sls",
            "pillar_roots": {"base": tempdir},
            "extension_modules": tempdir,
            "file_ignore_regex": [],
            "file_ignore_glob": [],
            "pillar": pillar,
        }
        with patch("salt.loader.grains", return_value={}), patch(
            "salt.minion.SMinion.gen_modules"
        ), patch("tornado.ioloop.IOLoop.current"):
            minion = salt.minion.SMinion(opts)
            self.assertTrue("pillar" in os.listdir(tempdir))
            pillar_cache = os.path.join(tempdir, "pillar")
            self.assertTrue("top.sls" in os.listdir(pillar_cache))
            self.assertTrue("cache.sls" in os.listdir(pillar_cache))
            with fopen(os.path.join(pillar_cache, "cache.sls"), "rb") as f:
                cached_data = salt.utils.yaml.safe_load(f)
                assert cached_data == pillar
