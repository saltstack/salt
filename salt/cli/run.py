import salt.defaults.exitcodes
import salt.utils.parsers
import salt.utils.profile
from salt.exceptions import SaltClientError
from salt.utils.verify import check_user


class SaltRun(salt.utils.parsers.SaltRunOptionParser):
    """
    Used to execute Salt runners
    """

    def run(self):
        """
        Execute salt-run
        """
        import salt.runner

        self.parse_args()

        profiling_enabled = self.options.profiling_enabled

        # ``client_config()`` sets ``opts["__role"] = "client"`` when the CLI
        # is pointed at ``/etc/salt/client``.  Pick the remote-only sibling
        # class in that case so the master-local path stays untouched.
        if self.config.get("__role") == "client":
            runner_cls = salt.runner.RemoteRunner
        else:
            runner_cls = salt.runner.Runner

        with runner_cls(self.config) as runner:
            if self.options.doc:
                runner.print_docs()
                self.exit(salt.defaults.exitcodes.EX_OK)

            # Run this here so SystemExit isn't raised anywhere else when
            # someone tries to use the runners via the python API
            try:
                # ``client_config()`` sets ``client_auth=True`` when the CLI is
                # pointed at ``/etc/salt/client`` (remote operator), False when
                # it falls back to the master config (local use on the master
                # host). Skip the local-user check in client mode.
                if self.config.get("client_auth") or check_user(self.config["user"]):
                    pr = salt.utils.profile.activate_profile(profiling_enabled)
                    try:
                        ret = runner.run(full_return=True)
                        # In older versions ret['data']['retcode'] was used
                        # for signaling the return code. This has been
                        # changed for the orchestrate runner, but external
                        # runners might still use it. For this reason, we
                        # also check ret['data']['retcode'] if
                        # ret['retcode'] is not available.
                        if (
                            isinstance(ret, dict)
                            and "return" in ret
                            and "retcode" not in ret
                        ):
                            ret = ret["return"]
                        if isinstance(ret, dict) and "retcode" in ret:
                            self.exit(ret["retcode"])
                        elif isinstance(ret, dict) and "retcode" in ret.get("data", {}):
                            self.exit(ret["data"]["retcode"])
                    finally:
                        salt.utils.profile.output_profile(
                            pr, stats_path=self.options.profiling_path, stop=True
                        )

            except SaltClientError as exc:
                raise SystemExit(str(exc))
