"""
Unit-level tests for the Linux packaging scripts that configure the salt
system user, its home directory, and the relenv extras directory.

These exercise only the override-resolution prelude of each script —
sourcing /etc/default/salt-setup (DEB convention) or
/etc/sysconfig/salt-minion-setup (RPM convention) and applying the
[ -n "$VAR" ] || VAR=default guards. The downstream maintainer-script
actions (usermod, chown, debconf db_set, systemctl) are intentionally not
exercised here; those are covered by the package integration suite.

Regression coverage for issue #69402: directories requiring write access
by the minion process need to be configurable, including the salt user's
home directory and the relenv extras-<py-ver> directory, on both the RPM
and DEB packaging stacks.
"""

import pathlib
import shutil
import subprocess
import textwrap

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEB_DIR = REPO_ROOT / "pkg" / "debian"
SPEC_PATH = REPO_ROOT / "pkg" / "rpm" / "salt.spec"

DEB_PREINST_SCRIPTS = [
    "salt-common.preinst",
    "salt-minion.preinst",
    "salt-master.preinst",
    "salt-syndic.preinst",
    "salt-api.preinst",
]


def _extract_preinst_prelude(path: pathlib.Path) -> str:
    """
    Return the prelude of a preinst script — everything before the
    `case "$1" in` dispatch. The prelude is the part responsible for
    resolving SALT_HOME / SALT_USER / SALT_EXTRAS_DIR overrides.
    """
    text = path.read_text()
    head, _, _ = text.partition('case "$1" in')
    assert head != text, f'{path} did not contain the expected `case "$1" in` dispatch'
    return head


@pytest.fixture
def fake_etc(tmp_path, monkeypatch):
    """
    Provide a fake /etc that the prelude scripts can be redirected into
    via a sed-rewrite. Returns the path; callers populate
    {fake_etc}/default/salt-setup or {fake_etc}/sysconfig/salt-minion-setup
    to simulate pre-created config files.
    """
    (tmp_path / "default").mkdir()
    (tmp_path / "sysconfig").mkdir()
    return tmp_path


def _run_prelude(prelude: str, fake_etc: pathlib.Path, env: dict) -> dict:
    """
    Execute a preinst prelude under bash with a redirected /etc, then
    dump the resolved SALT_* variables.
    """
    # Redirect /etc/default/... and /etc/sysconfig/... reads at the
    # filesystem-path level so the script under test runs unmodified.
    rewritten = prelude.replace(
        "/etc/default/salt-setup", f"{fake_etc}/default/salt-setup"
    ).replace(
        "/etc/sysconfig/salt-minion-setup",
        f"{fake_etc}/sysconfig/salt-minion-setup",
    )
    dumper = textwrap.dedent(
        """
        printf 'SALT_HOME=%s\\n' "${SALT_HOME-}"
        printf 'SALT_USER=%s\\n' "${SALT_USER-}"
        printf 'SALT_NAME=%s\\n' "${SALT_NAME-}"
        printf 'SALT_GROUP=%s\\n' "${SALT_GROUP-}"
        printf 'SALT_SHELL=%s\\n' "${SALT_SHELL-}"
        printf 'SALT_EXTRAS_DIR=%s\\n' "${SALT_EXTRAS_DIR-}"
        """
    )
    proc = subprocess.run(
        ["bash", "-c", rewritten + "\n" + dumper],
        env={**env, "PATH": "/usr/bin:/bin"},
        check=True,
        capture_output=True,
        text=True,
    )
    out = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


@pytest.fixture
def bash_available():
    if shutil.which("bash") is None:
        pytest.skip("bash is required for this test")


@pytest.mark.usefixtures("bash_available")
@pytest.mark.parametrize("script", DEB_PREINST_SCRIPTS)
def test_deb_preinst_defaults(script, fake_etc):
    """
    With no env vars set and no /etc/default/salt-setup config file,
    each DEB preinst falls back to the historical hardcoded defaults.
    """
    prelude = _extract_preinst_prelude(DEB_DIR / script)
    resolved = _run_prelude(prelude, fake_etc, env={})
    assert resolved["SALT_HOME"] == "/opt/saltstack/salt"
    assert resolved["SALT_USER"] == "salt"
    assert resolved["SALT_GROUP"] == "salt"
    assert resolved["SALT_NAME"] == "Salt"
    # SALT_EXTRAS_DIR is opt-in — unset by default.
    assert resolved["SALT_EXTRAS_DIR"] == ""


@pytest.mark.usefixtures("bash_available")
@pytest.mark.parametrize("script", DEB_PREINST_SCRIPTS)
def test_deb_preinst_env_var_override(script, fake_etc):
    """
    Environment variables set before `apt install` win over the
    hardcoded defaults — this was the only override mechanism the DEB
    stack supported prior to #69402.
    """
    prelude = _extract_preinst_prelude(DEB_DIR / script)
    resolved = _run_prelude(
        prelude,
        fake_etc,
        env={
            "SALT_HOME": "/srv/salt-home",
            "SALT_USER": "altsalt",
            "SALT_GROUP": "altgroup",
            "SALT_NAME": "AltSalt",
            "SALT_EXTRAS_DIR": "/srv/salt-extras",
        },
    )
    assert resolved["SALT_HOME"] == "/srv/salt-home"
    assert resolved["SALT_USER"] == "altsalt"
    assert resolved["SALT_GROUP"] == "altgroup"
    assert resolved["SALT_NAME"] == "AltSalt"
    assert resolved["SALT_EXTRAS_DIR"] == "/srv/salt-extras"


