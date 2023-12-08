import filecmp

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_issue_25250_force_copy_deletes(file, tmp_path):
    """
    ensure force option in copy state does not delete target file
    """
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.write_text("source")
    dest.write_text("destination")

    ret = file.copy(name=str(dest), source=str(source), force=True)
    assert ret.result is True
    assert filecmp.cmp(str(source), str(dest)) is True


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="Windows does not report any file modes.")
def test_file_copy_make_dirs(modules, file, tmp_path, state_file_account):
    """
    ensure make_dirs creates correct user perms
    """
    source = tmp_path / "source"
    source.write_text("source")
    dest = tmp_path / "dir1" / "dir2" / "dest"

    mode = "0644"
    ret = file.copy(
        name=str(dest),
        source=str(source),
        user=state_file_account.username,
        makedirs=True,
        mode=mode,
    )
    assert ret.result is True
    file_checks = [
        (str(dest), mode),
        (str(dest.parent), "0755"),
        (str(dest.parent.parent), "0755"),
    ]
    for check, expected_mode in file_checks:
        user_check = modules.file.get_user(check)
        mode_check = modules.file.get_mode(check)
        assert user_check == state_file_account.username
        assert salt.utils.files.normalize_mode(mode_check) == expected_mode
