import salt.utils.parsers
from salt.exceptions import SaltInvocationError
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
        if self.options.delete_all:
            if self.args:
                raise SaltInvocationError(
                    "Delete all takes no arguments. Use -d to delete specified keys"
                )

        key = salt.key.KeyCLI(self.config)
        if check_user(self.config["user"]):
            key.run()
