import os
import re
import shutil
import stat
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
    "Un_E.exe",
    "Un_F.exe",
    "Un_G.exe",
]

# Max seconds to wait for each discrete cleanup phase before giving up and
# force-killing.  These are all far longer than the normal happy-path times
# (typically < 3 s each) so they only trigger when something is genuinely stuck.
PROC_WAIT_SECS = 30  # installer/uninstaller processes to exit
INST_DIR_WAIT_SECS = 30  # install dir to be deleted by Un.exe
SCM_WAIT_SECS = 15  # SCM to remove the salt-minion service registry key


def _kill_lingering_processes():
    """Force-kill any installer/uninstaller processes that are still running."""
    for name in PROCESSES:
        subprocess.run(
            ["taskkill", "/F", "/T", "/IM", name],
            capture_output=True,
        )


def _live_processes():
    """Return the set of process names currently in the process list."""
    live = set()
    for p in psutil.process_iter():
        try:
            live.add(p.name())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return live


def _wait_for_processes(wait_secs=PROC_WAIT_SECS):
    """
    Wait up to wait_secs for every name in PROCESSES to leave the process list.
    If the timeout expires, force-kill them all, then wait up to 5 s for the
    OS to remove them from the process table.
    Returns True if they exited cleanly, False if they had to be force-killed.
    Callers should treat False as a test failure signal.
    """
    elapsed = 0.0
    while elapsed < wait_secs:
        if not any(name in _live_processes() for name in PROCESSES):
            return True
        elapsed += 0.1
        time.sleep(0.1)

    # Timed out — force-kill, then give the OS up to 5 s to clean up.
    _kill_lingering_processes()
    for _ in range(50):
        time.sleep(0.1)
        if not any(name in _live_processes() for name in PROCESSES):
            break

    return False  # signal to caller: processes were force-killed


def reg_key_exists(hive=winreg.HKEY_LOCAL_MACHINE, key=None):
    """
    Helper function to determine if a registry key exists. It does this by
    opening the key. If the connection is successful, the key exists. Otherwise
    an error is returned, which means the key does not exist
    """
    try:
        with winreg.OpenKey(hive, key, 0, winreg.KEY_READ):
            return True
    except OSError:
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

    # Remove old salt dir (C:\salt).  PKI files (minion.pem etc.) are created
    # with restrictive NTFS permissions by the Salt installer, so a plain
    # rmtree raises PermissionError.  The onerror handler clears the read-only
    # attribute and retries so the tree is always removed cleanly.
    def _force_remove(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if os.path.exists(OLD_DIR):
        shutil.rmtree(OLD_DIR, onerror=_force_remove)
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
def clean_env(inst_dir=INST_DIR):
    # Track whether any process had to be force-killed.  If so we return
    # False so the caller's `assert clean_env()` fails the test — a forced
    # kill means something got stuck, which is exactly what this test suite
    # is designed to catch.
    killed = False

    # Un.exe (the NSIS temp-copy uninstaller) is still alive when the
    # previous iteration's run_command() returns — it continues stripping
    # parent directories and registry entries after uninst.exe exits.
    # Wait (and kill if stuck) before asserting so we don't race the tail
    # of the previous uninstall.
    if not _wait_for_processes():
        killed = True

    # Verify all installer/uninstaller processes are gone after the wait.
    # We do NOT raise AssertionError here — if a process is still visible
    # (e.g. Un.exe appeared between the wait and this check), treat it as
    # a force-kill failure so the test is marked ERROR rather than crashing
    # the fixture with an unhandled exception.
    live = _live_processes()
    for proc in PROCESSES:
        if proc in live:
            print(f"\nWARNING: {proc} still in process list after wait — force-killing")
            _kill_lingering_processes()
            killed = True
            break  # _kill_lingering_processes covers all PROCESSES at once

    # Uninstall existing installation if one is present.
    for uninst_bin in [f"{inst_dir}\\uninst.exe", f"{OLD_DIR}\\uninst.exe"]:
        if os.path.exists(uninst_bin):
            install_dir = os.path.dirname(uninst_bin)
            cmd = [f'"{uninst_bin}"', "/S", "/delete-root-dir", "/delete-install-dir"]
            if not run_command(cmd):
                killed = True

            # uninst.exe immediately re-launches itself as Un.exe (or Un_*.exe)
            # from a temp path so it can delete its own binary, then exits.
            # run_command() returns at that point while Un.exe is still working.
            # Give Un.exe a moment to appear in the OS process table before we
            # start polling — without this pause _wait_for_processes() may poll
            # in the brief window between uninst.exe launching Un.exe and Un.exe
            # actually appearing in the process table, causing a false-positive
            # "no processes" result while Un.exe is still doing its cleanup.
            time.sleep(0.5)
            if not _wait_for_processes():
                killed = True

            # Un.exe's last act is RMDir $INSTDIR.  Waiting here until the
            # directory is gone is a belt-and-suspenders check that every
            # file-system operation in the uninstall has completed.
            elapsed_time = 0
            while os.path.exists(install_dir) and elapsed_time < INST_DIR_WAIT_SECS:
                elapsed_time += 0.1
                time.sleep(0.1)

            # Wait for the Windows SCM to finish removing the salt-minion
            # service entry from the registry.  ssm.exe remove marks the
            # service for deletion, but SCM keeps the
            # HKLM\SYSTEM\CurrentControlSet\Services\salt-minion key alive
            # until all open handles (including its own internal ones) are
            # closed.  If CreateService for the *next* iteration races with
            # this cleanup, Windows can return ERROR_SERVICE_MARKED_FOR_DELETE
            # or leave NSSM in a state where SetServiceStatus(RUNNING) blocks
            # on an SCM-internal lock — causing `nssm start` to hang.
            scm_key = r"SYSTEM\CurrentControlSet\Services\salt-minion"
            scm_elapsed = 0.0
            while scm_elapsed < SCM_WAIT_SECS:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, scm_key):
                        pass  # key still present
                except OSError:
                    break  # key gone — SCM cleanup complete
                scm_elapsed += 0.5
                time.sleep(0.5)

            try:
                clean_fragments(inst_dir=install_dir)
            except Exception as exc:
                print(f"\nERROR in clean_fragments({install_dir!r}): {exc}")
                killed = True

    return not killed


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
    assert run_command(
        cmd
    ), "Installer failed (non-zero exit or force-killed on timeout)"

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


