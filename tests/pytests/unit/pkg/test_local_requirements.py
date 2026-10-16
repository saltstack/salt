"""Exercise package upgrade hooks without installing packages or services."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]


def _postinst(tmp_path):
    """Substitute an isolated runtime and config into the real maintainer script."""
    runtime = tmp_path / "new runtime"
    config = tmp_path / "salt config"
    runtime.mkdir()
    config.mkdir()
    # compileall is independent of pip; record both to check execution order.
    for name, command in (
        ("bin/python3", 'echo compile >> "$HOOK_EVENTS"'),
        (
            "salt-pip",
            'echo pip >> "$HOOK_EVENTS"\n'
            'printf "%s\\n" "$@" > "$HOOK_ARGS"\n'
            'printf "%s\\n" "$SALT_CONFIG_DIR" "$SALT_EXTRAS_DIR" > "$HOOK_ENV"\n'
            'exit "${HOOK_PIP_EXIT:-0}"',
        ),
    ):
        executable = runtime / name
        executable.parent.mkdir(exist_ok=True)
        executable.write_text(f"#!/bin/sh\n{command}\n")
        executable.chmod(0o755)

    source = (REPO_ROOT / "pkg/debian/salt-common.postinst").read_text()
    source = source.replace("/opt/saltstack/salt", str(runtime))
    # Quote the runtime substitutions, including the compileall argument.
    source = source.replace(f"{runtime}/bin/python3", f'"{runtime}/bin/python3"')
    source = source.replace(f"{runtime}/lib", f'"{runtime}/lib"')
    source = source.replace(f"{runtime}/salt-pip", f'"{runtime}/salt-pip"')
    source = source.replace(
        "/etc/salt/local-requirements.txt", f'"{config}/local-requirements.txt"'
    )
    source = source.replace("SALT_CONFIG_DIR=/etc/salt", f'SALT_CONFIG_DIR="{config}"')
    source = source.replace("/etc/default/salt-setup", f'"{tmp_path}/salt-setup"')
    source = source.replace(
        "/etc/sysconfig/salt-minion-setup", f'"{tmp_path}/rpm-setup"'
    )
    source = source.replace("#DEBHELPER#", 'echo service-hooks >> "$HOOK_EVENTS"')
    script = tmp_path / "postinst"
    script.write_text(source)
    env = os.environ.copy()
    env.update(
        HOOK_EVENTS=str(tmp_path / "events"),
        HOOK_ARGS=str(tmp_path / "args"),
        HOOK_ENV=str(tmp_path / "env"),
        SALT_EXTRAS_DIR="",
    )
    return script, config, env


@pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required")
@pytest.mark.parametrize(
    "requirements,action,pip_exit,expected_events,expected_exit",
    [
        (None, "configure", 0, ["compile", "service-hooks"], 0),
        ("", "configure", 0, ["compile", "pip", "service-hooks"], 0),
        ("pymysql==1.1.1\n", "configure", 0, ["compile", "pip", "service-hooks"], 0),
        ("unavailable-package\n", "configure", 17, ["compile", "pip"], 1),
        ("pymysql\n", "abort-upgrade", 0, ["service-hooks"], 0),
    ],
)
def test_debian_local_requirements(
    tmp_path, requirements, action, pip_exit, expected_events, expected_exit
):
    script, config, env = _postinst(tmp_path)
    if requirements is not None:
        (config / "local-requirements.txt").write_text(requirements)
    # An assignment sourced from salt-setup must reach the pip subprocess.
    (tmp_path / "salt-setup").write_text('SALT_EXTRAS_DIR="/srv/salt extras"\n')
    env["HOOK_PIP_EXIT"] = str(pip_exit)
    result = subprocess.run(
        ["sh", str(script), action],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == expected_exit, result.stderr
    assert (tmp_path / "events").read_text().splitlines() == expected_events
    if "pip" in expected_events:
        assert (tmp_path / "args").read_text().splitlines() == [
            "install",
            "--requirement",
            str(config / "local-requirements.txt"),
        ]
        assert (tmp_path / "env").read_text().splitlines() == [
            str(config),
            "/srv/salt extras",
        ]
    if pip_exit:
        assert "salt-common remains unconfigured" in result.stderr


def test_msi_requirements_action_precedes_service_start():
    """Validate the WiX action's sequencing, data and failure propagation."""
    root = ElementTree.parse(REPO_ROOT / "pkg/windows/msi/Product.wxs").getroot()
    ns = {"w": "http://schemas.microsoft.com/wix/2006/wi"}
    action = root.find(
        ".//w:InstallExecuteSequence/w:Custom[@Action='InstallLocalRequirements_DECAC']",
        ns,
    )
    assert action.attrib["Before"] == "StartServices"
    assert action.text == 'NOT (REMOVE ~= "ALL")'
    definition = root.find(
        ".//w:CustomAction[@Id='InstallLocalRequirements_DECAC']", ns
    )
    assert definition.attrib["Execute"] == "deferred"
    assert definition.attrib["Return"] == "check"
    assert definition.attrib["Impersonate"] == "no"


