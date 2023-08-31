import pytest
from saltfactories.utils import random_string


@pytest.fixture(scope="package")
def salt_master_factory(request, salt_factories):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
    }

    return salt_factories.salt_master_daemon(
        random_string("master-daemonized-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )


@pytest.fixture(scope="package")
def salt_minion_factory(salt_master_factory):
    config_defaults = {
        "transport": salt_master_factory.config["transport"],
    }

    return salt_master_factory.salt_minion_daemon(
        random_string("minion-daemonized-"),
        defaults=config_defaults,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
