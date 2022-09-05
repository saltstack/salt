"""
Test for ssh_pre_flight roster option
"""

import os

import pytest

import salt.utils.files
from tests.support.case import SSHCase
from tests.support.runtests import RUNTIME_VARS


class SSHPreFlightTest(SSHCase):
    """
    Test ssh_pre_flight roster option
    """

    def setUp(self):
        super().setUp()
        self.roster = os.path.join(RUNTIME_VARS.TMP, "pre_flight_roster")
        self.data = {
            "ssh_pre_flight": os.path.join(RUNTIME_VARS.TMP, "ssh_pre_flight.sh")
        }
        self.test_script = os.path.join(
            RUNTIME_VARS.TMP, "test-pre-flight-script-worked.txt"
        )

    def _create_roster(self, pre_flight_script_args=None):
        data = dict(self.data)
        if pre_flight_script_args:
            data["ssh_pre_flight_args"] = pre_flight_script_args

        self.custom_roster(self.roster, data)

        with salt.utils.files.fopen(data["ssh_pre_flight"], "w") as fp_:
            fp_.write("touch {}".format(self.test_script))

    @pytest.mark.slow_test
    def test_ssh_pre_flight(self):
        """
        test ssh when ssh_pre_flight is set
        ensure the script runs successfully
        """
        self._create_roster()
        assert self.run_function("test.ping", roster_file=self.roster)

        assert os.path.exists(self.test_script)

    @pytest.mark.slow_test
    def test_ssh_run_pre_flight(self):
        """
        test ssh when --pre-flight is passed to salt-ssh
        to ensure the script runs successfully
        """
        self._create_roster()
        # make sure we previously ran a command so the thin dir exists
        self.run_function("test.ping", wipe=False)
        assert not os.path.exists(self.test_script)

        assert self.run_function(
            "test.ping", ssh_opts="--pre-flight", roster_file=self.roster, wipe=False
        )
        assert os.path.exists(self.test_script)

    @pytest.mark.slow_test
    def test_ssh_run_pre_flight_args(self):
        """
        test ssh when --pre-flight is passed to salt-ssh
        to ensure the script runs successfully passing some args
        """
        self._create_roster(pre_flight_script_args="foobar test")
        # make sure we previously ran a command so the thin dir exists
        self.run_function("test.ping", wipe=False)
        assert not os.path.exists(self.test_script)

        assert self.run_function(
            "test.ping", ssh_opts="--pre-flight", roster_file=self.roster, wipe=False
        )
        assert os.path.exists(self.test_script)

    @pytest.mark.slow_test
    def test_ssh_run_pre_flight_args_prevent_injection(self):
        """
        test ssh when --pre-flight is passed to salt-ssh
        and evil arguments are used in order to produce shell injection
        """
        injected_file = os.path.join(RUNTIME_VARS.TMP, "injection")
        self._create_roster(
            pre_flight_script_args="foobar; echo injected > {}".format(injected_file)
        )
        # make sure we previously ran a command so the thin dir exists
        self.run_function("test.ping", wipe=False)
        assert not os.path.exists(self.test_script)
        assert not os.path.isfile(injected_file)

        assert self.run_function(
            "test.ping", ssh_opts="--pre-flight", roster_file=self.roster, wipe=False
        )

        assert not os.path.isfile(
            injected_file
        ), "File injection suceeded. This shouldn't happend"

    @pytest.mark.slow_test
    def test_ssh_run_pre_flight_failure(self):
        """
        test ssh_pre_flight when there is a failure
        in the script.
        """
        self._create_roster()
        with salt.utils.files.fopen(self.data["ssh_pre_flight"], "w") as fp_:
            fp_.write("exit 2")

        ret = self.run_function(
            "test.ping", ssh_opts="--pre-flight", roster_file=self.roster, wipe=False
        )
        assert ret["retcode"] == 2

    def tearDown(self):
        """
        make sure to clean up any old ssh directories
        """
        files = [
            self.roster,
            self.data["ssh_pre_flight"],
            self.test_script,
            os.path.join(RUNTIME_VARS.TMP, "injection"),
        ]
        for fp_ in files:
            if os.path.exists(fp_):
                os.remove(fp_)
