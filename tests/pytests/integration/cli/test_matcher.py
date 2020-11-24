import pytest
import salt.defaults.exitcodes
from tests.support.helpers import slowTest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def pillar_tree(base_env_pillar_tree_root_dir, salt_minion, salt_sub_minion, salt_cli):
    top_file = """
    base:
      '{}':
        - basic
      '{}':
        - basic
        - sub
    """.format(
        salt_minion.id, salt_sub_minion.id
    )
    basic_pillar_file = """
    monty: python
    os: {{ grains['os'] }}
    {% if grains['os'] == 'Fedora' %}
    class: redhat
    {% else %}
    class: other
    {% endif %}

    knights:
      - Lancelot
      - Galahad
      - Bedevere
      - Robin

    level1:
      level2: foo

    companions:
      three:
        - liz
        - jo
        - sarah jane
    """
    sub_pillar_file = """
    sub: {}
    """.format(
        salt_sub_minion.id
    )
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    basic_tempfile = pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    )
    sub_tempfile = pytest.helpers.temp_file(
        "sub.sls", sub_pillar_file, base_env_pillar_tree_root_dir
    )
    try:
        with top_tempfile, basic_tempfile, sub_tempfile:
            ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
            assert ret.exitcode == 0
            assert salt_minion.id in ret.json
            assert ret.json[salt_minion.id] is True
            assert salt_sub_minion.id in ret.json
            assert ret.json[salt_sub_minion.id] is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
        assert ret.exitcode == 0
        assert salt_minion.id in ret.json
        assert ret.json[salt_minion.id] is True
        assert salt_sub_minion.id in ret.json
        assert ret.json[salt_sub_minion.id] is True


