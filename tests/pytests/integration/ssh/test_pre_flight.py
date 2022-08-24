"""
Test for ssh_pre_flight roster option
"""
import logging

import attr
import pytest

import salt.utils.files
import salt.utils.yaml

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@attr.s
class Roster:
    tmp_path = attr.ib(repr=False)
    salt_ssh_roster_file = attr.ib()
    path = attr.ib(init=False)
    touch_file_path = attr.ib(init=False)
    ssh_pre_flight = attr.ib(init=False)
    ssh_pre_flight_args = attr.ib(default=None)

    @path.default
    def _default_path(self):
        return self.tmp_path / "pre-flight-roster"

    @touch_file_path.default
    def _default_touch_file_path(self):
        return self.tmp_path / "pre-flight-script-worked.txt"

    @ssh_pre_flight.default
    def _default_ssh_pre_flight(self):
        script = self.tmp_path / "pre-flight-script.sh"
        script.write_text("touch {}\n".format(self.touch_file_path))
        return script

    def __call__(self, ssh_pre_flight_args=None):
        self.ssh_pre_flight_args = ssh_pre_flight_args
        return self

    def __enter__(self):
        with salt.utils.files.fopen(self.salt_ssh_roster_file) as rfh:
            roster_data = salt.utils.yaml.safe_load(rfh)

        update_kwargs = {
            "ssh_pre_flight": str(self.ssh_pre_flight),
        }
        if self.ssh_pre_flight_args:
            update_kwargs["ssh_pre_flight_args"] = self.ssh_pre_flight_args

        roster_data["localhost"].update(update_kwargs)
        with salt.utils.files.fopen(str(self.path), "w") as wfh:
            salt.utils.yaml.safe_dump(roster_data, wfh)
        log.debug("Wrote %s:\n%s", self.path, self.path.read_text())

    def __exit__(self, *_):
        pass


@pytest.fixture
def pre_fligh_inject_file(tmp_path):
    return tmp_path / "pre-flight-script-worked.txt"


@pytest.fixture
def roster(tmp_path, salt_ssh_roster_file):
    return Roster(tmp_path=tmp_path, salt_ssh_roster_file=salt_ssh_roster_file)


@pytest.fixture
def salt_ssh_cli(salt_master, roster, sshd_config_dir):
    """
    The ``salt-ssh`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=str(roster.path),
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
        base_script_args=["--ignore-host-keys"],
    )


def test_ssh_pre_flight(salt_ssh_cli, roster):
    """
    test ssh when ssh_pre_flight is set
    ensure the script runs successfully
    """
    with roster:
        ret = salt_ssh_cli.run("test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert not roster.touch_file_path.exists()


def test_ssh_run_pre_flight(salt_ssh_cli, roster):
    """
    test ssh when --pre-flight is passed to salt-ssh
    to ensure the script runs successfully
    """
    with roster:
        # make sure we previously ran a command so the thin dir exists
        ret = salt_ssh_cli.run("test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert not roster.touch_file_path.exists()
        ret = salt_ssh_cli.run("--pre-flight", "test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert roster.touch_file_path.exists()


def test_ssh_run_pre_flight_args(salt_ssh_cli, roster):
    """
    test ssh when --pre-flight is passed to salt-ssh
    to ensure the script runs successfully passing some args
    """
    with roster(ssh_pre_flight_args="foobar test"):
        # make sure we previously ran a command so the thin dir exists
        ret = salt_ssh_cli.run("test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert not roster.touch_file_path.exists()
        ret = salt_ssh_cli.run("--pre-flight", "test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert roster.touch_file_path.exists()


def test_ssh_run_pre_flight_args_prevent_injection(salt_ssh_cli, roster, tmp_path):
    """
    test ssh when --pre-flight is passed to salt-ssh
    and evil arguments are used in order to produce shell injection
    """
    inject_file_path = tmp_path / "shell-injection"
    with roster(
        ssh_pre_flight_args="foobar; echo injected > {}".format(inject_file_path)
    ):
        # make sure we previously ran a command so the thin dir exists
        ret = salt_ssh_cli.run("test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert not roster.touch_file_path.exists()
        assert not inject_file_path.exists()
        ret = salt_ssh_cli.run("--pre-flight", "test.ping", _timeout=30)
        assert ret.returncode == 0
        assert ret.data is True
        assert roster.touch_file_path.exists()
        assert not inject_file_path.exists()


def test_ssh_run_pre_flight_failure(salt_ssh_cli, roster):
    """
    test ssh_pre_flight when there is a failure
    in the script.
    """
    with roster:
        roster.ssh_pre_flight.write_text("exit 2\n")
        ret = salt_ssh_cli.run("--pre-flight", "test.ping", _timeout=30)
        assert ret.returncode != 0
        assert ret.data["retcode"] == 2
        assert not roster.touch_file_path.exists()
