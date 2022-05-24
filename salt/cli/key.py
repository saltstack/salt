import salt.utils.parsers
from salt.utils.verify import check_user


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

        key = salt.key.KeyCLI(self.config)
        if check_user(self.config["user"]):
            key.run()
