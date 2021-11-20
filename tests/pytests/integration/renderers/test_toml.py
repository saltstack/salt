import pytest
import salt.serializers.toml


@pytest.mark.skipif(
    salt.serializers.toml.HAS_TOML is False, reason="The 'toml' library is missing"
)
def test_toml_renderer(salt_call_cli, tmp_path, base_env_state_tree_root_dir):
    config_file_path = tmp_path / "config.toml"
    state_file = """
    toml-config:
      file.serialize:
        - name: {{ pillar.get("toml-config-path") }}
        - formatter: toml
        - dataset:
            tool:
              black:
                exclude: foobar
              isort:
                include_trailing_comma: true
    """
    pillar = {
        "toml-config-path": str(config_file_path).replace("\\", "/"),
    }
    with pytest.helpers.temp_file(
        "issue-58822.sls", state_file, base_env_state_tree_root_dir
    ):
        ret = salt_call_cli.run("state.apply", "issue-58822", pillar=pillar)
        assert ret.exitcode == 0
    contents = config_file_path.read_text()
    expected = (
        '[tool.black]\nexclude = "foobar"\n\n[tool.isort]\ninclude_trailing_comma ='
        " true\n\n"
    )
    assert contents == expected
