"""Device connection globals must belong to one deltaproxy sub-proxy (#70760)."""

import time
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
    """Dunders remain device-specific through grains/pillar refresh and reload."""
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Deltaproxy under the TCP transport is not working. See #61367")

    salt_master = temp_salt_master
    control_id = random_string("connection-control-")
    hosts = {f"{control_id}-{n}": f"10.0.0.1{n}" for n in (1, 2, 3)}
    grain_revisions = dict.fromkeys(hosts, 1)
    pillar_revisions = dict.fromkeys(hosts, 1)
    revision_files = {}
    for minion_id in hosts:
        revision_file = tmp_path / f"{minion_id}.revision"
        revision_file.write_text("1", encoding="utf-8")
        revision_files[minion_id] = str(revision_file)
    top = {"base": {minion_id: [minion_id] for minion_id in (control_id, *hosts)}}
    proxy_module = """
    __proxyenabled__ = ["connection_test"]
    DETAILS = {}

    def __virtual__():
        return True

    def init(opts):
        DETAILS["host"] = opts["proxy"]["host"]
        __context__["connection_test"] = {
            "host": opts["proxy"]["host"],
            "revision_file": opts["proxy"]["revision_file"],
        }

    def initialized():
        return "host" in DETAILS

    def shutdown(opts):
        DETAILS.clear()

    def host():
        return DETAILS.get("host")

    def context_host():
        return __context__["connection_test"]["host"]

    def grains():
        with open(__context__["connection_test"]["revision_file"], encoding="utf-8") as stream:
            revision = int(stream.read())
        return {"device_host": DETAILS.get("host"), "device_revision": revision}

    def dunders():
        return {
            "context_host": __context__["connection_test"]["host"],
            "grains": {
                "device_host": __grains__.get("device_host"),
                "device_revision": __grains__.get("device_revision"),
            },
            "pillar_host": __pillar__["proxy"]["host"],
            "pillar_revision": __pillar__["dunder_revision"],
            "proxy_host": __proxy__["connection_test.host"](),
        }
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
            "module_id": DETAILS["id"],
            "execution": {
                "context_host": __context__.setdefault("execution_host", __opts__["proxy"]["host"]),
                "grains": {
                    "device_host": __grains__.get("device_host"),
                    "device_revision": __grains__.get("device_revision"),
                },
                "pillar_host": __pillar__["proxy"]["host"],
                "pillar_revision": __pillar__["dunder_revision"],
                "proxy_host": __proxy__["connection_test.host"](),
            },
            "proxy": __proxy__["connection_test.dunders"](),
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
                minion_id: {
                    "proxy": {
                        "proxytype": "connection_test",
                        "host": host,
                        "revision_file": revision_files[minion_id],
                    },
                    "dunder_revision": 1,
                }
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

            def assert_dunders(stage):
                expected = {}
                for minion_id, host in hosts.items():
                    dunders = {
                        "context_host": host,
                        "grains": {
                            "device_host": host,
                            "device_revision": grain_revisions[minion_id],
                        },
                        "pillar_host": host,
                        "pillar_revision": pillar_revisions[minion_id],
                        "proxy_host": host,
                    }
                    expected[minion_id] = {
                        "host": host,
                        "module_id": minion_id,
                        "execution": dunders,
                        "proxy": dunders,
                    }
                # refresh_grains signals the event loop asynchronously. Poll for
                # the new values, checking every sibling on every attempt.
                deadline = time.monotonic() + 30
                while True:
                    ret = salt_cli.run(
                        "-L", "connection_test.connection", minion_tgt=",".join(hosts)
                    )
                    assert ret.returncode == 0, ret
                    if ret.data == expected or time.monotonic() >= deadline:
                        assert ret.data == expected, (stage, ret)
                        break
                    time.sleep(0.25)

            assert_dunders("startup")

            # Refresh only one device at a time: sibling values must stay put.
            for minion_id in hosts:
                grain_revisions[minion_id] = 2
                (tmp_path / f"{minion_id}.revision").write_text("2", encoding="utf-8")
                ret = salt_cli.run(
                    "saltutil.refresh_grains",
                    refresh_pillar=False,
                    minion_tgt=minion_id,
                )
                assert ret.returncode == 0, ret
                assert ret.data is True, ret
                assert_dunders(f"grains refresh on {minion_id}")

                pillars[minion_id]["dunder_revision"] = 2
                stack.enter_context(
                    salt_master.pillar_tree.base.temp_file(
                        f"{minion_id}.sls",
                        salt.utils.yaml.safe_dump(pillars[minion_id]),
                    )
                )
                pillar_revisions[minion_id] = 2
                ret = salt_cli.run(
                    "saltutil.refresh_pillar", wait=True, minion_tgt=minion_id
                )
                assert ret.returncode == 0, ret
                assert ret.data is True, ret
                assert_dunders(f"pillar refresh on {minion_id}")

                ret = salt_cli.run("sys.reload_modules", minion_tgt=minion_id)
                assert ret.returncode == 0, ret
                assert ret.data is True, ret
                assert_dunders(f"module reload on {minion_id}")

            ret = salt_cli.run(
                "-L",
                "grains.item",
                "device_host",
                "device_revision",
                minion_tgt=",".join(hosts),
            )
            assert ret.returncode == 0, ret
            assert ret.data == {
                minion_id: {
                    "device_host": host,
                    "device_revision": grain_revisions[minion_id],
                }
                for minion_id, host in hosts.items()
            }, ret
