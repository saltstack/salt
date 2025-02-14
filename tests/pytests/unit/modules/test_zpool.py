"""
Tests for salt.modules.zpool

:codeauthor:    Nitin Madhok <nmadhok@g.clemson.edu>, Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux
"""

import pytest

import salt.loader
import salt.modules.zpool as zpool
import salt.utils.decorators
import salt.utils.decorators.path
import salt.utils.zfs
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch
from tests.support.zfs import ZFSMockData

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture
def utils_patch():
    return ZFSMockData().get_patched_utils()


@pytest.fixture
def configure_loader_modules(minion_opts):
    utils = salt.loader.utils(
        minion_opts, whitelist=["zfs", "args", "systemd", "path", "platform"]
    )
    zpool_obj = {
        zpool: {
            "__opts__": minion_opts,
            "__utils__": utils,
        },
    }

    return zpool_obj


@pytest.mark.slow_test
def test_exists_success(utils_patch):
    """
    Tests successful return of exists function
    """
    ret = {}
    ret["stdout"] = (
        "NAME      SIZE  ALLOC   FREE    CAP  DEDUP  HEALTH  ALTROOT\n"
        "myzpool   149G   128K   149G     0%  1.00x  ONLINE  -"
    )
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        assert zpool.exists("myzpool")


