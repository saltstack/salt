import os
import shutil
import subprocess
import time
import winreg

import psutil
import pytest

pytest_plugins = ["helpers_namespace"]

# \n characters are converted to os.linesep
existing_content = [
    "# Existing config from test suite line 1/6\n",
    "master: existing_master\n",
    "# Existing config from test suite line 2/6\n",
    "id: existing_minion\n",
    "# Existing config from test suite line 3/6\n",
    "# Existing config from test suite line 4/6\n",
    "# Existing config from test suite line 5/6\n",
    "# Existing config from test suite line 6/6\n",
]

# \n characters are converted to os.linesep
custom_content = [
    "# Custom config from test suite line 1/6\n",
    "master: custom_master\n",
    "# Custom config from test suite line 2/6\n",
    "id: custom_minion\n",
    "# Custom config from test suite line 3/6\n",
    "# Custom config from test suite line 4/6\n",
    "# Custom config from test suite line 5/6\n",
    "# Custom config from test suite line 6/6\n",
]

# \n characters are converted to os.linesep
old_content = [
    "# Old config from test suite line 1/6\n",
    "master: old_master\n",
    "# Old config from test suite line 2/6\n",
    "id: old_minion\n",
    "# Old config from test suite line 3/6\n",
    "# Old config from test suite line 4/6\n",
    "# Old config from test suite line 5/6\n",
    "# Old config from test suite line 6/6\n",
]

INST_DIR = r"C:\Program Files\Salt Project\Salt"
DATA_DIR = r"C:\ProgramData\Salt Project\Salt"
SYSTEM_DRIVE = os.environ.get("SystemDrive")
OLD_DIR = f"{SYSTEM_DRIVE}\\salt"


def reg_key_exists(hive=winreg.HKEY_LOCAL_MACHINE, key=None):
    try:
        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ):
            exists = True
    except:
        exists = False

    return exists


def delete_key(hive=winreg.HKEY_LOCAL_MACHINE, key=None):
    if reg_key_exists(hive=hive, key=key):
        parent, _, base = key.rpartition("\\")
        with winreg.OpenKey(hive, parent, 0, winreg.KEY_ALL_ACCESS) as reg:
            winreg.DeleteKey(reg, base)


def pytest_configure():
    pytest.DATA_DIR = DATA_DIR
    pytest.INST_DIR = INST_DIR
    pytest.REPO_DIR = REPO_DIR
    pytest.INST_BIN = INST_BIN
    pytest.OLD_DIR = OLD_DIR
    pytest.EXISTING_CONTENT = existing_content
    pytest.CUSTOM_CONTENT = custom_content
    pytest.OLD_CONTENT = old_content


@pytest.helpers.register
def clean_env(inst_dir=INST_DIR):
    # Run uninstaller
    for uninst_bin in [f"{inst_dir}\\uninst.exe", f"{OLD_DIR}\\uninst.exe"]:
        if os.path.exists(uninst_bin):
            run_command([uninst_bin, "/S", "/delete-root-dir", "/delete-install-dir"])
            # This is needed to avoid a race condition where the uninstall is completing
            start_time = time.time()
            while "Un_A.exe" in (p.name() for p in psutil.process_iter()):
                # Sometimes the Uninstall binary hangs... we'll kill it after 10 seconds
                if (time.time() - start_time) > 10:
                    for proc in psutil.process_iter():
                        if proc.name() == "Un_A.exe":
                            proc.kill()
                time.sleep(0.1)

    # This is needed to avoid a race condition where the installer isn't closed
    start_time = time.time()
    while os.path.basename(INST_BIN) in (p.name() for p in psutil.process_iter()):
        if (time.time() - start_time) > 10:
            # If it's not dead after 10 seconds, kill it
            for proc in psutil.process_iter():
                if proc.name() == os.path.basename(INST_BIN):
                    proc.kill()
                time.sleep(0.1)

    # Remove root_dir
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    # Remove install dir
    if os.path.exists(inst_dir):
        shutil.rmtree(inst_dir)
    # Remove old salt dir (C:\salt)
    if os.path.exists(OLD_DIR):
        shutil.rmtree(OLD_DIR)
    # Remove custom config
    if os.path.exists(rf"{REPO_DIR}\custom_conf"):
        os.remove(rf"{REPO_DIR}\custom_conf")
    # Remove registry entries
    delete_key(key="SOFTWARE\\Salt Project\\Salt")
    delete_key(key="SOFTWARE\\Salt Project")


@pytest.helpers.register
def existing_config():
    # Create an existing config
    if not os.path.exists(f"{DATA_DIR}\\conf"):
        os.makedirs(f"{DATA_DIR}\\conf")
    with open(f"{DATA_DIR}\\conf\\minion", "w") as f:
        # \n characters are converted to os.linesep
        f.writelines(existing_content)


@pytest.helpers.register
def custom_config():
    if os.path.exists(rf"{REPO_DIR}\custom_conf"):
        os.remove(rf"{REPO_DIR}\custom_conf")
    # Create a custom config
    with open(rf"{REPO_DIR}\custom_conf", "w") as f:
        # \n characters are converted to os.linesep
        f.writelines(custom_content)


@pytest.helpers.register
def old_install():
    # Create old binaries, don't have to be valid exe's
    if not os.path.exists(f"{OLD_DIR}\\bin"):
        os.makedirs(f"{OLD_DIR}\\bin")
    with open(f"{OLD_DIR}\\bin\\python.exe", "w") as f:
        f.write("binary data")
    with open(f"{OLD_DIR}\\bin\\ssm.exe", "w") as f:
        f.write("binary data")

    # Create an old config
    if not os.path.exists(f"{OLD_DIR}\\conf"):
        os.makedirs(f"{OLD_DIR}\\conf")
    with open(f"{OLD_DIR}\\conf\\minion", "w") as f:
        # \n characters are converted to os.linesep
        f.writelines(old_content)
    while not (os.path.exists(f"{OLD_DIR}\\bin\\python.exe")):
        time.sleep(0.1)
    while not (os.path.exists(f"{OLD_DIR}\\bin\\ssm.exe")):
        time.sleep(0.1)
    while not (os.path.exists(f"{OLD_DIR}\\conf\\minion")):
        time.sleep(0.1)
    assert os.path.exists(f"{OLD_DIR}\\bin\\python.exe")
    assert os.path.exists(f"{OLD_DIR}\\bin\\ssm.exe")
    assert os.path.exists(f"{OLD_DIR}\\conf\\minion")


@pytest.helpers.register
def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip().replace("/", "\\")


# These are at the bottom because they depend on some of the functions
REPO_DIR = run_command(["git", "rev-parse", "--show-toplevel"])
REPO_DIR = rf"{REPO_DIR}\pkg\windows\nsis\tests"
os.chdir(REPO_DIR)
INST_BIN = rf"{REPO_DIR}\test-setup.exe"
