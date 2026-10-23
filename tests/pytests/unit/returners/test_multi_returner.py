"""
Regression tests for multi_returner dispatch and real job-cache aggregation.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

import salt.payload
import salt.returners.local_cache as local_cache
import salt.returners.multi_returner as multi_returner
import salt.returners.salt_cache as salt_cache
import salt.utils.files
import salt.utils.jid
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(tmp_path):
    return {
        multi_returner: {
            "__opts__": {
                multi_returner.CONFIG_KEY: ["local_cache", "salt_cache", "unsupported"]
            }
        },
        local_cache: {
            "__opts__": {
                "cachedir": str(tmp_path / "local-cache"),
                "hash_type": "sha256",
                "keep_jobs_seconds": 86400,
                "job_cache_store_endtime": False,
            }
        },
        salt_cache: {
            "__opts__": {
                "cachedir": str(tmp_path / "salt-cache"),
                "cache": "localfs",
                "extension_modules": str(tmp_path / "salt-cache" / "extmods"),
                "hash_type": "sha256",
                "keep_jobs_seconds": 86400,
                "job_cache_store_endtime": False,
            }
        },
    }


@pytest.fixture(autouse=True)
def reset_mminion_cache():
    with patch.object(multi_returner, "MMINION", None):
        yield


@pytest.fixture
def mock_returners():
    """Only replace the loader container; tests supply its callable entries."""
    returners = {}
    with patch.object(
        multi_returner, "_mminion", return_value=SimpleNamespace(returners=returners)
    ):
        yield returners


@pytest.fixture
def real_returners(mock_returners):
    for backend in (local_cache, salt_cache):
        name = backend.__name__.rsplit(".", 1)[-1]
        for function in (
            "save_load",
            "save_minions",
            "get_load",
            "get_jids_filter",
            "update_endtime",
            "get_endtime",
        ):
            mock_returners[f"{name}.{function}"] = getattr(backend, function)
    with patch.dict(
        multi_returner.__opts__,
        {multi_returner.CONFIG_KEY: ["local_cache", "salt_cache"]},
    ):
        yield


@pytest.mark.parametrize("cmd", ["_return", "publish", None])
def test_save_load_dispatches_and_forwards_minions(mock_returners, cmd):
    local_save = MagicMock()
    other_save = MagicMock()
    mock_returners.update(
        {"local_cache.save_load": local_save, "salt_cache.save_load": other_save}
    )
    load = {"jid": "20260622000000000010", "tgt": "*"}
    if cmd is not None:
        load["cmd"] = cmd
    minions = ["minion-1", "minion-2"]
    with patch.dict(
        multi_returner.__opts__,
        {multi_returner.CONFIG_KEY: ["local_cache", "salt_cache"]},
    ):
        multi_returner.save_load(load["jid"], load, minions=minions)
    if cmd == "_return":
        local_save.assert_not_called()
    else:
        local_save.assert_called_once_with(load["jid"], load, minions)
    other_save.assert_called_once_with(load["jid"], load, minions)


def test_save_load_forwards_default_minions(mock_returners):
    save = MagicMock()
    mock_returners["salt_cache.save_load"] = save
    load = {"cmd": "_return"}
    with patch.dict(
        multi_returner.__opts__,
        {multi_returner.CONFIG_KEY: ["local_cache", "salt_cache"]},
    ):
        multi_returner.save_load("jid", load)
    save.assert_called_once_with("jid", load, None)


@pytest.mark.parametrize("count", [2, 3])
def test_get_jids_filter_merges_backend_lists_and_dedupes(mock_returners, count):
    jobs = [
        {"JID": "20260622000000000001", "Function": "test.ping"},
        {"JID": "20260622000000000002", "Function": "test.sleep"},
        {"JID": "20260622000000000003", "Function": "later.overwrite"},
    ]
    first = MagicMock(return_value=[dict(jobs[2], Function="cmd.run"), jobs[0]])
    second = MagicMock(return_value=[jobs[2], jobs[1]])
    mock_returners.update(
        {"local_cache.get_jids_filter": first, "salt_cache.get_jids_filter": second}
    )
    result = multi_returner.get_jids_filter(count, filter_find_job=False)
    assert isinstance(result, list)
    assert result == jobs[-count:]
    first.assert_called_once_with(count, False)
    second.assert_called_once_with(count, False)


@pytest.mark.parametrize("count", [0, -1])
def test_get_jids_filter_count_zero_and_negative_return_empty(mock_returners, count):
    backend = MagicMock(return_value=[{"JID": "20260622000000000001"}])
    mock_returners["local_cache.get_jids_filter"] = backend
    assert multi_returner.get_jids_filter(count) == []
    backend.assert_called_once_with(count, True)


def test_get_jids_filter_attribute_exists_under_plural_name():
    assert callable(multi_returner.get_jids_filter)
    assert not hasattr(multi_returner, "get_jid_filter")


def test_get_jids_filter_without_implementors(mock_returners):
    assert multi_returner.get_jids_filter(10) == []


def test_save_minions_forwards_to_implementing_returners(mock_returners):
    first = MagicMock()
    second = MagicMock()
    mock_returners.update(
        {"local_cache.save_minions": first, "salt_cache.save_minions": second}
    )
    multi_returner.save_minions("jid", ["m1"], syndic_id="syndic-1")
    first.assert_called_once_with("jid", ["m1"], "syndic-1")
    second.assert_called_once_with("jid", ["m1"], "syndic-1")


def test_update_endtime_forwards_to_all_implementing(mock_returners):
    first = MagicMock()
    second = MagicMock()
    mock_returners.update(
        {"local_cache.update_endtime": first, "salt_cache.update_endtime": second}
    )
    endtime = "2026-10-22 12:00:00"
    multi_returner.update_endtime("jid", endtime)
    first.assert_called_once_with("jid", endtime)
    second.assert_called_once_with("jid", endtime)


@pytest.mark.parametrize(
    "first_value, second_value, expected",
    [
        (False, "later", "later"),
        (None, "later", "later"),
        ("first", "later", "first"),
        (False, None, False),
    ],
)
def test_get_endtime_returns_first_truthy_in_config_order(
    mock_returners, first_value, second_value, expected
):
    first = MagicMock(return_value=first_value)
    second = MagicMock(return_value=second_value)
    mock_returners.update(
        {"local_cache.get_endtime": first, "salt_cache.get_endtime": second}
    )
    assert multi_returner.get_endtime("jid") == expected
    first.assert_called_once_with("jid")
    if first_value:
        second.assert_not_called()
    else:
        second.assert_called_once_with("jid")


def test_get_endtime_without_implementors(mock_returners):
    assert multi_returner.get_endtime("jid") is False


def test_get_endtime_skips_returners_without_interface(mock_returners):
    backend = MagicMock(return_value="endtime")
    mock_returners["salt_cache.get_endtime"] = backend
    assert multi_returner.get_endtime("jid") == "endtime"
    backend.assert_called_once_with("jid")


def test_save_reg_writes_to_every_configured_returner(mock_returners):
    first = MagicMock()
    second = MagicMock()
    mock_returners.update(
        {"local_cache.save_reg": first, "salt_cache.save_reg": second}
    )
    payload = {"event": "thorium.fire"}
    multi_returner.save_reg(payload)
    first.assert_called_once_with(payload)
    second.assert_called_once_with(payload)


def test_save_reg_skips_returners_without_save_reg(mock_returners):
    save = MagicMock()
    mock_returners["local_cache.save_reg"] = save
    payload = {"event": "thorium.fire"}
    multi_returner.save_reg(payload)
    save.assert_called_once_with(payload)


@pytest.mark.parametrize("first_value", [{"event": "thorium.fire"}, None, {}])
def test_load_reg_returns_first_implementor_result(mock_returners, first_value):
    first = MagicMock(return_value=first_value)
    second = MagicMock(return_value={"event": "later"})
    mock_returners.update(
        {"local_cache.load_reg": first, "salt_cache.load_reg": second}
    )
    assert multi_returner.load_reg() == first_value
    first.assert_called_once_with()
    second.assert_not_called()


def test_load_reg_skips_non_implementors(mock_returners):
    load = MagicMock(return_value={"event": "later"})
    mock_returners["salt_cache.load_reg"] = load
    assert multi_returner.load_reg() == {"event": "later"}
    load.assert_called_once_with()


def test_load_reg_without_implementors(mock_returners):
    assert multi_returner.load_reg() is None


def test_save_load_real_local_cache_not_overwritten_by_return_load(real_returners):
    jid = "20260622000000000010"
    publish = {
        "jid": jid,
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "arg": [],
        "user": "root",
    }
    # Master publishing loads have no cmd key; this must still reach local_cache.
    multi_returner.save_load(jid, publish, minions=["minion-1"])
    return_load = {
        "jid": jid,
        "cmd": "_return",
        "id": "minion-1",
        "return": "ok",
        "retcode": 0,
        "success": True,
    }
    multi_returner.save_load(jid, return_load)
    assert local_cache.get_load(jid) == dict(publish, Minions=["minion-1"])
    assert salt_cache.get_load(jid) == dict(return_load, Minions=["minion-1"])


@pytest.fixture
def real_jobs(real_returners):
    jids = [f"2026062200000000000{index}" for index in range(1, 5)]
    for backend, jid, function in (
        (local_cache, jids[1], "cmd.run"),
        (local_cache, jids[0], "test.ping"),
        (salt_cache, jids[2], "test.sleep"),
        (salt_cache, jids[1], "salt.test_userfun"),
        (local_cache, jids[3], "saltutil.find_job"),
        (salt_cache, jids[3], "saltutil.find_job"),
    ):
        backend.save_load(jid, {"jid": jid, "fun": function, "arg": []})
    return jids


def test_get_jids_filter_real_aggregation_dedupe_count_order(real_jobs):
    result = multi_returner.get_jids_filter(10)
    assert isinstance(result, list)
    assert [job["JID"] for job in result] == real_jobs[:3]
    assert all("StartTime" in job for job in result)
    assert result[1]["Function"] == "salt.test_userfun"
    assert [job["JID"] for job in multi_returner.get_jids_filter(2)] == real_jobs[1:3]
    unfiltered = multi_returner.get_jids_filter(2, filter_find_job=False)
    assert [job["JID"] for job in unfiltered] == real_jobs[2:]
    assert unfiltered[-1]["Function"] == "saltutil.find_job"


@pytest.mark.parametrize("count", [0, -1])
def test_get_jids_filter_real_nonpositive_count_returns_empty(real_jobs, count):
    assert multi_returner.get_jids_filter(count) == []


def test_endtime_real_roundtrip_through_multi_returner(real_returners):
    jid = "20260622000000000020"
    endtime = "2026-10-22 12:00:00"
    multi_returner.update_endtime(jid, endtime)
    assert local_cache.get_endtime(jid) == endtime
    assert salt_cache.get_endtime(jid) == endtime
    assert multi_returner.get_endtime(jid) == endtime
    assert multi_returner.get_endtime("20260622000000000099") is False
    # A job present only in the second backend must remain readable.
    second_jid = "20260622000000000021"
    salt_cache.update_endtime(second_jid, endtime)
    assert multi_returner.get_endtime(second_jid) == endtime


def test_save_minions_real_persists_minion_list(real_returners):
    jid = "20260622000000000030"
    multi_returner.save_load(
        jid, {"jid": jid, "fun": "test.ping", "tgt": "*", "arg": []}, minions=[]
    )
    multi_returner.save_minions(jid, ["m-a", "m-b"])
    multi_returner.save_minions(jid, ["m-c"], syndic_id="syndic-1")
    assert local_cache.get_load(jid)["Minions"] == ["m-a", "m-b", "m-c"]
    assert salt_cache.get_load(jid)["Minions"] == ["m-a", "m-b", "m-c"]
    opts = local_cache.__opts__
    job_dir = Path(
        salt.utils.jid.jid_dir(
            jid, str(Path(opts["cachedir"]) / "jobs"), opts["hash_type"]
        )
    )
    syndic_path = job_dir / local_cache.SYNDIC_MINIONS_P.format("syndic-1")
    with salt.utils.files.fopen(syndic_path, "rb") as stream:
        assert salt.payload.load(stream) == ["m-c"]
