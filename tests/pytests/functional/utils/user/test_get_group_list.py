import logging

import pytest

import salt.utils.platform
import salt.utils.user

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_on_windows,
]


@pytest.fixture(scope="module")
def user():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


@pytest.fixture(scope="module")
def dupegroup(user):
    grpid = user.group.info.gid
    with pytest.helpers.create_group(
        name="dupegroup", gid=grpid, members=user.username
    ) as _group:
        yield _group


@pytest.mark.skip_on_platforms(
    darwin=True,
    freebsd=True,
    reason="This test should not run on FreeBSD and Mac due to lack of duplicate GID support",
)
def test_get_group_list_with_duplicate_gid_group(user, dupegroup):
    group_list = salt.utils.user.get_group_list(user.username)
    assert user.group.info.name in group_list
    assert dupegroup.name in group_list
