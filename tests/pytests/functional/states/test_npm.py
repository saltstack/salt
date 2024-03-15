import pathlib
import shutil

import pytest

from salt.exceptions import CommandExecutionError
from salt.utils.versions import Version

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.requires_network,
]

MAX_NPM_VERSION = "5.0.0"


@pytest.fixture(scope="module")
def install_npm(states):
    try:
        ret = states.pkg.installed(name="npm")
        assert ret.result is True
        # Just name the thing we're looking for
        states.npm  # pylint: disable=pointless-statement
    except (CommandExecutionError, AttributeError, AssertionError) as exc:
        pytest.skip(f"Unable to install npm - {exc}")


@pytest.fixture(scope="module")
def apply_gitconfig_workaround(install_npm):
    # See https://github.com/npm/cli/issues/1673 as to why
    gitconfig = pathlib.Path("~/.gitconfig").expanduser().resolve()
    gitconfig_backup = gitconfig.with_suffix(".bak")
    try:
        if gitconfig.exists():
            shutil.move(str(gitconfig), str(gitconfig_backup))
        gitconfig.write_text(
            """[url "git@github.com:"]\n  insteadOf = git://github.com/\n"""
        )
        yield
    finally:
        if not gitconfig_backup.exists():
            gitconfig.unlink()
        else:
            shutil.move(str(gitconfig), str(gitconfig_backup))


@pytest.fixture
def npm(states, modules, apply_gitconfig_workaround):
    try:
        yield states.npm
    finally:
        for pkg in ("pm2", "request", "grunt"):
            modules.npm.uninstall(pkg)


@pytest.mark.skip_if_not_root
@pytest.mark.timeout_unless_on_windows(120)
def test_removed_installed_cycle(npm, modules):
    project_version = "pm2@5.1.0"
    success = modules.npm.uninstall("pm2")
    assert success, "Unable to uninstall pm2 in prep for tests"

    ret = npm.installed(name=project_version)
    assert ret.result is True, "Failed to states.npm.installed {} - {}".format(
        project_version, ret.comment
    )

    ret = npm.removed(name=project_version)
    assert ret.result is True, "Failed to states.npm.removed {} - {}".format(
        project_version, ret.comment
    )


@pytest.fixture
def npm_version(shell, install_npm):
    ret = shell.run("npm", "-v")
    assert ret.returncode == 0
    return ret.stdout.strip()


@pytest.mark.skip(
    reason="This test tries to install from a git repo using ssh, at least now. Skipping.",
)
@pytest.mark.skip_if_not_root
@pytest.mark.skip_if_binaries_missing("git")
def test_npm_install_url_referenced_package(modules, npm, npm_version, states):
    """
    Determine if URL-referenced NPM module can be successfully installed.
    """
    ret = npm.installed(
        name="request/request#v2.88.2",
        registry="https://registry.npmjs.org/",
    )
    assert ret.result is True
    ret = npm.removed(
        name="git://github.com/request/request",
    )
    assert ret.result is True


@pytest.mark.skip_if_not_root
def test_npm_installed_pkgs(npm):
    """
    Basic test to determine if NPM module successfully installs multiple
    packages.
    """
    ret = npm.installed(
        name="unused",
        pkgs=["pm2@5.1.0", "grunt@1.5.3"],
        registry="https://registry.npmjs.org/",
    )
    assert ret.result is True


def test_npm_cache_clean(npm, npm_version):
    """
    Basic test to determine if NPM successfully cleans its cached packages.
    """
    if Version(npm_version) >= Version(MAX_NPM_VERSION):
        pytest.skip("Skip with npm >= 5.0.0 until #41770 is fixed")
    ret = npm.cache_cleaned(name="unused", force=True)
    assert ret.result is True
