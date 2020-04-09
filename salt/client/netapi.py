# encoding: utf-8
"""
The main entry point for salt-api
"""
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import signal

# Import salt-api libs
import salt.loader
import salt.utils.process

log = logging.getLogger(__name__)


class RunNetapi(salt.utils.process.SignalHandlingProcess):
    """
    Runner class that's pickable for netapi modules
    """

    def __init__(self, opts, fname, **kwargs):
        super(RunNetapi, self).__init__(**kwargs)
        self.opts = opts
        self.fname = fname

    # __setstate__ and __getstate__ are only used on Windows.
    # We do this so that __init__ will be invoked on Windows in the child
    # process so that a register_after_fork() equivalent will work on Windows.
    def __setstate__(self, state):
        self.__init__(
            state["opts"],
            state["fname"],
            log_queue=state["log_queue"],
            log_queue_level=state["log_queue_level"],
        )

    def __getstate__(self):
        return {
            "opts": self.opts,
            "fname": self.fname,
            "log_queue": self.log_queue,
            "log_queue_level": self.log_queue_level,
        }

    def run(self):
        netapi = salt.loader.netapi(self.opts)
        netapi_func = netapi[self.fname]
        netapi_func()


class NetapiClient(object):
    """
    Start each netapi module that is configured to run
    """

    def __init__(self, opts):
        self.opts = opts
        self.process_manager = salt.utils.process.ProcessManager(
            name="NetAPIProcessManager"
        )
        self.netapi = salt.loader.netapi(self.opts)

    def run(self):
        """
        Load and start all available api modules
        """
        if not self.netapi:
            log.error("Did not find any netapi configurations, nothing to start")

        kwargs = {}
        if salt.utils.platform.is_windows():
            kwargs["log_queue"] = salt.log.setup.get_multiprocessing_logging_queue()
            kwargs[
                "log_queue_level"
            ] = salt.log.setup.get_multiprocessing_logging_level()

        for fun in self.netapi:
            if fun.endswith(".start"):
                log.info("Starting %s netapi module", fun)
                self.process_manager.add_process(
                    RunNetapi, args=(self.opts, fun), kwargs=kwargs, name="RunNetapi"
                )

        # Install the SIGINT/SIGTERM handlers if not done so far
        if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGINT, self._handle_signals)

        if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
            # No custom signal handling was added, install our own
            signal.signal(signal.SIGTERM, self._handle_signals)

        self.process_manager.run()

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate the signals to the process manager
        self.process_manager.stop_restarting()
        self.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.process_manager.kill_children()