@pytest.mark.slow_test
def test_exists_failure(utils_patch):
    """
    Tests failure return of exists function
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'myzpool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        assert not zpool.exists("myzpool")


def test_healthy(utils_patch):
    """
    Tests successful return of healthy function
    """
    ret = {}
    ret["stdout"] = "all pools are healthy"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        assert zpool.healthy()


def test_status(utils_patch):
    """
    Tests successful return of status function
    """
    ret = {}
    ret["stdout"] = "\n".join(
        [
            "  pool: mypool",
            " state: ONLINE",
            "  scan: scrub repaired 0 in 0h6m with 0 errors on Mon Dec 21 02:06:17"
            " 2015",
            "config:",
            "",
            "\tNAME        STATE     READ WRITE CKSUM",
            "\tmypool      ONLINE       0     0     0",
            "\t  mirror-0  ONLINE       0     0     0",
            "\t    c2t0d0  ONLINE       0     0     0",
            "\t    c2t1d0  ONLINE       0     0     0",
            "",
            "errors: No known data errors",
        ]
    )
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.status()
        assert "ONLINE" == ret["mypool"]["state"]


def test_status_with_colons_in_vdevs(utils_patch):
    """
    Tests successful return of status function
    """
    ret = {}
    ret["stdout"] = "\n".join(
        [
            "  pool: mypool",
            " state: ONLINE",
            "  scan: scrub repaired 0 in 0h6m with 0 errors on Mon Dec 21 02:06:17"
            " 2015",
            "config:",
            "",
            "\tNAME        STATE     READ WRITE CKSUM",
            "\tmypool      ONLINE       0     0     0",
            "\t  mirror-0  ONLINE       0     0     0",
            "\t    usb-WD_My_Book_Duo_25F6_....32-0:0  ONLINE       0     0     0",
            "\t    usb-WD_My_Book_Duo_25F6_....32-0:1  ONLINE       0     0     0",
            "",
            "errors: No known data errors",
        ]
    )
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.status()
        assert "ONLINE" == ret["mypool"]["state"]


@pytest.mark.slow_test
def test_iostat(utils_patch):
    """
    Tests successful return of iostat function
    """
    ret = {}
    ret["stdout"] = "\n".join(
        [
            "               capacity     operations    bandwidth",
            "pool        alloc   free   read  write   read  write",
            "----------  -----  -----  -----  -----  -----  -----",
            "mypool      46.7G  64.3G      4     19   113K   331K",
            "  mirror    46.7G  64.3G      4     19   113K   331K",
            "    c2t0d0      -      -      1     10   114K   334K",
            "    c2t1d0      -      -      1     10   114K   334K",
            "----------  -----  -----  -----  -----  -----  -----",
        ]
    )
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.iostat("mypool", parsable=False)
        assert "46.7G" == ret["mypool"]["capacity-alloc"]


def test_iostat_parsable(utils_patch):
    """
    Tests successful return of iostat function

    .. note:
        The command output is the same as the non parsable!
        There is no -p flag for zpool iostat, but our type
        conversions can handle this!
    """
    ret = {}
    ret["stdout"] = "\n".join(
        [
            "               capacity     operations    bandwidth",
            "pool        alloc   free   read  write   read  write",
            "----------  -----  -----  -----  -----  -----  -----",
            "mypool      46.7G  64.3G      4     19   113K   331K",
            "  mirror    46.7G  64.3G      4     19   113K   331K",
            "    c2t0d0      -      -      1     10   114K   334K",
            "    c2t1d0      -      -      1     10   114K   334K",
            "----------  -----  -----  -----  -----  -----  -----",
        ]
    )
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.iostat("mypool", parsable=True)
        assert 50143743180 == ret["mypool"]["capacity-alloc"]


def test_list(utils_patch):
    """
    Tests successful return of list function
    """
    ret = {}
    ret["stdout"] = "mypool\t1.81T\t661G\t1.17T\t35%\t11%\tONLINE"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.list_(parsable=False)
        res = OrderedDict(
            [
                (
                    "mypool",
                    OrderedDict(
                        [
                            ("size", "1.81T"),
                            ("alloc", "661G"),
                            ("free", "1.17T"),
                            ("cap", "35%"),
                            ("frag", "11%"),
                            ("health", "ONLINE"),
                        ]
                    ),
                )
            ]
        )
        assert ret == res


@pytest.mark.slow_test
def test_list_parsable(utils_patch):
    """
    Tests successful return of list function with parsable output
    """
    ret = {}
    ret["stdout"] = "mypool\t1.81T\t661G\t1.17T\t35%\t11%\tONLINE"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.list_(parsable=True)
        res = OrderedDict(
            [
                (
                    "mypool",
                    OrderedDict(
                        [
                            ("size", 1990116046274),
                            ("alloc", 709743345664),
                            ("free", 1286428604497),
                            ("cap", "35%"),
                            ("frag", "11%"),
                            ("health", "ONLINE"),
                        ]
                    ),
                )
            ]
        )
        assert ret == res


def test_get(utils_patch):
    """
    Tests successful return of get function
    """
    ret = {}
    ret["stdout"] = "mypool\tsize\t1.81T\t-\n"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.get("mypool", "size", parsable=False)
        res = OrderedDict(OrderedDict([("size", "1.81T")]))
        assert ret == res


@pytest.mark.slow_test
def test_get_parsable(utils_patch):
    """
    Tests successful return of get function with parsable output
    """
    ret = {}
    ret["stdout"] = "mypool\tsize\t1.81T\t-\n"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.get("mypool", "size", parsable=True)
        res = OrderedDict(OrderedDict([("size", 1990116046274)]))
        assert ret == res


@pytest.mark.slow_test
def test_get_whitespace(utils_patch):
    """
    Tests successful return of get function with a string with whitespaces
    """
    ret = {}
    ret["stdout"] = "mypool\tcomment\tmy testing pool\t-\n"
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.get("mypool", "comment")
        res = OrderedDict(OrderedDict([("comment", "my testing pool")]))
        assert ret == res


@pytest.mark.slow_test
def test_scrub_start(utils_patch):
    """
    Tests start of scrub
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    mock_exists = MagicMock(return_value=True)

    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"cmd.run_all": mock_cmd}
    ), patch.dict(zpool.__utils__, utils_patch):
        ret = zpool.scrub("mypool")
        res = OrderedDict(OrderedDict([("scrubbing", True)]))
        assert ret == res


