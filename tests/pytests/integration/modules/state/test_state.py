import hashlib
import os
import zipfile

import pytest
import salt.utils.files
import salt.utils.stringutils
from tests.support.runtests import RUNTIME_VARS


def test_get_file_from_env_in_top_match(salt_cli, salt_sub_minion):
    tgt = os.path.join(RUNTIME_VARS.TMP, "prod-cheese-file")
    try:
        ret = salt_cli.run("state.highstate", minion_tgt=salt_sub_minion.id)
        assert ret.exitcode == 0
        assert os.path.isfile(tgt)
        with salt.utils.files.fopen(tgt, "r") as cheese:
            data = salt.utils.stringutils.to_unicode(cheese.read())
        assert "Gromit" in data
        assert "Comte" in data
    finally:
        if os.path.exists(tgt):
            os.unlink(tgt)


def test_issue_56131(salt_minion, base_env_state_tree_root_dir, tmp_path):
    """
    archive.extracted fails if setting an unless clause and pip is not installed.
    """
    zipfile_path = base_env_state_tree_root_dir / "issue-56131.zip"
    with zipfile.ZipFile(
        str(zipfile_path), "w", compression=zipfile.ZIP_DEFLATED
    ) as myzip:
        myzip.writestr("issue-56131.txt", "issue-56131")
    zipfile_hash = hashlib.sha256(zipfile_path.read_bytes()).hexdigest()
    sls_contents = """
    {}:
      archive.extracted:
        - source: salt://issue-56131.zip
        - source_hash: sha256={}
        - archive_format: zip
        - enforce_toplevel: False
        - unless:
          - echo hello; exit 1
    """.format(
        tmp_path, zipfile_hash
    )
    pip_path_dir = tmp_path / "fakepip"
    pip_path_dir.mkdir()
    pip_path = pip_path_dir / "pip.py"
    pip_path.write_text('raise ImportError("No module named pip")')

    environ = os.environ.copy()
    pythonpath = os.environ.get("PYTHONPATH")
    if pythonpath is None:
        pythonpath = str(pip_path_dir)
    else:
        pythonpath = os.pathsep.join([str(pip_path_dir)] + pythonpath.split(os.pathsep))
    environ["PYTHONPATH"] = pythonpath
    salt_call_cli = salt_minion.get_salt_call_cli(environ=environ)
    extract_path = tmp_path / "issue-56131.txt"
    try:
        assert extract_path.exists() is False
        with pytest.helpers.temp_file(
            "issue-56131.sls", sls_contents, base_env_state_tree_root_dir
        ):
            ret = salt_call_cli.run("state.sls", "issue-56131")
            assert ret.exitcode == 0
            staterun = pytest.helpers.state_return(ret.json)
            staterun.assert_state_true_return()
            assert extract_path.exists()
    finally:
        zipfile_path.unlink()


@pytest.mark.skip_unless_on_windows(
    reason="Tested in tests/pytests/functional/modules/state/test_state.py"
)
def test_pydsl(salt_call_cli, base_env_state_tree_root_dir, tmp_path):
    """
    Test the basics of the pydsl
    """
    testfile = tmp_path / "testfile"
    sls_contents = """
    #!pydsl

    state("{}").file("touch")
    """.format(
        testfile
    )
    with pytest.helpers.temp_file(
        "pydsl.sls", sls_contents, base_env_state_tree_root_dir
    ):
        ret = salt_call_cli.run("state.sls", "pydsl")
        assert ret.exitcode == 0
        assert ret.json
        ret = pytest.helpers.state_return(ret.json)
        ret.assert_state_true_return()
        assert testfile.exists()


@pytest.mark.skip_unless_on_windows(
    reason="Tested in tests/pytests/functional/modules/state/test_state.py"
)
def test_state_sls_unicode_characters(salt_call_cli, base_env_state_tree_root_dir):
    """
    test state.sls when state file contains non-ascii characters
    """
    sls_contents = """
    echo1:
      cmd.run:
        - name: "echo 'This is Æ test!'"
    """
    with pytest.helpers.temp_file(
        "issue-46672.sls", sls_contents, base_env_state_tree_root_dir
    ):
        ret = salt_call_cli.run("state.sls", "issue-46672")
        assert ret.exitcode == 0
        assert ret.json
        expected = "cmd_|-echo1_|-echo 'This is Æ test!'_|-run"
        assert expected in ret.json
