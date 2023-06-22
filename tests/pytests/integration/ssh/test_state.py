import json

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


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
      test.succeed_without_changes
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
    top_file = """
    {%- from "test/map.jinja" import abc with context %}
    base:
      'localhost':
        - test
      '127.0.0.1':
        - test
    """
    map_file = """
    {%- set abc = "def" %}
    """
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
    state_tempfile = pytest.helpers.temp_file(
        "test.sls", state_file, base_env_state_tree_root_dir
    )

    with top_tempfile, map_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="class")
def state_tree_render_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_render
      '127.0.0.1':
        - fail_render
    """
    state_file = r"""
    abc var is not defined {{ abc }}:
      test.nop
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_render.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="class")
def state_tree_req_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_req
      '127.0.0.1':
        - fail_req
    """
    state_file = """
    This has an invalid requisite:
      test.nop:
        - name: foo
        - require_in:
          - file.managed: invalid_requisite
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_req.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="class")
def state_tree_structure_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_structure
      '127.0.0.1':
        - fail_structure
    """
    state_file = """
    extend:
      Some file state:
        file:
            - name: /tmp/bar
            - contents: bar
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_structure.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="class")
def state_tree_run_fail(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_run
      '127.0.0.1':
        - fail_run
    """
    state_file = """
    This file state fails:
      file.managed:
        - name: /tmp/non/ex/is/tent
        - makedirs: false
        - contents: foo
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_run.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="class")
def pillar_tree_render_fail(base_env_pillar_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_render
      '127.0.0.1':
        - fail_render
    """
    pillar_file = r"""
    not_defined: {{ abc }}
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    pillar_tempfile = pytest.helpers.temp_file(
        "fail_render.sls", pillar_file, base_env_pillar_tree_root_dir
    )
    with top_tempfile, pillar_tempfile:
        yield


@pytest.fixture(scope="class")
def state_tree_render_module_exception(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - fail_module_exception
      '127.0.0.1':
        - fail_module_exception
    """
    state_file = r"""
    This should fail being rendered:
      test.show_notification:
        - text: {{ salt["disk.usage"]("c") | yaml_dquote }}
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "fail_module_exception.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, state_tempfile:
        yield


@pytest.mark.slow_test
def test_state_with_import(salt_ssh_cli, state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run("state.sls", "test")
    assert ret.returncode == 0
    assert ret.data


@pytest.mark.parametrize(
    "ssh_cmd",
    [
        "state.sls",
        "state.highstate",
        "state.apply",
        "state.show_top",
        "state.show_highstate",
        "state.show_low_sls",
        "state.show_lowstate",
        "state.sls_id",
        "state.show_sls",
        "state.top",
    ],
)
@pytest.mark.slow_test
def test_state_with_import_dir(salt_ssh_cli, state_tree_dir, ssh_cmd):
    """
    verify salt-ssh can use imported map files in states
    when the map files are in another directory outside of
    sls files importing them.
    """
    if ssh_cmd in ("state.sls", "state.show_low_sls", "state.show_sls"):
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "test")
    elif ssh_cmd == "state.top":
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "top.sls")
    elif ssh_cmd == "state.sls_id":
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "Ok with def", "test")
    else:
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd)
    assert ret.returncode == 0
    if ssh_cmd == "state.show_top":
        assert ret.data == {"base": ["test", "master_tops_test"]} or {"base": ["test"]}
    elif ssh_cmd in ("state.show_highstate", "state.show_sls"):
        assert ret.data == {
            "Ok with def": {
                "__sls__": "test",
                "__env__": "base",
                "test": ["succeed_without_changes", {"order": 10000}],
            }
        }
    elif ssh_cmd in ("state.show_low_sls", "state.show_lowstate", "state.show_sls"):
        assert ret.data == [
            {
                "state": "test",
                "name": "Ok with def",
                "__sls__": "test",
                "__env__": "base",
                "__id__": "Ok with def",
                "order": 10000,
                "fun": "succeed_without_changes",
            }
        ]
    else:
        assert ret.data["test_|-Ok with def_|-Ok with def_|-succeed_without_changes"][
            "result"
        ]
    assert ret.data


