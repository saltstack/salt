import pytest


@pytest.fixture(scope="module")
def state_tree(base_env_state_tree_root_dir):
    top_file = """
    {%- from "map.jinja" import abc with context %}
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    map_file = """
    {%- set abc = "def" %}
    """
    state_file = """
    {%- from "map.jinja" import abc with context %}
    Ok with {{ abc }}:
      test.succeed_with_changes
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file(
        "map.jinja", map_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "test.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, map_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="module")
def state_tree_dir(base_env_state_tree_root_dir):
    """
    State tree with files to test salt-ssh
    when the map.jinja file is in another directory
    """
    # Remove unused import from top file to avoid salt-ssh file sync issues
    # Use "testdir" instead of "test" to avoid conflicts with state_tree fixture
    top_file = """
    base:
      'localhost':
        - testdir
      '127.0.0.1':
        - testdir
    """
    map_file = """
    {%- set abc = "def" %}
    """
    # State file imports from subdirectory - this is what we're testing
    state_file = """
    {%- from "test/map.jinja" import abc with context %}

    Ok with {{ abc }}:
      test.succeed_without_changes
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file(
        "test/map.jinja", map_file, base_env_state_tree_root_dir
    )
    # Use testdir.sls to avoid collision with state_tree's test.sls
    state_tempfile = pytest.helpers.temp_file(
        "testdir.sls", state_file, base_env_state_tree_root_dir
    )

    with top_tempfile, map_tempfile, state_tempfile:
        yield


@pytest.fixture
def nested_state_tree(base_env_state_tree_root_dir, tmp_path):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    # Import map.jinja at the SLS level (not inside a file.managed template)
    # so that --extra-filerefs can properly sync it to the thin tarball.
    map_file = """
    {% set comment = "blah blah" %}
    """
    state_file = """
    {%- from 'foo/map.jinja' import comment with context %}
    the_comment:
      test.succeed_with_changes:
        - comment: {{ comment }}
    """
    statedir = base_env_state_tree_root_dir / "foo"
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file("map.jinja", map_file, statedir)
    state_tempfile = pytest.helpers.temp_file("init.sls", state_file, statedir)

    with top_tempfile, map_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="module")
def pillar_tree_nested(base_env_pillar_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - nested
      '127.0.0.1':
        - nested
    """
    nested_pillar = r"""
    {%- do salt.log.warning("hithere: pillar was rendered") %}
    monty: python
    the_meaning:
      of:
        life: 42
        bar: tender
      for: what
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    nested_tempfile = pytest.helpers.temp_file(
        "nested.sls", nested_pillar, base_env_pillar_tree_root_dir
    )
    with top_tempfile, nested_tempfile:
        yield
