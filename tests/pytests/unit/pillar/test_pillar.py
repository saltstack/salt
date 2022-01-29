import pytest
import salt.loader
import salt.pillar
from salt.utils.odict import OrderedDict


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
