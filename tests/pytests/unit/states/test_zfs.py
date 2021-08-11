"""
Tests for salt.states.zfs

:codeauthor:    Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs, salt.modules.zfs
:platform:      illumos,freebsd,linux
"""

import pytest
import salt.config
import salt.loader
import salt.states.zfs as zfs
import salt.utils.zfs
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch
from tests.support.zfs import ZFSMockData


@pytest.fixture
def utils_patch():
    return ZFSMockData().get_patched_utils()


@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    utils = salt.loader.utils(opts, whitelist=["zfs"])
    zfs_obj = {
        zfs: {"__opts__": opts, "__grains__": {"kernel": "SunOS"}, "__utils__": utils}
    }

    return zfs_obj


def test_filesystem_absent_nofs(utils_patch):
    """
    Test if filesystem is absent (non existing filesystem)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "filesystem myzpool/filesystem is absent",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.filesystem_absent("myzpool/filesystem")


def test_filesystem_absent_removed(utils_patch):
    """
    Test if filesystem is absent
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "filesystem myzpool/filesystem was destroyed",
        "changes": {"myzpool/filesystem": "destroyed"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(return_value=OrderedDict([("destroyed", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.filesystem_absent("myzpool/filesystem")


def test_filesystem_absent_fail(utils_patch):
    """
    Test if filesystem is absent (with snapshots)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": False,
        "comment": "\n".join(
            [
                "cannot destroy 'myzpool/filesystem': filesystem has children",
                "use 'recursive=True' to destroy the following datasets:",
                "myzpool/filesystem@snap",
            ]
        ),
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(
        return_value=OrderedDict(
            [
                ("destroyed", False),
                (
                    "error",
                    "\n".join(
                        [
                            "cannot destroy 'myzpool/filesystem': filesystem has"
                            " children",
                            "use 'recursive=True' to destroy the following datasets:",
                            "myzpool/filesystem@snap",
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.filesystem_absent("myzpool/filesystem")


def test_volume_absent_novol(utils_patch):
    """
    Test if volume is absent (non existing volume)
    """
    ret = {
        "name": "myzpool/volume",
        "result": True,
        "comment": "volume myzpool/volume is absent",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.volume_absent("myzpool/volume")


def test_volume_absent_removed(utils_patch):
    """
    Test if volume is absent
    """
    ret = {
        "name": "myzpool/volume",
        "result": True,
        "comment": "volume myzpool/volume was destroyed",
        "changes": {"myzpool/volume": "destroyed"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(return_value=OrderedDict([("destroyed", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.volume_absent("myzpool/volume")


def test_volume_absent_fail(utils_patch):
    """
    Test if volume is absent (with snapshots)
    """
    ret = {
        "name": "myzpool/volume",
        "result": False,
        "comment": "\n".join(
            [
                "cannot destroy 'myzpool/volume': volume has children",
                "use 'recursive=True' to destroy the following datasets:",
                "myzpool/volume@snap",
            ]
        ),
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(
        return_value=OrderedDict(
            [
                ("destroyed", False),
                (
                    "error",
                    "\n".join(
                        [
                            "cannot destroy 'myzpool/volume': volume has children",
                            "use 'recursive=True' to destroy the following datasets:",
                            "myzpool/volume@snap",
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.volume_absent("myzpool/volume")


def test_snapshot_absent_nosnap(utils_patch):
    """
    Test if snapshot is absent (non existing snapshot)
    """
    ret = {
        "name": "myzpool/filesystem@snap",
        "result": True,
        "comment": "snapshot myzpool/filesystem@snap is absent",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.snapshot_absent("myzpool/filesystem@snap")


def test_snapshot_absent_removed(utils_patch):
    """
    Test if snapshot is absent
    """
    ret = {
        "name": "myzpool/filesystem@snap",
        "result": True,
        "comment": "snapshot myzpool/filesystem@snap was destroyed",
        "changes": {"myzpool/filesystem@snap": "destroyed"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(return_value=OrderedDict([("destroyed", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.snapshot_absent("myzpool/filesystem@snap")


def test_snapshot_absent_fail(utils_patch):
    """
    Test if snapshot is absent (with snapshots)
    """
    ret = {
        "name": "myzpool/filesystem@snap",
        "result": False,
        "comment": "cannot destroy snapshot myzpool/filesystem@snap: dataset is busy",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(
        return_value=OrderedDict(
            [
                ("destroyed", False),
                (
                    "error",
                    "cannot destroy snapshot myzpool/filesystem@snap: dataset is busy",
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.snapshot_absent("myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_bookmark_absent_nobook(utils_patch):
    """
    Test if bookmark is absent (non existing bookmark)
    """
    ret = {
        "name": "myzpool/filesystem#book",
        "result": True,
        "comment": "bookmark myzpool/filesystem#book is absent",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.bookmark_absent("myzpool/filesystem#book")


def test_bookmark_absent_removed(utils_patch):
    """
    Test if bookmark is absent
    """
    ret = {
        "name": "myzpool/filesystem#book",
        "result": True,
        "comment": "bookmark myzpool/filesystem#book was destroyed",
        "changes": {"myzpool/filesystem#book": "destroyed"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(return_value=OrderedDict([("destroyed", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.destroy": mock_destroy}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.bookmark_absent("myzpool/filesystem#book")


def test_hold_absent_nohold(utils_patch):
    """
    Test if hold is absent (non existing hold)
    """
    ret = {
        "name": "myhold",
        "result": True,
        "comment": "hold myhold is absent",
        "changes": {},
    }

    mock_holds = MagicMock(return_value=OrderedDict([]))
    with patch.dict(zfs.__salt__, {"zfs.holds": mock_holds}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.hold_absent("myhold", "myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_hold_absent_removed(utils_patch):
    """
    Test if hold is absent
    """
    ret = {
        "name": "myhold",
        "result": True,
        "comment": "hold myhold released",
        "changes": OrderedDict(
            [("myzpool/filesystem@snap", OrderedDict([("myhold", "released")]))]
        ),
    }

    mock_holds = MagicMock(
        return_value=OrderedDict([("myhold", "Thu Feb 15 16:24 2018")])
    )
    mock_release = MagicMock(return_value=OrderedDict([("released", True)]))
    with patch.dict(zfs.__salt__, {"zfs.holds": mock_holds}), patch.dict(
        zfs.__salt__, {"zfs.release": mock_release}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.hold_absent("myhold", "myzpool/filesystem@snap")


def test_hold_absent_fail(utils_patch):
    """
    Test if hold is absent (non existing snapshot)
    """
    ret = {
        "name": "myhold",
        "result": False,
        "comment": "cannot open 'myzpool/filesystem@snap': dataset does not exist",
        "changes": {},
    }

    mock_holds = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "error",
                    "cannot open 'myzpool/filesystem@snap': dataset does not exist",
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.holds": mock_holds}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.hold_absent("myhold", "myzpool/filesystem@snap")


def test_hold_present(utils_patch):
    """
    Test if hold is present (hold already present)
    """
    ret = {
        "name": "myhold",
        "result": True,
        "comment": "hold myhold is present for myzpool/filesystem@snap",
        "changes": {},
    }

    mock_holds = MagicMock(
        return_value=OrderedDict([("myhold", "Thu Feb 15 16:24 2018")])
    )
    with patch.dict(zfs.__salt__, {"zfs.holds": mock_holds}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.hold_present("myhold", "myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_hold_present_new(utils_patch):
    """
    Test if hold is present (new)
    """
    ret = {
        "name": "myhold",
        "result": True,
        "comment": "hold myhold added to myzpool/filesystem@snap",
        "changes": {"myzpool/filesystem@snap": {"myhold": "held"}},
    }

    mock_holds = MagicMock(return_value=OrderedDict([]))
    mock_hold = MagicMock(return_value=OrderedDict([("held", True)]))
    with patch.dict(zfs.__salt__, {"zfs.holds": mock_holds}), patch.dict(
        zfs.__salt__, {"zfs.hold": mock_hold}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.hold_present("myhold", "myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_hold_present_fail(utils_patch):
    """
    Test if hold is present (using non existing snapshot)
    """
    ret = {
        "name": "myhold",
        "result": False,
        "comment": (
            "cannot hold snapshot 'zsalt/filesystem@snap': dataset does not exist"
        ),
        "changes": {},
    }

    mock_holds = MagicMock(return_value=OrderedDict([]))
    mock_hold = MagicMock(
        return_value=OrderedDict(
            [
                ("held", False),
                (
                    "error",
                    "cannot hold snapshot 'zsalt/filesystem@snap': dataset does not"
                    " exist",
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.holds": mock_holds}), patch.dict(
        zfs.__salt__, {"zfs.hold": mock_hold}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.hold_present("myhold", "myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_filesystem_present(utils_patch):
    """
    Test if filesystem is present (existing filesystem)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "filesystem myzpool/filesystem is uptodate",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "myzpool/filesystem",
                    OrderedDict(
                        [
                            ("type", OrderedDict([("value", "filesystem")])),
                            ("compression", OrderedDict([("value", False)])),
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.get": mock_get}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.filesystem_present("myzpool/filesystem")


def test_filesystem_present_new(utils_patch):
    """
    Test if filesystem is present (non existing filesystem)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "filesystem myzpool/filesystem was created",
        "changes": {"myzpool/filesystem": "created"},
    }

    mock_exists = MagicMock(return_value=False)
    mock_create = MagicMock(return_value=OrderedDict([("created", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.create": mock_create}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.filesystem_present("myzpool/filesystem")


@pytest.mark.slow_test
def test_filesystem_present_update(utils_patch):
    """
    Test if filesystem is present (non existing filesystem)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "filesystem myzpool/filesystem was updated",
        "changes": {"myzpool/filesystem": {"compression": "lz4"}},
    }

    mock_exists = MagicMock(return_value=True)
    mock_set = MagicMock(return_value=OrderedDict([("set", True)]))
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "myzpool/filesystem",
                    OrderedDict(
                        [
                            ("type", OrderedDict([("value", "filesystem")])),
                            ("compression", OrderedDict([("value", False)])),
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.get": mock_get}
    ), patch.dict(zfs.__salt__, {"zfs.set": mock_set}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.filesystem_present(
            name="myzpool/filesystem",
            properties={"compression": "lz4"},
        )


def test_filesystem_present_fail(utils_patch):
    """
    Test if filesystem is present (non existing pool)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": False,
        "comment": "cannot create 'myzpool/filesystem': no such pool 'myzpool'",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    mock_create = MagicMock(
        return_value=OrderedDict(
            [
                ("created", False),
                (
                    "error",
                    "cannot create 'myzpool/filesystem': no such pool 'myzpool'",
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.create": mock_create}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.filesystem_present("myzpool/filesystem")


@pytest.mark.slow_test
def test_volume_present(utils_patch):
    """
    Test if volume is present (existing volume)
    """
    ret = {
        "name": "myzpool/volume",
        "result": True,
        "comment": "volume myzpool/volume is uptodate",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "myzpool/volume",
                    OrderedDict(
                        [
                            ("type", OrderedDict([("value", "volume")])),
                            ("compression", OrderedDict([("value", False)])),
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.get": mock_get}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.volume_present("myzpool/volume", volume_size="1G")


def test_volume_present_new(utils_patch):
    """
    Test if volume is present (non existing volume)
    """
    ret = {
        "name": "myzpool/volume",
        "result": True,
        "comment": "volume myzpool/volume was created",
        "changes": {"myzpool/volume": "created"},
    }

    mock_exists = MagicMock(return_value=False)
    mock_create = MagicMock(return_value=OrderedDict([("created", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.create": mock_create}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.volume_present("myzpool/volume", volume_size="1G")


def test_volume_present_update(utils_patch):
    """
    Test if volume is present (non existing volume)
    """
    ret = {
        "name": "myzpool/volume",
        "result": True,
        "comment": "volume myzpool/volume was updated",
        "changes": {"myzpool/volume": {"compression": "lz4"}},
    }

    mock_exists = MagicMock(return_value=True)
    mock_set = MagicMock(return_value=OrderedDict([("set", True)]))
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "myzpool/volume",
                    OrderedDict(
                        [
                            ("type", OrderedDict([("value", "volume")])),
                            ("compression", OrderedDict([("value", False)])),
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.get": mock_get}
    ), patch.dict(zfs.__salt__, {"zfs.set": mock_set}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.volume_present(
            name="myzpool/volume",
            volume_size="1G",
            properties={"compression": "lz4"},
        )


def test_volume_present_fail(utils_patch):
    """
    Test if volume is present (non existing pool)
    """
    ret = {
        "name": "myzpool/volume",
        "result": False,
        "comment": "cannot create 'myzpool/volume': no such pool 'myzpool'",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    mock_create = MagicMock(
        return_value=OrderedDict(
            [
                ("created", False),
                ("error", "cannot create 'myzpool/volume': no such pool 'myzpool'"),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.create": mock_create}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.volume_present("myzpool/volume", volume_size="1G")


def test_bookmark_present(utils_patch):
    """
    Test if bookmark is present (bookmark already present)
    """
    ret = {
        "name": "myzpool/filesystem#mybookmark",
        "result": True,
        "comment": "bookmark is present",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.bookmark_present("mybookmark", "myzpool/filesystem@snap")


def test_bookmark_present_new(utils_patch):
    """
    Test if bookmark is present (new)
    """
    ret = {
        "name": "myzpool/filesystem#mybookmark",
        "result": True,
        "comment": (
            "myzpool/filesystem@snap bookmarked as myzpool/filesystem#mybookmark"
        ),
        "changes": {"myzpool/filesystem#mybookmark": "myzpool/filesystem@snap"},
    }

    mock_exists = MagicMock(return_value=False)
    mock_bookmark = MagicMock(return_value=OrderedDict([("bookmarked", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.bookmark": mock_bookmark}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.bookmark_present("mybookmark", "myzpool/filesystem@snap")


def test_bookmark_present_fail(utils_patch):
    """
    Test if bookmark is present (using non existing snapshot)
    """
    ret = {
        "name": "myzpool/filesystem#mybookmark",
        "result": False,
        "comment": (
            "cannot bookmark snapshot 'zsalt/filesystem@snap': dataset does not exist"
        ),
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    mock_bookmark = MagicMock(
        return_value=OrderedDict(
            [
                ("bookmarked", False),
                (
                    "error",
                    "cannot bookmark snapshot 'zsalt/filesystem@snap': dataset does not"
                    " exist",
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.bookmark": mock_bookmark}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.bookmark_present("mybookmark", "myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_snapshot_present(utils_patch):
    """
    Test if snapshot is present (snapshot already present)
    """
    ret = {
        "name": "myzpool/filesystem@snap",
        "result": True,
        "comment": "snapshot is present",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.snapshot_present("myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_snapshot_present_new(utils_patch):
    """
    Test if snapshot is present (new)
    """
    ret = {
        "name": "myzpool/filesystem@snap",
        "result": True,
        "comment": "snapshot myzpool/filesystem@snap was created",
        "changes": {"myzpool/filesystem@snap": "snapshotted"},
    }

    mock_exists = MagicMock(return_value=False)
    mock_snapshot = MagicMock(return_value=OrderedDict([("snapshotted", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.snapshot": mock_snapshot}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.snapshot_present("myzpool/filesystem@snap")


@pytest.mark.slow_test
def test_snapshot_present_fail(utils_patch):
    """
    Test if snapshot is present (using non existing snapshot)
    """
    ret = {
        "name": "myzpool/filesystem@snap",
        "result": False,
        "comment": "cannot open 'myzpool/filesystem': dataset does not exist",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    mock_snapshot = MagicMock(
        return_value=OrderedDict(
            [
                ("snapshotted", False),
                (
                    "error",
                    "cannot open 'myzpool/filesystem': dataset does not exist",
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.snapshot": mock_snapshot}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.snapshot_present("myzpool/filesystem@snap")


def test_propmoted(utils_patch):
    """
    Test promotion of clone (already promoted)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "myzpool/filesystem already promoted",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "myzpool/filesystem",
                    OrderedDict([("origin", OrderedDict([("value", "-")]))]),
                ),
            ]
        )
    )
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.get": mock_get}
    ), patch.dict(zfs.__utils__, utils_patch):
        assert ret == zfs.promoted("myzpool/filesystem")


@pytest.mark.slow_test
def test_propmoted_clone(utils_patch):
    """
    Test promotion of clone
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": True,
        "comment": "myzpool/filesystem promoted",
        "changes": {"myzpool/filesystem": "promoted"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                (
                    "myzpool/filesystem",
                    OrderedDict(
                        [
                            (
                                "origin",
                                OrderedDict(
                                    [("value", "myzool/filesystem_source@clean")]
                                ),
                            ),
                        ]
                    ),
                ),
            ]
        )
    )
    mock_promote = MagicMock(return_value=OrderedDict([("promoted", True)]))
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__salt__, {"zfs.get": mock_get}
    ), patch.dict(zfs.__salt__, {"zfs.promote": mock_promote}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.promoted("myzpool/filesystem")


def test_propmoted_fail(utils_patch):
    """
    Test promotion of clone (unknown dataset)
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": False,
        "comment": "dataset myzpool/filesystem does not exist",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.promoted("myzpool/filesystem")


@pytest.mark.slow_test
def test_scheduled_snapshot_fail(utils_patch):
    """
    Test scheduled_snapshot of unknown dataset
    """
    ret = {
        "name": "myzpool/filesystem",
        "result": False,
        "comment": "dataset myzpool/filesystem does not exist",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zfs.__salt__, {"zfs.exists": mock_exists}), patch.dict(
        zfs.__utils__, utils_patch
    ):
        assert ret == zfs.scheduled_snapshot(
            "myzpool/filesystem", "shadow", schedule={"hour": 6}
        )
