import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
]


def test_issue_54765_salt(tmp_path, salt_cli, salt_minion):
    file_path = str(tmp_path / "issue-54765")
    ret = salt_cli.run(
        "state.sls",
        mods="issue-54765",
        pillar={"file_path": file_path},
        minion_tgt=salt_minion.id,
    ).data
    key = f"file_|-issue-54765_|-{file_path}_|-managed"
    assert key in ret
    assert ret[key]["result"] is True
    with salt.utils.files.fopen(file_path, "r") as fp:
        assert fp.read().strip() == "bar"


def test_issue_54765_call(tmp_path, salt_call_cli):
    file_path = str(tmp_path / "issue-54765")
    ret = salt_call_cli.run(
        "--local",
        "state.apply",
        "issue-54765",
        pillar=f"{{'file_path': '{file_path}'}}",
    )
    key = f"file_|-issue-54765_|-{file_path}_|-managed"
    assert ret.data[key]["result"] is True
    with salt.utils.files.fopen(file_path, "r") as fp:
        assert fp.read().strip() == "bar"
