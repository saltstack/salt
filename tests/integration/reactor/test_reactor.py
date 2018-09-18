# -*- coding: utf-8 -*-
"""

    integration.reactor.reactor
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's reactor system
"""

from __future__ import absolute_import

import signal

import pytest

# Import Salt libs
import salt.utils.event
import salt.utils.reactor

# Import Salt testing libs
from tests.support.case import ShellTestCase
from tests.support.mixins import SaltMinionEventAssertsMixin
from tests.support.unit import skipIf


class TimeoutException(Exception):
    pass


@pytest.mark.windows_whitelisted
class ReactorTest(ShellTestCase, SaltMinionEventAssertsMixin):
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
        raise TimeoutException("Timeout of {0} seconds reached".format(self.timeout))

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
        when leader is set to false reactor should timeout/not do anything
        """
        # by default reactor should be leader
        ret = self.run_run_plus("reactor.is_leader")
        self.assertTrue(ret["return"])

        # make reactor not leader
        self.run_run_plus("reactor.set_leader", False)
        ret = self.run_run_plus("reactor.is_leader")
        self.assertFalse(ret["return"])

        signal.signal(signal.SIGALRM, self.alarm_handler)
        signal.alarm(self.timeout)

        try:
            master_event = self.get_event()
            self.fire_event({"id": "minion"}, "salt/test/reactor")

            while True:
                event = master_event.get_event(full=True)

                if event is None:
                    continue

                if event.get("tag") == "test_reaction":
                    # if we reach this point, the test is a failure
                    self.assertTrue(False)  # pylint: disable=redundant-unittest-assert
                    break
        except TimeoutException as exc:
            self.assertTrue("Timeout" in str(exc))
        finally:
            signal.alarm(0)

        # make reactor leader again
        self.run_run_plus("reactor.set_leader", True)
        ret = self.run_run_plus("reactor.is_leader")
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
