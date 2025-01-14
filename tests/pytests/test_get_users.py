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
    assert False