@pytest.mark.slow_test
def test_scrub_pause(utils_patch):
    """
    Tests pause of scrub
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    mock_exists = MagicMock(return_value=True)

    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"cmd.run_all": mock_cmd}
    ), patch.dict(zpool.__utils__, utils_patch):
        ret = zpool.scrub("mypool", pause=True)
        res = OrderedDict(OrderedDict([("scrubbing", False)]))
        assert ret == res


@pytest.mark.slow_test
def test_scrub_stop(utils_patch):
    """
    Tests pauze of scrub
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)
    mock_exists = MagicMock(return_value=True)

    with patch.dict(zpool.__salt__, {"zpool.exists": mock_exists}), patch.dict(
        zpool.__salt__, {"cmd.run_all": mock_cmd}
    ), patch.dict(zpool.__utils__, utils_patch):
        ret = zpool.scrub("mypool", stop=True)
        res = OrderedDict(OrderedDict([("scrubbing", False)]))
        assert ret == res


def test_split_success(utils_patch):
    """
    Tests split on success
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.split("datapool", "backuppool")
        res = OrderedDict([("split", True)])
        assert ret == res


@pytest.mark.slow_test
def test_split_exist_new(utils_patch):
    """
    Tests split on exising new pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "Unable to split datapool: pool already exists"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.split("datapool", "backuppool")
        res = OrderedDict(
            [
                ("split", False),
                ("error", "Unable to split datapool: pool already exists"),
            ]
        )
        assert ret == res


def test_split_missing_pool(utils_patch):
    """
    Tests split on missing source pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'datapool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.split("datapool", "backuppool")
        res = OrderedDict(
            [("split", False), ("error", "cannot open 'datapool': no such pool")]
        )
        assert ret == res


@pytest.mark.slow_test
def test_split_not_mirror(utils_patch):
    """
    Tests split on source pool is not a mirror
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = (
        "Unable to split datapool: Source pool must be composed only of mirrors"
    )
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.split("datapool", "backuppool")
        res = OrderedDict(
            [
                ("split", False),
                (
                    "error",
                    "Unable to split datapool: Source pool must be composed only of"
                    " mirrors",
                ),
            ]
        )
        assert ret == res


def test_labelclear_success(utils_patch):
    """
    Tests labelclear on successful label removal
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.labelclear("/dev/rdsk/c0t0d0", force=False)
        res = OrderedDict([("labelcleared", True)])
        assert ret == res


def test_labelclear_nodevice(utils_patch):
    """
    Tests labelclear on non existing device
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "failed to open /dev/rdsk/c0t0d0: No such file or directory"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.labelclear("/dev/rdsk/c0t0d0", force=False)
        res = OrderedDict(
            [
                ("labelcleared", False),
                (
                    "error",
                    "failed to open /dev/rdsk/c0t0d0: No such file or directory",
                ),
            ]
        )
        assert ret == res


def test_labelclear_cleared(utils_patch):
    """
    Tests labelclear on device with no label
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "failed to read label from /dev/rdsk/c0t0d0"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.labelclear("/dev/rdsk/c0t0d0", force=False)
        res = OrderedDict(
            [
                ("labelcleared", False),
                ("error", "failed to read label from /dev/rdsk/c0t0d0"),
            ]
        )
        assert ret == res


def test_labelclear_exported(utils_patch):
    """
    Tests labelclear on device with from exported pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "\n".join(
        [
            "use '-f' to override the following error:",
            '/dev/rdsk/c0t0d0 is a member of exported pool "mypool"',
        ]
    )
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)
    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.labelclear("/dev/rdsk/c0t0d0", force=False)
        res = OrderedDict(
            [
                ("labelcleared", False),
                (
                    "error",
                    "use 'force=True' to override the following"
                    " error:\n/dev/rdsk/c0t0d0 is a member of exported pool"
                    ' "mypool"',
                ),
            ]
        )
        assert ret == res


