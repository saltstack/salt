import functools
import os
import subprocess

import pytest
import salt.utils.user

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_on_windows,
]


@pytest.fixture(scope="module")
def account_1():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


@pytest.fixture(scope="module")
def account_2(account_1):
    with pytest.helpers.create_account(group_name=account_1.group.name) as _account:
        yield _account


def test_chugid(account_1, tmp_path):

    # Since we're changing accounts to touch the file, the parent directory must be user and group writable
    tmp_path.chmod(0o770)

    testfile = tmp_path / "testfile"

    # We should fail because the parent directory group owner is not the account running the test
    ret = subprocess.run(
        ["touch", str(testfile)],
        preexec_fn=functools.partial(
            salt.utils.user.chugid_and_umask,
            runas=account_1.username,
            umask=None,
            group=None,
        ),
        check=False,
    )
    assert ret.returncode != 0

    # However if we change the group ownership to one of the account's groups, it should succeed
    os.chown(str(tmp_path), 0, account_1.group.info.gid)

    ret = subprocess.run(
        ["touch", str(testfile)],
        preexec_fn=functools.partial(
            salt.utils.user.chugid_and_umask,
            runas=account_1.username,
            umask=None,
            group=None,
        ),
        check=False,
    )
    assert ret.returncode == 0
    assert testfile.exists()
    testfile_stat = testfile.stat()
    assert testfile_stat.st_uid == account_1.info.uid
    assert testfile_stat.st_gid == account_1.info.gid


def test_chugid_and_group(account_1, account_2, tmp_path):

    # Since we're changing accounts to touch the file, the parent directory must be world-writable
    tmp_path.chmod(0o770)

    testfile = tmp_path / "testfile"

    # We should fail because the parent directory group owner is not the account running the test
    ret = subprocess.run(
        ["touch", str(testfile)],
        preexec_fn=functools.partial(
            salt.utils.user.chugid_and_umask,
            runas=account_2.username,
            umask=None,
            group=account_1.group.name,
        ),
        check=False,
    )
    assert ret.returncode != 0

    # However if we change the group ownership to one of the account's groups, it should succeed
    os.chown(str(tmp_path), 0, account_1.group.info.gid)

    ret = subprocess.run(
        ["touch", str(testfile)],
        preexec_fn=functools.partial(
            salt.utils.user.chugid_and_umask,
            runas=account_2.username,
            umask=None,
            group=account_1.group.name,
        ),
        check=False,
    )
    assert ret.returncode == 0
    assert testfile.exists()
    testfile_stat = testfile.stat()
    assert testfile_stat.st_uid == account_2.info.uid
    assert testfile_stat.st_gid == account_1.group.info.gid
