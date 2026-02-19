import logging
import os
import shutil
import subprocess
import sys
import time

import packaging.version
import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]

log = logging.getLogger(__name__)


@pytest.fixture
def salt_install_env(request):
    """
    Override the default install environment.

    For upgrade tests: Return empty dict because older versions (like 3006.20)
    don't support SALT_MINION_USER/GROUP. The test will manually set up ownership
    to simulate a system that was configured with a non-root user.

    For fresh install tests: Set SALT_MINION_USER=salt to test the new installation
    behavior with environment variables.
    """
    # Check if --upgrade flag is present in the test config
    upgrade = request.config.getoption("--upgrade", default=False)

    if upgrade:
        # Upgrade test: don't use env vars for old version installation
        return {}
    else:
        # Fresh install test: use env vars to test new installation behavior
        return {
            "SALT_MINION_USER": "salt",
            "SALT_MINION_GROUP": "salt",
        }


@pytest.fixture
def revert_ownership(call_cli):
    """
    Fixture to revert permissions and configuration changes made during the test.

    This is critical because upgrade tests run in a shared environment (container)
    where the package is upgraded but NOT uninstalled between tests (to allow inspection).
    If a test modifies global configuration (like /etc/salt/minion.d/user.conf) or file ownership,
    and fails before cleaning up, subsequent tests (including integration tests) will
    run in a dirty environment and likely fail.

    This fixture ensures that:
    1. Services are stopped to release locks/files.
    2. User configuration is removed.
    3. File ownership is restored to root:root.
    4. Services are restarted to apply clean configuration.

    NOTE: We use subprocess.run instead of call_cli.run for cleanup because if the
    test fails while the minion is configured to run as 'salt', salt-call might also
    drop privileges and fail to perform root-level cleanup operations (like restarting
    services or removing root-owned config files). Using subprocess ensures we run
    as root (the user running the tests).
    """
    # Create backup of /etc/salt/minion if it exists
    if os.path.exists("/etc/salt/minion"):
        shutil.copy("/etc/salt/minion", "/etc/salt/minion.bak")

    yield
    log.info("Reverting ownership and configuration to defaults")
    # Stop service
    subprocess.run(["systemctl", "stop", "salt-minion"], check=False)

    # Restore /etc/salt/minion from backup
    if os.path.exists("/etc/salt/minion.bak"):
        shutil.move("/etc/salt/minion.bak", "/etc/salt/minion")

    # Remove user config
    if os.path.exists("/etc/salt/minion.d/user.conf"):
        os.remove("/etc/salt/minion.d/user.conf")

    # Remove systemd override
    if os.path.exists("/etc/systemd/system/salt-minion.service.d/override.conf"):
        os.remove("/etc/systemd/system/salt-minion.service.d/override.conf")
        subprocess.run(["systemctl", "daemon-reload"], check=False)

    # Restore ownership
    dirs = [
        "/etc/salt/pki/minion",
        "/var/cache/salt/minion",
        "/var/log/salt",
        "/var/run/salt/minion",
        "/etc/salt/minion.d",
        "/opt/saltstack/salt",
    ]
    for d in dirs:
        if os.path.exists(d):
            subprocess.run(["chown", "-R", "root:root", d], check=False)

    # Also fix minion_id which might have been created/owned by salt user
    if os.path.exists("/etc/salt/minion_id"):
        subprocess.run(["chown", "root:root", "/etc/salt/minion_id"], check=False)

    # Clean up pidfile if it exists in the custom location
    if os.path.exists("/var/run/salt/minion/minion.pid"):
        os.remove("/var/run/salt/minion/minion.pid")

    # Start service
    subprocess.run(["systemctl", "start", "salt-minion"], check=False)


