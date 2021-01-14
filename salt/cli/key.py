import salt.utils.parsers
from salt.utils.verify import check_user, verify_log


class SaltKey(salt.utils.parsers.SaltKeyOptionParser):
    """
    Initialize the Salt key manager
    """

    def run(self):
        """
        Execute salt-key
        """
        import salt.key

        self.parse_args()

        self.setup_logfile_logger()
        verify_log(self.config)

        key = salt.key.KeyCLI(self.config)
        if check_user(self.config["user"]):
            key.run()
