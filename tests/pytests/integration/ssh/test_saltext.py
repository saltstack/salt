import pytest

from tests.support.helpers import SaltVirtualEnv
from tests.support.pytest.helpers import FakeSaltExtension


@pytest.fixture(scope="module")
def salt_extension(tmp_path_factory):
    with FakeSaltExtension(
        tmp_path_factory=tmp_path_factory, name="salt-ext-ssh-test"
    ) as extension:
        yield extension


@pytest.fixture
def venv(tmp_path):
    with SaltVirtualEnv(venv_dir=tmp_path / ".venv") as _venv:
        yield _venv


def test_saltext_is_available_on_target(
    venv, salt_extension, salt_ssh_roster_file, sshd_config_dir, salt_master
):
    venv.install(str(salt_extension.srcdir))
    installed_packages = venv.get_installed_packages()
    assert salt_extension.name in installed_packages
    args = [
        venv.venv_bin_dir / "salt-ssh",
        "--thin-include-saltexts",
        f"--config-dir={salt_master.config_dir}",
        f"--roster-file={salt_ssh_roster_file}",
        f"--priv={sshd_config_dir / 'client_key'}",
        "localhost",
        "foobar.echo1",
        "foo",
    ]
    res = venv.run(*args, check=True)
    assert res.stdout == "localhost:\n    foo\n"
