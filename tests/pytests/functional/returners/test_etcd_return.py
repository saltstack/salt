import logging
import time

import pytest

import salt.returners.etcd_return as etcd_return
import salt.utils.jid
from salt.utils.etcd_util import get_conn
from tests.support.mock import patch
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]

JID = "20261103120000123456"


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        etcd_return: {
            "__opts__": minion_opts,
        },
    }


@pytest.fixture(scope="module")
def prefix():
    return "/salt/return/test"


@pytest.fixture(scope="module")
def minion_config_overrides(etcd_profile, profile_name, prefix):
    overrides = dict(etcd_profile)
    overrides["etcd_plain"] = dict(
        etcd_profile[profile_name], **{"etcd.encode_values": False}
    )
    overrides["etcd_ttl"] = dict(etcd_profile[profile_name], **{"etcd.ttl": 2})
    overrides.update(
        {
            "etcd.returner": profile_name,
            "etcd.returner_root": prefix,
            "keep_jobs_seconds": 3600,
        }
    )
    return overrides


@pytest.fixture(scope="module")
def etcd_client(minion_opts, profile_name):
    return get_conn(minion_opts, profile=profile_name)


@pytest.fixture(autouse=True)
def cleanup_prefixed_entries(etcd_client, prefix):
    """
    Cleanup after each test to ensure a consistent starting state.
    """
    try:
        assert etcd_client.get(prefix, recurse=True) is None
        yield
    finally:
        etcd_client.delete(prefix, recurse=True)


def _ret(minion_id, jid=JID, fun="test.ping", ret=True):
    return {
        "id": minion_id,
        "jid": jid,
        "fun": fun,
        "fun_args": [],
        "return": ret,
        "retcode": 0,
        "success": True,
    }


def test_returner_and_reads(subtests):
    etcd_return.returner(_ret("minion1"))
    etcd_return.returner(_ret("minion2", ret={"nested": [1, 2]}))

    with subtests.test("get_jid returns each minion's return"):
        jid = etcd_return.get_jid(JID)
        assert sorted(jid) == ["minion1", "minion2"]
        assert jid["minion1"]["return"] is True
        assert jid["minion2"]["return"] == {"nested": [1, 2]}
        assert jid["minion2"]["retcode"] == 0

    with subtests.test("get_minions lists the minions that returned"):
        assert etcd_return.get_minions() == ["minion1", "minion2"]

    with subtests.test("get_fun maps minions to their last function"):
        assert etcd_return.get_fun("test.ping") == {
            "minion1": "test.ping",
            "minion2": "test.ping",
        }
        assert etcd_return.get_fun("cmd.run") == {}


def test_load_and_job_listing(subtests):
    load = {
        "fun": "test.ping",
        "arg": [],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root",
    }
    find_job = dict(load, fun="saltutil.find_job")
    later = "20261103120001000000"
    etcd_return.save_load(JID, load, minions=["minion2", "minion1"])
    etcd_return.save_load(later, find_job, minions=["minion1"])
    etcd_return.save_minions(JID, ["minion3"])

    with subtests.test("get_load includes the targeted minions"):
        assert etcd_return.get_load(JID) == dict(
            load, Minions=["minion1", "minion2", "minion3"]
        )
        assert etcd_return.get_load("20000101000000000000") == {}

    with subtests.test("get_jids maps job IDs to job information"):
        jids = etcd_return.get_jids()
        assert sorted(jids) == [JID, later]
        assert jids[JID]["Function"] == "test.ping"
        assert jids[JID]["Target"] == "*"

    with subtests.test("get_jids_filter skips find_job and limits the count"):
        assert [j["JID"] for j in etcd_return.get_jids_filter(5)] == [JID]
        assert [
            j["JID"] for j in etcd_return.get_jids_filter(1, filter_find_job=False)
        ] == [later]

    with subtests.test("end times are saved and read back"):
        assert etcd_return.get_endtime(JID) is False
        etcd_return.update_endtime(JID, "2026, Nov 03 12:00:05.000000")
        assert etcd_return.get_endtime(JID) == "2026, Nov 03 12:00:05.000000"


def test_req_jid_gets_a_real_jid(etcd_client, prefix):
    etcd_return.returner(_ret("minion1", jid="req"))
    jid = etcd_client.get(f"{prefix}/minions/minion1")
    assert salt.utils.jid.is_jid(jid)
    assert sorted(etcd_return.get_jid(jid)) == ["minion1"]


def test_binary_return_data():
    etcd_return.returner(_ret("minion1", ret={"blob": b"\x00\xff\x10"}))
    assert etcd_return.get_jid(JID)["minion1"]["return"] == {"blob": b"\x00\xff\x10"}


def test_nocache_job_is_not_stored():
    jid = etcd_return.prep_jid(nocache=True)
    etcd_return.returner(_ret("minion1", jid=jid))
    assert etcd_return.get_jid(jid) == {}


def test_plain_json_values(etcd_client, prefix):
    with patch.dict(etcd_return.__opts__, {"etcd.returner": "etcd_plain"}):
        etcd_return.returner(_ret("minion1", ret={"key": "value"}))
        assert etcd_return.get_jid(JID)["minion1"]["return"] == {"key": "value"}
    raw = get_conn(etcd_return.__opts__, profile="etcd_plain").get(
        f"{prefix}/jobs/{JID}/minion1"
    )
    assert '"key": "value"' in raw


def test_ttl_expires_returns():
    with patch.dict(etcd_return.__opts__, {"etcd.returner_write_profile": "etcd_ttl"}):
        etcd_return.returner(_ret("minion1"))
    assert etcd_return.get_minions() == ["minion1"]
    time.sleep(4)
    assert etcd_return.get_minions() == []
    assert etcd_return.get_jid(JID) == {}


def test_clean_old_jobs():
    old = "20000101000000000000"
    etcd_return.returner(_ret("minion1", jid=old))
    etcd_return.save_load(old, {"fun": "test.ping"}, minions=["minion1"])
    new = etcd_return.prep_jid()
    etcd_return.returner(_ret("minion1", jid=new))
    etcd_return.clean_old_jobs()
    assert etcd_return.get_jid(old) == {}
    assert etcd_return.get_load(old) == {}
    assert sorted(etcd_return.get_jid(new)) == ["minion1"]
