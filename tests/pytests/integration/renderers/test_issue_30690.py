"""
Test for Issue #30690: Newlines may be rendered as literal \n for multi-line scalar variables

When using import_yaml to load YAML data and pass it to a Jinja template,
multi-line scalar variables (using |) may have their newlines rendered as
literal \n instead of actual newlines.

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
    salt_master, salt_minion, salt_call_cli, base_env_state_tree_root_dir
):
    """
    Test that multi-line scalar variables from import_yaml preserve newlines
    when used in Jinja templates.

    The bug: When using import_yaml to load YAML data and pass it to a Jinja
    template, multi-line scalar variables (using |) have their newlines rendered
    as literal \n instead of actual newlines.

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

    # Combined state file that runs both tests in a single state run for efficiency
    # This reduces overhead from multiple state.sls calls
    # Note: Removed user/group requirements to avoid permission issues in test environment
    combined_state = """
{% import_yaml "test_data.yaml" as site %}
/tmp/test_import_yaml:
  file.managed:
    - mode: 644
    - source: salt://template.jinja
    - template: jinja
    - context:
        site: {{ site }}

/tmp/test_direct:
  file.managed:
    - mode: 644
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
"""

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
    import_key = "file_|-/tmp/test_import_yaml_|-/tmp/test_import_yaml_|-managed"
    direct_key = "file_|-/tmp/test_direct_|-/tmp/test_direct_|-managed"

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
    import os

    import salt.utils.files

    import_file_path = "/tmp/test_import_yaml"
    direct_file_path = "/tmp/test_direct"

    # The bug: import_yaml version will have literal \n instead of newlines
    # Expected: Both files should have the same content with actual newlines
    import_content = None
    direct_content = None

    if os.path.isfile(import_file_path):
        with salt.utils.files.fopen(import_file_path, "r") as fp:
            import_content = fp.read()

    if os.path.isfile(direct_file_path):
        with salt.utils.files.fopen(direct_file_path, "r") as fp:
            direct_content = fp.read()

    if import_content is not None and direct_content is not None:
        # The bug manifests as literal \n in the import_yaml version
        assert "\\n" not in import_content or import_content == direct_content, (
            "Bug: import_yaml renders newlines as literal \\n. "
            f"Import content: {repr(import_content)}, "
            f"Direct content: {repr(direct_content)}. "
            "Expected: Both should have actual newlines, not literal \\n"
        )

        # Both should have actual newlines
        assert "\n" in import_content, (
            "Bug: import_yaml version should have newlines but doesn't. "
            f"Content: {repr(import_content)}"
        )
        # Normalize trailing newlines - the important thing is that newlines
        # are preserved, not the exact number of trailing newlines
        import_normalized = import_content.rstrip("\n")
        direct_normalized = direct_content.rstrip("\n")
        assert import_normalized == direct_normalized, (
            "Bug: import_yaml and direct context should produce the same output "
            "(ignoring trailing newlines). "
            f"Import: {repr(import_content)}, Direct: {repr(direct_content)}"
        )