@pytest.mark.skip_if_binaries_missing("mkfile", reason="Cannot find mkfile executable")
def test_create_file_vdev_success(utils_patch):
    """
    Tests create_file_vdev when out of space
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.create_file_vdev("64M", "/vdisks/disk0")
        res = OrderedDict([("/vdisks/disk0", "created")])
        assert ret == res


@pytest.mark.skip_if_binaries_missing("mkfile", reason="Cannot find mkfile executable")
def test_create_file_vdev_nospace(utils_patch):
    """
    Tests create_file_vdev when out of space
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = (
        "/vdisks/disk0: initialized 10424320 of 67108864 bytes: No space left on"
        " device"
    )
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.create_file_vdev("64M", "/vdisks/disk0")
        res = OrderedDict(
            [
                ("/vdisks/disk0", "failed"),
                (
                    "error",
                    OrderedDict(
                        [
                            (
                                "/vdisks/disk0",
                                " initialized 10424320 of 67108864 bytes: No space"
                                " left on device",
                            ),
                        ]
                    ),
                ),
            ]
        )
        assert ret == res


def test_export_success(utils_patch):
    """
    Tests export
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.export("mypool")
        res = OrderedDict([("exported", True)])
        assert ret == res


@pytest.mark.slow_test
def test_export_nopool(utils_patch):
    """
    Tests export when the pool does not exists
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'mypool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.export("mypool")
        res = OrderedDict(
            [("exported", False), ("error", "cannot open 'mypool': no such pool")]
        )
        assert ret == res


@pytest.mark.slow_test
def test_import_success(utils_patch):
    """
    Tests import
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.import_("mypool")
        res = OrderedDict([("imported", True)])
        assert ret == res


def test_import_duplicate(utils_patch):
    """
    Tests import with already imported pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "\n".join(
        [
            "cannot import 'mypool': a pool with that name already exists",
            "use the form 'zpool import <pool | id> <newpool>' to give it a new"
            " name",
        ]
    )
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.import_("mypool")
        res = OrderedDict(
            [
                ("imported", False),
                (
                    "error",
                    "cannot import 'mypool': a pool with that name already"
                    " exists\nuse the form 'zpool import <pool | id> <newpool>' to"
                    " give it a new name",
                ),
            ]
        )
        assert ret == res


def test_import_nopool(utils_patch):
    """
    Tests import
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot import 'mypool': no such pool available"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.import_("mypool")
        res = OrderedDict(
            [
                ("imported", False),
                ("error", "cannot import 'mypool': no such pool available"),
            ]
        )
        assert ret == res


@pytest.mark.slow_test
def test_online_success(utils_patch):
    """
    Tests online
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.online("mypool", "/dev/rdsk/c0t0d0")
        res = OrderedDict([("onlined", True)])
        assert ret == res


def test_online_nodevice(utils_patch):
    """
    Tests online
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot online /dev/rdsk/c0t0d1: no such device in pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.online("mypool", "/dev/rdsk/c0t0d1")
        res = OrderedDict(
            [
                ("onlined", False),
                ("error", "cannot online /dev/rdsk/c0t0d1: no such device in pool"),
            ]
        )
        assert ret == res


def test_offline_success(utils_patch):
    """
    Tests offline
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.offline("mypool", "/dev/rdsk/c0t0d0")
        res = OrderedDict([("offlined", True)])
        assert ret == res


def test_offline_nodevice(utils_patch):
    """
    Tests offline
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot offline /dev/rdsk/c0t0d1: no such device in pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.offline("mypool", "/dev/rdsk/c0t0d1")
        res = OrderedDict(
            [
                ("offlined", False),
                (
                    "error",
                    "cannot offline /dev/rdsk/c0t0d1: no such device in pool",
                ),
            ]
        )
        assert ret == res


def test_offline_noreplica(utils_patch):
    """
    Tests offline
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot offline /dev/rdsk/c0t0d1: no valid replicas"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.offline("mypool", "/dev/rdsk/c0t0d1")
        res = OrderedDict(
            [
                ("offlined", False),
                ("error", "cannot offline /dev/rdsk/c0t0d1: no valid replicas"),
            ]
        )
        assert ret == res


