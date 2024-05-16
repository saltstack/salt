import json
import shutil
from pathlib import Path

import pytest

from tests.support.helpers import SaltVirtualEnv
from tests.support.pytest.helpers import FakeSaltExtension


@pytest.fixture(scope="module")
def salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory, name="salt-ext-ssh-test"
    ) as extension:
        yield extension


@pytest.fixture(scope="module")
def other_salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory,
        name="salt-ext2-ssh-test",
        virtualname="barbaz",
    ) as extension:
        yield extension


@pytest.fixture(scope="module")
def venv(tmp_path_factory, salt_extension, other_salt_extension):
    venv_dir = tmp_path_factory.mktemp("saltext-ssh-test-venv")
    try:
        with SaltVirtualEnv(venv_dir=venv_dir) as _venv:
            _venv.install(str(salt_extension.srcdir))
            _venv.install(str(other_salt_extension.srcdir))
            installed_packages = _venv.get_installed_packages()
            assert salt_extension.name in installed_packages
            assert other_salt_extension.name in installed_packages
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
        {"thin_saltext_allowlist": ["salt-ext-ssh-test"]},
        {"thin_saltext_blocklist": ["salt-ext2-ssh-test"]},
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


@pytest.mark.usefixtures("saltext_conf")
@pytest.mark.parametrize(
    "saltext_conf", ({"thin_exclude_saltexts": True},), indirect=True
)
def test_saltexts_can_be_excluded(venv, args):
    for ext in ("foobar", "barbaz"):
        ext_args = args + [f"{ext}.echo1", "foo"]
        res = venv.run(*ext_args, check=False)
        assert res.returncode > 0
        assert f"'{ext}.echo1' is not available" in res.stdout
