"""Publications must reach children sharing a DeltaProxy connection."""

import time

import pytest

pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="Deltaproxy minions do not currently work on spawning platforms.",
    ),
    pytest.mark.slow_test,
]


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
