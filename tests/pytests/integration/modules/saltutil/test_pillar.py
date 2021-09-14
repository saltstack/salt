"""
Integration tests for the saltutil module.
"""


import logging
import time

import pytest
import salt.defaults.events

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(autouse=True)
def refresh_pillar(salt_call_cli, salt_minion):
    ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
    assert ret.exitcode == 0
    assert ret.json
    try:
        yield
    finally:
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json


@pytest.mark.slow_test
@pytest.mark.parametrize("sync_refresh", [False, True])
def test_pillar_refresh(
    salt_master,
    salt_minion,
    salt_call_cli,
    event_listener,
    sync_refresh,
):
    """
    test pillar refresh module
    """
    pillar_key = "it-worked-{}".format("sync" if sync_refresh else "async")
    top_pillar_contents = """
    base:
      '*':
        - add-pillar-{}
    """.format(
        "sync" if sync_refresh else "async"
    )
    add_pillar_contents = """
    {0}: {0}
    """.format(
        pillar_key
    )

    ret = salt_call_cli.run("pillar.raw")
    assert ret.exitcode == 0
    assert ret.json
    pre_pillar = ret.json
    # Remove keys which are not important and consume too much output when reading through failures
    for key in ("master", "ext_pillar_opts"):
        pre_pillar.pop(key, None)
    assert pillar_key not in pre_pillar

    top_file = salt_master.pillar_tree.base.temp_file("top.sls", top_pillar_contents)
    add_pillar_file = salt_master.pillar_tree.base.temp_file(
        "add-pillar-{}.sls".format("sync" if sync_refresh else "async"),
        add_pillar_contents,
    )

    with top_file, add_pillar_file:
        start_time = time.time()

        ret = salt_call_cli.run(
            "--retcode-passthrough",
            "saltutil.refresh_pillar",
            wait=sync_refresh,
        )
        assert ret.exitcode == 0

        expected_tag = salt.defaults.events.MINION_PILLAR_REFRESH_COMPLETE
        event_pattern = (salt_minion.id, expected_tag)
        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=120
        )
        assert (
            matched_events.found_all_events
        ), "Failed to receive the refresh pillar complete event."
        log.debug("Refresh pillar complete event received: %s", matched_events.matches)

        ret = salt_call_cli.run("pillar.raw")
        assert ret.exitcode == 0
        assert ret.json
        post_pillar = ret.json
        # Remove keys which are not important and consume too much output when reading through failures
        for key in ("master", "ext_pillar_opts"):
            post_pillar.pop(key, None)
        assert pillar_key in post_pillar
        assert post_pillar[pillar_key] == pillar_key
