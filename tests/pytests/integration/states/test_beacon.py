"""
Integration tests for the beacon states
"""
import logging

import pytest

log = logging.getLogger(__name__)


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(240)
def test_present_absent(salt_master, salt_minion, salt_call_cli):
    ret = salt_call_cli.run("beacons.reset")

    content = """
    beacon-diskusage:
      beacon.present:
        - name: diskusage
        - interval: 5
        - /: 38%
    """

    with salt_master.state_tree.base.temp_file("manage_beacons.sls", content):
        ret = salt_call_cli.run(
            "state.apply",
            "manage_beacons",
        )
        assert ret.returncode == 0
        state_id = "beacon_|-beacon-diskusage_|-diskusage_|-present"
        assert state_id in ret.data
        assert ret.data[state_id]["result"]
        assert ret.data[state_id]["comment"] == "Adding diskusage to beacons"

        ret = salt_call_cli.run("beacons.list", return_yaml=False)
        assert "diskusage" in ret.data
        assert {"interval": 5} in ret.data["diskusage"]
        assert {"/": "38%"} in ret.data["diskusage"]

        ret = salt_call_cli.run("state.single", "beacon.absent", "diskusage")
        assert ret.data

        ret = salt_call_cli.run("beacons.list", return_yaml=False)
        assert ret.data == {}

        ret = salt_call_cli.run("beacons.reset")
