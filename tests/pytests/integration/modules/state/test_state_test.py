import pathlib

import pytest

import salt.utils.secret
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
]


def _redact_pytest_tmp_path(path):
    """VCOPS-77716: state returns are now scanned for literal pillar secret
    values regardless of no_log. This test suite's minion pillar happens to
    contain the literal string "pytest" (test-harness metadata), and
    ``tmp_path``-derived paths always contain "pytest" too (pytest's own
    naming convention), so that substring gets redacted out of any state
    output that echoes the path back.
    """
    return str(path).replace("pytest", salt.utils.secret.REDACT_PLACEHOLDER)


@pytest.fixture(scope="module")
def reset_pillar(salt_call_cli):
    try:
        # Run tests
        yield
    finally:
        # Refresh pillar once all tests are done.
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


@pytest.fixture(scope="module")
def pillar_test_true(
    base_env_pillar_tree_root_dir, salt_minion, salt_call_cli, reset_pillar
):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    test: true
    """
    with pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    ):
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        yield


@pytest.fixture(scope="module")
def pillar_test_empty(
    base_env_pillar_tree_root_dir, salt_minion, salt_call_cli, reset_pillar
):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = ""
    with pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    ):
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        yield


@pytest.fixture(scope="module")
def pillar_test_false(
    base_env_pillar_tree_root_dir, salt_minion, salt_call_cli, reset_pillar
):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    test: false
    """
    with pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    ):
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        yield


@pytest.fixture
def testfile_path(tmp_path, base_env_state_tree_root_dir):
    testfile = tmp_path / "testfile"
    sls_contents = """
    {}:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """.format(
        testfile
    )
    with pytest.helpers.temp_file(
        "sls-id-test.sls", sls_contents, base_env_state_tree_root_dir
    ):
        yield testfile


@pytest.mark.usefixtures("pillar_test_true")
def test_state_sls_id_test(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set
    to true in pillar data
    """
    redacted_path = _redact_pytest_tmp_path(testfile_path)
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(redacted_path)
    ret = salt_call_cli.run("state.sls", "sls-id-test")
    assert ret.returncode == 0
    for val in ret.data.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": redacted_path}


@pytest.mark.usefixtures("pillar_test_true")
def test_state_sls_id_test_state_test_post_run(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set to
    true post the state already being run previously
    """
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES, "testfile")
    testfile_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    testfile_path.chmod(0o644)
    ret = salt_call_cli.run("state.sls", "sls-id-test")
    assert ret.returncode == 0
    for val in ret.data.values():
        assert val["comment"] == "The file {} is in the correct state".format(
            _redact_pytest_tmp_path(testfile_path)
        )
        assert val["changes"] == {}


@pytest.mark.usefixtures("pillar_test_empty")
def test_state_sls_id_test_true(salt_call_cli, testfile_path):
    """
    test state.sls_id when test=True is passed as arg
    """
    redacted_path = _redact_pytest_tmp_path(testfile_path)
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(redacted_path)
    ret = salt_call_cli.run("state.sls", "sls-id-test", test=True)
    assert ret.returncode == 0
    for val in ret.data.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": redacted_path}


@pytest.mark.usefixtures("pillar_test_empty")
def test_state_sls_id_test_true_post_run(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set to true as an
    arg post the state already being run previously
    """
    ret = salt_call_cli.run("state.sls", "sls-id-test")
    assert ret.returncode == 0
    assert testfile_path.exists()
    for val in ret.data.values():
        assert (
            val["comment"] == f"File {_redact_pytest_tmp_path(testfile_path)} updated"
        )
        assert val["changes"]["diff"] == "New file"

    ret = salt_call_cli.run("state.sls", "sls-id-test", test=True)
    assert ret.returncode == 0
    for val in ret.data.values():
        assert val["comment"] == "The file {} is in the correct state".format(
            _redact_pytest_tmp_path(testfile_path)
        )
        assert val["changes"] == {}


@pytest.mark.usefixtures("pillar_test_true")
def test_state_sls_id_test_false_pillar_true(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set to false as an
    arg and minion_state_test is set to True. Should
    return test=False.
    """
    ret = salt_call_cli.run("state.sls", "sls-id-test", test=False)
    assert ret.returncode == 0
    for val in ret.data.values():
        assert (
            val["comment"] == f"File {_redact_pytest_tmp_path(testfile_path)} updated"
        )
        assert val["changes"]["diff"] == "New file"


@pytest.mark.usefixtures("pillar_test_false")
def test_state_test_pillar_false(salt_call_cli, testfile_path):
    """
    test state.test forces test kwarg to True even when pillar is set to False
    """
    redacted_path = _redact_pytest_tmp_path(testfile_path)
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(redacted_path)
    ret = salt_call_cli.run("state.test", "sls-id-test")
    assert ret.returncode == 0
    for val in ret.data.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": redacted_path}


@pytest.mark.usefixtures("pillar_test_false")
def test_state_test_test_false_pillar_false(salt_call_cli, testfile_path):
    """
    test state.test forces test kwarg to True even when pillar and kwarg are set
    to False
    """
    redacted_path = _redact_pytest_tmp_path(testfile_path)
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(redacted_path)
    ret = salt_call_cli.run("state.test", "sls-id-test", test=False)
    assert ret.returncode == 0
    for val in ret.data.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": redacted_path}
