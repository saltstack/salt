# isort:skip_file

import os
import sys

sys.modules["pkg_resources"] = None

import salt.defaults.exitcodes
import salt.utils.parsers
import salt.utils.stringutils
from salt.exceptions import (
    AuthenticationError,
    AuthorizationError,
    EauthAuthenticationError,
    LoaderError,
    SaltClientError,
    SaltInvocationError,
    SaltSystemExit,
)
from salt.utils.args import yamlify_arg


class SaltCMD(salt.utils.parsers.SaltCMDOptionParser):
    """
    The execution of a salt command happens here
    """

    def run(self):
        """
        Execute the salt command line
        """
        import salt.client

        self.parse_args()

        try:
            # We don't need to bail on config file permission errors
            # if the CLI process is run with the -a flag
            skip_perm_errors = self.options.eauth != ""

            self.local_client = salt.client.get_local_client(
                self.get_config_file_path(),
                skip_perm_errors=skip_perm_errors,
                auto_reconnect=True,
            )
        except SaltClientError as exc:
            self.exit(2, f"{exc}\n")
            return

        if self.options.batch or self.options.static:
            # _run_batch() will handle all output and
            # exit with the appropriate error condition
            # Execution will not continue past this point
            # in batch mode.
            self._run_batch()
            return

        if self.options.preview_target:
            minion_list = self._preview_target()
            self._output_ret(minion_list, self.config.get("output", "nested"))
            return

        if self.options.timeout <= 0:
            self.options.timeout = self.local_client.opts["timeout"]

        kwargs = {
            "tgt": self.config["tgt"],
            "fun": self.config["fun"],
            "arg": self.config["arg"],
            "timeout": self.options.timeout,
            "show_timeout": self.options.show_timeout,
            "show_jid": self.options.show_jid,
        }

        if "token" in self.config:
            import salt.utils.files

            try:
                with salt.utils.files.fopen(
                    os.path.join(self.config["cachedir"], ".root_key"), "r"
                ) as fp_:
                    kwargs["key"] = fp_.readline()
            except OSError:
                kwargs["token"] = self.config["token"]

        kwargs["delimiter"] = self.options.delimiter

        if self.selected_target_option:
            kwargs["tgt_type"] = self.selected_target_option
        else:
            kwargs["tgt_type"] = "glob"

        # If batch_safe_limit is set, check minions matching target and
        # potentially switch to batch execution
        if self.options.batch_safe_limit > 1:
            if len(self._preview_target()) >= self.options.batch_safe_limit:
                salt.utils.stringutils.print_cli(
                    "\nNOTICE: Too many minions targeted, switching to batch execution."
                )
                self.options.batch = self.options.batch_safe_size
                try:
                    self._run_batch()
                finally:
                    self.local_client.destroy()
                return

        if getattr(self.options, "return"):
            kwargs["ret"] = getattr(self.options, "return")

        if getattr(self.options, "return_config"):
            kwargs["ret_config"] = getattr(self.options, "return_config")

        if getattr(self.options, "return_kwargs"):
            kwargs["ret_kwargs"] = yamlify_arg(getattr(self.options, "return_kwargs"))

        if getattr(self.options, "module_executors"):
            kwargs["module_executors"] = yamlify_arg(
                getattr(self.options, "module_executors")
            )

        if getattr(self.options, "executor_opts"):
            kwargs["executor_opts"] = yamlify_arg(
                getattr(self.options, "executor_opts")
            )

        if getattr(self.options, "metadata"):
            kwargs["metadata"] = yamlify_arg(getattr(self.options, "metadata"))

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if "token" not in kwargs and "key" not in kwargs and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth

            resolver = salt.auth.Resolver(self.config)
            res = resolver.cli(self.options.eauth)
            if self.options.mktoken and res:
                tok = resolver.token_cli(self.options.eauth, res)
                if tok:
                    kwargs["token"] = tok.get("token", "")
            if not res:
                sys.stderr.write("ERROR: Authentication failed\n")
                sys.exit(2)
            kwargs.update(res)
            kwargs["eauth"] = self.options.eauth

        if self.config["async"]:
            jid = self.local_client.cmd_async(**kwargs)
            salt.utils.stringutils.print_cli(f"Executed command with job ID: {jid}")
            return

        # local will be None when there was an error
        if not self.local_client:
            return

        retcodes = []
        errors = []

        try:
            if self.options.subset:
                cmd_func = self.local_client.cmd_subset
                kwargs["subset"] = self.options.subset
                kwargs["cli"] = True
            else:
                cmd_func = self.local_client.cmd_cli

            if self.options.progress:
                kwargs["progress"] = True
                self.config["progress"] = True
                ret = {}
                for progress in cmd_func(**kwargs):
                    out = "progress"
                    try:
                        self._progress_ret(progress, out)
                    except LoaderError as exc:
                        raise SaltSystemExit(exc)
                    if "return_count" not in progress:
                        ret.update(progress)
                self._progress_end(out)
                self._print_returns_summary(ret)
            elif self.config["fun"] == "sys.doc":
                ret = {}
                out = ""
                for full_ret in self.local_client.cmd_cli(**kwargs):
                    ret_, out, retcode = self._format_ret(full_ret)
                    ret.update(ret_)
                self._output_ret(ret, out, retcode=retcode)
            else:
                if self.options.verbose:
                    kwargs["verbose"] = True
                ret = {}
                for full_ret in cmd_func(**kwargs):
                    try:
                        ret_, out, retcode = self._format_ret(full_ret)
                        retcodes.append(retcode)
                        self._output_ret(ret_, out, retcode=retcode)
                        ret.update(full_ret)
                    except KeyError:
                        errors.append(full_ret)

            # Returns summary
            if self.config["cli_summary"] is True:
                if self.config["fun"] != "sys.doc":
                    if self.options.output is None:
                        self._print_returns_summary(ret)
                        self._print_errors_summary(errors)

            # NOTE: Return code is set here based on if all minions
            # returned 'ok' with a retcode of 0.
            # This is the final point before the 'salt' cmd returns,
            # which is why we set the retcode here.
            if not all(
                exit_code == salt.defaults.exitcodes.EX_OK for exit_code in retcodes
            ):
                sys.stderr.write("ERROR: Minions returned with non-zero exit code\n")
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)

        except (
            AuthenticationError,
            AuthorizationError,
            SaltInvocationError,
            EauthAuthenticationError,
            SaltClientError,
        ) as exc:
            self._output_ret(str(exc), "", retcode=1)
        finally:
            self.local_client.destroy()

    def _preview_target(self):
        """
        Return a list of minions from a given target
        """
        return self.local_client.gather_minions(
            self.config["tgt"], self.selected_target_option or "glob"
        )

    def _run_batch(self):
        import salt.cli.batch

        eauth = {}
        if "token" in self.config:
            eauth["token"] = self.config["token"]

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if "token" not in eauth and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth

            resolver = salt.auth.Resolver(self.config)
            res = resolver.cli(self.options.eauth)
            if self.options.mktoken and res:
                tok = resolver.token_cli(self.options.eauth, res)
                if tok:
                    eauth["token"] = tok.get("token", "")
            if not res:
                sys.stderr.write("ERROR: Authentication failed\n")
                sys.exit(2)
            eauth.update(res)
            eauth["eauth"] = self.options.eauth

        # When --async and --batch are both set, hand off to the
        # master-side BatchManager: publish the first sub-batch under
        # a shared JID, persist BatchState, and exit.  The CLI does
        # not wait for returns.
        if self.config.get("async") and self.options.batch:
            self._run_batch_async(eauth)
            return

        if self.options.static:

            if not self.options.batch:
                self.config["batch"] = "100%"

            try:
                batch = salt.cli.batch.Batch(self.config, eauth=eauth, quiet=True)
            except SaltClientError:
                sys.exit(2)

            ret = {}

            for res, _ in batch.run():
                ret.update(res)

            self._output_ret(ret, "")

        else:
            try:
                self.config["batch"] = self.options.batch
                batch = salt.cli.batch.Batch(
                    self.config, eauth=eauth, _parser=self.options
                )
            except SaltClientError:
                # We will print errors to the console further down the stack
                sys.exit(1)
            # Printing the output is already taken care of in run() itself
            retcode = 0
            for res, job_retcode in batch.run():
                if job_retcode > retcode:
                    # Exit with the highest retcode we find
                    retcode = job_retcode
            sys.exit(retcode)

    def _run_batch_async(self, eauth):
        """
        Hand off an async batch to the master-side BatchManager.

        Resolves the target (sync gather_minions via
        :class:`salt.cli.batch.Batch`), generates a single JID,
        publishes the first sub-batch under that JID via the CLI's
        ``LocalClient`` (so eauth runs the normal auth pipeline
        exactly once), writes ``.batch.p``, registers the JID in the
        active index, fires ``salt/batch/<jid>/new`` so BatchManager
        adopts it, prints the JID, and exits.

        Subsequent sub-batch publishes are issued by the BatchManager
        using ``state["user"]`` captured here so publisher-ACL and
        audit still attribute every sub-batch publish to the original
        operator.
        """
        import time

        import salt.cli.batch
        import salt.utils.batch_output
        import salt.utils.batch_state
        import salt.utils.event
        import salt.utils.jid
        import salt.utils.user

        batch_jid = salt.utils.jid.gen_jid(self.config)

        try:
            helper = salt.cli.batch.Batch(self.config, eauth=eauth, quiet=True)
        except SaltClientError:
            sys.exit(2)
        try:
            minions, _ping_gen, down_minions = helper.gather_minions()
        finally:
            try:
                helper.local.destroy()
            except Exception:  # pylint: disable=broad-except
                pass

        if not minions:
            salt.utils.stringutils.print_cli("No minions matched the target.")
            sys.exit(0)

        for m in sorted(down_minions or ()):
            salt.utils.stringutils.print_cli(
                f"Minion {m} did not respond. No job will be sent."
            )

        opts_for_state = dict(self.config)
        opts_for_state["batch"] = self.options.batch
        opts_for_state["user"] = (
            eauth.get("username") if eauth else salt.utils.user.get_user()
        )
        state = salt.utils.batch_state.create_batch_state(
            opts_for_state, minions, batch_jid, driver="master"
        )

        batch_size = state["batch_size"]
        initial = state["pending"][:batch_size]
        state["pending"] = state["pending"][batch_size:]

        pub_kwargs = dict(eauth or {})
        try:
            self.local_client.run_job(
                tgt=list(initial),
                fun=self.config["fun"],
                arg=list(self.config.get("arg") or []),
                tgt_type="list",
                ret=self.config.get("ret", "") or "",
                timeout=self.config.get("timeout", 60),
                jid=batch_jid,
                listen=False,
                **pub_kwargs,
            )
        except (
            AuthenticationError,
            AuthorizationError,
            EauthAuthenticationError,
            SaltClientError,
            SaltInvocationError,
        ) as exc:
            sys.stderr.write(f"ERROR: {exc}\n")
            sys.exit(2)

        now = time.time()
        for m in initial:
            state["active"][m] = now
        state["last_progress"] = now

        salt.utils.batch_state.write_batch_state(batch_jid, state, self.config)
        salt.utils.batch_state.add_to_active_index(batch_jid, self.config)

        try:
            with salt.utils.event.get_master_event(
                self.config, self.config["sock_dir"], listen=False
            ) as event:
                event.fire_event(
                    salt.utils.batch_output.new_payload(state),
                    salt.utils.batch_output.tag_new(batch_jid),
                )
        except Exception:  # pylint: disable=broad-except
            # Non-fatal — BatchManager's _tick() reconciliation will
            # pick this batch up from the active index within one
            # loop interval.  Log the failure so operators see it.
            import logging

            logging.getLogger(__name__).exception(
                "Failed to fire salt/batch/%s/new; BatchManager will adopt "
                "via active-index reconciliation on its next tick",
                batch_jid,
            )

        salt.utils.stringutils.print_cli(
            f"Executed batch command with job ID: {batch_jid}"
        )

    def _print_errors_summary(self, errors):
        if errors:
            salt.utils.stringutils.print_cli("\n")
            salt.utils.stringutils.print_cli("---------------------------")
            salt.utils.stringutils.print_cli("Errors")
            salt.utils.stringutils.print_cli("---------------------------")
            for error in errors:
                salt.utils.stringutils.print_cli(self._format_error(error))

    def _print_returns_summary(self, ret):
        """
        Display returns summary
        """
        return_counter = 0
        not_return_counter = 0
        not_return_minions = []
        not_response_minions = []
        not_connected_minions = []
        failed_minions = []
        for each_minion in ret:
            minion_ret = ret[each_minion]
            if isinstance(minion_ret, dict) and "ret" in minion_ret:
                minion_ret = ret[each_minion].get("ret")
            if isinstance(minion_ret, str) and minion_ret.startswith(
                "Minion did not return"
            ):
                if "Not connected" in minion_ret:
                    not_connected_minions.append(each_minion)
                elif "No response" in minion_ret:
                    not_response_minions.append(each_minion)
                not_return_counter += 1
                not_return_minions.append(each_minion)
            else:
                return_counter += 1
                if self._get_retcode(ret[each_minion]):
                    failed_minions.append(each_minion)
        salt.utils.stringutils.print_cli("\n")
        salt.utils.stringutils.print_cli("-------------------------------------------")
        salt.utils.stringutils.print_cli("Summary")
        salt.utils.stringutils.print_cli("-------------------------------------------")
        salt.utils.stringutils.print_cli(
            f"# of minions targeted: {return_counter + not_return_counter}"
        )
        salt.utils.stringutils.print_cli(f"# of minions returned: {return_counter}")
        salt.utils.stringutils.print_cli(
            f"# of minions that did not return: {not_return_counter}"
        )
        salt.utils.stringutils.print_cli(
            f"# of minions with errors: {len(failed_minions)}"
        )
        if self.options.verbose:
            if not_connected_minions:
                salt.utils.stringutils.print_cli(
                    "Minions not connected: {}".format(" ".join(not_connected_minions))
                )
            if not_response_minions:
                salt.utils.stringutils.print_cli(
                    "Minions not responding: {}".format(" ".join(not_response_minions))
                )
            if failed_minions:
                salt.utils.stringutils.print_cli(
                    "Minions with failures: {}".format(" ".join(failed_minions))
                )
        salt.utils.stringutils.print_cli("-------------------------------------------")

    def _progress_end(self, out):
        import salt.output

        salt.output.progress_end(self.progress_bar)

    def _progress_ret(self, progress, out):
        """
        Print progress events
        """
        import salt.output

        # Get the progress bar
        if not hasattr(self, "progress_bar"):
            try:
                self.progress_bar = salt.output.get_progress(self.config, out, progress)
            except Exception:  # pylint: disable=broad-except
                raise LoaderError(
                    "\nWARNING: Install the `progressbar` python package. "
                    "Requested job was still run but output cannot be displayed.\n"
                )
        salt.output.update_progress(self.config, progress, self.progress_bar, out)

    def _output_ret(self, ret, out, retcode=0):
        """
        Print the output from a single return to the terminal
        """
        import salt.output

        # Handle special case commands
        if self.config["fun"] == "sys.doc" and not isinstance(ret, Exception):
            self._print_docs(ret)
        else:
            # Determine the proper output method and run it
            salt.output.display_output(ret, out=out, opts=self.config, _retcode=retcode)
        if not ret:
            sys.stderr.write("ERROR: No return received\n")
            sys.exit(2)

    def _format_ret(self, full_ret):
        """
        Take the full return data and format it to simple output
        """
        ret = {}
        out = ""
        retcode = 0
        for key, data in full_ret.items():
            ret[key] = data["ret"]
            if "out" in data:
                out = data["out"]
            ret_retcode = self._get_retcode(data)
            if ret_retcode > retcode:
                retcode = ret_retcode
        return ret, out, retcode

    def _get_retcode(self, ret):
        """
        Determine a retcode for a given return
        """
        retcode = 0
        # if there is a dict with retcode, use that
        if isinstance(ret, dict) and ret.get("retcode", 0) != 0:
            if isinstance(ret.get("retcode", 0), dict):
                return max(ret.get("retcode", {0: 0}).values())
            return ret["retcode"]
        # if its a boolean, False means 1
        elif isinstance(ret, bool) and not ret:
            return 1
        return retcode

    def _format_error(self, minion_error):
        for minion, error_doc in minion_error.items():
            error = "Minion [{}] encountered exception '{}'".format(
                minion, error_doc["message"]
            )
        return error

    def _print_docs(self, ret):
        """
        Print out the docstrings for all of the functions on the minions
        """
        import salt.output

        docs = {}
        if not ret:
            self.exit(2, "No minions found to gather docs from\n")
        if isinstance(ret, str):
            self.exit(2, f"{ret}\n")
        for host in ret:
            if isinstance(ret[host], str) and (
                ret[host].startswith("Minion did not return")
                or ret[host] == "VALUE_TRIMMED"
            ):
                continue
            for fun in ret[host]:
                if fun not in docs and ret[host][fun]:
                    docs[fun] = ret[host][fun]
        if self.options.output:
            for fun in sorted(docs):
                salt.output.display_output({fun: docs[fun]}, "nested", self.config)
        else:
            for fun in sorted(docs):
                salt.utils.stringutils.print_cli(f"{fun}:")
                salt.utils.stringutils.print_cli(docs[fun])
                salt.utils.stringutils.print_cli("")
