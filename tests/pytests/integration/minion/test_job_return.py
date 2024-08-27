import os
import shutil
import subprocess

import pytest

import salt.utils.platform
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
def salt_master_2(salt_factories, salt_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": salt_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.2",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = salt_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "master-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )

    # The secondary salt master depends on the primarily salt master fixture
    # because we need to clone the keys
    for keyfile in ("master.pem", "master.pub"):
        shutil.copyfile(
            os.path.join(salt_master_1.config["pki_dir"], keyfile),
            os.path.join(factory.config["pki_dir"], keyfile),
        )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def salt_minion_1(salt_master_1, salt_master_2):
    config_defaults = {
        "transport": salt_master_1.config["transport"],
    }

    master_1_port = salt_master_1.config["ret_port"]
    master_1_addr = salt_master_1.config["interface"]
    master_2_port = salt_master_2.config["ret_port"]
    master_2_addr = salt_master_2.config["interface"]
    config_overrides = {
        "master": [
            f"{master_1_addr}:{master_1_port}",
            f"{master_2_addr}:{master_2_port}",
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


@pytest.mark.timeout_unless_on_windows(360)
def test_job_return(salt_master_1, salt_master_2, salt_minion_1):
    cli = salt_master_1.salt_cli(timeout=120)
    ret = cli.run("test.ping", "-v", minion_tgt=salt_minion_1.id)
    for line in ret.stdout.splitlines():
        if "with jid" in line:
            jid = line.split("with jid")[1].strip()

    run_1 = salt_master_1.salt_run_cli(timeout=120)
    ret = run_1.run("jobs.lookup_jid", jid)
    assert ret.data == {"minion-1": True}

    run_2 = salt_master_2.salt_run_cli(timeout=120)
    ret = run_2.run("jobs.lookup_jid", jid)
    assert ret.data == {}
