"""
Specifically ensure that pillars are merged as expected
for the target as well and available for renderers.
This should be covered by `test.check_pillar` above, but
let's check the specific output for the most important funcs.
Issue #59802
"""

import json

import pytest

import salt.utils.dictupdate
from tests.support.helpers import system_python_version

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.usefixtures("pillar_tree_nested"),
    pytest.mark.slow_test,
    pytest.mark.skipif(
        system_python_version() < (3, 10),
        reason="System python too old for these tests",
    ),
]


@pytest.fixture
def _write_pillar_state(base_env_state_tree_root_dir, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("tgtdir")
    tgt_file = tmp_path / "deepthought.txt"
    top_file = """
    base:
      'localhost':
        - writepillar
      '127.0.0.1':
        - writepillar
    """
    # Inline the Jinja template content to avoid salt-ssh file server lookup issues
    # while still testing Jinja rendering with pillar data
    deepthought_template = r"""{{
      {
        "raw": {
          "the_meaning": pillar.get("the_meaning"),
          "btw": pillar.get("btw")},
        "modules": {
          "the_meaning": salt["pillar.get"]("the_meaning"),
          "btw": salt["pillar.get"]("btw")}
      } | json }}"""
    nested_pillar_file = f"""
    deep_thought:
      file.managed:
        - name: {tgt_file}
        - contents: |
            {deepthought_template}
        - template: jinja
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    show_tempfile = pytest.helpers.temp_file(
        "writepillar.sls", nested_pillar_file, base_env_state_tree_root_dir
    )

    with top_tempfile, show_tempfile:
        yield tgt_file


@pytest.fixture
def base():
    return {"the_meaning": {"of": {"life": 42, "bar": "tender"}, "for": "what"}}


@pytest.fixture
def override(base):
    poverride = {
        "the_meaning": {"of": {"life": 2.71, "foo": "lish"}},
        "btw": "turtles",
    }
    expected = salt.utils.dictupdate.merge(base, poverride)
    return expected, poverride


@pytest.mark.parametrize(
    "args,kwargs",
    (
        (("state.sls", "writepillar"), {}),
        (("state.highstate",), {"whitelist": "writepillar"}),
        (("state.top", "top.sls"), {}),
    ),
)
def test_it(salt_ssh_cli, args, kwargs, override, _write_pillar_state):
    expected, override = override
    ret = salt_ssh_cli.run(*args, **kwargs, pillar=override)
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert _write_pillar_state.exists()
    pillar = json.loads(_write_pillar_state.read_text())
    assert pillar["raw"] == expected
    assert pillar["modules"] == expected
