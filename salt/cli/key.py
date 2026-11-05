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

        with salt.key.KeyCLI(self.config) as key:
            # ``client_config()`` sets ``client_auth=True`` when the CLI is
            # pointed at ``/etc/salt/client`` (remote operator), False when
            # it falls back to the master config (local use on the master
            # host). No separate CLI flag; config file is the source of truth.
            if self.config.get("client_auth") or check_user(self.config["user"]):
                key.run()
