import pathlib

import pytest

import salt.defaults.exitcodes

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_minion, salt_sub_minion, salt_cli):
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
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    basic_tempfile = salt_master.pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    )
    sub_tempfile = salt_master.pillar_tree.base.temp_file("sub.sls", sub_pillar_file)
    try:
        with top_tempfile, basic_tempfile, sub_tempfile:
            ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
            assert ret.returncode == 0
            assert salt_minion.id in ret.data
            assert ret.data[salt_minion.id] is True
            assert salt_sub_minion.id in ret.data
            assert ret.data[salt_sub_minion.id] is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_cli.run("saltutil.refresh_pillar", wait=True, minion_tgt="*")
        assert ret.returncode == 0
        assert salt_minion.id in ret.data
        assert ret.data[salt_minion.id] is True
        assert salt_sub_minion.id in ret.data
        assert ret.data[salt_sub_minion.id] is True


def test_list(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt -L matcher
    """
    ret = salt_cli.run("-L", "test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True
    assert salt_minion.id in ret.stdout
    assert salt_sub_minion.id not in ret.stdout
    ret = salt_cli.run(
        "-L", "test.ping", minion_tgt=f"{salt_minion.id},{salt_sub_minion.id}"
    )
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_compound_min_with_grain(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt compound matcher
    """
    ret = salt_cli.run("-C", "test.ping", minion_tgt="min* and G@test_grain:cheese")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_compound_and_not_grain(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="min* and not G@test_grain:foo")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_compound_not_grain(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="min* not G@test_grain:foo")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_compound_pcre_grain_and_grain(salt_cli, salt_minion, salt_sub_minion):
    match = "P@test_grain:^cheese$ and * and G@test_grain:cheese"
    ret = salt_cli.run("-C", "test.ping", minion_tgt=match)
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_compound_list_and_pcre_minion(salt_cli, salt_minion, salt_sub_minion):
    match = f"L@{salt_sub_minion.id} and E@.*"
    ret = salt_cli.run("-C", "test.ping", minion_tgt=match)
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data


def test_compound_not_sub_minion(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt=f"not {salt_sub_minion.id}")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_compound_all_and_not_grains(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run(
        "-C", "test.ping", minion_tgt="* and ( not G@test_grain:cheese )"
    )
    assert ret.returncode == 0
    assert salt_minion.id not in ret.data
    assert salt_sub_minion.id in ret.data


def test_compound_grain_regex(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="G%@planets%merc*")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_coumpound_pcre_grain_regex(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="P%@planets%^(mercury|saturn)$")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_compound_pillar(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    # FYI, This test was previously being skipped because it was unreliable
    ret = salt_cli.run("-C", "test.ping", minion_tgt="I%@companions%three%sarah*")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_compound_pillar_pcre(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    # FYI, This test was previously being skipped because it was unreliable
    ret = salt_cli.run("-C", "test.ping", minion_tgt="J%@knights%^(Lancelot|Galahad)$")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_compound_nodegroup(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-C", "test.ping", minion_tgt="N@multiline_nodegroup")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    target = f"N@multiline_nodegroup not {salt_sub_minion.id}"
    ret = salt_cli.run("-C", "test.ping", minion_tgt=target)
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    target = "N@multiline_nodegroup not @fakenodegroup not {}".format(
        salt_sub_minion.id
    )
    ret = salt_cli.run("-C", "test.ping", minion_tgt=target)
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_nodegroup(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt nodegroup matcher
    """
    ret = salt_cli.run("-N", "test.ping", minion_tgt="min")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("-N", "test.ping", minion_tgt="sub_min")
    assert ret.returncode == 0
    assert salt_minion.id not in ret.data
    assert salt_sub_minion.id in ret.data
    ret = salt_cli.run("-N", "test.ping", minion_tgt="mins")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    ret = salt_cli.run("-N", "test.ping", minion_tgt="unknown_nodegroup")
    assert ret.returncode == 0
    assert not ret.data
    ret = salt_cli.run("-N", "test.ping", minion_tgt="redundant_minions")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    ret = salt_cli.run("-N", "test.ping", minion_tgt="nodegroup_loop_a")
    assert ret.returncode == 2  # No minions matched
    ret = salt_cli.run("-N", "test.ping", minion_tgt="multiline_nodegroup")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_nodegroup_list(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("-N", "test.ping", minion_tgt="list_group")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data

    ret = salt_cli.run("-N", "test.ping", minion_tgt="list_group2")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data

    ret = salt_cli.run("-N", "test.ping", minion_tgt="one_list_group")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data

    ret = salt_cli.run("-N", "test.ping", minion_tgt="one_minion_list")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data


def test_glob(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt glob matcher
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True
    assert salt_minion.id in ret.stdout
    assert salt_sub_minion.id not in ret.stdout
    ret = salt_cli.run("test.ping", minion_tgt="*")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_regex(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt regex matcher
    """
    ret = salt_cli.run("-E", "test.ping", minion_tgt=f"^{salt_minion.id}$")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("-E", "test.ping", minion_tgt=".*")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_grain(salt_cli, salt_master, salt_minion, salt_sub_minion):
    """
    test salt grain matcher
    """
    # Sync grains
    ret = salt_cli.run("saltutil.sync_grains", minion_tgt="*")
    assert ret.returncode == 0
    # First-level grain (string value)
    ret = salt_cli.run("-G", "test.ping", minion_tgt="test_grain:cheese")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("-G", "test.ping", minion_tgt="test_grain:spam")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data
    # Custom grain
    ret = salt_cli.run("-G", "test.ping", minion_tgt="match:maker")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    # First-level grain (list member)
    ret = salt_cli.run("-G", "test.ping", minion_tgt="planets:earth")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("-G", "test.ping", minion_tgt="planets:saturn")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data
    ret = salt_cli.run("-G", "test.ping", minion_tgt="planets:pluto")
    assert ret.returncode == 2  # No match
    # Nested grain (string value)
    ret = salt_cli.run("-G", "test.ping", minion_tgt="level1:level2:foo")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("-G", "test.ping", minion_tgt="level1:level2:bar")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data
    # Nested grain (list member)
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:one:ian")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:two:jamie")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data
    # Test for issue: https://github.com/saltstack/salt/issues/19651
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:*:susan")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    # Test to ensure wildcard at end works correctly
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:one:*")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    # Test to ensure multiple wildcards works correctly
    ret = salt_cli.run("-G", "test.ping", minion_tgt="companions:*:*")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_grains_targeting_os_running(grains, salt_cli, salt_minion, salt_sub_minion):
    """
    Tests running "salt -G 'os:<system-os>' test.ping and minions both return True
    """
    ret = salt_cli.run("-G", "test.ping", minion_tgt="os:{}".format(grains["os"]))
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert ret.data[salt_minion.id] is True
    assert salt_sub_minion.id in ret.data
    assert ret.data[salt_sub_minion.id] is True


def test_grains_targeting_minion_id_running(salt_cli, salt_minion, salt_sub_minion):
    """
    Tests return of each running test minion targeting with minion id grain
    """
    ret = salt_cli.run("-G", "test.ping", minion_tgt=f"id:{salt_minion.id}")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert ret.data[salt_minion.id] is True

    ret = salt_cli.run("-G", "test.ping", minion_tgt=f"id:{salt_sub_minion.id}")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert ret.data[salt_sub_minion.id] is True


def _check_skip(grains):
    if grains["os"] == "Windows":
        return True
    return False


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
def test_grains_targeting_minion_id_disconnected(salt_master, salt_minion, salt_cli):
    """
    Tests return of minion using grains targeting on a disconnected minion.
    """
    expected_output = "Minion did not return. [No response]"

    # Create a minion key, but do not start the "fake" minion. This mimics a
    # disconnected minion.
    disconnected_minion_id = "disconnected"
    minions_pki_dir = pathlib.Path(salt_master.config["pki_dir"]) / "minions"
    with pytest.helpers.temp_file(
        disconnected_minion_id,
        minions_pki_dir.joinpath(salt_minion.id).read_text(),
        minions_pki_dir,
    ):
        ret = salt_cli.run(
            "--timeout=1",
            "--log-level=debug",
            "-G",
            "test.ping",
            minion_tgt=f"id:{disconnected_minion_id}",
            _timeout=30,
        )
        assert ret.returncode == 1
        assert disconnected_minion_id in ret.data
        assert expected_output in ret.data[disconnected_minion_id]


def test_regrain(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt grain matcher
    """
    ret = salt_cli.run("--grain-pcre", "test.ping", minion_tgt="test_grain:^cheese$")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id not in ret.data
    ret = salt_cli.run("--grain-pcre", "test.ping", minion_tgt="test_grain:.*am$")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data


def test_pillar(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    """
    test pillar matcher
    """
    # First-level pillar (string value)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="monty:python")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    # First-level pillar (string value, only in sub_minion)
    ret = salt_cli.run("-I", "test.ping", minion_tgt=f"sub:{salt_sub_minion.id}")
    assert ret.returncode == 0
    assert salt_sub_minion.id in ret.data
    assert salt_minion.id not in ret.data
    # First-level pillar (list member)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="knights:Bedevere")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    # Nested pillar (string value)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="level1:level2:foo")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    # Nested pillar (list member)
    ret = salt_cli.run("-I", "test.ping", minion_tgt="companions:three:sarah jane")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_repillar(salt_cli, salt_minion, salt_sub_minion, pillar_tree):
    """
    test salt pillar PCRE matcher
    """
    ret = salt_cli.run("-J", "test.ping", minion_tgt="monty:^(python|hall)$")
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data
    ret = salt_cli.run(
        "--pillar-pcre", "test.ping", minion_tgt="knights:^(Robin|Lancelot)$"
    )
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_ipcidr(salt_cli, salt_minion, salt_sub_minion):
    ret = salt_cli.run("network.subnets", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data

    # We're just after the first defined subnet from 'minion'
    subnet = ret.data[0]

    ret = salt_cli.run("-S", "test.ping", minion_tgt=subnet)
    assert ret.returncode == 0
    assert salt_minion.id in ret.data
    assert salt_sub_minion.id in ret.data


def test_static(salt_cli, salt_minion, salt_sub_minion):
    """
    test salt static call
    """
    ret = salt_cli.run("test.ping", "--static", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True
    assert salt_minion.id in ret.stdout


def _check_skip(grains):
    if grains["os"] == "VMware Photon OS" and grains["osmajorrelease"] == 4:
        return True
    return False


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
def test_salt_documentation(salt_cli, salt_minion):
    """
    Test to see if we're supporting --doc
    """
    # Setting an explicity long timeout otherwise this test may fail when the
    # system is under load.
    ret = salt_cli.run("-d", "test", minion_tgt=salt_minion.id, _timeout=90)
    assert ret.returncode == 0
    assert "test.ping" in ret.data


def test_salt_documentation_too_many_arguments(salt_cli, salt_minion):
    """
    Test to see if passing additional arguments shows an error
    """
    ret = salt_cli.run(
        "-d", "salt", "ldap.search", "filter=ou=People", minion_tgt=salt_cli.id
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_USAGE
    assert "You can only get documentation for one method at one time" in ret.stderr
