"""
Tests that the pillar examples appearing in the documentation actually render.

Each fixture is a verbatim copy of an example used in the pillar topic guide.
If a doc example changes, the matching fixture must be updated and the test
re-run so the documentation stays trustworthy.

Covers the issues:

- 56239 (pillar update)
- 61283 (pillar yaml structure / merge behavior)
- 62802 (custom modules in pillar / pillar.items)
- 66622 (pillar include subkey separator)
- 63110 (pillarenv targeting)
"""

import textwrap

import pytest

import salt.pillar

pytestmark = [
    pytest.mark.slow_test,
]


# --- merge behavior (issue 61283) ---------------------------------------


@pytest.fixture(scope="module")
def merge_pillar_state_tree(pillar_state_tree):
    """
    Lay down the merge-behavior pillar example from the docs.
    """
    top_sls = textwrap.dedent(
        """\
        base:
          '*':
            - packages
            - services
        """
    )
    packages_sls = textwrap.dedent(
        """\
        bind:
          package-name: bind9
          version: 9.9.5
        """
    )
    services_sls = textwrap.dedent(
        """\
        bind:
          port: 53
          listen-on: any
        """
    )
    with pytest.helpers.temp_file(
        "top.sls", top_sls, pillar_state_tree
    ), pytest.helpers.temp_file(
        "packages.sls", packages_sls, pillar_state_tree
    ), pytest.helpers.temp_file(
        "services.sls", services_sls, pillar_state_tree
    ):
        yield None


def test_documented_dict_merge(salt_master, grains, merge_pillar_state_tree):
    """
    Verify the recursive dict merge example produces the documented output.
    """
    opts = salt_master.config.copy()
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    assert ret.get("bind") == {
        "package-name": "bind9",
        "version": "9.9.5",
        "port": 53,
        "listen-on": "any",
    }


@pytest.fixture(scope="module")
def overwrite_pillar_state_tree(pillar_state_tree):
    """
    Lay down the "last one wins" overwrite example.
    """
    top_sls = textwrap.dedent(
        """\
        base:
          '*':
            - packages
            - services
        """
    )
    packages_sls = "bind: bind9\n"
    services_sls = "bind: named\n"
    with pytest.helpers.temp_file(
        "top.sls", top_sls, pillar_state_tree
    ), pytest.helpers.temp_file(
        "packages.sls", packages_sls, pillar_state_tree
    ), pytest.helpers.temp_file(
        "services.sls", services_sls, pillar_state_tree
    ):
        yield None


def test_documented_last_one_wins(salt_master, grains, overwrite_pillar_state_tree):
    """
    The pillar topic guide promises "last one wins" for non-dict scalar
    collisions.  ``services.sls`` is applied after ``packages.sls`` so
    ``bind`` should resolve to ``named``.
    """
    opts = salt_master.config.copy()
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    assert ret.get("bind") == "named"


# --- include + subkey separator (issue 66622) ---------------------------


@pytest.fixture(scope="module")
def include_pillar_state_tree(pillar_state_tree):
    """
    Lay down the documented include-with-key example.
    """
    top_sls = textwrap.dedent(
        """\
        base:
          '*':
            - main
        """
    )
    main_sls = textwrap.dedent(
        """\
        include:
          - users:
              key: users
        """
    )
    users_sls = textwrap.dedent(
        """\
        alice: 1000
        bob: 1001
        """
    )
    with pytest.helpers.temp_file(
        "top.sls", top_sls, pillar_state_tree
    ), pytest.helpers.temp_file(
        "main.sls", main_sls, pillar_state_tree
    ), pytest.helpers.temp_file(
        "users.sls", users_sls, pillar_state_tree
    ):
        yield None


def test_documented_include_with_key(salt_master, grains, include_pillar_state_tree):
    """
    With the documented form ``- users: {key: users}`` the included pillar
    must be nested under the ``users`` key.  The pillar dictionary keys
    coming from ``users.sls`` should *not* appear at the top level.
    """
    opts = salt_master.config.copy()
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    assert ret.get("users") == {"alice": 1000, "bob": 1001}
    # The documented behavior: the included file contents are NOT promoted to
    # the top level when `key:` is set.
    assert "alice" not in ret
    assert "bob" not in ret


# --- pillarenv selection (issue 63110) ----------------------------------


@pytest.fixture(scope="module")
def multi_env_pillar_tree(tmp_path_factory):
    """
    Lay down two pillarenvs: ``base`` and ``qa``.
    """
    base_dir = tmp_path_factory.mktemp("pillar_base")
    qa_dir = tmp_path_factory.mktemp("pillar_qa")
    (base_dir / "top.sls").write_text("base:\n  '*':\n    - common\n")
    (base_dir / "common.sls").write_text("environment: base\nsentinel: from-base\n")
    (qa_dir / "top.sls").write_text("qa:\n  '*':\n    - common\n")
    (qa_dir / "common.sls").write_text("environment: qa\nsentinel: from-qa\n")
    yield {"base": [str(base_dir)], "qa": [str(qa_dir)]}


def test_documented_pillarenv_isolation(salt_master, grains, multi_env_pillar_tree):
    """
    The pillar topic guide says that setting ``pillarenv`` causes a single
    pillar environment to be used, ignoring all others.
    """
    opts = salt_master.config.copy()
    opts["pillar_roots"] = multi_env_pillar_tree
    opts["pillarenv"] = "qa"
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base", pillarenv="qa")
    ret = pillar_obj.compile_pillar()
    assert ret.get("environment") == "qa"
    assert ret.get("sentinel") == "from-qa"
