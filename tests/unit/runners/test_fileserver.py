# -*- coding: utf-8 -*-
"""
unit tests for the fileserver runner
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt libs
import salt.loader
import salt.runners.fileserver as fileserver
import salt.utils.files

# Import testing libs
from tests.support.helpers import with_tempdir
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DummyFS(object):
    """
    Dummy object to provide the attributes needed to run unit tests
    """

    def __init__(self, backends):
        self.backends = backends

    def keys(self):
        return ["{0}.envs".format(x) for x in self.backends]


class FileserverTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the cache runner
    """

    def setup_loader_modules(self):
        return {fileserver: {"__opts__": {"extension_modules": ""}}}

    def _make_file_lists_cache(self, cachedir, backends):
        """
        Create some dummy files to represent file list caches, as well as other
        files that aren't file list caches, so that we can confirm that *only*
        the cache files are touched. Create a dir for each configured backend,
        as well as for the roots backend (which is *not* configured as a
        backend in this test), so that we can ensure that its cache is left
        alone.
        """
        for back in backends:
            back_cachedir = os.path.join(cachedir, "file_lists", back)
            # Make file_lists cachedir
            os.makedirs(os.path.join(back_cachedir))
            # Touch a couple files
            for filename in ("base.p", "dev.p", "foo.txt"):
                with salt.utils.files.fopen(os.path.join(back_cachedir, filename), "w"):
                    pass

    @with_tempdir()
    def test_clear_file_list_cache_vcs(self, cachedir):
        """
        Test that VCS backends are cleared irrespective of whether they are
        configured as gitfs/git, hgfs/hg, svnfs/svn.
        """
        # Mixture of VCS backends specified with and without "fs" at the end,
        # to confirm that the correct dirs are cleared.
        backends = ["gitfs", "hg", "svnfs"]
        opts = {
            "fileserver_backend": backends,
            "cachedir": cachedir,
        }
        mock_fs = DummyFS(backends)

        self._make_file_lists_cache(cachedir, backends + ["roots"])

        with patch.dict(fileserver.__opts__, opts), patch.object(
            salt.loader, "fileserver", MagicMock(return_value=mock_fs)
        ):
            cleared = fileserver.clear_file_list_cache()

        # Make sure the return data matches what you'd expect
        expected = {
            "gitfs": ["base", "dev"],
            "hg": ["base", "dev"],
            "svnfs": ["base", "dev"],
        }
        assert cleared == expected, cleared

        # Trust, but verify! Check that the correct files are actually gone
        assert not os.path.exists(
            os.path.join(cachedir, "file_lists", "gitfs", "base.p")
        )
        assert not os.path.exists(
            os.path.join(cachedir, "file_lists", "gitfs", "dev.p")
        )
        assert not os.path.exists(os.path.join(cachedir, "file_lists", "hg", "base.p"))
        assert not os.path.exists(
            os.path.join(cachedir, "file_lists", "gitfs", "dev.p")
        )
        assert not os.path.exists(os.path.join(cachedir, "file_lists", "hg", "base.p"))
        assert not os.path.exists(
            os.path.join(cachedir, "file_lists", "svnfs", "dev.p")
        )

        # These files *should* exist and shouldn't have been cleaned
        assert os.path.exists(os.path.join(cachedir, "file_lists", "gitfs", "foo.txt"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "hg", "foo.txt"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "svnfs", "foo.txt"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "roots", "base.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "roots", "dev.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "roots", "foo.txt"))

    @with_tempdir()
    def test_clear_file_list_cache_vcs_limited(self, cachedir):
        """
        Test the arguments to limit what is cleared
        """
        # Mixture of VCS backends specified with and without "fs" at the end,
        # to confirm that the correct dirs are cleared.
        backends = ["gitfs", "hg", "svnfs"]
        opts = {
            "fileserver_backend": backends,
            "cachedir": cachedir,
        }
        mock_fs = DummyFS(backends)

        self._make_file_lists_cache(cachedir, backends + ["roots"])

        with patch.dict(fileserver.__opts__, opts), patch.object(
            salt.loader, "fileserver", MagicMock(return_value=mock_fs)
        ):
            cleared = fileserver.clear_file_list_cache(saltenv="base", backend="gitfs")

        expected = {"gitfs": ["base"]}
        assert cleared == expected, cleared

        # Trust, but verify! Check that the correct files are actually gone
        assert not os.path.exists(
            os.path.join(cachedir, "file_lists", "gitfs", "base.p")
        )

        # These files *should* exist and shouldn't have been cleaned
        assert os.path.exists(os.path.join(cachedir, "file_lists", "gitfs", "dev.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "gitfs", "foo.txt"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "hg", "base.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "hg", "dev.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "hg", "foo.txt"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "svnfs", "base.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "svnfs", "dev.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "svnfs", "foo.txt"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "roots", "base.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "roots", "dev.p"))
        assert os.path.exists(os.path.join(cachedir, "file_lists", "roots", "foo.txt"))
