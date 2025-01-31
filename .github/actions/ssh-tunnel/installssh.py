"""
"""

import pathlib
import subprocess
import zipfile

import requests

fwrule = """
New-NetFirewallRule `
  -Name sshd `
  -DisplayName 'OpenSSH SSH Server' `
  -Enabled True `
  -Direction Inbound `
  -Protocol TCP `
  -Action Allow `
  -LocalPort 22 `
  -Program "{}"
"""


def start_ssh_server():
    """
    Pretty print the GH Actions event.
    """
    resp = requests.get(
        "https://github.com/PowerShell/Win32-OpenSSH/releases/download/v9.8.1.0p1-Preview/OpenSSH-Win64.zip",
        allow_redirects=True,
    )
    with open("openssh.zip", "wb") as fp:
        fp.write(resp.content)
    with zipfile.ZipFile("openssh.zip") as fp:
        fp.extractall()
    install_script = pathlib.Path("./OpenSSH-Win64/install-sshd.ps1").resolve()
    print(f"{install_script}")
    subprocess.call(["powershell.exe", f"{install_script}"])
    with open("fwrule.ps1", "w") as fp:
        fp.write(fwrule.format(install_script.parent / "sshd.exe"))
    subprocess.call(["powershell.exe", f"fwrule.ps1"])


if __name__ == "__main__":
    start_ssh_server()