def _kill_process_tree(proc):
    """
    Kill a subprocess and every descendant it spawned.
    proc.kill() alone only terminates the top-level process; child processes
    (e.g. the nssm start child launched by the NSIS installer via Exec, or
    the salt-minion service process that NSSM itself started) keep running
    and leave the system in a dirty state for the next iteration.
    """
    try:
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass
    proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


@pytest.helpers.register
def run_command(cmd_args, timeout=60):
    if isinstance(cmd_args, list):
        cmd_args = " ".join(cmd_args)

    bin_file = re.findall(r'"(.*?)"', cmd_args)[0]

    elapsed_time = 0
    while (
        os.path.exists(bin_file) and is_file_locked(bin_file) and elapsed_time < timeout
    ):
        elapsed_time += 0.1
        time.sleep(0.1)

    # Use DEVNULL instead of PIPE for stdout/stderr.  PIPE creates inheritable
    # handles: NSIS's Exec (bInheritHandles=TRUE) passes them to the
    # "ssm.exe start salt-minion" child, which then holds the write-end of
    # the pipe open even after the installer itself has exited.
    # proc.communicate() can never see EOF while that child is alive, so the
    # test blocks indefinitely.  DEVNULL avoids creating any pipe handles,
    # so proc.wait() returns as soon as the installer process exits.
    proc = subprocess.Popen(
        cmd_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    try:
        proc.wait(timeout=timeout)
        if proc.returncode != 0:
            print(
                f"\nWARNING: process exited with code {proc.returncode}: {cmd_args[:120]}"
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        # Kill the installer/uninstaller and every child it spawned (nssm,
        # salt-minion, etc.) so they don't linger into the next iteration.
        print(
            f"\nWARNING: process timed out after {timeout}s — force-killing: {cmd_args[:120]}"
        )
        _kill_process_tree(proc)
        return False
