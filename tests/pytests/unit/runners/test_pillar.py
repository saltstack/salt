"""
unit tests for the pillar runner
"""

import logging
import os
import shutil

import pytest
import salt.runners.pillar as pillar_runner
import salt.utils.files
import salt.utils.gitfs
import salt.utils.msgpack
from tests.support.mock import MagicMock, mock_open, patch

log = logging.getLogger(__name__)


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


@pytest.fixture(scope="module")
def pillar_cache_dir(cachedir_tree):
    pillar_cache_dir = cachedir_tree / "pillar_cache"
    pillar_cache_dir.mkdir()
    return pillar_cache_dir


@pytest.fixture(scope="function")
def pillar_cache_files(pillar_cache_dir):
    MINION_ID = "test-host"
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

    with salt.utils.files.fopen(
        os.path.join(str(pillar_cache_dir), MINION_ID), "wb+"
    ) as fp:
        fp.write(cache_contents)

    MINION_ID = "another-host"
    cache = {
        "CacheDisk_data": {
            MINION_ID: {
                None: {
                    "this": "six",
                    "that": "seven",
                    "those": ["eight", "nine", "ten"],
                }
            }
        },
        "CacheDisk_cachetime": {MINION_ID: 1612302460.146923},
    }
    packer = salt.utils.msgpack.Packer()
    cache_contents = packer.pack(cache)

    with salt.utils.files.fopen(
        os.path.join(str(pillar_cache_dir), MINION_ID), "wb+"
    ) as fp:
        fp.write(cache_contents)


def test_clear_pillar_cache(cachedir_tree, pillar_cache_dir, pillar_cache_files):
    """
    test pillar.clear_pillar_cache
    """

    MINION_IDS = [
        ["test-host", "another-host"],
        ["test-host"],
        ["test-host", "another-host"],
        ["test-host", "another-host"],
    ]
    _CHECK_MINIONS_RETURN = []
    for entry in MINION_IDS:
        _CHECK_MINIONS_RETURN.append({"minions": entry, "missing": []})

    with patch.dict(pillar_runner.__opts__, {"cachedir": str(cachedir_tree)}):
        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(side_effect=_CHECK_MINIONS_RETURN),
        ):
            expected = {
                "test-host": {
                    "those": ["three", "four", "five"],
                    "that": "two",
                    "this": "one",
                },
                "another-host": {
                    "those": ["eight", "nine", "ten"],
                    "that": "seven",
                    "this": "six",
                },
            }
            ret = pillar_runner.show_pillar_cache()
            assert ret == expected

            ret = pillar_runner.clear_pillar_cache("test-host")
            assert ret == {}

            expected = {
                "another-host": {
                    "those": ["eight", "nine", "ten"],
                    "that": "seven",
                    "this": "six",
                }
            }
            ret = pillar_runner.show_pillar_cache()
            assert ret == expected

            ret = pillar_runner.clear_pillar_cache()
            assert ret == {}


def test_show_pillar_cache(cachedir_tree, pillar_cache_dir, pillar_cache_files):
    """
    test pillar.clear_pillar_cache
    """

    MINION_IDS = [["test-host", "another-host"], ["test-host"]]

    _CHECK_MINIONS_RETURN = []
    for entry in MINION_IDS:
        _CHECK_MINIONS_RETURN.append({"minions": entry, "missing": []})

    with patch.dict(pillar_runner.__opts__, {"cachedir": str(cachedir_tree)}):
        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(side_effect=_CHECK_MINIONS_RETURN),
        ):
            expected = {
                "test-host": {
                    "those": ["three", "four", "five"],
                    "that": "two",
                    "this": "one",
                },
                "another-host": {
                    "those": ["eight", "nine", "ten"],
                    "that": "seven",
                    "this": "six",
                },
            }
            ret = pillar_runner.show_pillar_cache()
            assert ret == expected

            expected = {
                "test-host": {
                    "this": "one",
                    "that": "two",
                    "those": ["three", "four", "five"],
                }
            }
            ret = pillar_runner.show_pillar_cache("test-host")
            assert ret == expected

        _EMPTY_CHECK_MINIONS_RETURN = {"minions": [], "missing": []}
        with patch(
            "salt.utils.minions.CkMinions.check_minions",
            MagicMock(return_value=_EMPTY_CHECK_MINIONS_RETURN),
        ), patch("salt.utils.atomicfile.atomic_open", mock_open()) as atomic_open_mock:
            ret = pillar_runner.show_pillar_cache("fake-host")
            assert ret == {}