@pytest.fixture
def local_runtime(tmp_path):
    """A new runtime whose pip and service commands record their invocation."""
    runtime = tmp_path / "runtime"
    config = tmp_path / "config"
    runtime.mkdir()
    config.mkdir()
    pip = runtime / "salt-pip"
    pip.write_text(
        '#!/bin/sh\necho pip >> "$HOOK_EVENTS"\n'
        'printf "%s\\n" "$@" > "$HOOK_ARGS"\n'
        'printf "%s\\n" "$SALT_EXTRAS_DIR" > "$HOOK_EXTRAS"\n'
        'exit "${HOOK_PIP_EXIT:-0}"\n'
    )
    pip.chmod(0o755)
    env = os.environ.copy()
    env.update(
        HOOK_EVENTS=str(tmp_path / "events"),
        HOOK_ARGS=str(tmp_path / "args"),
        HOOK_EXTRAS=str(tmp_path / "extras"),
        SALT_EXTRAS_DIR="",
        INSTALL_DIR=str(runtime),
        CONFIG_DIR=str(config),
    )
    return runtime, config, env


def _run_shell(source, env):
    return subprocess.run(
        ["sh", "-c", source],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _rpm_requirements_scripts(tmp_path, runtime, config):
    """Extract the real base-package hook and expand its restart guard macro."""
    spec = (REPO_ROOT / "pkg/rpm/salt.spec").read_text()
    base = re.search(r"^%post\n(.*?)(?=^%post cloud)", spec, re.M | re.S).group(1)
    guard = re.search(
        r"^%define salt_check_local_requirements\(\) \\\n(.*?)\nfi",
        spec,
        re.M | re.S,
    ).group(1)
    guard = (guard + "\nfi\n").replace("\\\n", "\n")
    state = tmp_path / "rpm-state"
    setup = tmp_path / "salt-setup"
    setup.write_text('SALT_EXTRAS_DIR="/srv/salt extras"\n')

    def relocate(source):
        return (
            source.replace("/opt/saltstack/salt", str(runtime))
            .replace("/etc/salt", str(config))
            .replace("/var/lib/rpm-state/salt", str(state))
            .replace("/etc/sysconfig/salt-minion-setup", str(setup))
        )

    return "ln() { :; }\n" + relocate(base), relocate(guard), state


@pytest.mark.skipif(shutil.which("sh") is None, reason="POSIX shell required")
@pytest.mark.parametrize("requirements,pip_exit", [(False, 0), (True, 0), (True, 17)])
@pytest.mark.parametrize("stale_failure", [False, True])
def test_rpm_requirements_gate_later_scriptlets(
    tmp_path, local_runtime, requirements, pip_exit, stale_failure
):
    runtime, config, env = local_runtime
    if requirements:
        (config / "local-requirements.txt").write_text("pymysql\n")
    env["HOOK_PIP_EXIT"] = str(pip_exit)
    base, guard, state = _rpm_requirements_scripts(tmp_path, runtime, config)
    # A stale marker from a previous failure must be cleared on successful
    # reinstallation, including when the operator removes the requirements.
    state.mkdir()
    marker = state / "local-requirements.failed"
    if stale_failure:
        marker.touch()
    result = _run_shell(base, env)
    assert result.returncode == (1 if pip_exit else 0), result.stderr
    assert marker.exists() == bool(pip_exit)
    # RPM continues the transaction after %post fails. Exercise independent
    # service scriptlets to ensure they all decline startup in that case.
    for _ in range(2):
        service = _run_shell(guard + 'echo service >> "$HOOK_EVENTS"\n', env)
        assert service.returncode == (1 if pip_exit else 0), service.stderr
    events = (tmp_path / "events").read_text().splitlines()
    assert events == (["pip"] if requirements else []) + (
        [] if pip_exit else ["service", "service"]
    )
    if requirements:
        assert (tmp_path / "args").read_text().splitlines() == [
            "install",
            "--requirement",
            str(config / "local-requirements.txt"),
        ]
        assert (tmp_path / "extras").read_text().strip() == "/srv/salt extras"


def test_rpm_all_service_starts_check_requirements():
    spec = (REPO_ROOT / "pkg/rpm/salt.spec").read_text()
    starts = re.findall(
        r"([^\n]*)\n[^\n]*/bin/systemctl (?:start|try-restart) salt-[^\n]*",
        spec,
    )
    assert starts
    assert all(line.strip() == "%{salt_check_local_requirements}" for line in starts)


@pytest.mark.skipif(shutil.which("bash") is None, reason="Bash required")
@pytest.mark.parametrize("requirements,pip_exit", [(False, 0), (True, 0), (True, 17)])
def test_macos_requirements_precede_launchd(
    tmp_path, local_runtime, requirements, pip_exit
):
    runtime, config, env = local_runtime
    if requirements:
        (config / "local-requirements.txt").write_text("pymysql\n")
    env["HOOK_PIP_EXIT"] = str(pip_exit)
    source = (REPO_ROOT / "pkg/macos/pkg-scripts/postinstall").read_text()
    source = source.split("# Register Salt as a service\n", 1)[1]
    source = source.replace("/bin/launchctl", "launchctl")
    source = 'log() { :; }\nlaunchctl() { echo service >> "$HOOK_EVENTS"; }\n' + source
    result = subprocess.run(
        ["bash", "-c", source],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == (1 if pip_exit else 0), result.stderr
    events = (tmp_path / "events").read_text().splitlines()
    if pip_exit:
        assert events == ["pip"]
        assert "local requirements installation failed" in result.stderr
    elif requirements:
        assert events[0] == "pip"
        assert "service" in events[1:]
    else:
        assert set(events) == {"service"}
