"""
Custom grains in ``salt://_grains`` must be available to pillar rendering
when a masterless minion starts.

See https://github.com/saltstack/salt/issues/65027
"""

import copy

import pytest

import salt.minion

pytestmark = [
    pytest.mark.windows_whitelisted,
]

CUSTOM_GRAIN_PY = """
def main():
    return {"custom_grain": "test_value"}
"""

PILLAR_TOP_SLS = """
base:
  '*':
    - defaults
"""

PILLAR_DEFAULTS_SLS = """
mypillar: "{{ grains['custom_grain'] }}"
"""


@pytest.fixture(scope="module")
def pillar_tree(tmp_path_factory):
    return tmp_path_factory.mktemp("pillar-tree-base")


@pytest.fixture(scope="module")
def minion_config_overrides(pillar_tree):
    return {"pillar_roots": {"base": [str(pillar_tree)]}}


@pytest.fixture
def custom_grain_and_pillar(state_tree, pillar_tree):
    with pytest.helpers.temp_file(
        "custom_grain.py", CUSTOM_GRAIN_PY, state_tree / "_grains"
    ), pytest.helpers.temp_file(
        "top.sls", PILLAR_TOP_SLS, pillar_tree
    ), pytest.helpers.temp_file(
        "defaults.sls", PILLAR_DEFAULTS_SLS, pillar_tree
    ):
        yield


@pytest.fixture
def isolated_opts(minion_opts, tmp_path):
    """
    Fresh cachedir and extension_modules so that a grain synced by one test
    cannot leak into another.
    """
    opts = copy.deepcopy(minion_opts)
    opts["cachedir"] = str(tmp_path / "cache")
    opts["extension_modules"] = str(tmp_path / "extmods")
    return opts


def test_sminion_masterless_syncs_custom_grains_before_pillar(
    isolated_opts, custom_grain_and_pillar
):
    """
    A masterless SMinion must sync ``_grains`` before it loads grains and
    compiles pillar, otherwise pillar that references a custom grain cannot
    render.
    """
    assert isolated_opts["file_client"] == "local"

    sminion = salt.minion.SMinion(isolated_opts)

    assert sminion.opts["grains"].get("custom_grain") == "test_value"
    assert sminion.opts["pillar"].get("mypillar") == "test_value"


def test_sminion_masterless_sync_keeps_unrelated_grains(
    isolated_opts, custom_grain_and_pillar, tmp_path
):
    """
    The implicit start-up sync only adds and updates grains. A grain that is
    already in ``extension_modules`` but not in ``file_roots`` (shipped by
    salt-ssh, say) must survive even though ``clean_dynamic_modules`` is on.
    """
    assert isolated_opts["clean_dynamic_modules"] is True
    other = tmp_path / "extmods" / "grains" / "shipped_grain.py"
    other.parent.mkdir(parents=True)
    other.write_text('def main():\n    return {"shipped_grain": "kept"}\n')

    sminion = salt.minion.SMinion(isolated_opts)

    assert other.is_file()
    assert sminion.opts["grains"].get("shipped_grain") == "kept"
    assert sminion.opts["grains"].get("custom_grain") == "test_value"


def test_sync_grains_leaves_cachedir_untouched(
    isolated_opts, custom_grain_and_pillar, tmp_path
):
    """
    The start-up sync must not leave file lists or cached files in the real
    ``cachedir``. The fileserver caches file lists per environment, not per set
    of roots, so anything left there can be served to a later reader that
    uses different roots (``state.pkg`` on a salt-ssh target).
    """
    salt.minion._sync_grains(isolated_opts)

    assert (tmp_path / "extmods" / "grains" / "custom_grain.py").is_file()
    cachedir = tmp_path / "cache"
    assert not (cachedir / "file_lists").exists()
    assert not (cachedir / "files").exists()
    assert not (cachedir / "roots").exists()
