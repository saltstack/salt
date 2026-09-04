"""
tests.pytests.integration.cli.test_salt_cloud
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import pytest

pytest.importorskip("libcloud", reason="salt-cloud requires >= libcloud 0.11.4")


def test_map_file_runs_without_attribute_error(salt_cloud_cli, tmp_path):
    """
    Regression test for #69281.

    ``salt-cloud -m <mapfile>`` failed on startup with
    ``AttributeError: module 'salt' has no attribute 'minion'`` because
    ``salt.cloud.Map.read`` references ``salt.minion.MasterMinion`` but
    ``salt.cloud`` did not explicitly ``import salt.minion``.

    Invoke the CLI with an empty map file. Without the fix the command
    aborts during ``Map.__init__`` with the AttributeError. With the fix
    it gets past ``read()`` and hits the "No nodes defined in this map"
    early exit.
    """
    map_file = tmp_path / "empty.map"
    map_file.write_text("")
    ret = salt_cloud_cli.run("-m", str(map_file))
    combined = (ret.stdout or "") + (ret.stderr or "")
    assert "AttributeError" not in combined, combined
    assert "module 'salt' has no attribute 'minion'" not in combined, combined
    assert "No nodes defined in this map" in combined, combined


def test_function_arguments(salt_cloud_cli):
    ret = salt_cloud_cli.run("--function", "show_image", "-h")
    assert ret.returncode != 0
    assert (
        "error: --function expects two arguments: <function-name> <provider>"
        in ret.stderr
    )


def test_list_providers_accepts_no_arguments(salt_cloud_cli):
    ret = salt_cloud_cli.run("--list-providers", "ec2")
    assert ret.returncode != 0
    assert "error: '--list-providers' does not accept any arguments" in ret.stderr


@pytest.mark.parametrize(
    "query_option", ["--query", "--full-query", "--select-query", "--list-providers"]
)
def test_mutually_exclusive_query_options(salt_cloud_cli, query_option):
    if query_option != "--query":
        conflicting_option = "--query"
    elif query_option != "--full-query":
        conflicting_option = "--full-query"
    elif query_option != "--select-query":
        conflicting_option = "--select-query"
    elif query_option != "--list-providers":
        conflicting_option = "--list-providers"

    ret = salt_cloud_cli.run(query_option, conflicting_option)
    assert ret.returncode != 0
    assert "are mutually exclusive. Please only choose one of them" in ret.stderr


@pytest.mark.parametrize(
    "list_option", ["--list-locations", "--list-images", "--list-sizes"]
)
def test_mutually_exclusive_list_options(salt_cloud_cli, list_option):
    if list_option != "--list-locations":
        conflicting__option = "--list-locations"
    elif list_option != "--list-images":
        conflicting__option = "--list-images"
    elif list_option != "--list-sizes":
        conflicting__option = "--list-sizes"

    ret = salt_cloud_cli.run(list_option, "ec2", conflicting__option, "ec2")
    assert ret.returncode != 0
    assert "are mutually exclusive. Please only choose one of them" in ret.stderr
