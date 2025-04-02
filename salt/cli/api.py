"""
    salt.cli.api
    ~~~~~~~~~~~~~

    Salt's api cli parser.

"""

import logging

import salt.client.netapi
import salt.utils.files
import salt.utils.parsers as parsers
from salt.utils.verify import check_user

log = logging.getLogger(__name__)


class SaltAPI(parsers.SaltAPIParser):
    """
    The cli parser object used to fire up the salt api system.
    """

    def prepare(self):
        """
        Run the preparation sequence required to start a salt-api daemon.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        """
        super().prepare()
        log.info("Setting up the Salt API")
        self.api = salt.client.netapi.NetapiClient(self.config)
        self.daemonize_if_required()
        self.set_pidfile()

    def start(self):
        """
        Start the actual master.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        """
        super().start()
        if check_user(self.config["user"]):
            log.info("The salt-api is starting up")
            self.api.run()

    def shutdown(self, exitcode=0, exitmsg=None):
        """
        If sub-classed, run any shutdown operations on this method.
        """
        log.info("The salt-api is shutting down..")
        msg = "The salt-api is shutdown. "
        if exitmsg is not None:
            exitmsg = msg + exitmsg
        else:
            exitmsg = msg.strip()
        super().shutdown(exitcode, exitmsg)

    def _handle_signals(self, signum, sigframe):
        # escalate signal to the process manager processes
        self.api.process_manager._handle_signals(signum, sigframe)
        super()._handle_signals(signum, sigframe)
