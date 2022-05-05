import sys

import salt.client.ssh
import salt.utils.parsers


class SaltSSH(salt.utils.parsers.SaltSSHOptionParser):
    """
    Used to Execute the salt ssh routine
    """

    def run(self):
        if "-H" in sys.argv or "--hosts" in sys.argv:
            sys.argv += ["x", "x"]  # Hack: pass a mandatory two options
            # that won't be used anyways with -H or --hosts
        self.parse_args()

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