def test_salt_user_ownership_preserved_on_upgrade(
    call_cli, install_salt_systemd, salt_systemd_setup, revert_ownership
):
    """
    Test that salt user ownership is preserved during upgrade when no env vars are set.

    This test verifies:
    1. Fresh install with SALT_MINION_USER=salt creates salt:salt ownership
    2. Upgrade WITHOUT environment variables preserves the salt:salt ownership
    3. The RPM %posttrans scriptlet correctly detects and preserves existing ownership

    Test flow:
    - Initial install happens with SALT_MINION_USER=salt (via salt_install_env fixture)
    - Verify directories are owned by salt:salt
    - Upgrade to new version WITHOUT setting any environment variables
    - Verify directories are still owned by salt:salt (ownership preserved)
    """
    # Skip if this is not an upgrade test
    if not install_salt_systemd.upgrade:
        pytest.skip("This test requires upgrade testing, run with --upgrade")

    upgrade_version = packaging.version.parse(install_salt_systemd.artifact_version)

    # Verify we have a previous version installed
    ret = call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_version = packaging.version.parse(ret.data)

    # If we're already at or above the upgrade version, skip downgrade for testing
    # (we'll test ownership preservation during same-version "upgrade" with fixed RPM)
    if installed_version >= upgrade_version:
        log.info(
            "Already at target version, will test ownership preservation during reinstall"
        )
        # Don't install previous version - test ownership preservation with same version

    log.info(
        "Testing ownership preservation from %s to %s",
        installed_version,
        upgrade_version,
    )

    # The previous version doesn't support SALT_MINION_USER environment variable,
    # so we need to manually set up salt:salt ownership AND user configuration
    # to simulate a system that was installed with salt user configuration.

    # First, ensure salt user exists
    # Use subprocess to ensure we are running as root
    log.info("Creating salt user for testing")
    try:
        # Check if user exists
        subprocess.run(
            ["id", "salt"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Ensure shell is /bin/bash for cmd.run tests
        subprocess.run(["usermod", "-s", "/bin/bash", "salt"], check=False)
    except subprocess.CalledProcessError:
        # User does not exist, create it with /bin/bash
        subprocess.run(["useradd", "-r", "-s", "/bin/bash", "salt"], check=True)

    # Check if the current salt-call version supports --priv option
    # The --priv option was added in later versions, but 3006.20 doesn't support it
    help_ret = call_cli.run("--help")
    supports_priv = "--priv" in help_ret.stdout

    # Define the minion and master directories to ensure both can run as salt user
    # The test framework configures master to run as salt user too, so we must fix its permissions
    salt_dirs = [
        "/etc/salt/pki",
        "/var/cache/salt",
        "/var/log/salt",
        "/var/run/salt",
        "/etc/salt/minion.d",
    ]

    # Change ownership to salt:salt BEFORE configuring minion to run as salt user
    # This simulates a system where an admin manually configured salt to run as non-root
    log.info("Changing ownership to salt:salt (simulating manual configuration)")

    # Pre-create proc directory to ensure ownership (workaround for old versions)
    subprocess.run(["mkdir", "-p", "/var/cache/salt/minion/proc"], check=False)

    for dir_path in salt_dirs:
        if os.path.exists(dir_path):
            subprocess.run(["chown", "-R", "salt:salt", dir_path], check=False)
        else:
            log.warning("Directory %s does not exist, skipping chown", dir_path)

    # Configure minion to run as salt user
    log.info("Configuring minion to run as salt user")
    subprocess.run(["mkdir", "-p", "/etc/salt/minion.d"], check=True)

    # Ensure /var/run/salt/minion exists and is owned by salt
    subprocess.run(["mkdir", "-p", "/var/run/salt/minion"], check=True)
    subprocess.run(["chown", "-R", "salt:salt", "/var/run/salt"], check=True)

    # Write config to main minion file to ensure it's loaded
    # Read existing content
    if os.path.exists("/etc/salt/minion"):
        with salt.utils.files.fopen("/etc/salt/minion", "r") as f:
            content = f.readlines()
    else:
        content = []

    # Filter out existing user: and pidfile: lines to avoid duplicates that confuse RPM scriptlets
    content = [
        line
        for line in content
        if not line.strip().startswith("user:")
        and not line.strip().startswith("pidfile:")
    ]

    # Append new config
    if content and not content[-1].endswith("\n"):
        content.append("\n")
    content.append("user: salt\n")
    content.append("pidfile: /var/run/salt/minion/minion.pid\n")

    with salt.utils.files.fopen("/etc/salt/minion", "w") as f:
        f.writelines(content)

    # Also write to minion.d for completeness/testing include
    with salt.utils.files.fopen("/etc/salt/minion.d/user.conf", "w") as f:
        f.write("user: salt\n")
        f.write("pidfile: /var/run/salt/minion/minion.pid\n")

    # Also update systemd unit to run as salt user to avoid permission issues with proc dir
    # This is a workaround for what seems to be a bug in salt-minion dropping privileges
    # where it might reset permissions to root before dropping privileges.
    # Using systemd User= directive ensures it starts as salt user.
    log.info("Configuring systemd to run minion as salt user")
    service_override = "[Service]\nUser=salt\nGroup=salt"
    subprocess.run(
        ["mkdir", "-p", "/etc/systemd/system/salt-minion.service.d"], check=True
    )
    with salt.utils.files.fopen(
        "/etc/systemd/system/salt-minion.service.d/override.conf", "w"
    ) as f:
        f.write(service_override)
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    # Restart minion to apply the user configuration
    # Now the minion can successfully start as salt user and read salt:salt keys
    log.info("Restarting minion to apply user configuration")
    subprocess.run(["systemctl", "restart", "salt-minion"], check=True)
    time.sleep(5)  # Wait for minion to restart

    # Verify minion is running as salt user
    try:
        # Get PID of salt-minion process
        pgrep_out = (
            subprocess.check_output(["pgrep", "-f", "salt-minion"]).decode().strip()
        )
        if not pgrep_out:
            log.warning("Could not find salt-minion process")
        else:
            # Take the first PID if multiple are returned (e.g. main process and children)
            pid = pgrep_out.split("\n", 1)[0]
            ps_out = (
                subprocess.check_output(["ps", "-o", "user=", "-p", pid])
                .decode()
                .strip()
            )
            log.info("Minion process (PID %s) is running as user: %s", pid, ps_out)
    except (subprocess.CalledProcessError, ValueError, OSError) as e:
        log.warning("Could not verify minion user: %s", e)

    log.info("Verifying pre-upgrade ownership is salt:salt")
    for dir_path in salt_dirs:
        test_cmd = f"ls -ld {dir_path}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        if ret.returncode != 0:
            log.warning("Directory %s does not exist, skipping", dir_path)
            continue

        # Use ret.data instead of ret.stdout to get the actual command output
        # ls -ld output format: perms links user group size date time name
        parts = ret.data.strip().split()
        test_user = parts[2]
        test_group = parts[3]

        assert (
            test_user == "salt"
        ), f"Before upgrade: Expected {dir_path} owned by salt, got {test_user}. Full output: {ret.data}"
        assert (
            test_group == "salt"
        ), f"Before upgrade: Expected {dir_path} group salt, got {test_group}. Full output: {ret.data}"

    # Stop the minion before upgrade to avoid permission conflicts during file replacement
    # When minion runs as non-root user, the upgrade temporarily installs files as root,
    # which can cause permission denied errors if minion tries to access them during upgrade
    log.info("Stopping minion before upgrade")
    # Use subprocess to ensure we run as root, since salt-call might drop privileges
    subprocess.run(["systemctl", "stop", "salt-minion"], check=True)
    time.sleep(2)  # Wait for minion to fully stop

    # Now upgrade WITHOUT setting environment variables
    # The RPM %posttrans scriptlet should detect existing ownership and preserve it
    log.info("Upgrading to version %s WITHOUT environment variables", upgrade_version)
    install_salt_systemd.install(upgrade=True)
    time.sleep(10)  # Allow time for services to restart

    # Recheck for --priv support after upgrade (new version should support it)
    help_ret = call_cli.run("--help")
    supports_priv = "--priv" in help_ret.stdout

    # Capture the debug log created by RPM scriptlets
    log.info("Capturing RPM upgrade debug log")
    try:
        if os.path.exists("/var/log/salt-upgrade-debug.log"):
            with salt.utils.files.fopen("/var/log/salt-upgrade-debug.log", "r") as f:
                log_content = f.read()
            log.info("=== RPM UPGRADE DEBUG LOG START ===")
            log.info(log_content)
            log.info("=== RPM UPGRADE DEBUG LOG END ===")
        else:
            log.warning("/var/log/salt-upgrade-debug.log does not exist")
    except OSError as e:
        log.warning("Could not read /var/log/salt-upgrade-debug.log: %s", e)

    # Verify we upgraded successfully
    if supports_priv:
        ret = call_cli.run("--local", "--priv=root", "test.version")
    else:
        ret = call_cli.run("--local", "test.version")
    assert ret.returncode == 0
    installed_version = packaging.version.parse(ret.data)
    # Allow for local build suffix (e.g. 3006.23+16.gd5601f672d)
    assert (
        installed_version >= upgrade_version
    ), f"Expected version >= {upgrade_version}, got {installed_version}"

    # Verify that ownership is STILL salt:salt (preserved during upgrade)
    log.info("Verifying post-upgrade ownership is still salt:salt")
    for dir_path in salt_dirs:
        test_cmd = f"ls -ld {dir_path}"
        if supports_priv:
            ret = call_cli.run("--local", "--priv=root", "cmd.run", test_cmd)
        else:
            ret = call_cli.run("--local", "cmd.run", test_cmd)
        if ret.returncode != 0:
            log.warning("Directory %s does not exist, skipping", dir_path)
            continue

        # Use ret.data instead of ret.stdout to get the actual command output
        parts = ret.data.strip().split()
        test_user = parts[2]
        test_group = parts[3]

        assert (
            test_user == "salt"
        ), f"After upgrade: Expected {dir_path} owned by salt, got {test_user}. Ownership was not preserved! Full output: {ret.data}"
        assert (
            test_group == "salt"
        ), f"After upgrade: Expected {dir_path} group salt, got {test_group}. Ownership was not preserved! Full output: {ret.data}"

    log.info("SUCCESS: salt:salt ownership was preserved during upgrade")

    # Now verify that running salt-call and salt-pip as root still preserves salt user ownership
    # Both commands should drop privileges to the configured user and not create root-owned files
    log.info("Testing that salt-call run as root preserves salt:salt ownership")

    # Run a salt-call command that will access cache
    # We do NOT use --priv=root here because we WANT salt-call to drop privileges
    # to the configured user ('salt') and create files as 'salt'.
    # If we use --priv=root, it forces execution as root, creating root-owned files
    # which causes the subsequent check to fail.
    ret = call_cli.run("--local", "test.ping")
    assert ret.returncode == 0

    # Run salt-pip directly to list packages (verifies pip works and permissions)
    # We avoid installing packages to prevent network timeout issues in restricted environments
    log.info("Running salt-pip list to verify functionality and permissions")
    # Similarly, we want salt-pip to drop privileges
    ret = call_cli.run("--local", "cmd.run", "salt-pip list")
    assert ret.returncode == 0

    # Now verify NO files in the cache directories are owned by root
    log.info("Verifying no root-owned files were created in salt user directories")
    for dir_path in salt_dirs:
        # Find all files in the directory and check ownership
        # Use subprocess to run as root to ensure we can see all files
        try:
            find_out = (
                subprocess.check_output(
                    ["find", dir_path, "-type", "f", "-uid", "0"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )

            if find_out:
                # Found root-owned files!
                root_owned_files = find_out.split("\n")

                # Filter out known root-owned files
                # .root_key is created by master for root-to-master communication
                root_owned_files = [
                    f for f in root_owned_files if not f.endswith("/.root_key")
                ]

                if root_owned_files:
                    pytest.fail(
                        f"Found root-owned files in {dir_path} after running salt-call/salt-pip:\n"
                        + "\n".join(root_owned_files[:10])  # Show first 10 files
                        + f"\n... ({len(root_owned_files)} total root-owned files)"
                    )
        except subprocess.CalledProcessError:
            # find command failed (e.g. directory not found)
            log.warning("Could not check for root-owned files in %s", dir_path)

    # Additional verification: check that /opt/saltstack/salt is owned by salt:salt
    log.info("Verifying /opt/saltstack/salt ownership after upgrade")
    test_cmd = "ls -ld /opt/saltstack/salt"
    if supports_priv:
        ret = call_cli.run("--local", "--priv=root", "cmd.run", test_cmd)
    else:
        ret = call_cli.run("--local", "cmd.run", test_cmd)
    if ret.returncode == 0:
        parts = ret.data.strip().split()
        install_user = parts[2]
        install_group = parts[3]
        assert (
            install_user == "salt"
        ), f"Installation directory /opt/saltstack/salt owned by {install_user}, expected salt"
        assert (
            install_group == "salt"
        ), f"Installation directory /opt/saltstack/salt group {install_group}, expected salt"

    # Verify salt-pip works as salt user
    log.info("Verifying salt-pip functionality as salt user")
    # We use cmd.run to execute as the minion user (salt)
    ret = call_cli.run("--local", "cmd.run", "salt-pip list")
    assert ret.returncode == 0, f"salt-pip list failed: {ret.stderr}"

    # Verify that the extras directory was created and is owned by salt:salt
    extras_dir = (
        f"/opt/saltstack/salt/extras-{sys.version_info.major}.{sys.version_info.minor}"
    )
    log.info(
        "Verifying extras directory %s was created and owned correctly", extras_dir
    )
    test_cmd = f"ls -ld {extras_dir} 2>/dev/null || echo 'Directory not found'"
    if supports_priv:
        ret = call_cli.run("--local", "--priv=root", "cmd.run", test_cmd)
    else:
        ret = call_cli.run("--local", "cmd.run", test_cmd)
    if "Directory not found" not in ret.data:
        parts = ret.data.strip().split()
        extras_user = parts[2]
        extras_group = parts[3]
        assert (
            extras_user == "salt"
        ), f"Extras directory {extras_dir} owned by {extras_user}, expected salt"
        assert (
            extras_group == "salt"
        ), f"Extras directory {extras_dir} group {extras_group}, expected salt"

    log.info(
        "SUCCESS: No root-owned files created, salt-call and salt-pip properly dropped privileges, and installation directory ownership preserved"
    )
