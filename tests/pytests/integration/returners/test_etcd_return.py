"""
Integration tests for the etcd returner as the master job cache
"""

import logging

import pytest
from saltfactories.utils import random_string

from salt.utils.etcd_util import get_conn
from tests.conftest import FIPS_TESTRUN
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]

RETURNER_ROOT = "/salt/return/integration"


@pytest.fixture(scope="module")
def etcd_master(salt_master_factory, etcd_profile, profile_name, etcd_container):
    overrides = dict(etcd_profile)
    overrides.update(
        {
            "master_job_cache": "etcd",
            "etcd.returner": profile_name,
            "etcd.returner_root": RETURNER_ROOT,
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        }
    )
    factory = salt_master_factory.salt_master_daemon(
        random_string("master-etcd-"), overrides=overrides
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def etcd_minion(etcd_master):
    factory = etcd_master.salt_minion_daemon(
        random_string("minion-etcd-"),
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    with factory.started():
        yield factory


def test_master_job_cache(etcd_master, etcd_minion, etcd_profile, profile_name):
    salt_cli = etcd_master.salt_cli(timeout=60)
    ret = salt_cli.run("test.echo", "etcd-job-cache", minion_tgt=etcd_minion.id)
    assert ret.returncode == 0
    assert ret.data == "etcd-job-cache"

    salt_run_cli = etcd_master.salt_run_cli(timeout=60)
    ret = salt_run_cli.run("jobs.list_jobs", search_function="test.echo")
    assert ret.returncode == 0
    jids = list(ret.data)
    assert len(jids) == 1
    jid = jids[0]
    assert ret.data[jid]["Function"] == "test.echo"

    ret = salt_run_cli.run("jobs.lookup_jid", jid)
    assert ret.returncode == 0
    assert ret.data == {etcd_minion.id: "etcd-job-cache"}

    # The job is in etcd, under the configured root.
    client = get_conn(etcd_profile[profile_name])
    assert client.get(f"{RETURNER_ROOT}/jobs/{jid}/{etcd_minion.id}")["return"] == (
        "etcd-job-cache"
    )
