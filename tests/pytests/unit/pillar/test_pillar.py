import pytest
import salt.loader
import salt.pillar
from salt.utils.odict import OrderedDict
from tests.support.mock import patch


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


def test_issue_61010_do_not_cache_pillar_errors(temp_salt_minion):
    expected_cache_data = {"some": "totally cool pillar data"}
    with patch("salt.pillar.Pillar", autospec=True) as fake_pillar:
        fake_pillar.return_value.compile_pillar.return_value = {
            "_errors": "these should not be",
            "some": "totally cool pillar data",
        }

        opts = temp_salt_minion.config.copy()
        grains = salt.loader.grains(opts)
        cache = salt.pillar.PillarCache(
            opts=temp_salt_minion.config.copy(),
            grains=grains,
            minion_id=temp_salt_minion.id,
            saltenv="base",
        )

        actual_cache_data = cache.fetch_pillar()

        assert "_errors" not in actual_cache_data
        assert actual_cache_data == expected_cache_data
