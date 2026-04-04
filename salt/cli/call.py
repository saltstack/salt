import os

import salt.cli.caller
import salt.defaults.exitcodes
import salt.utils.parsers
import salt.utils.verify
from salt.config import _expand_glob_path


class SaltCall(salt.utils.parsers.SaltCallOptionParser):
    """
    Used to locally execute a salt command
    """

    def run(self):
        """
        Execute the salt call!
        """
        self.parse_args()

        if self.options.file_root:
            # check if the argument is pointing to a file on disk
            file_root = os.path.abspath(self.options.file_root)
            self.config["file_roots"] = {"base": _expand_glob_path([file_root])}

        if self.options.pillar_root:
            # check if the argument is pointing to a file on disk
            pillar_root = os.path.abspath(self.options.pillar_root)
            self.config["pillar_roots"] = {"base": _expand_glob_path([pillar_root])}

        if self.options.states_dir:
            # check if the argument is pointing to a file on disk
            states_dir = os.path.abspath(self.options.states_dir)
            self.config["states_dirs"] = [states_dir]

        if self.options.local:
            self.config["file_client"] = "local"
        if self.options.master:
            self.config["master"] = self.options.master

        if self.config["verify_env"]:
            # When --priv is used, MergeConfigMixIn has already overwritten
            # config["user"] with the --priv value during parse_args().  We need
            # the user that is actually *configured* in the config files so that
            # verify_env chowns directories to the right owner (e.g. 'salt') rather
            # than the temporary execution-time override (e.g. 'root').
            if self.options.user:
                import salt.config as _salt_config

                _raw_opts = _salt_config.minion_config(
                    self.get_config_file_path(), cache_minion_id=False
                )
                _verify_user = _raw_opts.get("user", "root")
            else:
                _verify_user = self.config["user"]

            salt.utils.verify.verify_env(
                [
                    self.config["pki_dir"],
                    self.config["cachedir"],
                    self.config["extension_modules"],
                ],
                _verify_user,
                permissive=self.config["permissive_pki_access"],
                pki_dir=self.config["pki_dir"],
            )

        # config["user"] is already set to the --priv value by MergeConfigMixIn.
        # The explicit assignment below is kept for clarity and backward compatibility
        # in case MergeConfigMixIn behaviour ever changes.
        if self.options.user:
            self.config["user"] = self.options.user

        # Validate the execution user exists
        if self.config["user"] != salt.utils.user.get_user():
            if not salt.utils.verify.check_user(self.config["user"]):
                self.exit(salt.defaults.exitcodes.EX_NOUSER)

        caller = salt.cli.caller.Caller.factory(self.config)

        if self.options.doc:
            caller.print_docs()
            self.exit(salt.defaults.exitcodes.EX_OK)

        if self.options.grains_run:
            caller.print_grains()
            self.exit(salt.defaults.exitcodes.EX_OK)

        caller.run()
