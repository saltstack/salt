import logging

import pytest

# pylint: disable=unused-import
from tests.conftest import FIPS_TESTRUN
from tests.pytests.integration.cluster.conftest import (
    cluster_cache_path,
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_master_4,
    cluster_minion_1,
    cluster_pki_path,
    cluster_shared_path,
)

# pylint: enable=unused-import


log = logging.getLogger(__name__)


@pytest.fixture
def cluster_minion_all(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_master_4,
):
    """
    A minion subscribed to all four cluster masters.

    Required for the ``test_fourth_master_joins_existing_cluster`` test because
    ``salt`` dispatches jobs through master 4's publish channel and the minion
    must be listening there to receive them.
    """
    port = cluster_master_1.config["ret_port"]
    config_overrides = {
        "master": [
            f"{cluster_master_1.config['interface']}:{port}",
            f"{cluster_master_2.config['interface']}:{port}",
            f"{cluster_master_3.config['interface']}:{port}",
            f"{cluster_master_4.config['interface']}:{port}",
        ],
        "master_type": "failover",
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-all",
        defaults={"transport": cluster_master_1.config["transport"]},
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory
