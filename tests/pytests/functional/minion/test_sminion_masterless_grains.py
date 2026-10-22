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
