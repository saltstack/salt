"""
    tests.e2e.compat.test_with_versions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test current salt master with older salt minions
"""

import logging
import pathlib

import pytest
from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string

import salt.utils.platform
from tests.conftest import FIPS_TESTRUN
from tests.support.runtests import RUNTIME_VARS

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip("GREAT MODULE MIGRATION"),
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker"),
    pytest.mark.skipif(
        salt.utils.platform.is_photonos() is True, reason="Skip on PhotonOS"
    ),
]


# Debian 11 (bullseye) reached EOL on 2026-08-31 and its debian-security
# InRelease signatures are no longer refreshed. The
# ``ghcr.io/saltstack/salt-ci-containers/salt:{3002,3003,3004}`` images are
# pinned/immutable Debian 11 releases and cannot be rebuilt to pick up a
# snapshot.debian.org sources fix. So we patch each container in-place after
# it starts: point apt at snapshot.debian.org (pre-EOL bullseye snapshot) and
# disable ``Valid-Until`` freshness checks. GPG signature verification is
# untouched. Mirrors the pattern used by the salt-ci-containers
# ``testing:debian-11`` fresh-image fix, and matches the host-level
# ``_bullseye_eol_apt_bypass`` session fixture (which does not reach inside
# spawned containers).
_BULLSEYE_EOL_SNAPSHOT = "20260824T000000Z"
_BULLSEYE_APT_FIX_SH = (
    "set -e; "
    "cat > /etc/apt/sources.list <<EOF\n"
    f"deb http://snapshot.debian.org/archive/debian/{_BULLSEYE_EOL_SNAPSHOT} bullseye main contrib non-free\n"
    f"deb http://snapshot.debian.org/archive/debian-security/{_BULLSEYE_EOL_SNAPSHOT} bullseye-security main contrib non-free\n"
    f"deb http://snapshot.debian.org/archive/debian/{_BULLSEYE_EOL_SNAPSHOT} bullseye-updates main contrib non-free\n"
    "EOF\n"
    "mkdir -p /etc/apt/apt.conf.d; "
    "printf '%s\\n' 'Acquire::Check-Valid-Until \"false\";' "
    "> /etc/apt/apt.conf.d/99-salt-tests-bullseye-eol"
)


def _apply_bullseye_eol_apt_fix(factory):
    """
    ``after_start`` callback: rewrite apt sources inside the compat container
    to work around bullseye EOL. Best-effort; log and continue on failure so
    non-Debian containers (if any are added later) do not break startup.
    """
    try:
        ret = factory.run("sh", "-c", _BULLSEYE_APT_FIX_SH)
    except Exception as exc:  # pylint: disable=broad-except
        log.warning("Failed to apply bullseye EOL apt fix to %s: %s", factory, exc)
        return
    if ret.returncode != 0:
        log.warning(
            "bullseye EOL apt fix returned %s in %s; stdout=%r stderr=%r",
            ret.returncode,
            factory,
            ret.stdout,
            ret.stderr,
        )
    else:
        log.info("Applied bullseye EOL apt fix to %s", factory)


def _get_test_versions_ids(value):
    return f"SaltMinion~={value}"


@pytest.fixture(
    params=("3002", "3003", "3004"), ids=_get_test_versions_ids, scope="module"
)
def compat_salt_version(request):
    return request.param


@pytest.fixture(scope="module")
def minion_image_name(compat_salt_version):
    return f"salt-{compat_salt_version}"


@pytest.fixture(scope="function")
def minion_id(compat_salt_version):
    return random_string(
        f"salt-{compat_salt_version}-",
        uppercase=False,
    )


@pytest.fixture(scope="function")
def artifacts_path(minion_id, tmp_path):
    yield tmp_path / minion_id


# Note: a module-level `pytestmark` above already applies
# skip_if_binaries_missing("docker"). pytest >= 9 turns
# PytestRemovedIn9Warning "Marks applied to fixtures have no effect" into a
# collection error, so the redundant fixture-level mark is removed.
@pytest.fixture(scope="function")
def salt_minion(
    minion_id,
    salt_master,
    docker_client,
    artifacts_path,
    compat_salt_version,
    host_docker_network_ip_address,
):
    config_overrides = {
        "master": salt_master.config["interface"],
        "user": False,
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
        # We also want to scrutinize the key acceptance
        "open_mode": False,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        # SaltMinion kwargs
        name=minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(
            compat_salt_version
        ),
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "volumes": {
                str(artifacts_path): {
                    "bind": "/artifacts",
                    "mode": "z",
                },
            }
        },
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    # See _apply_bullseye_eol_apt_fix docstring above: patch the container's
    # apt sources in-place before any state.highstate / pkg.installed runs.
    factory.after_start(_apply_bullseye_eol_apt_fix, factory)
    with factory.started():
        yield factory


@pytest.fixture(scope="function")
def package_name():
    return "figlet"


@pytest.fixture
def populated_state_tree(minion_id, package_name, state_tree):
    module_contents = """
    def get_test_package_name():
        return "{}"
    """.format(
        package_name
    )
    top_file_contents = """
    base:
        {}:
          - install-package
    """.format(
        minion_id
    )
    install_package_sls_contents = """
    state-entry-contém-unicode:
        pkg.installed:
          - name: {{ salt.pkgnames.get_test_package_name() }}
    """
    with pytest.helpers.temp_file(
        "_modules/pkgnames.py",
        module_contents,
        state_tree,
    ), pytest.helpers.temp_file(
        "top.sls", top_file_contents, state_tree
    ), pytest.helpers.temp_file(
        "install-package.sls",
        install_package_sls_contents,
        state_tree,
    ):
        # Run the test
        yield


@pytest.mark.skip_on_fips_enabled_platform
def test_ping(salt_cli, salt_minion):
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0, ret
    assert ret.data is True


@pytest.mark.skip_on_fips_enabled_platform
@pytest.mark.usefixtures("populated_state_tree")
def test_highstate(salt_cli, salt_minion, package_name):
    """
    Assert a state.highstate with a newer master runs properly on older minions.
    """
    ret = salt_cli.run("state.highstate", minion_tgt=salt_minion.id, _timeout=300)
    assert ret.returncode == 0, ret
    assert ret.data is not None
    assert isinstance(ret.data, dict), ret.data
    state_return = next(iter(ret.data.values()))
    assert package_name in state_return["changes"], state_return


# pytest >= 9 errors on marks applied to fixtures (see comment above).
# The test_cp() consumer below carries the same mark, so the fixture-level
# mark is redundant and removed here.
@pytest.fixture
def cp_file_source():
    source = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "cheese"
    contents = source.read_text().replace("ee", "æ")
    with pytest.helpers.temp_file(contents=contents) as temp_file:
        yield pathlib.Path(temp_file)


@pytest.mark.skip_on_fips_enabled_platform
def test_cp(salt_cp_cli, salt_minion, artifacts_path, cp_file_source):
    """
    Assert proper behaviour for salt-cp with a newer master and older minions.
    """
    remote_path = "/artifacts/cheese"
    ret = salt_cp_cli.run(
        str(cp_file_source), remote_path, minion_tgt=salt_minion.id, _timeout=300
    )
    assert ret.returncode == 0, ret
    assert ret.data is not None
    assert isinstance(ret.data, dict), ret.data
    assert ret.data == {remote_path: True}
    cp_file_dest = artifacts_path / "cheese"
    assert cp_file_source.read_text() == cp_file_dest.read_text()