@pytest.fixture
def nested_state_tree(base_env_state_tree_root_dir, tmp_path):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    state_file = """
    /{}/file.txt:
      file.managed:
        - source: salt://foo/file.jinja
        - template: jinja
    """.format(
        tmp_path
    )
    file_jinja = """
    {% from 'foo/map.jinja' import comment %}{{ comment }}
    """
    map_file = """
    {% set comment = "blah blah" %}
    """
    statedir = base_env_state_tree_root_dir / "foo"
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file("map.jinja", map_file, statedir)
    file_tempfile = pytest.helpers.temp_file("file.jinja", file_jinja, statedir)
    state_tempfile = pytest.helpers.temp_file("init.sls", state_file, statedir)

    with top_tempfile, map_tempfile, state_tempfile, file_tempfile:
        yield


@pytest.mark.slow_test
def test_state_with_import_from_dir(salt_ssh_cli, nested_state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run(
        "--extra-filerefs=salt://foo/map.jinja", "state.apply", "foo"
    )
    assert ret.returncode == 0
    assert ret.data


@pytest.mark.slow_test
def test_state_low(salt_ssh_cli):
    """
    test state.low with salt-ssh
    """
    ret = salt_ssh_cli.run(
        "state.low", '{"state": "cmd", "fun": "run", "name": "echo blah"}'
    )
    assert (
        json.loads(ret.stdout)["localhost"]["cmd_|-echo blah_|-echo blah_|-run"][
            "changes"
        ]["stdout"]
        == "blah"
    )


@pytest.mark.slow_test
def test_state_high(salt_ssh_cli):
    """
    test state.high with salt-ssh
    """
    ret = salt_ssh_cli.run("state.high", '{"echo blah": {"cmd": ["run"]}}')
    assert (
        json.loads(ret.stdout)["localhost"]["cmd_|-echo blah_|-echo blah_|-run"][
            "changes"
        ]["stdout"]
        == "blah"
    )


@pytest.mark.slow_test
@pytest.mark.usefixtures("state_tree_render_fail")
class TestRenderExceptionRetcode:
    """
    Verify salt-ssh fails with a retcode > 0 when a state rendering fails.
    """

    def test_retcode_state_sls_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls", "fail_render")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_highstate_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.highstate")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_sls_id_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls_id", "foo", "fail_render")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_sls_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_sls", "fail_render")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_low_sls_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_low_sls", "fail_render")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_highstate_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_highstate")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_lowstate_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_lowstate")
        # state.show_lowstate exits with 0 for non-ssh as well
        self._assert_ret(ret, 0)

    def test_retcode_state_top_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.top", "top.sls")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_single_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.single", "file")
        assert ret.returncode == EX_AGGREGATE
        assert isinstance(ret.data, str)
        assert "single() missing 1 required positional argument" in ret.data

    def _assert_ret(self, ret, retcode):
        assert ret.returncode == retcode
        assert isinstance(ret.data, list)
        assert ret.data
        assert isinstance(ret.data[0], str)
        assert ret.data[0].startswith(
            "Rendering SLS 'base:fail_render' failed: Jinja variable 'abc' is undefined;"
        )


@pytest.mark.slow_test
@pytest.mark.usefixtures("pillar_tree_render_fail")
class TestPillarRenderExceptionRetcode:
    """
    Verify salt-ssh fails with a retcode > 0 when a pillar rendering fails.
    """

    def test_retcode_state_sls_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls", "basic")
        self._assert_ret(ret)

    def test_retcode_state_highstate_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.highstate")
        self._assert_ret(ret)

    def test_retcode_state_sls_id_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls_id", "foo", "basic")
        self._assert_ret(ret)

    def test_retcode_state_show_sls_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_sls", "basic")
        self._assert_ret(ret)

    def test_retcode_state_show_low_sls_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_low_sls", "basic")
        self._assert_ret(ret)

    def test_retcode_state_show_highstate_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_highstate")
        self._assert_ret(ret)

    def test_retcode_state_show_lowstate_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_lowstate")
        self._assert_ret(ret)

    def test_retcode_state_top_pillar_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.top", "top.sls")
        self._assert_ret(ret)

    def _assert_ret(self, ret):
        assert ret.returncode == EX_AGGREGATE
        assert isinstance(ret.data, list)
        assert ret.data
        assert isinstance(ret.data[0], str)
        assert ret.data[0] == "Pillar failed to render with the following messages:"
        assert ret.data[1].startswith("Rendering SLS 'fail_render' failed.")


