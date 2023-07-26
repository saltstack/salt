import sys

import salt.client.ssh
import salt.defaults.exitcodes
import salt.utils.parsers
from salt.utils.verify import check_user


class SaltSSH(salt.utils.parsers.SaltSSHOptionParser):
    """
    Used to Execute the salt ssh routine
    """

    def run(self):
        if "-H" in sys.argv or "--hosts" in sys.argv:
            sys.argv += ["x", "x"]  # Hack: pass a mandatory two options
            # that won't be used anyways with -H or --hosts
        self.parse_args()

        if not check_user(self.config["user"]):
            self.exit(
                salt.defaults.exitcodes.EX_NOUSER,
                "Cannot switch to configured user for Salt. Exiting",
            )

        ssh = salt.client.ssh.SSH(self.config)
        try:
            ssh.run()
        finally:
            ssh.fsclient.destroy()
