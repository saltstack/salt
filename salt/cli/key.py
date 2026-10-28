import os

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
            # Intelligent auth detection:
            # 1. If client_auth explicitly set, use that
            # 2. If user check passes, allow (traditional local execution)
            # 3. If user check fails but client keys exist, enable client auth automatically
            client_auth_mode = self.config.get("client_auth")

            if client_auth_mode is None:
                # Auto-detect: check if user has permissions first
                if not check_user(self.config["user"]):
                    # User check failed, see if we have client keys
                    import salt.syspaths

                    pki_dir = self.config.get(
                        "pki_dir",
                        os.path.join(salt.syspaths.CONFIG_DIR, "pki", "master"),
                    )
                    client_key = os.path.join(pki_dir, "client.pem")
                    if os.path.exists(client_key):
                        client_auth_mode = True
                else:
                    client_auth_mode = False

            if client_auth_mode or check_user(self.config["user"]):
                key.run()
