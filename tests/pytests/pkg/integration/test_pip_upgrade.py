import logging
import subprocess

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_pip_install(install_salt, salt_call_cli):
    """
    Test pip.install and ensure that a package included in the tiamat build can be upgraded
    """
    ret = subprocess.run(
        install_salt.binary_paths["salt"] + ["--versions-report"],
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )
    assert ret.returncode == 0

    possible_upgrades = [
        "docker-py",
        "msgpack",
        "pycparser",
        "python-gnupg",
        "pyyaml",
        "pyzmq",
        "jinja2",
    ]
    found_new = False
    for dep in possible_upgrades:
        get_latest = salt_call_cli.run("--local", "pip.list_all_versions", dep)
        if not get_latest.data:
            # No information available
            continue
        dep_version = get_latest.data[-1]
        installed_version = None
        for line in ret.stdout.splitlines():
            if dep in line.lower():
                installed_version = line.lower().strip().split(":")[-1].strip()
                break
        else:
            pytest.fail(f"Failed to find {dep} in the versions report output")

        if dep_version == installed_version:
            log.warning("The %s dependency is already latest", dep)
        else:
            found_new = True
            break

    if found_new:
        try:
            install = salt_call_cli.run(
                "--local", "pip.install", f"{dep}=={dep_version}"
            )
            assert install
            log.warning(install)
            # The assert is commented out because pip will actually trigger a failure since
            # we're breaking the dependency tree, but, for the purpose of this test, we can
            # ignore it.
            #
            # assert install.returncode == 0

            ret = subprocess.run(
                install_salt.binary_paths["salt"] + ["--versions-report"],
                capture_output=True,
                text=True,
                check=True,
                shell=False,
            )
            assert ret.returncode == 0
            for line in ret.stdout.splitlines():
                if dep in line.lower():
                    new_version = line.lower().strip().split(":")[-1].strip()
                    if new_version == installed_version:
                        pytest.fail(
                            f"The newly installed version of {dep} does not show in the versions report"
                        )
                    assert new_version == dep_version
                    break
            else:
                pytest.fail(f"Failed to find {dep} in the versions report output")
        finally:
            log.info("Uninstalling %s", dep_version)
            assert salt_call_cli.run(
                "--local", "pip.uninstall", f"{dep}=={dep_version}"
            )
    else:
        pytest.skip("Did not find an upgrade version for any of the dependencies")
