import logging
from pathlib import Path

import pytest

import salt.loader
import salt.pillar
import salt.utils.cache
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock


@pytest.mark.parametrize(
    "envs",
    (
        ["a", "b", "c"],
        ["c", "b", "a"],
        ["b", "a", "c"],
    ),
)
def test_pillar_envs_order(envs, temp_salt_minion, tmp_path):
    opts = temp_salt_minion.config.copy()
    # Stop using OrderedDict once we drop Py3.5 support
    opts["pillar_roots"] = OrderedDict()
    for envname in envs:
        opts["pillar_roots"][envname] = [str(tmp_path / envname)]
    grains = salt.loader.grains(opts)
    pillar = salt.pillar.Pillar(
        opts,
        grains,
        temp_salt_minion.id,
        "base",
    )
    # The base environment is always present and as the first environment name
    assert pillar._get_envs() == ["base"] + envs


def test_pillar_get_tops_should_not_error_when_merging_strategy_is_none_and_no_pillarenv(
    temp_salt_minion,
):
    opts = temp_salt_minion.config.copy()
    opts["pillarenv"] = None
    opts["pillar_source_merging_strategy"] = "none"
    pillar = salt.pillar.Pillar(
        opts=opts,
        grains=salt.loader.grains(opts),
        minion_id=temp_salt_minion.id,
        saltenv="base",
    )
    tops, errors = pillar.get_tops()
    assert not errors


def test_dynamic_pillarenv():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {
            "__env__": ["/srv/pillar/__env__"],
            "base": ["/srv/pillar/base"],
            "test": ["/srv/pillar/__env__"],
        },
        "file_roots": {"base": ["/srv/salt/base"], "__env__": ["/srv/salt/__env__"]},
        "extension_modules": "",
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    pillar = salt.pillar.Pillar(opts, {}, "mocked-minion", "base", pillarenv="dev")
    assert pillar.opts["pillar_roots"] == {
        "base": ["/srv/pillar/base"],
        "dev": ["/srv/pillar/dev"],
        "test": ["/srv/pillar/__env__"],
    }


def test_ignored_dynamic_pillarenv():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {
            "__env__": ["/srv/pillar/__env__"],
            "base": ["/srv/pillar/base"],
        },
        "file_roots": {"base": ["/srv/salt/base"], "dev": ["/svr/salt/dev"]},
        "extension_modules": "",
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    pillar = salt.pillar.Pillar(opts, {}, "mocked-minion", "base", pillarenv="base")
    assert pillar.opts["pillar_roots"] == {"base": ["/srv/pillar/base"]}


@pytest.mark.parametrize(
    "env",
    ("base", "something-else", "cool_path_123", "__env__"),
)
def test_pillar_envs_path_substitution(env, temp_salt_minion, tmp_path):
    """
    Test pillar access to a dynamic path using __env__
    """
    opts = temp_salt_minion.config.copy()

    if env == "__env__":
        # __env__ saltenv will pass "dynamic" as saltenv and
        # expect to be routed to the "dynamic" directory
        actual_env = "dynamic"
        leaf_dir = actual_env
    else:
        # any other saltenv will pass saltenv normally and
        # expect to be routed to a static "__env__" directory
        actual_env = env
        leaf_dir = "__env__"

    expected = {actual_env: [str(tmp_path / leaf_dir)]}

    # Stop using OrderedDict once we drop Py3.5 support
    opts["pillar_roots"] = OrderedDict()
    opts["pillar_roots"][env] = [str(tmp_path / leaf_dir)]
    grains = salt.loader.grains(opts)
    pillar = salt.pillar.Pillar(
        opts,
        grains,
        temp_salt_minion.id,
        actual_env,
    )

    # The __env__ string in the path has been substituted for the actual env
    assert pillar.opts["pillar_roots"] == expected


def test_pillar_get_cache_disk(temp_salt_minion, caplog):
    # create faked path for cache
    with pytest.helpers.temp_directory() as temp_path:
        tmp_cachedir = Path(str(temp_path) + "/pillar_cache/")
        tmp_cachedir.mkdir(parents=True)
        assert tmp_cachedir.exists()
        tmp_cachefile = Path(str(temp_path) + "/pillar_cache/" + temp_salt_minion.id)
        tmp_cachefile.touch()
        assert tmp_cachefile.exists()

        opts = temp_salt_minion.config.copy()
        opts["pillarenv"] = None
        opts["pillar_cache"] = True
        opts["cachedir"] = str(temp_path)

        caplog.at_level(logging.DEBUG)
        pillar = salt.pillar.PillarCache(
            opts=opts,
            grains=salt.loader.grains(opts),
            minion_id=temp_salt_minion.id,
            saltenv="base",
        )
        fresh_pillar = pillar.fetch_pillar()
        assert not (
            f"Error reading cache file at '{tmp_cachefile}': Unpack failed: incomplete input"
            in caplog.messages
        )
        assert fresh_pillar == {}


def test_pillar_fetch_pillar_override_skipped(temp_salt_minion, caplog):
    with pytest.helpers.temp_directory() as temp_path:
        tmp_cachedir = Path(str(temp_path) + "/pillar_cache/")
        tmp_cachedir.mkdir(parents=True)
        assert tmp_cachedir.exists()
        tmp_cachefile = Path(str(temp_path) + "/pillar_cache/" + temp_salt_minion.id)
        assert tmp_cachefile.exists() is False

        opts = temp_salt_minion.config.copy()
        opts["pillarenv"] = None
        opts["pillar_cache"] = True
        opts["cachedir"] = str(temp_path)

        pillar_override = {"inline_pillar": True}

        caplog.at_level(logging.DEBUG)
        pillar = salt.pillar.PillarCache(
            opts=opts,
            grains=salt.loader.grains(opts),
            minion_id=temp_salt_minion.id,
            saltenv="base",
            pillar_override=pillar_override,
        )

        fresh_pillar = pillar.fetch_pillar()
        assert fresh_pillar == {}


def test_remote_pillar_timeout(temp_salt_minion, tmp_path):
    opts = temp_salt_minion.config.copy()
    opts["master_uri"] = "tcp://127.0.0.1:12323"
    grains = salt.loader.grains(opts)
    pillar = salt.pillar.RemotePillar(
        opts,
        grains,
        temp_salt_minion.id,
        "base",
    )
    mock = MagicMock()
    mock.side_effect = salt.exceptions.SaltReqTimeoutError()
    pillar.channel.crypted_transfer_decode_dictentry = mock
    msg = r"^Pillar timed out after \d{1,4} seconds$"
    with pytest.raises(salt.exceptions.SaltClientError):
        pillar.compile_pillar()
