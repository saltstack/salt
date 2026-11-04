"""
Pillar targeting (``-I``) for a minion that uses ``pillarenv``.

The minion is configured with ``pillarenv: dev``. The ``dev`` pillar sets
``role: web`` and the ``prod`` pillar sets ``role: db``.
"""

import pytest

from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(180),
]

PILLARS = {"dev": "web", "prod": "db"}


@pytest.fixture(scope="module")
def pillarenv_trees(tmp_path_factory):
    root = tmp_path_factory.mktemp("pillarenv-targeting")
    pillar_roots = {}
    for env, role in PILLARS.items():
        env_dir = root / "pillar" / env
        env_dir.mkdir(parents=True)
        (env_dir / "top.sls").write_text(
            f"{env}:\n  '*':\n    - role\n", encoding="utf-8"
        )
        (env_dir / "role.sls").write_text(f"role: {role}\n", encoding="utf-8")
        pillar_roots[env] = [str(env_dir)]
    state_dir = root / "states"
    state_dir.mkdir()
    (state_dir / "noop.sls").write_text("noop:\n  test.nop: []\n", encoding="utf-8")
    return pillar_roots, {"base": [str(state_dir)]}


@pytest.fixture(scope="module")
def targeting_master(salt_factories, pillarenv_trees):
    pillar_roots, file_roots = pillarenv_trees
    factory = salt_factories.salt_master_daemon(
        "pillarenv-targeting-master",
        defaults={
            "open_mode": True,
            "pillar_cache": True,
            "pillar_roots": pillar_roots,
            "file_roots": file_roots,
        },
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def targeting_minion(targeting_master):
    factory = targeting_master.salt_minion_daemon(
        "pillarenv-targeting-minion",
        defaults={"open_mode": True, "pillarenv": "dev"},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        yield factory


@pytest.fixture()
def salt_call(targeting_minion):
    return targeting_minion.salt_call_cli()


@pytest.fixture()
def refreshed(targeting_minion, salt_call):
    """
    Start every test from a regular pillar refresh of the configured env.
    """
    ret = salt_call.run("saltutil.refresh_pillar", wait=True)
    assert ret.returncode == 0, ret
    assert ret.data is True
    return targeting_minion


def _matched(targeting_master, role, matcher="-I"):
    ret = targeting_master.salt_cli().run(
        matcher, "test.ping", minion_tgt=f"role:{role}"
    )
    if not isinstance(ret.data, dict):
        return set()
    return set(ret.data)


def test_pillar_targeting_with_pillarenv(targeting_master, refreshed):
    """
    The cached pillar of a minion with a ``pillarenv`` is what ``-I`` matches.
    """
    assert _matched(targeting_master, "web") == {refreshed.id}
    assert _matched(targeting_master, "db") == set()


def test_pillar_targeting_pcre_with_pillarenv(targeting_master, refreshed):
    assert _matched(targeting_master, "we.*", "-J") == {refreshed.id}
    assert _matched(targeting_master, "d.*", "-J") == set()


def test_one_off_pillarenv_query_keeps_targeting(
    targeting_master, refreshed, salt_call
):
    """
    ``pillar.items pillarenv=prod`` only looks at another environment, the
    minion keeps its own pillar and so does the targeting data.
    """
    ret = salt_call.run("pillar.items", "pillarenv=prod", "unmask=True")
    assert ret.returncode == 0, ret
    assert ret.data["role"] == "db"
    assert _matched(targeting_master, "web") == {refreshed.id}
    assert _matched(targeting_master, "db") == set()


def test_pillar_override_keeps_targeting(targeting_master, refreshed, salt_call):
    ret = salt_call.run("pillar.items", 'pillar={"role": "override"}', "unmask=True")
    assert ret.returncode == 0, ret
    assert ret.data["role"] == "override"
    assert _matched(targeting_master, "override") == set()
    assert _matched(targeting_master, "web") == {refreshed.id}


def test_state_apply_with_other_pillarenv_keeps_targeting(
    targeting_master, refreshed, salt_call
):
    """
    A state run that uses another ``pillarenv`` fetches that pillar through
    the same request as a highstate, but must not replace the targeting data.
    """
    ret = salt_call.run("state.apply", "noop", "pillarenv=prod", "test=True")
    assert ret.returncode == 0, ret
    assert _matched(targeting_master, "web") == {refreshed.id}
    assert _matched(targeting_master, "db") == set()


def test_state_apply_restores_targeting_data(targeting_master, refreshed):
    """
    A regular state run with the configured ``pillarenv`` refreshes the
    targeting data, as documented.
    """
    ret = targeting_master.salt_run_cli().run("cache.clear_pillar", refreshed.id)
    assert ret.returncode == 0, ret
    assert _matched(targeting_master, "web") == set()

    ret = targeting_master.salt_cli().run(
        "state.apply", "noop", "test=True", minion_tgt=refreshed.id
    )
    assert ret.returncode == 0, ret
    assert _matched(targeting_master, "web") == {refreshed.id}


def test_compile_cache_is_separate_per_environment(
    targeting_master, refreshed, salt_call
):
    """
    With ``pillar_cache`` on, compiling another environment must not change
    what the configured environment returns or what targeting sees.
    """
    ret = salt_call.run("pillar.items", "pillarenv=prod", "unmask=True")
    assert ret.data["role"] == "db"
    ret = salt_call.run("pillar.items", "pillarenv=dev", "unmask=True")
    assert ret.data["role"] == "web"
    ret = salt_call.run("pillar.items", "unmask=True")
    assert ret.data["role"] == "web"
    assert _matched(targeting_master, "web") == {refreshed.id}


def test_compile_cache_runners(targeting_master, refreshed, salt_call):
    """
    ``pillar.show_pillar_cache`` shows compiled pillars and
    ``pillar.clear_pillar_cache`` clears them without touching targeting.
    """
    salt_call.run("pillar.items", "pillarenv=prod", "unmask=True")
    run = targeting_master.salt_run_cli()
    ret = run.run("pillar.show_pillar_cache", refreshed.id, "pillarenv=prod")
    assert ret.returncode == 0, ret
    assert ret.data[refreshed.id]["role"] == "db"

    ret = run.run("pillar.clear_pillar_cache", refreshed.id, "pillarenv=prod")
    assert ret.returncode == 0, ret
    ret = run.run("pillar.show_pillar_cache", refreshed.id, "pillarenv=prod")
    assert not ret.data
    assert _matched(targeting_master, "web") == {refreshed.id}
