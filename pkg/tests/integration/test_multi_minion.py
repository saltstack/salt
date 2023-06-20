import os
import pathlib
import subprocess

import psutil
import pytest

pytestmark = [
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def mm_script(install_salt):
    yield install_salt.ssm_bin.parent / "multi-minion.ps1"


@pytest.fixture(scope="function")
def mm_conf(mm_script):
    yield pathlib.Path(os.getenv("LocalAppData"), "Salt Project", "Salt", "conf")
    subprocess.run(
        ["powershell", str(mm_script).replace(" ", "' '"), "-d"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )


def test_script_present(mm_script):
    """
    Ensure the multi-minion.ps1 file is present in the root of the installation
    """
    assert mm_script.exists()


def test_install(mm_script, mm_conf):
    """
    Install a second minion with default settings. Should create a minion config
    file in Local AppData
    """
    ret = subprocess.run(
        ["powershell", str(mm_script).replace(" ", "' '")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr
    conf_file = mm_conf / "minion"
    assert conf_file.exists()
    assert conf_file.read_text().find("master: salt") > -1


def test_install_master(mm_script, mm_conf):
    """
    Install a second minion and set the master to spongebob
    """
    ret = subprocess.run(
        ["powershell", str(mm_script).replace(" ", "' '"), "-m", "spongebob"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr
    conf_file = mm_conf / "minion"
    assert conf_file.exists()
    assert conf_file.read_text().find("master: spongebob") > -1


def test_install_prefix(mm_script, mm_conf):
    """
    Install a second minion and add a prefix to the minion id
    """
    ret = subprocess.run(
        ["powershell", str(mm_script).replace(" ", "' '"), "-p", "squarepants"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr
    conf_file = mm_conf / "minion"
    assert conf_file.exists()
    assert conf_file.read_text().find("id: squarepants") > -1


def test_install_log_level(mm_script, mm_conf):
    """
    Install a second minion and set the log level in the log file to debug
    """
    ret = subprocess.run(
        ["powershell", str(mm_script).replace(" ", "' '"), "-l", "debug"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr
    conf_file = mm_conf / "minion"
    assert conf_file.exists()
    assert conf_file.read_text().find("log_level_logfile: debug") > -1


def test_install_start(mm_script, mm_conf):
    """
    Install a second minion and start that minion in a hidden process
    """
    ret = subprocess.run(
        ["powershell", str(mm_script).replace(" ", "' '"), "-s"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert ret.returncode == 0, ret.stderr
    conf_file = mm_conf / "minion"
    assert conf_file.exists()
    assert conf_file.read_text().find("master: salt") > -1

    found = False
    for p in psutil.process_iter(["cmdline", "name"]):
        if p.info["name"] and p.info["name"] == "salt-minion.exe":
            if f"{mm_conf}" in p.info["cmdline"]:
                found = True
    assert found is True
