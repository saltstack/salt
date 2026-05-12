import functools
import os
import pathlib
import subprocess
import tempfile

import pytest

import salt.utils.user


def _check_skip(grains):
    if grains["os"] == "MacOS":
        return True
    return False


pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_on_windows,
    pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip),
    pytest.mark.skipif(
        "grains['osfinger'] == 'Rocky Linux-8' and grains['osarch'] == 'aarch64'",
        reason="Temporarily skip on Rocky Linux 8 Arm64",
    ),
]


@pytest.fixture(scope="module")
def account_1():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


@pytest.fixture(scope="module")
def account_2(account_1):
    with pytest.helpers.create_account(group_name=account_1.group.name) as _account:
        yield _account


def test_chugid(account_1):

    # Since we're changing accounts to touch the file, the parent directory must be user and group writable
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = pathlib.Path(tmp_path)
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
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = pathlib.Path(tmp_path)

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
