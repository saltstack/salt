"""
unit tests for the pillar runner
"""


import errno
import logging
import tempfile

import salt.runners.pillar as pillar_runner
import salt.utils.files
import salt.utils.gitfs
import salt.utils.msgpack
from tests.support.gitfs import _OPTS
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)

MINION_ID = "test-host"
_CHECK_MINIONS_RETURN = {"minions": [MINION_ID], "missing": []}


class PillarTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the illar runner
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp_cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    @classmethod
    def tearDownClass(cls):
        try:
            salt.utils.files.rm_rf(cls.tmp_cachedir)
        except OSError as exc:
            if exc.errno == errno.EACCES:
                log.error("Access error removing file %s", cls.tmp_cachedir)
            elif exc.errno != errno.EEXIST:
                raise

    def setup_loader_modules(self):
        opts = _OPTS.copy()
        opts["pillar_cache"] = True
        opts["pillar_cache_backend"] = "disk"
        opts["pillar_cache_ttl"] = 30
        opts["cachedir"] = self.tmp_cachedir
        return {pillar_runner: {"__opts__": opts}}

    def test_clear_pillar_cache(self):
        """
        test pillar.clear_pillar_cache
        """

        cache = {
            "CacheDisk_data": {
                MINION_ID: {
                    None: {
                        "this": "one",
                        "that": "two",
                        "those": ["three", "four", "five"],
                    }
                }
            },
            "CacheDisk_cachetime": {MINION_ID: 1612302460.146923},
        }
        packer = salt.utils.msgpack.Packer()
        cache_contents = packer.pack(cache)

        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(return_value=_CHECK_MINIONS_RETURN),
        ), patch("salt.utils.atomicfile.atomic_open", mock_open()) as atomic_open_mock:
            with patch("os.path.exists", MagicMock(return_value=True)):
                with patch(
                    "salt.utils.files.fopen", mock_open(read_data=cache_contents)
                ) as fopen_mock:
                    # No arguments defaults to all globbing
                    ret = pillar_runner.clear_pillar_cache()
                    assert ret == {}

                    # Also test passing specific minion
                    ret = pillar_runner.clear_pillar_cache("test-host")
                    assert ret == {}

    def test_show_pillar_cache(self):
        """
        test pillar.clear_pillar_cache
        """

        cache = {
            "CacheDisk_data": {
                MINION_ID: {
                    None: {
                        "this": "one",
                        "that": "two",
                        "those": ["three", "four", "five"],
                    }
                }
            },
            "CacheDisk_cachetime": {MINION_ID: 1612302460.146923},
        }
        packer = salt.utils.msgpack.Packer()
        cache_contents = packer.pack(cache)

        expected = {
            MINION_ID: {
                "this": "one",
                "that": "two",
                "those": ["three", "four", "five"],
            }
        }

        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(return_value=_CHECK_MINIONS_RETURN),
        ), patch("salt.utils.atomicfile.atomic_open", mock_open()) as atomic_open_mock:
            with patch("os.path.exists", MagicMock(return_value=True)):
                with patch(
                    "salt.utils.files.fopen", mock_open(read_data=cache_contents)
                ) as fopen_mock:
                    ret = pillar_runner.show_pillar_cache()
                    assert ret == expected

                    ret = pillar_runner.show_pillar_cache("test-host")
                    assert ret == expected

        _EMPTY_CHECK_MINIONS_RETURN = {"minions": [], "missing": []}
        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(return_value=_EMPTY_CHECK_MINIONS_RETURN),
        ), patch("salt.utils.atomicfile.atomic_open", mock_open()) as atomic_open_mock:
            ret = pillar_runner.show_pillar_cache("fake-host")
            assert ret == {}
