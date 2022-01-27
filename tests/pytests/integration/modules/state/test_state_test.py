import pathlib

import pytest
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def reset_pillar(salt_call_cli):
    try:
        # Run tests
        yield
    finally:
        # Refresh pillar once all tests are done.
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True


@pytest.fixture(scope="module")
def pillar_test_true(pillar_tree, salt_minion, salt_call_cli):
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
    with pillar_tree.base.temp_file("top.sls", top_file), pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    ):
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True
        yield


@pytest.fixture(scope="module")
def pillar_test_empty(pillar_tree, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = ""
    with pillar_tree.base.temp_file("top.sls", top_file), pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    ):
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True
        yield


@pytest.fixture(scope="module")
def pillar_test_false(pillar_tree, salt_minion, salt_call_cli):
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
    with pillar_tree.base.temp_file("top.sls", top_file), pillar_tree.base.temp_file(
        "basic.sls", basic_pillar_file
    ):
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True
        yield


@pytest.fixture
def testfile_path(tmp_path, state_tree):
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
    with state_tree.base.temp_file("sls-id-test.sls", sls_contents):
        yield testfile


@pytest.mark.usefixtures("pillar_test_true")
def test_state_sls_id_test(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set
    to true in pillar data
    """
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(testfile_path)
    ret = salt_call_cli.run("state.sls", "sls-id-test")
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": str(testfile_path)}


@pytest.mark.usefixtures("pillar_test_true")
def test_state_sls_id_test_state_test_post_run(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set to
    true post the state already being run previously
    """
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES, "testfile")
    testfile_path.write_text(source.read_text())
    testfile_path.chmod(0o644)
    ret = salt_call_cli.run("state.sls", "sls-id-test")
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == "The file {} is in the correct state".format(
            testfile_path
        )
        assert val["changes"] == {}


@pytest.mark.usefixtures("pillar_test_empty")
def test_state_sls_id_test_true(salt_call_cli, testfile_path):
    """
    test state.sls_id when test=True is passed as arg
    """
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(testfile_path)
    ret = salt_call_cli.run("state.sls", "sls-id-test", test=True)
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": str(testfile_path)}


@pytest.mark.usefixtures("pillar_test_empty")
def test_state_sls_id_test_true_post_run(salt_call_cli, testfile_path):
    """
    test state.sls_id when test is set to true as an
    arg post the state already being run previously
    """
    ret = salt_call_cli.run("state.sls", "sls-id-test")
    assert ret.exitcode == 0
    assert testfile_path.exists()
    for val in ret.json.values():
        assert val["comment"] == "File {} updated".format(testfile_path)
        assert val["changes"]["diff"] == "New file"

    ret = salt_call_cli.run("state.sls", "sls-id-test", test=True)
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == "The file {} is in the correct state".format(
            testfile_path
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
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == "File {} updated".format(testfile_path)
        assert val["changes"]["diff"] == "New file"


@pytest.mark.usefixtures("pillar_test_false")
def test_state_test_pillar_false(salt_call_cli, testfile_path):
    """
    test state.test forces test kwarg to True even when pillar is set to False
    """
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(testfile_path)
    ret = salt_call_cli.run("state.test", "sls-id-test")
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": str(testfile_path)}


@pytest.mark.usefixtures("pillar_test_false")
def test_state_test_test_false_pillar_false(salt_call_cli, testfile_path):
    """
    test state.test forces test kwarg to True even when pillar and kwarg are set
    to False
    """
    expected_comment = (
        "The file {} is set to be changed\nNote: No changes made, actual changes may\n"
        "be different due to other states."
    ).format(testfile_path)
    ret = salt_call_cli.run("state.test", "sls-id-test", test=False)
    assert ret.exitcode == 0
    for val in ret.json.values():
        assert val["comment"] == expected_comment
        assert val["changes"] == {"newfile": str(testfile_path)}
