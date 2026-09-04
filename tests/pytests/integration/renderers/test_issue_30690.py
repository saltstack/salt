"""
Test for Issue #30690: Newlines may be rendered as literal \\n for multi-line scalar variables

When using import_yaml to load YAML data and pass it to a Jinja template,
multi-line scalar variables (using ``|``) may have their newlines rendered as
literal ``\\n`` instead of actual newlines.

This test reproduces the bug described in:
https://github.com/saltstack/salt/issues/30690
"""

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.slow_test,
]


def test_issue_30690_newlines_rendered_as_literal_in_import_yaml(
    salt_master, salt_minion, salt_call_cli, base_env_state_tree_root_dir, tmp_path
):
    """
    Test that multi-line scalar variables from import_yaml preserve newlines
    when used in Jinja templates.

    The bug: When using import_yaml to load YAML data and pass it to a Jinja
    template, multi-line scalar variables (using |) have their newlines rendered
    as literal \\n instead of actual newlines.

    Expected behavior: Multi-line scalars from import_yaml should preserve
    newlines when rendered in templates.
    """
    # Template file that uses the multi-line variable
    template_contents = """{% for k, v in site.quux.items() %}
{{ k }}
{{ v.garply }}
{% endfor %}
"""

    # YAML file with multi-line scalar
    yaml_contents = """quux:
  blurfl:
    garply: |
      corge
      wibble
      wobble
"""

    import_target = tmp_path / "test_import_yaml"
    direct_target = tmp_path / "test_direct"

    # Combined state file that runs both tests in a single state run for
    # efficiency. This reduces overhead from multiple state.sls calls.
    combined_state = """
{{% import_yaml "test_data.yaml" as site %}}
{import_target}:
  file.managed:
    - source: salt://template.jinja
    - template: jinja
    - context:
        site: {{{{ site }}}}

{direct_target}:
  file.managed:
    - source: salt://template.jinja
    - template: jinja
    - context:
        site:
          quux:
            blurfl:
              garply: |
                corge
                wibble
                wobble
""".format(
        import_target=import_target, direct_target=direct_target
    )

    # Create files in state tree
    template_file = base_env_state_tree_root_dir / "template.jinja"
    template_file.write_text(template_contents)

    yaml_file = base_env_state_tree_root_dir / "test_data.yaml"
    yaml_file.write_text(yaml_contents)

    # Use a single combined state file to reduce test execution time
    combined_state_file = base_env_state_tree_root_dir / "test_combined.sls"
    combined_state_file.write_text(combined_state)

    # Run combined state once instead of two separate calls
    ret = salt_call_cli.run("state.sls", "test_combined", timeout=120)

    assert ret.returncode == 0, f"State run failed: {ret.stdout}"
    assert ret.data, "State run returned no data"

    # Verify both states succeeded
    import_key = f"file_|-{import_target}_|-{import_target}_|-managed"
    direct_key = f"file_|-{direct_target}_|-{direct_target}_|-managed"

    assert (
        import_key in ret.data
    ), f"Import state not found in results. Keys: {list(ret.data.keys())}"
    assert (
        direct_key in ret.data
    ), f"Direct state not found in results. Keys: {list(ret.data.keys())}"

    assert (
        ret.data[import_key]["result"] is True
    ), f"Import state failed: {ret.data[import_key]}"
    assert (
        ret.data[direct_key]["result"] is True
    ), f"Direct state failed: {ret.data[direct_key]}"

    # Read the generated files
    with salt.utils.files.fopen(str(import_target), "r") as fp:
        import_content = fp.read()
    with salt.utils.files.fopen(str(direct_target), "r") as fp:
        direct_content = fp.read()

    # The bug manifests as literal \n in the import_yaml version.
    assert "\\n" not in import_content, (
        "Bug: import_yaml renders newlines as literal \\n. "
        f"Import content: {repr(import_content)}, "
        f"Direct content: {repr(direct_content)}."
    )

    # Both should have actual newlines
    assert "\n" in import_content, (
        "Bug: import_yaml version should have newlines but doesn't. "
        f"Content: {repr(import_content)}"
    )

    # Normalize trailing whitespace and CRLF -> LF so the comparison is
    # platform-independent. file.managed writes CRLF on Windows; the number
    # of trailing blank lines depends on how YAML parses the |-block in each
    # path (the SLS-inline block scalar can carry one extra trailing line
    # depending on how the SLS file's line endings are normalized). The fix
    # under test is about preserving newlines *inside* the multi-line scalar,
    # not about exact trailing-newline accounting.
    def _normalize(s):
        return s.replace("\r\n", "\n").rstrip()

    import_normalized = _normalize(import_content)
    direct_normalized = _normalize(direct_content)
    assert import_normalized == direct_normalized, (
        "Bug: import_yaml and direct context should produce the same output "
        "(ignoring trailing whitespace and line endings). "
        f"Import: {repr(import_content)}, Direct: {repr(direct_content)}"
    )
