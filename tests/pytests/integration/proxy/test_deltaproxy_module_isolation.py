"""Device connection globals must belong to one deltaproxy sub-proxy (#70760)."""

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


@pytest.mark.parametrize("multiprocessing", [False, True])
@pytest.mark.parametrize("parallel_startup", [False, True])
def test_subproxies_keep_their_own_connections(
    temp_salt_master, request, tmp_path, multiprocessing, parallel_startup
):
    """Execution calls and grains must use the targeted device's connection."""
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Deltaproxy under the TCP transport is not working. See #61367")

    salt_master = temp_salt_master
    control_id = random_string("connection-control-")
    hosts = {f"{control_id}-{n}": f"10.0.0.1{n}" for n in (1, 2, 3)}
    top = {"base": {minion_id: [minion_id] for minion_id in (control_id, *hosts)}}
    proxy_module = """
    __proxyenabled__ = ["connection_test"]
    DETAILS = {}

    def __virtual__():
        return True

    def init(opts):
        DETAILS["host"] = opts["proxy"]["host"]
        __context__["connection_test"] = {"host": opts["proxy"]["host"]}

    def initialized():
        return "host" in DETAILS

    def shutdown(opts):
        DETAILS.clear()

    def host():
        return DETAILS.get("host")

    def context_host():
        return __context__["connection_test"]["host"]

    def grains():
        return {"device_host": DETAILS.get("host")}
    """
    execution_module = """
    __proxyenabled__ = ["connection_test"]
    DETAILS = {}

    def __virtual__():
        DETAILS["id"] = __opts__["id"]
        return True

    def connection():
        return {
            "host": __proxy__["connection_test.host"](),
            "context_host": __proxy__["connection_test.context_host"](),
            "module_id": DETAILS["id"],
            "grains": __proxy__["connection_test.grains"](),
            "pillar_host": __pillar__["proxy"]["host"],
        }
    """

    proxy_dir = tmp_path / "proxy"
    module_dir = tmp_path / "modules"
    proxy_dir.mkdir()
    module_dir.mkdir()
    (proxy_dir / "connection_test.py").write_text(dedent(proxy_module))
    (module_dir / "connection_test.py").write_text(dedent(execution_module))

    with ExitStack() as stack:
        stack.enter_context(
            salt_master.pillar_tree.base.temp_file(
                "top.sls", salt.utils.yaml.safe_dump(top)
            )
        )
        pillars = {
            control_id: {
                "proxy": {
                    "proxytype": "deltaproxy",
                    "parallel_startup": parallel_startup,
                    "ids": list(hosts),
                }
            },
            **{
                minion_id: {"proxy": {"proxytype": "connection_test", "host": host}}
                for minion_id, host in hosts.items()
            },
        }
        for minion_id, pillar in pillars.items():
            stack.enter_context(
                salt_master.pillar_tree.base.temp_file(
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
                "multiprocessing": multiprocessing,
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
            ret = salt_cli.run(
                "-L", "connection_test.connection", minion_tgt=",".join(hosts)
            )
            assert ret.returncode == 0, ret
            assert ret.data == {
                minion_id: {
                    "host": host,
                    "context_host": host,
                    "module_id": minion_id,
                    "grains": {"device_host": host},
                    "pillar_host": host,
                }
                for minion_id, host in hosts.items()
            }, ret

            ret = salt_cli.run(
                "-L", "grains.item", "device_host", minion_tgt=",".join(hosts)
            )
            assert ret.returncode == 0, ret
            assert ret.data == {
                minion_id: {"device_host": host} for minion_id, host in hosts.items()
            }, ret
