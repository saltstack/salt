"""
Tests for dynamically loading configuration
"""
import json

import pytest


@pytest.fixture(scope="module")
def sls_contents():
    return """
    test:
      test.nop
    """


def get_pillar_top_file(*pillar_files):
    top = f"""
    base:
      '*':
    """
    for file_name in pillar_files:
        top = f"{top}\n        - {file_name}"
    return top


def get_pillar_contents(prop_name):
    return f"""
    {prop_name}: true
    """


@pytest.fixture(scope="module")
def formula_path(tmp_path_factory, sls_contents):
    path = tmp_path_factory.mktemp("formulas")

    # Create the initial formula files
    with pytest.helpers.temp_file(
        "initial-formula/initial-test.sls",
        sls_contents,
        path,
    ):
        yield path


@pytest.fixture(scope="module")
def pillar_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("pillars")
    with pytest.helpers.temp_file(
        "initial-pillar/initial-pillar.sls",
        get_pillar_contents("initial"),
        path,
    ):
        yield path


@pytest.fixture(scope="module")
def runner_master_config(formula_path, pillar_path):
    return {
        "auto_accept": True,
        "env_order": ["base"],
        "file_roots": {"base": [str(formula_path / "*-formula")]},
        "pillar_roots": {"base": [str(pillar_path / "*-pillar")]},
    }


@pytest.fixture(scope="module")
def runner_salt_master(
    salt_factories, runner_master_config, formula_path, sls_contents, pillar_path
):
    factory = salt_factories.salt_master_daemon(
        "runner-master", defaults=runner_master_config
    )
    with factory.started():
        # Create base test files
        with pytest.helpers.temp_file(
            "base-test.sls",
            sls_contents,
            factory.state_tree.base.paths[-1],
        ), pytest.helpers.temp_file(
            "base-pillar.sls",
            get_pillar_contents("base"),
            factory.pillar_tree.base.paths[-1],
        ), factory.pillar_tree.base.temp_file(
            "top.sls",
            get_pillar_top_file("base-pillar", "initial-pillar"),
        ):
            yield factory


@pytest.fixture(scope="module")
def runner_salt_minion(runner_salt_master):
    assert runner_salt_master.is_running()
    factory = runner_salt_master.salt_minion_daemon("runner-minion")
    # Don't actually start the minion since we only need the salt call API
    yield factory


@pytest.fixture(scope="module")
def runner_salt_call_cli(runner_salt_minion):
    return runner_salt_minion.salt_call_cli()


def test_initial_formulas(runner_salt_call_cli):
    # Base state tree files work
    ret = runner_salt_call_cli.run("state.apply", "base-test")
    assert ret.returncode == 0
    assert "No matching sls found for 'base-test'" not in ret.stdout

    # The initial formula exists
    ret = runner_salt_call_cli.run("state.apply", "initial-test")
    assert ret.returncode == 0
    assert "No matching sls found for 'initial-test'" not in ret.stdout

    # The new formula does not
    ret = runner_salt_call_cli.run("state.apply", "new-test")
    assert ret.returncode != 0
    assert "No matching sls found for 'new-test'" in ret.stdout


def test_dynamic_formula(runner_salt_call_cli, formula_path, sls_contents):
    with pytest.helpers.temp_file(
        "new-formula/new-test.sls",
        sls_contents,
        formula_path,
    ):
        ret = runner_salt_call_cli.run("state.apply", "new-test")
        assert ret.returncode == 0
        assert "No matching sls found for 'new-test'" not in ret.stdout


def test_initial_pillars(runner_salt_call_cli, runner_salt_master):
    # Base pillar files work
    ret = runner_salt_call_cli.run("pillar.get", "base")
    assert ret.returncode == 0
    assert json.loads(ret.stdout) == {"local": True}

    # The initial pillar exists
    ret = runner_salt_call_cli.run("pillar.get", "initial")
    assert ret.returncode == 0
    assert json.loads(ret.stdout) == {"local": True}

    # The new pillar does not
    ret = runner_salt_call_cli.run("pillar.get", "new")
    assert ret.returncode == 0
    assert json.loads(ret.stdout) == {"local": ""}


def test_dynamic_pillar(runner_salt_call_cli, runner_salt_master, pillar_path):
    with pytest.helpers.temp_file(
        "new-pillar/new-pillar.sls",
        get_pillar_contents("new"),
        pillar_path,
    ), runner_salt_master.pillar_tree.base.temp_file(
        "top.sls",
        get_pillar_top_file("base-pillar", "initial-pillar", "new-pillar"),
    ):
        ret = runner_salt_call_cli.run("pillar.get", "new")
        assert ret.returncode == 0
        assert json.loads(ret.stdout) == {"local": True}
