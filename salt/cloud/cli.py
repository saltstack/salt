"""
Primary interfaces for the salt-cloud system
"""

# Need to get data from 4 sources!
# CLI options
# salt cloud config - CONFIG_DIR + '/cloud'
# salt master config (for master integration)
# salt VM config, where VMs are defined - CONFIG_DIR + '/cloud.profiles'
#
# The cli, master and cloud configs will merge for opts
# the VM data will be in opts['profiles']


import logging
import os
import sys

import salt.cloud
import salt.config
import salt.defaults.exitcodes
import salt.output
import salt.syspaths as syspaths
import salt.utils.cloud
import salt.utils.parsers
import salt.utils.user
from salt.exceptions import SaltCloudException, SaltCloudSystemExit
from salt.utils.verify import check_user, verify_env

log = logging.getLogger(__name__)


class SaltCloud(salt.utils.parsers.SaltCloudParser):
    def run(self):
        """
        Execute the salt-cloud command line
        """
        # Parse shell arguments
        self.parse_args()

        salt_master_user = self.config.get("user")
        if salt_master_user is None:
            salt_master_user = salt.utils.user.get_user()

        if not check_user(salt_master_user):
            self.error(
                "If salt-cloud is running on a master machine, salt-cloud "
                "needs to run as the same user as the salt-master, '{0}'. "
                "If salt-cloud is not running on a salt-master, the "
                "appropriate write permissions must be granted to '{1}'. "
                "Please run salt-cloud as root, '{0}', or change "
                "permissions for '{1}'.".format(salt_master_user, syspaths.CONFIG_DIR)
            )

        try:
            if self.config["verify_env"]:
                verify_env(
                    [os.path.dirname(self.config["conf_file"])],
                    salt_master_user,
                    root_dir=self.config["root_dir"],
                )
        except OSError as err:
            log.error("Error while verifying the environment: %s", err)
            sys.exit(err.errno)

        if self.options.update_bootstrap:
            ret = salt.utils.cloud.update_bootstrap(self.config)
            salt.output.display_output(ret, self.options.output, opts=self.config)
            self.exit(salt.defaults.exitcodes.EX_OK)

        log.info("salt-cloud starting")
        try:
            mapper = salt.cloud.Map(self.config)
        except SaltCloudSystemExit as exc:
            self.handle_exception(exc.args, exc)
        except SaltCloudException as exc:
            msg = "There was an error generating the mapper."
            self.handle_exception(msg, exc)

        names = self.config.get("names", None)
        if names is not None:
            filtered_rendered_map = {}
            for map_profile in mapper.rendered_map:
                filtered_map_profile = {}
                for name in mapper.rendered_map[map_profile]:
                    if name in names:
                        filtered_map_profile[name] = mapper.rendered_map[map_profile][
                            name
                        ]
                if filtered_map_profile:
                    filtered_rendered_map[map_profile] = filtered_map_profile
            mapper.rendered_map = filtered_rendered_map

        ret = {}

        if self.selected_query_option is not None:
            if self.selected_query_option == "list_providers":
                try:
                    ret = mapper.provider_list()
                except Exception as exc:  # pylint: disable=broad-except
                    msg = "There was an error listing providers: {0}"
                    self.handle_exception(msg, exc)

            elif self.selected_query_option == "list_profiles":
                provider = self.options.list_profiles
                try:
                    ret = mapper.profile_list(provider)
                except Exception as exc:  # pylint: disable=broad-except
                    msg = "There was an error listing profiles: {0}"
                    self.handle_exception(msg, exc)

            elif self.config.get("map", None):
                log.info("Applying map from '%s'.", self.config["map"])
                try:
                    ret = mapper.interpolated_map(query=self.selected_query_option)
                except Exception as exc:  # pylint: disable=broad-except
                    msg = "There was an error with a custom map: {0}"
                    self.handle_exception(msg, exc)
            else:
                try:
                    ret = mapper.map_providers_parallel(
                        query=self.selected_query_option
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    msg = "There was an error with a map: {0}"
                    self.handle_exception(msg, exc)

        elif self.options.list_locations is not None:
            try:
                ret = mapper.location_list(self.options.list_locations)
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error listing locations: {0}"
                self.handle_exception(msg, exc)

        elif self.options.list_images is not None:
            try:
                ret = mapper.image_list(self.options.list_images)
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error listing images: {0}"
                self.handle_exception(msg, exc)

        elif self.options.list_sizes is not None:
            try:
                ret = mapper.size_list(self.options.list_sizes)
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error listing sizes: {0}"
                self.handle_exception(msg, exc)

        elif self.options.destroy and (
            self.config.get("names", None) or self.config.get("map", None)
        ):
            map_file = self.config.get("map", None)
            names = self.config.get("names", ())
            if map_file is not None:
                if names != ():
                    msg = (
                        "Supplying a mapfile, '{}', in addition to instance names {}"
                        " with the '--destroy' or '-d' function is not supported."
                        " Please choose to delete either the entire map file or"
                        " individual instances.".format(map_file, names)
                    )
                    self.handle_exception(msg, SaltCloudSystemExit)

                log.info("Applying map from '%s'.", map_file)
                matching = mapper.delete_map(query="list_nodes")
            else:
                matching = mapper.get_running_by_names(
                    names, profile=self.options.profile
                )

            if not matching:
                print("No machines were found to be destroyed")
                self.exit(salt.defaults.exitcodes.EX_OK)

            msg = "The following virtual machines are set to be destroyed:\n"
            names = set()
            for alias, drivers in matching.items():
                msg += f"  {alias}:\n"
                for driver, vms in drivers.items():
                    msg += f"    {driver}:\n"
                    for name in vms:
                        msg += f"      {name}\n"
                        names.add(name)
            try:
                if self.print_confirm(msg):
                    ret = mapper.destroy(names, cached=True)
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error destroying machines: {0}"
                self.handle_exception(msg, exc)

        elif self.options.action and (
            self.config.get("names", None) or self.config.get("map", None)
        ):
            if self.config.get("map", None):
                log.info("Applying map from '%s'.", self.config["map"])
                try:
                    names = mapper.get_vmnames_by_action(self.options.action)
                except SaltCloudException as exc:
                    msg = "There was an error actioning virtual machines."
                    self.handle_exception(msg, exc)
            else:
                names = self.config.get("names", None)

            kwargs = {}
            machines = []
            msg = (
                "The following virtual machines are set to be actioned with "
                '"{}":\n'.format(self.options.action)
            )
            for name in names:
                if "=" in name:
                    # This is obviously not a machine name, treat it as a kwarg
                    key, value = name.split("=", 1)
                    kwargs[key] = value
                else:
                    msg += f"  {name}\n"
                    machines.append(name)
            names = machines

            try:
                if self.print_confirm(msg):
                    ret = mapper.do_action(names, kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error actioning machines: {0}"
                self.handle_exception(msg, exc)

        elif self.options.function:
            kwargs = {}
            args = self.args[:]
            for arg in args[:]:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    kwargs[key] = value
                    args.remove(arg)

            if args:
                self.error(
                    "Any arguments passed to --function need to be passed "
                    "as kwargs. Ex: image=ami-54cf5c3d. Remaining "
                    "arguments: {}".format(args)
                )
            try:
                ret = mapper.do_function(
                    self.function_provider, self.function_name, kwargs
                )
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error running the function: {0}"
                self.handle_exception(msg, exc)

        elif self.options.profile and self.config.get("names", False):
            try:
                ret = mapper.run_profile(self.options.profile, self.config.get("names"))
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was a profile error: {0}"
                self.handle_exception(msg, exc)

        elif self.options.set_password:
            username = self.credential_username
            provider_name = f"salt.cloud.provider.{self.credential_provider}"
            # TODO: check if provider is configured
            # set the password
            salt.utils.cloud.store_password_in_keyring(provider_name, username)
        elif self.config.get("map", None) and self.selected_query_option is None:
            if not mapper.rendered_map:
                sys.stderr.write("No nodes defined in this map")
                self.exit(salt.defaults.exitcodes.EX_GENERIC)
            try:
                ret = {}
                run_map = True

                log.info("Applying map from '%s'.", self.config["map"])
                dmap = mapper.map_data()

                msg = ""
                if "errors" in dmap:
                    # display profile errors
                    msg += "Found the following errors:\n"
                    for profile_name, error in dmap["errors"].items():
                        msg += f"  {profile_name}: {error}\n"
                    sys.stderr.write(msg)
                    sys.stderr.flush()

                msg = ""
                if "existing" in dmap:
                    msg += "The following virtual machines already exist:\n"
                    for name in dmap["existing"]:
                        msg += f"  {name}\n"

                if dmap["create"]:
                    msg += "The following virtual machines are set to be created:\n"
                    for name in dmap["create"]:
                        msg += f"  {name}\n"

                if "destroy" in dmap:
                    msg += "The following virtual machines are set to be destroyed:\n"
                    for name in dmap["destroy"]:
                        msg += f"  {name}\n"

                if not dmap["create"] and not dmap.get("destroy", None):
                    if not dmap.get("existing", None):
                        # nothing to create or destroy & nothing exists
                        print(msg)
                        self.exit(1)
                    else:
                        # nothing to create or destroy, print existing
                        run_map = False

                if run_map:
                    if self.print_confirm(msg):
                        ret = mapper.run_map(dmap)

                    if self.config.get("parallel", False) is False:
                        log.info("Complete")

                if dmap.get("existing", None):
                    for name in dmap["existing"]:
                        if "ec2" in dmap["existing"][name]["provider"]:
                            msg = (
                                "Instance already exists, or is terminated and has the"
                                " same name."
                            )
                        else:
                            msg = "Already running."
                        ret[name] = {"Message": msg}

            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was a query error: {0}"
                self.handle_exception(msg, exc)

        elif self.options.bootstrap:
            host = self.options.bootstrap
            if self.args and "=" not in self.args[0]:
                minion_id = self.args.pop(0)
            else:
                minion_id = host

            vm_ = {
                "driver": "",
                "ssh_host": host,
                "name": minion_id,
            }
            args = self.args[:]
            for arg in args[:]:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    vm_[key] = value
                    args.remove(arg)

            if args:
                self.error(
                    "Any arguments passed to --bootstrap need to be passed as "
                    "kwargs. Ex: ssh_username=larry. Remaining arguments: {}".format(
                        args
                    )
                )

            try:
                ret = salt.utils.cloud.bootstrap(vm_, self.config)
            except Exception as exc:  # pylint: disable=broad-except
                msg = "There was an error bootstrapping the minion: {0}"
                self.handle_exception(msg, exc)

        else:
            self.error("Nothing was done. Using the proper arguments?")

        salt.output.display_output(ret, self.options.output, opts=self.config)
        self.exit(salt.defaults.exitcodes.EX_OK)

    def print_confirm(self, msg):
        if self.options.assume_yes:
            return True
        print(msg)
        res = input("Proceed? [N/y] ")
        if not res.lower().startswith("y"):
            return False
        print("... proceeding")
        return True

    def handle_exception(self, msg, exc):
        if isinstance(exc, SaltCloudException):
            # It's a known exception and we know how to handle it
            if isinstance(exc, SaltCloudSystemExit):
                # This is a salt cloud system exit
                if exc.exit_code > 0:
                    # the exit code is bigger than 0, it's an error
                    msg = f"Error: {msg}"
                self.exit(exc.exit_code, msg.format(exc).rstrip() + "\n")
            # It's not a system exit but it's an error we can
            # handle
            self.error(msg.format(exc))
        # This is a generic exception, log it, include traceback if
        # debug logging is enabled and exit.
        log.error(
            msg.format(exc),
            # Show the traceback if the debug logging level is
            # enabled
            exc_info_on_loglevel=logging.DEBUG,
        )
        self.exit(salt.defaults.exitcodes.EX_GENERIC)