@pytest.mark.slow_test
@pytest.mark.usefixtures("state_tree_req_fail")
class TestStateReqFailRetcode:
    """
    Verify salt-ssh fails with a retcode > 0 when a highstate verification fails.
    ``state.show_highstate`` does not validate this.
    """

    def test_retcode_state_sls_invalid_requisite(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls", "fail_req")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_highstate_invalid_requisite(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.highstate")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_sls_invalid_requisite(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_sls", "fail_req")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_low_sls_invalid_requisite(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_low_sls", "fail_req")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_lowstate_invalid_requisite(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_lowstate")
        # state.show_lowstate exits with 0 for non-ssh as well
        self._assert_ret(ret, 0)

    def test_retcode_state_top_invalid_requisite(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.top", "top.sls")
        self._assert_ret(ret, EX_AGGREGATE)

    def _assert_ret(self, ret, retcode):
        assert ret.returncode == retcode
        assert isinstance(ret.data, list)
        assert ret.data
        assert isinstance(ret.data[0], str)
        assert ret.data[0].startswith(
            "Invalid requisite in require: file.managed for invalid_requisite"
        )


@pytest.mark.slow_test
@pytest.mark.usefixtures("state_tree_structure_fail")
class TestStateStructureFailRetcode:
    """
    Verify salt-ssh fails with a retcode > 0 when a highstate verification fails.
    This targets another step of the verification.
    ``state.sls_id`` does not seem to support extends.
    ``state.show_highstate`` does not validate this.
    """

    def test_retcode_state_sls_invalid_structure(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls", "fail_structure")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_highstate_invalid_structure(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.highstate")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_sls_invalid_structure(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_sls", "fail_structure")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_low_sls_invalid_structure(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_low_sls", "fail_structure")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_lowstate_invalid_structure(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_lowstate")
        # state.show_lowstate exits with 0 for non-ssh as well
        self._assert_ret(ret, 0)

    def test_retcode_state_top_invalid_structure(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.top", "top.sls")
        self._assert_ret(ret, EX_AGGREGATE)

    def _assert_ret(self, ret, retcode):
        assert ret.returncode == retcode
        assert isinstance(ret.data, list)
        assert ret.data
        assert isinstance(ret.data[0], str)
        assert ret.data[0].startswith(
            "Cannot extend ID 'Some file state' in 'base:fail_structure"
        )


@pytest.mark.slow_test
@pytest.mark.usefixtures("state_tree_run_fail")
class TestStateRunFailRetcode:
    """
    Verify salt-ssh passes on a failing retcode from state execution.
    """

    def test_retcode_state_sls_run_fail(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls", "fail_run")
        assert ret.returncode == EX_AGGREGATE

    def test_retcode_state_highstate_run_fail(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.highstate")
        assert ret.returncode == EX_AGGREGATE

    def test_retcode_state_sls_id_render_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls_id", "This file state fails", "fail_run")
        assert ret.returncode == EX_AGGREGATE

    def test_retcode_state_top_run_fail(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.top", "top.sls")
        assert ret.returncode == EX_AGGREGATE


@pytest.mark.slow_test
@pytest.mark.usefixtures("state_tree_render_module_exception")
class TestRenderModuleException:
    """
    Verify salt-ssh stops state execution and fails with a retcode > 0
    when a state rendering fails because an execution module throws an exception.
    """

    def test_retcode_state_sls_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls", "fail_module_exception")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_highstate_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.highstate")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_sls_id_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.sls_id", "foo", "fail_module_exception")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_sls_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_sls", "fail_module_exception")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_low_sls_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_low_sls", "fail_module_exception")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_highstate_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_highstate")
        self._assert_ret(ret, EX_AGGREGATE)

    def test_retcode_state_show_lowstate_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.show_lowstate")
        # state.show_lowstate exits with 0 for non-ssh as well
        self._assert_ret(ret, 0)

    def test_retcode_state_top_render_module_exception(self, salt_ssh_cli):
        ret = salt_ssh_cli.run("state.top", "top.sls")
        self._assert_ret(ret, EX_AGGREGATE)

    def _assert_ret(self, ret, retcode):
        assert ret.returncode == retcode
        assert isinstance(ret.data, list)
        assert ret.data
        assert isinstance(ret.data[0], str)
        # While these three should usually follow each other, there
        # can be warnings in between that would break such a logic.
        assert "Rendering SLS 'base:fail_module_exception' failed:" in ret.data[0]
        assert "Problem running salt function in Jinja template:" in ret.data[0]
        assert (
            "Error running 'disk.usage': Invalid flag passed to disk.usage"
            in ret.data[0]
        )
