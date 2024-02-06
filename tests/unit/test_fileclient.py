"""
    :codeauthor: Erik Johnson <palehose@gmail.com>
"""

import salt.config
from salt import fileclient
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class FSClientTestCase(TestCase):
    def _get_defaults(self, **kwargs):
        """
        master/minion config defaults
        """
        ret = {
            "saltenv": kwargs.pop("saltenv", None),
            "id": "test",
            "cachedir": "/A",
            "sock_dir": "/B",
            "root_dir": "/C",
            "fileserver_backend": "roots",
            "open_mode": False,
            "auto_accept": False,
            "file_roots": {},
            "pillar_roots": {},
            "file_ignore_glob": [],
            "file_ignore_regex": [],
            "worker_threads": 5,
            "hash_type": "sha256",
            "log_file": "foo.log",
            "ssl": True,
            "file_client": "local",
        }
        ret.update(kwargs)
        return ret

    def test_master_no_fs_update(self):
        """
        Test that an FSClient spawned from the master does not cause fileserver
        backends to be refreshed on instantiation. The master already has the
        maintenance thread for that.
        """
        opts = salt.config.apply_master_config(defaults=self._get_defaults())
        fileserver = MagicMock()

        with patch("salt.fileserver.Fileserver", fileserver):
            client = fileclient.FSClient(opts)
            assert client.channel.fs.update.call_count == 0

    def test_masterless_fs_update(self):
        """
        Test that an FSClient spawned from a masterless run refreshes the
        fileserver backends. This is necessary to ensure that a masterless run
        can access any configured gitfs remotes.
        """
        opts = salt.config.apply_minion_config(defaults=self._get_defaults())
        fileserver = MagicMock()

        with patch("salt.fileserver.Fileserver", fileserver):
            client = fileclient.FSClient(opts)
            assert client.channel.fs.update.call_count == 1
