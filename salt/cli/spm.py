"""
    salt.cli.spm
    ~~~~~~~~~~~~~

    Salt's spm cli parser.

.. versionadded:: 2015.8.0
"""


import salt.spm
import salt.utils.parsers as parsers
from salt.utils.verify import verify_env


class SPM(parsers.SPMParser):
    """
    The cli parser object used to fire up the salt spm system.
    """

    def run(self):
        """
        Run the api
        """
        ui = salt.spm.SPMCmdlineInterface()
        self.parse_args()
        v_dirs = [
            self.config["spm_cache_dir"],
        ]
        verify_env(
            v_dirs,
            self.config["user"],
            root_dir=self.config["root_dir"],
        )
        client = salt.spm.SPMClient(ui, self.config)
        client.run(self.args)
