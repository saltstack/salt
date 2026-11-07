"""Publications must reach children sharing a DeltaProxy connection."""

import time
from pathlib import Path

import pytest

import salt.utils.yaml
from salt.utils.immutabletypes import freeze

pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.slow_test,
]


def configure_filtering(factory, enabled, **overrides):
    """Reload a factory with the requested on-disk publication setting."""
    config = salt.utils.yaml.safe_load(
        Path(factory.config_file).read_text(encoding="utf-8")
    )
    config.update(conf_file=factory.config_file, zmq_filtering=enabled)
    config.update(overrides)
    factory.config = freeze(factory.write_config(config))
    return factory


@pytest.fixture(
    scope="session",
    params=[False, True],
    ids=["zmq_filtering=False", "zmq_filtering=True"],
)
def salt_master_factory(request, salt_master_factory):
    """Exercise both ZeroMQ publication modes using the shared factories."""
    return configure_filtering(salt_master_factory, request.param)


@pytest.fixture(scope="session")
def salt_delta_proxy_factory(salt_delta_proxy_factory, salt_master_factory):
    """Use matching publication framing on the master and controller."""
    # These tests need only built-in modules. Keep file synchronization local
    # while fetching pillar from the real master, so a separate SyncWrapper
    # startup bug cannot prevent the publication tests from reaching readiness.
    local_files = Path(salt_delta_proxy_factory.config["root_dir"]) / "local-files"
    local_files.mkdir(exist_ok=True)
    return configure_filtering(
        salt_delta_proxy_factory,
        salt_master_factory.config["zmq_filtering"],
        file_client="local",
        use_master_when_local=True,
        file_roots={"base": [str(local_files)]},
    )


@pytest.mark.parametrize("target_type", ["id", "glob", "list", "pcre", "compound"])
def test_child_publication(salt_delta_proxy, salt_cli, tmp_path, target_type):
    """Check execution independently of the child's return channel (#70711)."""
    child_id = pytest.helpers.proxy.delta_proxy_minion_ids()[0]
    marker = tmp_path / "executed"
    targets = {
        "id": ([], child_id),
        "glob": ([], "dummy_proxy_o*"),
        "list": (["-L"], child_id),
        "pcre": (["-E"], f"^{child_id}$"),
        "compound": (["-C"], f"L@{child_id}"),
    }
    arguments, target = targets[target_type]
    # Controller responsiveness establishes that the shared connection is live.
    ret = salt_cli.run("test.ping", minion_tgt=salt_delta_proxy.id)
    assert ret.returncode == 0
    assert ret.data is True

    ret = salt_cli.run(
        "--async", *arguments, "file.touch", str(marker), minion_tgt=target
    )
    assert ret.returncode == 0
    deadline = time.monotonic() + 15
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert marker.exists(), f"Publication using {target_type} did not reach {child_id}"

    ret = salt_cli.run(*arguments, "test.ping", minion_tgt=target)
    assert ret.returncode == 0
    data = ret.data if isinstance(ret.data, dict) else {child_id: ret.data}
    assert data == {child_id: True}


def test_multiple_children(salt_delta_proxy, salt_cli):
    """A list publication must reach each selected child's own instance."""
    children = pytest.helpers.proxy.delta_proxy_minion_ids()[:2]
    ret = salt_cli.run("-L", "config.get", "id", minion_tgt=",".join(children))
    assert ret.returncode == 0
    assert ret.data == {child: child for child in children}
