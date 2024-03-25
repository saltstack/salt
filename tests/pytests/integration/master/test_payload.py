"""
Tests for payload
"""

import pytest


@pytest.mark.slow_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows
@pytest.mark.skip_on_darwin
def test_payload_no_exception(salt_cli, salt_master, salt_minion):
    """
    Test to confirm that no exception is thrown with the jinja file
    when executed on the minion
    """
    test_set_hostname = """
    {%- set host = pillar.get("hostname", "UNKNOWN") %}
    {%- if host == 'UNKNOWN' %}
      {{ raise("Unsupported UNKNOWN hostname") }}
    {%- else %}
        hostnamectl set-hostname {{ host }}
    {%- endif %}
    """
    with salt_master.state_tree.base.temp_file("set_hostname.j2", test_set_hostname):

        ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
        assert ret.returncode == 0
        assert ret.data is True

        ret = salt_cli.run(
            "cmd.script",
            "salt://set_hostname.j2",
            "template=jinja",
            pillar={"hostname": "test"},
            minion_tgt=salt_minion.id,
        )
        assert "AttributeError:" not in ret.stdout
