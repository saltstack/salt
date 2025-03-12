import os
import re
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
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
INST_BIN = rf"{SCRIPT_DIR}\test-setup.exe"
PROCESSES = [
    os.path.basename(INST_BIN),
    "uninst.exe",
    "Un.exe",
    "Un_A.exe",
    "Un_B.exe",
    "Un_C.exe",
    "Un_D.exe",
    "Un_D.exe",
    "Un_F.exe",
    "Un_G.exe",
]


def reg_key_exists(hive=winreg.HKEY_LOCAL_MACHINE, key=None):
    """
    Helper function to determine if a registry key exists. It does this by
    opening the key. If the connection is successful, the key exists. Otherwise
    an error is returned, which means the key does not exist
    """
    try:
        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ):
            return True
    except:
        return False


def delete_key(hive=winreg.HKEY_LOCAL_MACHINE, key=None):
    if reg_key_exists(hive=hive, key=key):
        parent, _, base = key.rpartition("\\")
        with winreg.OpenKey(hive, parent, 0, winreg.KEY_ALL_ACCESS) as reg:
            winreg.DeleteKey(reg, base)
    assert not reg_key_exists(hive=hive, key=key)


def pytest_configure():
    pytest.DATA_DIR = DATA_DIR
    pytest.INST_DIR = INST_DIR
    pytest.INST_BIN = INST_BIN
    pytest.OLD_DIR = OLD_DIR
    pytest.SCRIPT_DIR = SCRIPT_DIR
    pytest.EXISTING_CONTENT = existing_content
    pytest.CUSTOM_CONTENT = custom_content
    pytest.OLD_CONTENT = old_content


def clean_fragments(inst_dir=INST_DIR):
    # Remove root_dir
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)
    assert not os.path.exists(DATA_DIR)

    # Remove install dir
    if os.path.exists(inst_dir):
        shutil.rmtree(inst_dir)
    assert not os.path.exists(inst_dir)

    # Remove old salt dir (C:\salt)
    if os.path.exists(OLD_DIR):
        shutil.rmtree(OLD_DIR)
    assert not os.path.exists(OLD_DIR)

    # Remove custom config
    if os.path.exists(rf"{SCRIPT_DIR}\custom_conf"):
        os.remove(rf"{SCRIPT_DIR}\custom_conf")
    assert not os.path.exists(rf"{SCRIPT_DIR}\custom_conf")

    # Remove registry entries
    delete_key(key="SOFTWARE\\Salt Project\\Salt")
    assert not reg_key_exists(
        hive=winreg.HKEY_LOCAL_MACHINE, key="SOFTWARE\\Salt Project\\Salt"
    )

    delete_key(key="SOFTWARE\\Salt Project")
    assert not reg_key_exists(
        hive=winreg.HKEY_LOCAL_MACHINE, key="SOFTWARE\\Salt Project"
    )

    return True


@pytest.helpers.register
def clean_env(inst_dir=INST_DIR, timeout=300):
    # Let's make sure none of the install/uninstall processes are running
    for proc in PROCESSES:
        try:
            assert proc not in (p.name() for p in psutil.process_iter())
        except psutil.NoSuchProcess:
            continue

    # Uninstall existing installation
    # Run the uninstaller.
    for uninst_bin in [f"{inst_dir}\\uninst.exe", f"{OLD_DIR}\\uninst.exe"]:
        if os.path.exists(uninst_bin):
            install_dir = os.path.dirname(uninst_bin)
            cmd = [f'"{uninst_bin}"', "/S", "/delete-root-dir", "/delete-install-dir"]
            run_command(cmd)

            # Uninst.exe launches a 2nd binary (Un.exe or Un_*.exe)
            # Let's get the name of the process
            proc_name = ""
            for proc in PROCESSES:
                try:
                    if proc in (p.name() for p in psutil.process_iter()):
                        proc_name = proc
                except psutil.NoSuchProcess:
                    continue

            # We need to give the process time to exit
            if proc_name:
                elapsed_time = 0
                while elapsed_time < timeout:
                    try:
                        if proc_name not in (p.name() for p in psutil.process_iter()):
                            break
                    except psutil.NoSuchProcess:
                        continue
                    elapsed_time += 0.1
                    time.sleep(0.1)

            assert clean_fragments(inst_dir=install_dir)

    return True


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
    conf_file = rf"{SCRIPT_DIR}\custom_conf"
    if os.path.exists(conf_file):
        os.remove(conf_file)
    # Create a custom config
    with open(conf_file, "w") as f:
        # \n characters are converted to os.linesep
        f.writelines(custom_content)
    assert os.path.exists(conf_file)
    return conf_file


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

    assert os.path.exists(f"{OLD_DIR}\\bin\\python.exe")
    assert os.path.exists(f"{OLD_DIR}\\bin\\ssm.exe")
    assert os.path.exists(f"{OLD_DIR}\\conf\\minion")


@pytest.helpers.register
def install_salt(args):
    """
    Cleans the environment and installs salt with passed arguments
    """
    cmd = [f'"{INST_BIN}"']
    if isinstance(args, str):
        cmd.append(args)
    elif isinstance(args, list):
        cmd.extend(args)
    else:
        raise TypeError(f"Invalid args format: {args}")
    run_command(cmd)

    # Let's make sure none of the install/uninstall processes are running
    try:
        assert os.path.basename(INST_BIN) not in (
            p.name() for p in psutil.process_iter()
        )
    except psutil.NoSuchProcess:
        pass


def is_file_locked(path):
    """
    Try to see if a file is locked
    """
    if not (os.path.exists(path)):
        return False
    try:
        f = open(path)
        f.close()
    except OSError:
        return True
    return False


@pytest.helpers.register
def run_command(cmd_args, timeout=300):
    if isinstance(cmd_args, list):
        cmd_args = " ".join(cmd_args)

    bin_file = re.findall(r'"(.*?)"', cmd_args)[0]

    elapsed_time = 0
    while (
        os.path.exists(bin_file) and is_file_locked(bin_file) and elapsed_time < timeout
    ):
        elapsed_time += 0.1
        time.sleep(0.1)

    proc = subprocess.Popen(cmd_args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    elapsed_time = 0
    while (
        os.path.exists(bin_file) and is_file_locked(bin_file) and elapsed_time < timeout
    ):
        elapsed_time += 0.1
        time.sleep(0.1)

    try:
        out, err = proc.communicate(timeout=timeout)
        assert proc.returncode == 0
    except subprocess.TimeoutExpired:
        # This hides the hung installer/uninstaller problem
        proc.kill()
        out = "process killed"

    return out