@pytest.mark.slow_test
def test_reguid_success(utils_patch):
    """
    Tests reguid
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.reguid("mypool")
        res = OrderedDict([("reguided", True)])
        assert ret == res


@pytest.mark.slow_test
def test_reguid_nopool(utils_patch):
    """
    Tests reguid with missing pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'mypool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.reguid("mypool")
        res = OrderedDict(
            [("reguided", False), ("error", "cannot open 'mypool': no such pool")]
        )
        assert ret == res


@pytest.mark.slow_test
def test_reopen_success(utils_patch):
    """
    Tests reopen
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.reopen("mypool")
        res = OrderedDict([("reopened", True)])
        assert ret == res


def test_reopen_nopool(utils_patch):
    """
    Tests reopen with missing pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'mypool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.reopen("mypool")
        res = OrderedDict(
            [("reopened", False), ("error", "cannot open 'mypool': no such pool")]
        )
        assert ret == res


def test_upgrade_success(utils_patch):
    """
    Tests upgrade
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.upgrade("mypool")
        res = OrderedDict([("upgraded", True)])
        assert ret == res


def test_upgrade_nopool(utils_patch):
    """
    Tests upgrade with missing pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'mypool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.upgrade("mypool")
        res = OrderedDict(
            [("upgraded", False), ("error", "cannot open 'mypool': no such pool")]
        )
        assert ret == res


@pytest.mark.slow_test
def test_history_success(utils_patch):
    """
    Tests history
    """
    ret = {}
    ret["stdout"] = "\n".join(
        [
            "History for 'mypool':",
            "2018-01-18.16:56:12 zpool create -f mypool /dev/rdsk/c0t0d0",
            "2018-01-19.16:01:55 zpool attach -f mypool /dev/rdsk/c0t0d0"
            " /dev/rdsk/c0t0d1",
        ]
    )
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.history("mypool")
        res = OrderedDict(
            [
                (
                    "mypool",
                    OrderedDict(
                        [
                            (
                                "2018-01-18.16:56:12",
                                "zpool create -f mypool /dev/rdsk/c0t0d0",
                            ),
                            (
                                "2018-01-19.16:01:55",
                                "zpool attach -f mypool /dev/rdsk/c0t0d0"
                                " /dev/rdsk/c0t0d1",
                            ),
                        ]
                    ),
                ),
            ]
        )
        assert ret == res


def test_history_nopool(utils_patch):
    """
    Tests history with missing pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'mypool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.history("mypool")
        res = OrderedDict([("error", "cannot open 'mypool': no such pool")])
        assert ret == res


def test_clear_success(utils_patch):
    """
    Tests clear
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = ""
    ret["retcode"] = 0
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.clear("mypool")
        res = OrderedDict([("cleared", True)])
        assert ret == res


def test_clear_nopool(utils_patch):
    """
    Tests clear with missing pool
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot open 'mypool': no such pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.clear("mypool")
        res = OrderedDict(
            [("cleared", False), ("error", "cannot open 'mypool': no such pool")]
        )


def test_clear_nodevice(utils_patch):
    """
    Tests clear with non existign device
    """
    ret = {}
    ret["stdout"] = ""
    ret["stderr"] = "cannot clear errors for /dev/rdsk/c0t0d0: no such device in pool"
    ret["retcode"] = 1
    mock_cmd = MagicMock(return_value=ret)

    with patch.dict(zpool.__salt__, {"cmd.run_all": mock_cmd}), patch.dict(
        zpool.__utils__, utils_patch
    ):
        ret = zpool.clear("mypool", "/dev/rdsk/c0t0d0")
        res = OrderedDict(
            [
                ("cleared", False),
                (
                    "error",
                    "cannot clear errors for /dev/rdsk/c0t0d0: no such device in"
                    " pool",
                ),
            ]
        )
        assert ret == res
