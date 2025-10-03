import sys

import pytest

import salt.utils.event
import salt.utils.platform
import tests.support.helpers
from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def salt_master_1(request, salt_factories):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }

    factory = salt_factories.salt_master_daemon(
        "master-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def salt_minion_1(salt_master_1):
    config_defaults = {
        "transport": salt_master_1.config["transport"],
    }
    master_1_port = salt_master_1.config["ret_port"]
    master_1_addr = salt_master_1.config["interface"]
    config_overrides = {
        "master": [
            f"{master_1_addr}:{master_1_port}",
        ],
        "test.foo": "baz",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = salt_master_1.salt_minion_daemon(
        "minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def script(salt_minion_1, tmp_path):
    path = tmp_path / "script.py"
    content = f"""
    import salt.config
    import salt.utils.event

    opts = salt.config.minion_config('{salt_minion_1.config_file}')

    payload =  b'0' * 1048576000

    big_event = dict()
    for i in range(10000):
        big_event[i] = payload =  b'0' * 100

    with salt.utils.event.get_event("minion", opts=opts) as event:
        event.fire_master(big_event, 'bigevent')

    """
    path.write_text(tests.support.helpers.dedent(content))
    return path


# @pytest.mark.timeout_unless_on_windows(360)
def test_schedule_large_event(salt_master_1, salt_minion_1, script):
    cli = salt_master_1.salt_cli(timeout=120)
    ret = cli.run(
        "schedule.add",
        name="myjob",
        function="cmd.run",
        seconds=5,
        job_args=f'["{sys.executable} {script}"]',
        minion_tgt=salt_minion_1.id,
    )
    assert "result" in ret.data
    assert ret.data["result"]
    with salt.utils.event.get_event(
        "master",
        salt_master_1.config["sock_dir"],
        salt_master_1.config,
    ) as event:
        event = event.get_event(tag="bigevent", wait=15)
        assert event
        assert "data" in event
        assert len(event["data"]) == 10000
