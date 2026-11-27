"""Reconnecting an offline DeltaProxy child must leave its siblings online."""

from contextlib import ExitStack
from textwrap import dedent

import pytest
from saltfactories.utils import random_string

import salt.utils.yaml
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.slow_test,
    pytest.mark.timeout_unless_on_windows(400),
]


def test_reconnect_only_restarts_offline_child(temp_salt_master, tmp_path):
    """Run the real reconnect command against one offline and two online children."""
    control_id = random_string("reconnect-control-")
    child_ids = [f"{control_id}-{index}" for index in range(3)]
    offline_id = child_ids[0]
    proxy_dir = tmp_path / "proxy"
    module_dir = tmp_path / "modules"
    proxy_dir.mkdir()
    module_dir.mkdir()
    proxy_module = """
    __proxyenabled__ = ["reconnect_test"]
    CONNECTION = {"online": False, "opens": 0, "closes": 0}

    def init(opts):
        CONNECTION.update(device=opts["id"], online=True)
        CONNECTION["opens"] += 1

    def initialized():
        return CONNECTION["opens"] > 0

    def alive(opts):
        return CONNECTION["online"]

    def shutdown(opts):
        CONNECTION["online"] = False
        CONNECTION["closes"] += 1

    def disconnect():
        CONNECTION["online"] = False
        return True

    def snapshot():
        return dict(CONNECTION)
    """
    execution_module = """
    __proxyenabled__ = ["reconnect_test"]

    def disconnect():
        return __proxy__["reconnect_test.disconnect"]()

    def snapshot():
        return __proxy__["reconnect_test.snapshot"]()
    """
    (proxy_dir / "reconnect_test.py").write_text(dedent(proxy_module), encoding="utf-8")
    (module_dir / "reconnect_test.py").write_text(
        dedent(execution_module), encoding="utf-8"
    )

    salt_master = temp_salt_master
    pillars = {
        control_id: {
            "proxy": {
                "proxytype": "deltaproxy",
                "parallel_startup": True,
                "ids": child_ids,
            }
        },
        **{
            child_id: {"proxy": {"proxytype": "reconnect_test"}}
            for child_id in child_ids
        },
    }
    top = {"base": {minion_id: [minion_id] for minion_id in pillars}}
    with ExitStack() as stack:
        pillar_tree = salt_master.pillar_tree.base
        stack.enter_context(
            pillar_tree.temp_file("top.sls", salt.utils.yaml.safe_dump(top))
        )
        for minion_id, pillar in pillars.items():
            stack.enter_context(
                pillar_tree.temp_file(
                    f"{minion_id}.sls", salt.utils.yaml.safe_dump(pillar)
                )
            )

        factory = salt_master.salt_proxy_minion_daemon(
            control_id,
            defaults={"metaproxy": "deltaproxy"},
            overrides={
                "saltenv": "base",
                "proxy_dirs": [str(proxy_dir)],
                "module_dirs": [str(module_dir)],
                # Keep commands and the driver state in the controller process.
                "multiprocessing": False,
                "enable_fqdns_grains": False,
                "proxy_keep_alive": False,
                "fips_mode": FIPS_TESTRUN,
                "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
                "signing_algorithm": (
                    "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                ),
            },
            start_timeout=320,
        )
        for minion_id in pillars:
            factory.after_terminate(
                pytest.helpers.remove_stale_minion_key, salt_master, minion_id
            )

        with salt_master.started(), factory.started():
            salt_cli = salt_master.salt_cli(timeout=30)
            child_target = ",".join(child_ids)

            def assert_connections(expected):
                ret = salt_cli.run(
                    "-L", "reconnect_test.snapshot", minion_tgt=child_target
                )
                assert ret.returncode == 0, ret
                assert ret.data == expected, ret

            expected = {
                child_id: {"device": child_id, "online": True, "opens": 1, "closes": 0}
                for child_id in child_ids
            }
            assert_connections(expected)

            ret = salt_cli.run("reconnect_test.disconnect", minion_tgt=offline_id)
            assert ret.returncode == 0, ret
            assert ret.data is True, ret
            expected[offline_id]["online"] = False
            assert_connections(expected)

            # Ask all three to reconnect so the healthy-child no-op is tested too.
            ret = salt_cli.run(
                "-L",
                "status.proxy_reconnect",
                "reconnect_test",
                minion_tgt=child_target,
            )
            assert ret.returncode == 0, ret
            assert ret.data == dict.fromkeys(child_ids, True), ret
            expected[offline_id].update(online=True, opens=2, closes=1)
            assert_connections(expected)
