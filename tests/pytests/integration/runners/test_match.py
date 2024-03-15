"""
Integration tests for the match runner
"""

import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="class")
def match_master_config():
    return {
        "open_mode": True,
        "peer_run": {
            "match-minion-bob": [
                "match.compound_matches",
            ],
        },
        "nodegroups": {
            "alice_eve": "I@name:ali*",
            "alice": "L@match-minion-alice",
        },
        "minion_data_cache": True,
    }


@pytest.fixture(scope="class", autouse=True)
def pillar_tree(match_salt_master, match_salt_minion_alice, match_salt_minion_eve):
    top_file = f"""
    base:
      '{match_salt_minion_alice.id}':
        - alice
      '{match_salt_minion_eve.id}':
        - eve
    """
    alice_pillar_file = """
    name: alice
    """
    eve_pillar_file = """
    name: alice_whoops_sorry_eve_hrhr
    """
    top_tempfile = match_salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    alice_tempfile = match_salt_master.pillar_tree.base.temp_file(
        "alice.sls", alice_pillar_file
    )
    eve_tempfile = match_salt_master.pillar_tree.base.temp_file(
        "eve.sls", eve_pillar_file
    )

    with top_tempfile, alice_tempfile, eve_tempfile:
        ret = match_salt_minion_alice.salt_call_cli().run(
            "saltutil.refresh_pillar", wait=True
        )
        assert ret.returncode == 0
        assert ret.data is True
        ret = match_salt_minion_eve.salt_call_cli().run(
            "saltutil.refresh_pillar", wait=True
        )
        assert ret.returncode == 0
        assert ret.data is True
        yield


