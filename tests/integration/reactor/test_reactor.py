"""

    integration.reactor.reactor
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's reactor system
"""


import logging
import signal

import pytest
import salt.utils.event
import salt.utils.reactor
from tests.support.case import ShellCase
from tests.support.mixins import SaltMinionEventAssertsMixin
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


class TimeoutException(Exception):
    pass


@pytest.mark.windows_whitelisted
class ReactorTest(SaltMinionEventAssertsMixin, ShellCase):
    """
    Test Salt's reactor system
    """

    def setUp(self):
        self.timeout = 30

    def get_event(self, class_type="master"):
        return salt.utils.event.get_event(
            class_type,
            sock_dir=self.master_opts["sock_dir"],
            transport=self.master_opts["transport"],
            keep_loop=True,
            opts=self.master_opts,
        )

    def fire_event(self, tag, data):
        event = self.get_event()
        event.fire_event(tag, data)

    def alarm_handler(self, signal, frame):
        raise TimeoutException("Timeout of {} seconds reached".format(self.timeout))

    def test_ping_reaction(self):
        """
        Fire an event on the master and ensure
        that it pings the minion
        """
        # Create event bus connection
        e = salt.utils.event.get_event(
            "minion", sock_dir=self.minion_opts["sock_dir"], opts=self.minion_opts
        )

        e.fire_event({"a": "b"}, "/test_event")

        self.assertMinionEventReceived({"a": "b"}, timeout=30)

    @skipIf(salt.utils.platform.is_windows(), "no sigalarm on windows")
    def test_reactor_reaction(self):
        """
        Fire an event on the master and ensure
        The reactor event responds
        """
        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        master_event = self.get_event()
        master_event.fire_event({"id": "minion"}, "salt/test/reactor")

        try:
            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get("tag") == "test_reaction":
                    self.assertTrue(event["data"]["test_reaction"])
                    break
        finally:
            signal.alarm(0)

    @skipIf(salt.utils.platform.is_windows(), "no sigalarm on windows")
    def test_reactor_is_leader(self):
        """
        If reactor system is unavailable, an exception is thrown.
        When leader is true (the default), the reacion event should return.
        When leader is set to false reactor should timeout/not do anything.
        """
        ret = self.run_run_plus("reactor.is_leader")
        self.assertIn("CommandExecutionError", ret["return"])

        self.run_run_plus("reactor.set_leader", False)
        self.assertIn("CommandExecutionError", ret["return"])

        ret = self.run_run_plus("reactor.is_leader")
        self.assertIn("CommandExecutionError", ret["return"])

        # by default reactor should be leader
        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        # make reactor not the leader
        # ensure reactor engine is available
        opts_overrides = {
            "engines": [
                {
                    "reactor": {
                        "refresh_interval": 60,
                        "worker_threads": 10,
                        "worker_hwm": 10000,
                    }
                }
            ]
        }
        self.run_run_plus("reactor.set_leader", False, opts_overrides=opts_overrides)
        ret = self.run_run_plus("reactor.is_leader", opts_overrides=opts_overrides)
        self.assertFalse(ret["return"])

        try:
            master_event = self.get_event()
            self.fire_event({"id": "minion"}, "salt/test/reactor")

            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get("tag") == "test_reaction":
                    # if we reach this point, the test is a failure
                    self.assertTrue(True)  # pylint: disable=redundant-unittest-assert
                    break
        except TimeoutException as exc:
            self.assertTrue("Timeout" in str(exc))
        finally:
            signal.alarm(0)

        # make reactor the leader again
        # ensure reactor engine is available
        opts_overrides = {
            "engines": [
                {
                    "reactor": {
                        "refresh_interval": 60,
                        "worker_threads": 10,
                        "worker_hwm": 10000,
                    }
                }
            ]
        }
        self.run_run_plus("reactor.set_leader", True, opts_overrides=opts_overrides)
        ret = self.run_run_plus("reactor.is_leader", opts_overrides=opts_overrides)
        self.assertTrue(ret["return"])

        # trigger a reaction
        signal.alarm(self.timeout)

        try:
            master_event = self.get_event()
            self.fire_event({"id": "minion"}, "salt/test/reactor")

            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get("tag") == "test_reaction":
                    self.assertTrue(event["data"]["test_reaction"])
                    break
        finally:
            signal.alarm(0)