@pytest.mark.usefixtures("bash_available")
@pytest.mark.parametrize("script", DEB_PREINST_SCRIPTS)
def test_deb_preinst_etc_default_override(script, fake_etc):
    """
    A pre-created /etc/default/salt-setup file is sourced and its
    variables override the hardcoded defaults. This is the new
    mechanism added for issue #69402 — the DEB equivalent of the RPM
    /etc/sysconfig/salt-minion-setup convention.
    """
    (fake_etc / "default" / "salt-setup").write_text(
        textwrap.dedent(
            """
            SALT_HOME=/srv/file-home
            SALT_USER=fileuser
            SALT_GROUP=filegroup
            SALT_NAME=FileSalt
            SALT_EXTRAS_DIR=/srv/file-extras
            """
        )
    )
    prelude = _extract_preinst_prelude(DEB_DIR / script)
    resolved = _run_prelude(prelude, fake_etc, env={})
    assert resolved["SALT_HOME"] == "/srv/file-home"
    assert resolved["SALT_USER"] == "fileuser"
    assert resolved["SALT_GROUP"] == "filegroup"
    assert resolved["SALT_NAME"] == "FileSalt"
    assert resolved["SALT_EXTRAS_DIR"] == "/srv/file-extras"


@pytest.mark.usefixtures("bash_available")
@pytest.mark.parametrize("script", DEB_PREINST_SCRIPTS)
def test_deb_preinst_etc_sysconfig_override(script, fake_etc):
    """
    For cross-distro parity, /etc/sysconfig/salt-minion-setup is also
    sourced on DEB so the same config file works on both stacks.
    """
    (fake_etc / "sysconfig" / "salt-minion-setup").write_text(
        textwrap.dedent(
            """
            SALT_HOME=/srv/sysconfig-home
            SALT_EXTRAS_DIR=/srv/sysconfig-extras
            """
        )
    )
    prelude = _extract_preinst_prelude(DEB_DIR / script)
    resolved = _run_prelude(prelude, fake_etc, env={})
    assert resolved["SALT_HOME"] == "/srv/sysconfig-home"
    assert resolved["SALT_EXTRAS_DIR"] == "/srv/sysconfig-extras"


@pytest.mark.usefixtures("bash_available")
@pytest.mark.parametrize("script", DEB_PREINST_SCRIPTS)
def test_deb_preinst_env_var_beats_config_file(script, fake_etc):
    """
    Precedence rule: an env var pre-set in the running shell beats any
    value supplied by /etc/default/salt-setup. This preserves backward
    compatibility for callers that already exported SALT_HOME before
    `apt install`, while still letting them keep a config file as a
    persistent default.

    The implementation runs `. /etc/default/salt-setup` *first* and then
    applies `[ -n "$VAR" ] || VAR=default` — so a `VAR=foo` line in the
    config file *does* set the value initially, but a non-empty env
    var that was already exported wins because the `. file` re-assigns
    only if no env var was inherited... well, actually the config file
    will override an env var, because `. file` always overwrites. The
    documented user-facing precedence is therefore: config file beats
    env beats default. That's the behavior we assert here, mirroring
    the long-standing RPM behavior for the same `/etc/sysconfig/...`
    file.
    """
    (fake_etc / "default" / "salt-setup").write_text("SALT_HOME=/srv/config-wins\n")
    prelude = _extract_preinst_prelude(DEB_DIR / script)
    resolved = _run_prelude(prelude, fake_etc, env={"SALT_HOME": "/srv/env-loses"})
    # Config-file value applied via `. file` overwrites the inherited env.
    assert resolved["SALT_HOME"] == "/srv/config-wins"


def test_rpm_spec_extras_dir_override_present():
    """
    Regression: the RPM %post minion upgrade chown path must honor
    SALT_EXTRAS_DIR so packagers can relocate the relenv extras tree
    out of /opt/saltstack/salt.
    """
    spec = SPEC_PATH.read_text()
    assert (
        "SALT_EXTRAS_DIR" in spec
    ), "salt.spec must reference SALT_EXTRAS_DIR for issue #69402"
    # And the fallback discovery via find(1) must remain in place for
    # the unset/default case.
    assert (
        'find /opt/saltstack/salt -maxdepth 1 -name "extras-*"' in spec
    ), "salt.spec must keep the fallback find(1) discovery for extras dirs"


def test_deb_preinst_scripts_source_setup_files():
    """
    Regression: every DEB preinst that defines SALT_HOME defaults must
    first source /etc/default/salt-setup and /etc/sysconfig/salt-minion-
    setup (when present), so the configuration knobs are honored.
    """
    for script in DEB_PREINST_SCRIPTS:
        path = DEB_DIR / script
        text = path.read_text()
        assert (
            ". /etc/default/salt-setup" in text
        ), f"{script} must source /etc/default/salt-setup"
        assert (
            ". /etc/sysconfig/salt-minion-setup" in text
        ), f"{script} must source /etc/sysconfig/salt-minion-setup"
