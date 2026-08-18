import pytest

import salt.pillar.saltclass as saltclass


@pytest.fixture
def configure_loader_modules():
    return {saltclass: {}}


@pytest.fixture
def minion_id():
    return "fake_id"


@pytest.fixture
def temp_saltclass_tree(tmp_path, minion_id):
    dirname = tmp_path / "saltclass" / "examples"
    dirname.mkdir(parents=True, exist_ok=True)
    classes_dir = dirname / "classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    nodes_dir = dirname / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    default_dir = classes_dir / "default"
    default_dir.mkdir(parents=True, exist_ok=True)
    users_dir = default_dir / "users"
    users_dir.mkdir(parents=True, exist_ok=True)
    roles_dir = classes_dir / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)
    nginx_subdir = roles_dir / "nginx"
    nginx_subdir.mkdir(parents=True, exist_ok=True)

    default_init = default_dir / "init.yml"
    test_list = """
    classes:
      - default.users
      - default.motd
      - default.empty

    states:
      - default

    pillars:
      default:
        network:
          dns:
    {% if __grains__['os'] == 'should_never_match' %}
            srv1: 192.168.0.1
            srv2: 192.168.0.2
            domain: example.com
    {% endif %}
          ntp:
            srv1: 192.168.10.10
            srv2: 192.168.10.20
      test_list:
        - a: ${default:network:ntp:srv1}
        - ${default:network:ntp:srv2}

      global_scalar: from default
      test_dict:
        a_scalar: from default
        a_list:
          - element1
          - element2
    """
    default_init.write_text(test_list)

    minion_node_file = nodes_dir / f"{minion_id}.yml"
    nodes_text = """
    environment: base

    states:
      - minion_node

    classes:
    {% for class in ['default', 'roles.*', 'empty.*'] %}
      - {{ class }}
    {% endfor %}

    pillars:
      global_scalar: from minion_node
      test_dict:
        a_scalar: from minion_node
    """
    minion_node_file.write_text(nodes_text)

    (users_dir / "init.yml").write_text(
        """
        classes:
          - default.users.foo

        states:
          - users

        pillars:
          default:
            ntp:
              srv1: 192.168.20.10

          global_scalar: from users
          test_dict:
            a_scalar: from users
        """
    )
    (users_dir / "foo.yml").write_text(
        """
        states:
          - users.foo

        global_scalar: from users.foo
        users_foo_scalar: from users.foo
        test_dict:
          a_scalar: from users.foo
        """
    )
    (default_dir / "empty.yml").write_text("test: this is a test")
    (default_dir / "motd.yml").write_text(
        """
        states:
          - motd

        pillars:
          global_scalar: from motd
        """
    )
    (roles_dir / "app.yml").write_text(
        """
        states:
          - app

        pillars:
          global_scalar: from app
        """
    )
    (nginx_subdir / "init.yml").write_text(
        """
        states:
          - nginx

        pillars:
          global_scalar: from nginx
          nginx_scalar: from nginx
        """
    )

    return dirname


def test_classes_order(temp_saltclass_tree):
    """
    Classes must be correctly ordered.

    See: https://github.com/saltstack/salt/issues/58969
    """
    expected_ret = [
        "default.users.foo",
        "default.users",
        "default.motd",
        "default.empty",
        "default",
        "roles.app",
        "roles.nginx",
    ]
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["__saltclass__"]["classes"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret


def test_list_expansion_succeeds(temp_saltclass_tree):
    expected_ret = [{"a": "192.168.10.10"}, "192.168.10.20"]
    full_ret = {}
    parsed_ret = []
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["test_list"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret


def test_node_override_classes_scalars(temp_saltclass_tree):
    """
    Scalars pillars defined in a node definition must override the
    definition from classes.
    """
    expected_ret = "from minion_node"
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["global_scalar"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret


def test_node_override_classes_scalar_in_dict(temp_saltclass_tree):
    """
    Scalars defined in `dict` pillars defined in a node definition must override the
    same dict definition from classes.

    See: https://github.com/saltstack/salt/issues/63933
    """
    expected_ret = "from minion_node"
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["test_dict"]["a_scalar"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret


def test_node_override_classes_list_in_dict(temp_saltclass_tree):
    """
    `list` under a `dict` defined in a node definition must override the
    same definition from classes.

    See: https://github.com/saltstack/salt/issues/63933
    """
    expected_ret = {"srv1": "192.168.10.10", "srv2": "192.168.10.20"}
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["default"]["network"]["ntp"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret


def test_list_in_dict_no_duplication(temp_saltclass_tree):
    """
    `list` under a `dict` in pillar must not be duplicated.

    See:
    """
    expected_ret = ["element1", "element2"]
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["test_dict"]["a_list"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret


def test_nested_classes_has_pillars(temp_saltclass_tree):
    """
    pillars defined in nested classes are present
    """
    expected_ret = "from nginx"
    fake_args = {"path": str(temp_saltclass_tree)}
    fake_pillar = {}
    fake_minion_id = "fake_id"
    try:
        full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
        parsed_ret = full_ret["nginx_scalar"]
    # Fail the test if we hit our NoneType error
    except TypeError as err:
        pytest.fail(err)
    # Else give the parsed content result
    assert expected_ret == parsed_ret
