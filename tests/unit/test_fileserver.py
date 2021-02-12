"""
    :codeauthor: Joao Mesquita <jmesquita@sangoma.com>
"""


from salt import fileserver
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class MapDiffTestCase(TestCase):
    def test_diff_with_diffent_keys(self):
        """
        Test that different maps are indeed reported different
        """
        map1 = {"file1": 1234}
        map2 = {"file2": 1234}
        assert fileserver.diff_mtime_map(map1, map2) is True

    def test_diff_with_diffent_values(self):
        """
        Test that different maps are indeed reported different
        """
        map1 = {"file1": 12345}
        map2 = {"file1": 1234}
        assert fileserver.diff_mtime_map(map1, map2) is True


class VCSBackendWhitelistCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {fileserver: {}}

    def test_whitelist(self):
        opts = {
            "fileserver_backend": ["roots", "git", "s3fs", "hgfs", "svn"],
            "extension_modules": "",
        }
        fs = fileserver.Fileserver(opts)
        assert sorted(fs.servers.whitelist) == sorted(
            ["git", "gitfs", "hg", "hgfs", "svn", "svnfs", "roots", "s3fs"]
        ), fs.servers.whitelist
