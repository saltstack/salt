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
    """
    default_init.write_text(test_list)

    minion_node_file = nodes_dir / "{}.yml".format(minion_id)
    nodes_text = """
    environment: base

    classes:
    {% for class in ['default', 'roles.*', 'empty.*'] %}
      - {{ class }}
    {% endfor %}
    """
    minion_node_file.write_text(nodes_text)

    (default_dir / "users.yml").write_text("test: this is a test")
    (default_dir / "empty.yml").write_text("test: this is a test")
    (default_dir / "motd.yml").write_text("test: this is a test")
    (roles_dir / "app.yml").write_text("test: this is a test")
    (nginx_subdir / "init.yml").write_text("test: this is a test")

    return dirname


def test_succeeds(temp_saltclass_tree):
    expected_ret = [
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
