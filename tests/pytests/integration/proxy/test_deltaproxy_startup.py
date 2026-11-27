"""Verify DeltaProxy can finish startup while a child's key is pending."""

import time
from contextlib import ExitStack
from pathlib import Path

import pytest
from saltfactories.utils import random_string

import salt.utils.yaml
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(240),
]


@pytest.mark.parametrize("parallel_startup", [False, True])
def test_pending_child_joins_after_startup(salt_factories, request, parallel_startup):
    control_id = random_string("startup-control-")
    pending_id = f"{control_id}-pending"
    healthy_id = f"{control_id}-healthy"
    transport = request.config.getoption("--transport")
    master = salt_factories.salt_master_daemon(
        random_string("startup-master-"),
        on_auth_event_callback=lambda *_: None,
        overrides={
            "transport": transport,
            "autosign_file": "autosign",
            "auto_accept": False,
            "open_mode": False,
            "zmq_filtering": transport == "zeromq",
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    autosign_file = Path(master.config["autosign_file"])
    autosign_file.write_text(f"{control_id}\n{healthy_id}\n", encoding="utf-8")
    factory = master.salt_proxy_minion_daemon(
        control_id,
        defaults={"metaproxy": "deltaproxy"},
        overrides={
            "acceptance_wait_time": 1,
            "enable_fqdns_grains": False,
            "proxy_keep_alive": False,
            "zmq_filtering": transport == "zeromq",
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    pillars = {
        control_id: {
            "proxy": {
                "proxytype": "deltaproxy",
                "ids": [pending_id, healthy_id],
                "parallel_startup": parallel_startup,
                "startup_auth_retries": 2,
                "startup_retry_interval": 1,
            }
        },
        healthy_id: {"proxy": {"proxytype": "dummy"}},
        pending_id: {"proxy": {"proxytype": "dummy"}},
    }
    key_cli = master.salt_key_cli()
    salt_cli = master.salt_cli(timeout=5)
    expected = {control_id: True, healthy_id: True}
    targets = ",".join(expected)
    with ExitStack() as stack:
        top = {"base": {minion_id: [minion_id] for minion_id in pillars}}
        stack.enter_context(
            master.pillar_tree.base.temp_file("top.sls", salt.utils.yaml.safe_dump(top))
        )
        for minion_id, pillar in pillars.items():
            stack.enter_context(
                master.pillar_tree.base.temp_file(
                    f"{minion_id}.sls", salt.utils.yaml.safe_dump(pillar)
                )
            )
        stack.enter_context(master.started())
        stack.enter_context(factory.started(start_timeout=60))
        keys = key_cli.run("-L")
        assert keys.returncode == 0, keys
        assert pending_id in keys.data["minions_pre"]
        response = salt_cli.run("-L", "test.ping", minion_tgt=targets)
        assert response.data == expected, response

        accepted = key_cli.run("-a", pending_id, "-y")
        assert accepted.returncode == 0, accepted
        deadline = time.monotonic() + 30
        while True:
            response = salt_cli.run("test.ping", minion_tgt=pending_id)
            if response.data is True or time.monotonic() >= deadline:
                assert response.data is True, response
                break
            time.sleep(0.25)

        response = salt_cli.run("-L", "test.ping", minion_tgt=targets)
        assert response.data == expected, response
