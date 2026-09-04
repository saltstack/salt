import json

import pytest


@pytest.fixture(scope="module", autouse=True)
def mock_inotify(salt_call_cli, salt_master):
    beacon_mod = """
def validate(config):
    return True

def beacon(config):
    pass
    """
    with salt_master.state_tree.base.temp_file("_beacons/inotify.py", beacon_mod):
        res = salt_call_cli.run("saltutil.sync_beacons")
        assert res.returncode == 0
        assert "beacons.inotify" in res.data
        yield

    salt_call_cli.run("saltutil.sync_beacons")


@pytest.fixture(autouse=True)
def clear_beacons(salt_call_cli):
    try:
        yield
    finally:
        res = salt_call_cli.run("beacons.reset")
        assert res.returncode == 0


def test_mod_beacon(salt_call_cli, salt_master, tmp_path):
    """
    Test that a state's mod_beacon is called when the `beacon` state argument is passed.
    """
    test_file = tmp_path / "test_beacon.txt"
    sls_content = f"""
test_beacon_file:
  file.managed:
    - name: {json.dumps(str(test_file))}
    - contents: "test content"
    - beacon: true
    - beacon_data:
        interval: 1337
"""

    with salt_master.state_tree.base.temp_file("test_mod_beacon.sls", sls_content):
        ret = salt_call_cli.run("state.apply", "test_mod_beacon")
        assert ret.returncode == 0
        assert test_file.exists()

        file_state_found = False
        beacon_state_found = False

        for state_id, state_result in ret.data.items():
            if "file_|-test_beacon_file" in state_id:
                file_state_found = True
                assert state_result["result"] is True
            elif "beacon_test_beacon_file" in state_id and "mod_beacon" in state_id:
                beacon_state_found = True
                assert state_result["result"] is True

        assert file_state_found, "File state not found in results"
        assert beacon_state_found, "Beacon state not found in results"

    res = salt_call_cli.run("beacons.list", "return_yaml=False")
    assert res.returncode == 0
    assert res.data
    beacon_name = next(beacon for beacon in res.data if "test_beacon.txt" in beacon)
    beacon_config = {k: v for d in res.data[beacon_name] for k, v in d.items()}
    assert beacon_config["beacon_module"] == "inotify"
    assert beacon_config["files"][str(test_file)]
    assert beacon_config["interval"] == 1337
