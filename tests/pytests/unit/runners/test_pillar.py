"""
unit tests for the pillar runner
"""

import logging
import shutil

import pytest
import salt.runners.pillar as pillar_runner
import salt.utils.files
import salt.utils.gitfs
import salt.utils.msgpack
from tests.support.mock import MagicMock, mock_open, patch

log = logging.getLogger(__name__)

MINION_ID = "test-host"
_CHECK_MINIONS_RETURN = {"minions": [MINION_ID], "missing": []}


@pytest.fixture
def configure_loader_modules():
    return {
        pillar_runner: {
            "__opts__": {
                "pillar_cache": True,
                "pillar_cache_backend": "disk",
                "pillar_cache_ttl": 30,
            }
        }
    }


@pytest.fixture(scope="module")
def cachedir_tree(tmp_path_factory):
    _cachedir_tree = tmp_path_factory.mktemp("cachedir")
    try:
        yield _cachedir_tree
    finally:
        shutil.rmtree(str(_cachedir_tree), ignore_errors=True)


def test_clear_pillar_cache(cachedir_tree):
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

    with patch.dict(pillar_runner.__opts__, {"cachedir": str(cachedir_tree)}):
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


def test_show_pillar_cache(cachedir_tree):
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
        MINION_ID: {"this": "one", "that": "two", "those": ["three", "four", "five"]}
    }

    with patch.dict(pillar_runner.__opts__, {"cachedir": str(cachedir_tree)}):
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