@pytest.fixture(scope="class")
def match_salt_master(salt_factories, match_master_config):
    factory = salt_factories.salt_master_daemon(
        "match-master", defaults=match_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def match_salt_minion_alice(match_salt_master):
    assert match_salt_master.is_running()
    factory = match_salt_master.salt_minion_daemon(
        "match-minion-alice",
        defaults={"open_mode": True, "grains": {"role": "alice"}},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def match_salt_minion_eve(match_salt_master):
    assert match_salt_master.is_running()
    factory = match_salt_master.salt_minion_daemon(
        "match-minion-eve",
        defaults={"open_mode": True, "grains": {"role": "eve"}},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def match_salt_minion_bob(match_salt_master):
    assert match_salt_master.is_running()
    factory = match_salt_master.salt_minion_daemon(
        "match-minion-bob",
        defaults={"open_mode": True},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def match_salt_call_cli(match_salt_minion_bob):
    return match_salt_minion_bob.salt_call_cli()


@pytest.fixture(scope="class")
def match_salt_run_cli(match_salt_master):
    return match_salt_master.salt_run_cli()


class TestMatchCompoundRunner:
    @pytest.fixture
    def alice_uncached(self, match_salt_minion_alice, match_salt_run_cli):
        ret = match_salt_run_cli.run("cache.clear_all", "match-minion-alice")
        assert ret.returncode == 0
        yield
        match_salt_minion_alice.salt_call_cli().run("pillar.items")

    @pytest.fixture
    def eve_cached(self, match_salt_minion_eve):
        ret = match_salt_minion_eve.salt_call_cli().run("pillar.items")
        assert ret.returncode == 0
        yield

    @pytest.fixture
    def alice_down(self, match_salt_minion_alice):
        with match_salt_minion_alice.stopped():
            yield

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("G@role:alice", True),
            ("G@role:ali*", True),
            (r"E@match\-minion\-(alice|bob)", True),
            ("P@role:^(alice|bob)$", True),
            ("L@match-minion-alice,match-minion-bob", True),
            ("I@name:alice", True),
            ("I@name:ali*", False),
            ("J@name:alice", True),
            ("J@name:^(alice|bob)$", False),
            ("N@alice", True),
            ("N@alice_eve", False),
            ("G@role:ali* and I@name:alice", True),
            ("G@role:ali* and I@name:ali*", False),
            ("G@role:ali* or I@name:ali*", True),
            ("G@role:ali* and not I@name:alice", False),
        ],
    )
    def test_match_compound_matches(self, match_salt_run_cli, expr, expected):
        if expected:
            expected = "match-minion-alice"
        ret = match_salt_run_cli.run(
            "match.compound_matches", expr, "match-minion-alice"
        )
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] == expected

    @pytest.mark.usefixtures("eve_cached")
    def test_match_compound_matches_only_allows_exact_pillar_matching(
        self, match_salt_run_cli
    ):
        """
        This check is mostly redundant, but better check explicitly with the scenario
        to prevent because it is security-critical.
        """
        ret = match_salt_run_cli.run(
            "match.compound_matches", "I@name:alic*", "match-minion-eve"
        )
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] is False

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("G@role:alice", False),
            ("G@role:ali*", False),
            ("I@name:alice", False),
            ("I@name:ali*", False),
            ("G@role:ali* and I@name:alice", False),
            ("L@match-minion-alice,match-minion-bob", True),
            ("L@match-minion-alice,match-minion-bob and G@role:alice", False),
            ("L@match-minion-alice,match-minion-bob and I@name:alice", False),
        ],
    )
    @pytest.mark.usefixtures("alice_uncached")
    def test_match_compound_matches_with_uncached_minion_data(
        self, match_salt_run_cli, expr, expected
    ):
        if expected:
            expected = "match-minion-alice"
        ret = match_salt_run_cli.run(
            "match.compound_matches", expr, "match-minion-alice"
        )
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] == expected

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("G@role:alice", True),
            ("G@role:ali*", True),
            ("I@name:alice", True),
            ("I@name:ali*", False),
            ("G@role:ali* and I@name:alice", True),
            ("L@match-minion-alice,match-minion-bob", True),
        ],
    )
    @pytest.mark.usefixtures("alice_down")
    def test_match_compound_matches_when_minion_is_down(
        self, match_salt_run_cli, expr, expected
    ):
        if expected:
            expected = "match-minion-alice"
        ret = match_salt_run_cli.run(
            "match.compound_matches", expr, "match-minion-alice"
        )
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] == expected

    @pytest.mark.parametrize(
        "minion_id",
        [
            "hi\\there",
            "my/minion",
            "../../../../../../../../../etc/shadow",
        ],
    )
    def test_match_compound_matches_with_invalid_minion_id(
        self, minion_id, match_salt_run_cli
    ):
        ret = match_salt_run_cli.run("match.compound_matches", "*", minion_id)
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] is False

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("G@role:alice", True),
            ("G@role:ali*", True),
            ("I@name:alice", True),
            ("I@name:ali*", False),
            ("G@role:ali* and I@name:alice", True),
            ("L@match-minion-alice,match-minion-bob", True),
        ],
    )
    def test_match_compound_matches_as_peer_run(
        self, match_salt_call_cli, expr, expected
    ):
        if expected:
            expected = "match-minion-alice"
        ret = match_salt_call_cli.run(
            "publish.runner", "match.compound_matches", [expr, "match-minion-alice"]
        )
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] == expected


class TestMatchCompoundRunnerWithoutMinionDataCache:
    @pytest.fixture(scope="class")
    def match_master_config(self):
        return {
            "open_mode": True,
            "minion_data_cache": False,
        }

    @pytest.mark.parametrize(
        "expr",
        [
            "G@role:alice",
            "G@role:ali*",
            "I@name:alice",
            "I@name:ali*",
            "G@role:ali* and I@name:alice",
        ],
    )
    def test_match_compound_matches(self, match_salt_run_cli, expr):
        ret = match_salt_run_cli.run(
            "match.compound_matches", expr, "match-minion-alice"
        )
        assert ret.returncode == 0
        assert ret.data
        assert "res" in ret.data
        assert ret.data["res"] is False