@slowTest
def test_list(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt -L matcher
    """
    ret = salt_cli.run("-L", "test.ping", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0
    assert ret.json is True
    assert salt_minion.id in ret.stdout
    assert salt_sub_minion.id not in ret.stdout
    ret = salt_cli.run(
        "-L", "test.ping", minion_tgt="{},{}".format(salt_minion.id, salt_sub_minion.id)
    )
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_compound_min_with_grain(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt compound matcher
    """
    ret = salt_cli.run("-C", "test.ping", minion_tgt="min* and G@test_grain:cheese")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_compound_and_not_grain(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="min* and not G@test_grain:foo")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_compound_not_grain(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="min* not G@test_grain:foo")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_compound_pcre_grain_and_grain(salt_cli, salt_minion, salt_sub_minion):
    match = "P@test_grain:^cheese$ and * and G@test_grain:cheese"
    ret = salt_cli.run("-t", "1", "-C", "test.ping", minion_tgt=match)
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_compound_list_and_pcre_minion(salt_cli, salt_minion, salt_sub_minion):
    match = "L@{} and E@.*".format(salt_sub_minion.id)
    ret = salt_cli.run("-t", "1", "-C", "test.ping", minion_tgt=match)
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json


@slowTest
def test_compound_not_sub_minion(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run(
        "-C", "test.ping", minion_tgt="not {}".format(salt_sub_minion.id)
    )
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_compound_all_and_not_grains(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run(
        "-C", "test.ping", minion_tgt="* and ( not G@test_grain:cheese )"
    )
    assert ret.exitcode == 0
    assert salt_minion.id not in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_compound_grain_regex(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="G%@planets%merc*")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_coumpound_pcre_grain_regex(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="P%@planets%^(mercury|saturn)$")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_compound_pillar(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    # FYI, This test was previously being skipped because it was unreliable
    ret = salt_cli.run("-C", "test.ping", minion_tgt="I%@companions%three%sarah*")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_compound_pillar_pcre(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    # FYI, This test was previously being skipped because it was unreliable
    ret = salt_cli.run("-C", "test.ping", minion_tgt="J%@knights%^(Lancelot|Galahad)$")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


def test_compound_nodegroup(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="N@multiline_nodegroup")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    target = "N@multiline_nodegroup not {}".format(salt_sub_minion.id)
    ret = salt_cli.run("-C", "test.ping", minion_tgt=target)
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    target = "N@multiline_nodegroup not @fakenodegroup not {}".format(
        salt_sub_minion.id
    )
    ret = salt_cli.run("-C", "test.ping", minion_tgt=target)
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_nodegroup(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt nodegroup matcher
    """
    ret = salt_cli.run("-N", "test.ping", minion_tgt="min")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("-N", "test.ping", minion_tgt="sub_min")
    assert ret.exitcode == 0
    assert salt_minion.id not in ret.json
    assert salt_sub_minion.id in ret.json
    ret = salt_cli.run("-N", "test.ping", minion_tgt="mins")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    ret = salt_cli.run("-N", "test.ping", minion_tgt="unknown_nodegroup")
    assert ret.exitcode == 0
    assert not ret.json
    ret = salt_cli.run("-N", "test.ping", minion_tgt="redundant_minions")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    ret = salt_cli.run("-N", "test.ping", minion_tgt="nodegroup_loop_a")
    assert ret.exitcode == 2  # No minions matched
    ret = salt_cli.run("-N", "test.ping", minion_tgt="multiline_nodegroup")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_nodegroup_list(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-N", "test.ping", minion_tgt="list_group")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json

    ret = salt_cli.run("-N", "test.ping", minion_tgt="list_group2")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json

    ret = salt_cli.run("-N", "test.ping", minion_tgt="one_list_group")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json

    ret = salt_cli.run("-N", "test.ping", minion_tgt="one_minion_list")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json


@slowTest
def test_glob(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt glob matcher
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0
    assert ret.json is True
    assert salt_minion.id in ret.stdout
    assert salt_sub_minion.id not in ret.stdout
    ret = salt_cli.run("test.ping", minion_tgt="*")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_regex(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt regex matcher
    """
    ret = salt_cli.run("-E", "test.ping", minion_tgt="^{}$".format(salt_minion.id))
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("-E", "test.ping", minion_tgt=".*")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_grain(salt_cli, salt_master, salt_minion, salt_sub_minion):
    """
    test salt grain matcher
    """
    # Sync grains
    ret = salt_cli.run("-t1", "saltutil.sync_grains", minion_tgt="*")
    assert ret.exitcode == 0
    # First-level grain (string value)
    ret = salt_cli.run("-t1", "-G", "test.ping", minion_tgt="test_grain:cheese")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("-G", "test.ping", minion_tgt="test_grain:spam")
    assert ret.exitcode == 0
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json
    # Custom grain
    ret = salt_cli.run("-t1", "-G", "test.ping", minion_tgt="match:maker")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    # First-level grain (list member)
    ret = salt_cli.run("-t1", "-G", "test.ping", minion_tgt="planets:earth")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("-G", "test.ping", minion_tgt="planets:saturn")
    assert ret.exitcode == 0
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json
    ret = salt_cli.run("-G", "test.ping", minion_tgt="planets:pluto")
    assert ret.exitcode == 2  # No match
    # Nested grain (string value)
    ret = salt_cli.run("-t1", "-G", "test.ping", minion_tgt="level1:level2:foo")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("-G", "test.ping", minion_tgt="level1:level2:bar")
    assert ret.exitcode == 0
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json
    # Nested grain (list member)
    ret = salt_cli.run("-t1", "-G", "test.ping", minion_tgt="companions:one:ian")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:two:jamie")
    assert ret.exitcode == 0
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json
    # Test for issue: https://github.com/saltstack/salt/issues/19651
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:*:susan")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    # Test to ensure wildcard at end works correctly
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:one:*")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    # Test to ensure multiple wildcards works correctly
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:*:*")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_regrain(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt grain matcher
    """
    ret = salt_cli.run(
        "-t1", "--grain-pcre", "test.ping", minion_tgt="test_grain:^cheese$"
    )
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id not in ret.json
    ret = salt_cli.run("--grain-pcre", "test.ping", minion_tgt="test_grain:.*am$")
    assert ret.exitcode == 0
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json


@slowTest
def test_pillar(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    """
    test pillar matcher
    """
    # First-level pillar (string value)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="monty:python")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    # First-level pillar (string value, only in sub_minion)
    ret = salt_cli.run(
        "-I", "test.ping", minion_tgt="sub:{}".format(salt_sub_minion.id)
    )
    assert ret.exitcode == 0
    assert salt_sub_minion.id in ret.json
    assert salt_minion.id not in ret.json
    # First-level pillar (list member)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="knights:Bedevere")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    # Nested pillar (string value)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="level1:level2:foo")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    # Nested pillar (list member)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="companions:three:sarah jane")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_repillar(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    """
    test salt pillar PCRE matcher
    """
    ret = salt_cli.run("-J", "test.ping", minion_tgt="monty:^(python|hall)$")
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json
    ret = salt_cli.run(
        "--pillar-pcre", "test.ping", minion_tgt="knights:^(Robin|Lancelot)$"
    )
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_ipcidr(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("network.subnets", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0
    assert ret.json

    # We're just after the first defined subnet from 'minion'
    subnet = ret.json[0]

    ret = salt_cli.run("-S", "test.ping", minion_tgt=subnet)
    assert ret.exitcode == 0
    assert salt_minion.id in ret.json
    assert salt_sub_minion.id in ret.json


@slowTest
def test_static(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt static call
    """
    ret = salt_cli.run("test.ping", "--static", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0
    assert ret.json is True
    assert salt_minion.id in ret.stdout


@slowTest
def test_salt_documentation(salt_cli, salt_minion):
    """
    Test to see if we're supporting --doc
    """
    ret = salt_cli.run("-d", "test", minion_tgt=salt_minion.id)
    assert ret.exitcode == 0
    assert "test.ping" in ret.json


@slowTest
def test_salt_documentation_too_many_arguments(salt_cli, salt_minion):
    """
    Test to see if passing additional arguments shows an error
    """
    ret = salt_cli.run(
        "-d", "salt", "ldap.search", "filter=ou=People", minion_tgt=salt_cli.id
    )
    assert ret.exitcode == salt.defaults.exitcodes.EX_USAGE
    assert "You can only get documentation for one method at one time" in ret.stderr
