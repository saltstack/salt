"""
Tests for salt.states.zpool

:codeauthor:    Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs, salt.modules.zpool
:platform:      illumos,freebsd,linux
"""

import pytest

import salt.config
import salt.loader
import salt.states.zpool as zpool
import salt.utils.zfs
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch
from tests.support.zfs import ZFSMockData


@pytest.fixture
def utils_patch():
    return ZFSMockData().get_patched_utils()


@pytest.fixture
def configure_loader_modules(minion_opts):
    utils = salt.loader.utils(minion_opts, whitelist=["zfs"])
    zpool_obj = {
        zpool: {
            "__opts__": minion_opts,
            "__grains__": {"kernel": "SunOS"},
            "__utils__": utils,
        }
    }

    return zpool_obj


def test_absent_without_pool(utils_patch):
    """
    Test zpool absent without a pool
    """
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "storage pool myzpool is absent",
        "changes": {},
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        assert zpool.absent("myzpool") == ret


def test_absent_destroy_pool(utils_patch):
    """
    Test zpool absent destroying pool
    """
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "storage pool myzpool was destroyed",
        "changes": {"myzpool": "destroyed"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(return_value=OrderedDict([("destroyed", True)]))
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.destroy": mock_destroy}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert zpool.absent("myzpool") == ret


def test_absent_exporty_pool(utils_patch):
    """
    Test zpool absent exporting pool
    """
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "storage pool myzpool was exported",
        "changes": {"myzpool": "exported"},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(return_value=OrderedDict([("exported", True)]))
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.export": mock_destroy}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert zpool.absent("myzpool", export=True) == ret


def test_absent_busy(utils_patch):
    """
    Test zpool absent on a busy pool
    """
    ret = {
        "name": "myzpool",
        "result": False,
        "comment": "\n".join(
            [
                "cannot unmount '/myzpool': Device busy",
                "cannot export 'myzpool': pool is busy",
            ]
        ),
        "changes": {},
    }

    mock_exists = MagicMock(return_value=True)
    mock_destroy = MagicMock(
        return_value=OrderedDict(
            [
                ("exported", False),
                (
                    "error",
                    "\n".join(
                        [
                            "cannot unmount '/myzpool': Device busy",
                            "cannot export 'myzpool': pool is busy",
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.export": mock_destroy}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert zpool.absent("myzpool", export=True) == ret


def test_present_import_success(utils_patch):
    """
    Test zpool present with import allowed and unimported pool
    """
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "storage pool myzpool was imported",
        "changes": {"myzpool": "imported"},
    }

    config = {
        "import": True,
    }

    mock_exists = MagicMock(return_value=False)
    mock_import = MagicMock(return_value=OrderedDict([("imported", True)]))
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.import": mock_import}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert zpool.present("myzpool", config=config) == ret


def test_present_import_fail(utils_patch):
    """
    Test zpool present with import allowed and no unimported pool or layout
    """
    ret = {
        "name": "myzpool",
        "result": False,
        "comment": (
            "storage pool myzpool was not imported, no (valid) layout specified for"
            " creation"
        ),
        "changes": {},
    }

    config = {
        "import": True,
    }

    mock_exists = MagicMock(return_value=False)
    mock_import = MagicMock(return_value=OrderedDict([("imported", False)]))
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.import": mock_import}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert zpool.present("myzpool", config=config) == ret


def test_present_create_success(utils_patch):
    """
    Test zpool present with non existing pool
    """
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "storage pool myzpool was created",
        "changes": {"myzpool": "created"},
    }

    config = {
        "import": False,
    }
    layout = [
        OrderedDict([("mirror", ["disk0", "disk1"])]),
        OrderedDict([("mirror", ["disk2", "disk3"])]),
    ]
    properties = {
        "autoexpand": True,
    }
    filesystem_properties = {
        "quota": "5G",
    }

    mock_exists = MagicMock(return_value=False)
    mock_create = MagicMock(
        return_value=OrderedDict(
            [
                ("created", True),
                (
                    "vdevs",
                    OrderedDict(
                        [
                            ("mirror-0", ["/dev/dsk/disk0", "/dev/dsk/disk1"]),
                            ("mirror-1", ["/dev/dsk/disk2", "/dev/dsk/disk3"]),
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.create": mock_create}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert (
            zpool.present(
                "myzpool",
                config=config,
                layout=layout,
                properties=properties,
                filesystem_properties=filesystem_properties,
            )
            == ret
        )


def test_present_create_fail(utils_patch):
    """
    Test zpool present with non existing pool (without a layout)
    """
    ret = {
        "name": "myzpool",
        "result": False,
        "comment": (
            "storage pool myzpool was not imported, no (valid) layout specified for"
            " creation"
        ),
        "changes": {},
    }

    config = {
        "import": False,
    }

    mock_exists = MagicMock(return_value=False)
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        assert zpool.present("myzpool", config=config) == ret


def test_present_create_passthrough_fail(utils_patch):
    """
    Test zpool present with non existing pool (without a layout)
    """
    ret = {
        "name": "myzpool",
        "result": False,
        "comment": "\n".join(
            [
                "invalid vdev specification",
                "use 'force=True' to override the following errors:",
                "/data/salt/vdisk0 is part of exported pool 'zsalt'",
                "/data/salt/vdisk1 is part of exported pool 'zsalt'",
            ]
        ),
        "changes": {},
    }

    config = {
        "force": False,
        "import": False,
    }
    layout = [
        OrderedDict([("mirror", ["disk0", "disk1"])]),
        OrderedDict([("mirror", ["disk2", "disk3"])]),
    ]
    properties = {
        "autoexpand": True,
    }
    filesystem_properties = {
        "quota": "5G",
    }

    mock_exists = MagicMock(return_value=False)
    mock_create = MagicMock(
        return_value=OrderedDict(
            [
                ("created", False),
                (
                    "error",
                    "\n".join(
                        [
                            "invalid vdev specification",
                            "use 'force=True' to override the following errors:",
                            "/data/salt/vdisk0 is part of exported pool 'zsalt'",
                            "/data/salt/vdisk1 is part of exported pool 'zsalt'",
                        ]
                    ),
                ),
            ]
        )
    )
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.create": mock_create}
    ), patch.dict(zpool.__utils__, utils_patch):
        assert (
            zpool.present(
                "myzpool",
                config=config,
                layout=layout,
                properties=properties,
                filesystem_properties=filesystem_properties,
            )
            == ret
        )


def test_present_update_success(utils_patch):
    """
    Test zpool present with an existing pool that needs an update
    """
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "properties updated",
        "changes": {"myzpool": {"autoexpand": False, "feature@bookmarks": "enabled"}},
    }

    config = {
        "import": False,
    }
    layout = [
        OrderedDict([("mirror", ["disk0", "disk1"])]),
        OrderedDict([("mirror", ["disk2", "disk3"])]),
    ]
    properties = {
        "autoexpand": False,
        "feature@hole_birth": "enabled",
        "feature@bookmarks": "enabled",
    }

    mock_exists = MagicMock(return_value=True)
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                ("comment", "salt managed pool"),
                ("freeing", 0),
                ("listsnapshots", False),
                ("leaked", 0),
                ("feature@obsolete_counts", "enabled"),
                ("feature@sha512", "enabled"),
                ("delegation", True),
                ("dedupditto", "0"),
                ("dedupratio", "1.00x"),
                ("autoexpand", True),
                ("feature@bookmarks", "disabled"),
                ("allocated", 115712),
                ("guid", 1591906802560842214),
                ("feature@large_blocks", "enabled"),
                ("size", 2113929216),
                ("feature@enabled_txg", "active"),
                ("feature@hole_birth", "active"),
                ("capacity", 0),
                ("feature@multi_vdev_crash_dump", "enabled"),
                ("feature@extensible_dataset", "enabled"),
                ("cachefile", "-"),
                ("bootfs", "-"),
                ("autoreplace", True),
                ("readonly", False),
                ("version", "-"),
                ("health", "ONLINE"),
                ("expandsize", "-"),
                ("feature@embedded_data", "active"),
                ("feature@lz4_compress", "active"),
                ("feature@async_destroy", "enabled"),
                ("feature@skein", "enabled"),
                ("feature@empty_bpobj", "enabled"),
                ("feature@spacemap_histogram", "active"),
                ("bootsize", "-"),
                ("free", 2113813504),
                ("feature@device_removal", "enabled"),
                ("failmode", "wait"),
                ("feature@filesystem_limits", "enabled"),
                ("feature@edonr", "enabled"),
                ("altroot", "-"),
                ("fragmentation", "0%"),
            ]
        )
    )
    mock_set = MagicMock(return_value=OrderedDict([("set", True)]))
    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"zpool.get": mock_get}
    ), patch.dict(zpool.__salt__, {"zpool.set": mock_set}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        assert (
            zpool.present(
                "myzpool",
                config=config,
                layout=layout,
                properties=properties,
            )
            == ret
        )


def test_present_update_nochange_success(utils_patch):
    """
    Test zpool present with an up-to-date pool
    """
    config = {
        "import": False,
    }
    layout = [
        OrderedDict([("mirror", ["disk0", "disk1"])]),
        OrderedDict([("mirror", ["disk2", "disk3"])]),
    ]
    properties = {
        "autoexpand": True,
        "feature@hole_birth": "enabled",
        "feature@bookmarks": "enabled",
    }

    mock_exists = MagicMock(return_value=True)
    mock_get = MagicMock(
        return_value=OrderedDict(
            [
                ("comment", "salt managed pool"),
                ("freeing", 0),
                ("listsnapshots", False),
                ("leaked", 0),
                ("feature@obsolete_counts", "enabled"),
                ("feature@sha512", "enabled"),
                ("delegation", True),
                ("dedupditto", "0"),
                ("dedupratio", "1.00x"),
                ("autoexpand", True),
                ("feature@bookmarks", "enabled"),
                ("allocated", 115712),
                ("guid", 1591906802560842214),
                ("feature@large_blocks", "enabled"),
                ("size", 2113929216),
                ("feature@enabled_txg", "active"),
                ("feature@hole_birth", "active"),
                ("capacity", 0),
                ("feature@multi_vdev_crash_dump", "enabled"),
                ("feature@extensible_dataset", "enabled"),
                ("cachefile", "-"),
                ("bootfs", "-"),
                ("autoreplace", True),
                ("readonly", False),
                ("version", "-"),
                ("health", "ONLINE"),
                ("expandsize", "-"),
                ("feature@embedded_data", "active"),
                ("feature@lz4_compress", "active"),
                ("feature@async_destroy", "enabled"),
                ("feature@skein", "enabled"),
                ("feature@empty_bpobj", "enabled"),
                ("feature@spacemap_histogram", "active"),
                ("bootsize", "-"),
                ("free", 2113813504),
                ("feature@device_removal", "enabled"),
                ("failmode", "wait"),
                ("feature@filesystem_limits", "enabled"),
                ("feature@edonr", "enabled"),
                ("altroot", "-"),
                ("fragmentation", "0%"),
            ]
        )
    )

    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "no update needed",
        "changes": {},
    }

    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}):
        with patch.dict(zpool.__salt__, {"zpool.get": mock_get}):
            with patch.dict(zpool.__utils__, utils_patch):
                assert (
                    zpool.present(
                        "myzpool",
                        config=config,
                        layout=layout,
                        properties=properties,
                    )
                    == ret
                )

    # Run state with test=true
    ret = {
        "name": "myzpool",
        "result": True,
        "comment": "storage pool myzpool is uptodate",
        "changes": {},
    }

    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}):
        with patch.dict(zpool.__salt__, {"zpool.get": mock_get}):
            with patch.dict(zpool.__utils__, utils_patch):
                with patch.dict(zpool.__opts__, {"test": True}):
                    assert (
                        zpool.present(
                            "myzpool",
                            config=config,
                            layout=layout,
                            properties=properties,
                        )
                        == ret
                    )
