import json
import shutil
from pathlib import Path

import pytest

from tests.pytests.integration.ssh.test_slsutil import check_system_python_version
from tests.support.helpers import SaltVirtualEnv
from tests.support.pytest.helpers import FakeSaltExtension

pytestmark = [
    pytest.mark.skip_unless_on_linux,
    pytest.mark.skipif(
        not check_system_python_version(), reason="Needs system python >= 3.8"
    ),
]


@pytest.fixture(scope="module")
def salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory, name="salt-ext-ssh-test"
    ) as extension:
        yield extension


@pytest.fixture(scope="module")
def namespaced_salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory,
        name="saltext.ssh-test2",
        virtualname="barbaz",
    ) as extension:
        yield extension


@pytest.fixture(scope="module")
def namespaced_salt_extension_2(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory,
        name="saltext.ssh-test3",
        virtualname="wut",
    ) as extension:
        yield extension


@pytest.fixture(scope="module")
def venv(
    tmp_path_factory,
    salt_extension,
    namespaced_salt_extension,
    namespaced_salt_extension_2,
):
    venv_dir = tmp_path_factory.mktemp("saltext-ssh-test-venv")
    saltexts = (salt_extension, namespaced_salt_extension, namespaced_salt_extension_2)
    try:
        with SaltVirtualEnv(venv_dir=venv_dir) as _venv:
            for saltext in saltexts:
                _venv.install(str(saltext.srcdir))
            installed_packages = _venv.get_installed_packages()
            for saltext in saltexts:
                assert saltext.name in installed_packages
            yield _venv
    finally:
        shutil.rmtree(venv_dir, ignore_errors=True)


@pytest.fixture(params=({},))
def saltext_conf(request, salt_master):
    with pytest.helpers.temp_file(
        "saltext_ssh.conf",
        json.dumps(request.param),
        Path(salt_master.config_dir) / "master.d",
    ):
        yield request.param


@pytest.fixture
def args(venv, salt_master, salt_ssh_roster_file, sshd_config_dir):
    return [
        venv.venv_bin_dir / "salt-ssh",
        f"--config-dir={salt_master.config_dir}",
        f"--roster-file={salt_ssh_roster_file}",
        f"--priv={sshd_config_dir / 'client_key'}",
        "--regen-thin",
        "localhost",
    ]


@pytest.mark.parametrize(
    "saltext_conf",
    (
        {},
        {"thin_saltext_allowlist": ["salt-ext-ssh-test", "saltext.ssh-test3"]},
        {"thin_saltext_blocklist": ["saltext.ssh-test2"]},
    ),
    indirect=True,
)
def test_saltexts_are_available_on_target(venv, args, saltext_conf):
    ext1_args = args + ["foobar.echo1", "foo"]
    res = venv.run(*ext1_args, check=True)
    assert res.stdout == "localhost:\n    foo\n"
    ext2_args = args + ["barbaz.echo1", "bar"]
    res = venv.run(*ext2_args, check=False)
    if (
        "thin_saltext_allowlist" not in saltext_conf
        and "thin_saltext_blocklist" not in saltext_conf
    ):
        assert res.returncode == 0
        assert res.stdout == "localhost:\n    bar\n"
    else:
        assert res.returncode > 0
        assert "'barbaz.echo1' is not available" in res.stdout
    ext3_args = args + ["wut.echo1", "wat"]
    res = venv.run(*ext3_args, check=True)
    assert res.stdout == "localhost:\n    wat\n"


@pytest.mark.usefixtures("saltext_conf")
@pytest.mark.parametrize(
    "saltext_conf", ({"thin_exclude_saltexts": True},), indirect=True
)
def test_saltexts_can_be_excluded(venv, args):
    for ext in ("foobar", "barbaz", "wut"):
        ext_args = args + [f"{ext}.echo1", "foo"]
        res = venv.run(*ext_args, check=False)
        assert res.returncode > 0
        assert f"'{ext}.echo1' is not available" in res.stdout
