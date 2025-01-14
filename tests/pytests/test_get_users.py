import json
import subprocess
import sys

import pytest


def test_get_local_users():
    if sys.platform != "win32":
        pytest.skip("This test only runs on Windows")

    ps_command = "Get-LocalUser | Select-Object Name, Enabled | ConvertTo-Json"
    result = subprocess.run(
        ["powershell", "-Command", ps_command], capture_output=True, text=True
    )

    print(result.stdout)
    assert result.returncode == 0, f"PowerShell command failed: {result.stderr}"

    # Parse the JSON output
    users = json.loads(result.stdout)

    # Make test fail by asserting there are no disabled users
    disabled_users = [user for user in users if not user["Enabled"]]
    assert not disabled_users, f"Found disabled users: {disabled_users}"
