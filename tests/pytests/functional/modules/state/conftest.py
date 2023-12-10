import shutil

import pytest


@pytest.fixture(scope="module")
def state(modules):
    return modules.state


@pytest.fixture(scope="module")
def state_testfile_dest_path(tmp_path_factory):
    tempfile_dir = tmp_path_factory.mktemp("testfile-dir")
    try:
        yield tempfile_dir / "testfile"
    finally:
        shutil.rmtree(str(tempfile_dir), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree(state_tree, state_testfile_dest_path):
    top_sls_contents = """
    base:
      "*":
        - core
    """
    core_sls_contents = """
    {}:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """.format(
        state_testfile_dest_path
    )
    with pytest.helpers.temp_file(
        "top.sls", top_sls_contents, state_tree
    ), pytest.helpers.temp_file(
        "core.sls", core_sls_contents, state_tree
    ), pytest.helpers.temp_file(
        "testfile", "testfile base env contents", state_tree
    ):
        yield state_tree


@pytest.fixture(autouse=True)
def delete_state_testfile(state_testfile_dest_path):
    # Run Test
    try:
        yield
    finally:
        if state_testfile_dest_path.exists():
            state_testfile_dest_path.unlink()
