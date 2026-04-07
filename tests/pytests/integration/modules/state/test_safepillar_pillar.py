"""
Integration tests for SafeDict/SafeList pillar wrapping and output redaction.
"""

import textwrap

import pytest

pytestmark = [
    pytest.mark.slow_test,
]

SECRET = "VCOPS77716_integration_secret_value_xyz"


@pytest.fixture
def pillar_and_sls(
    salt_minion, base_env_pillar_tree_root_dir, base_env_state_tree_root_dir
):
    top_pillar = textwrap.dedent("""
        base:
          '{}':
            - secret_pillar
        """).format(salt_minion.id)
    pillar_sls = textwrap.dedent("""
        secret_key: {}
        """.format(SECRET))
    state_sls = textwrap.dedent("""
        demo_secret_state:
          test.configurable_test_state:
            - name: show_secret
            - changes: true
            - result: true
            - comment: "Rendered pillar contains {{ pillar['secret_key'] }}"
        """)
    with pytest.helpers.temp_file(
        "top.sls", top_pillar, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "secret_pillar.sls", pillar_sls, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "safepillar_demo.sls", state_sls, base_env_state_tree_root_dir
    ):
        yield


@pytest.mark.usefixtures("pillar_and_sls")
def test_state_apply_redacts_pillar_from_cli_output(salt_cli, salt_minion):
    """
    Pillar secrets must not appear verbatim in highstate output / return.
    """
    shell_result = salt_cli.run(
        "state.apply", "safepillar_demo", minion_tgt=salt_minion.id
    )
    assert shell_result.returncode == 0, shell_result.stderr
    out = shell_result.stdout or ""
    assert SECRET not in out, out
    data = shell_result.data or {}
    assert SECRET not in str(data), data


@pytest.mark.usefixtures("pillar_and_sls")
def test_no_log_masks_state_chunk(salt_cli, salt_minion, base_env_state_tree_root_dir):
    sls = textwrap.dedent("""
        nolog_demo:
          test.configurable_test_state:
            - name: nolog_show
            - changes: true
            - result: true
            - no_log: true
            - comment: "should not appear {{ pillar['secret_key'] }}"
        """)
    with pytest.helpers.temp_file(
        "safepillar_nolog.sls", sls, base_env_state_tree_root_dir
    ):
        shell_result = salt_cli.run(
            "state.apply", "safepillar_nolog", minion_tgt=salt_minion.id
        )
    assert shell_result.returncode == 0, shell_result.stderr
    out = shell_result.stdout or ""
    assert SECRET not in out
    assert "should not appear" not in out
