# -*- coding: utf-8 -*-
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

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import sys

# Import salt libs
import salt.cloud
import salt.config
import salt.defaults.exitcodes
import salt.output
import salt.syspaths as syspaths
import salt.utils.cloud
import salt.utils.parsers
import salt.utils.user
from salt.exceptions import SaltCloudException, SaltCloudSystemExit

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import input
from salt.utils.verify import check_user, verify_env, verify_log, verify_log_files

log = logging.getLogger(__name__)

# pylint: disable=broad-except


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
                logfile = self.config["log_file"]
                if logfile is not None:
                    # Logfile is not using Syslog, verify
                    verify_log_files([logfile], salt_master_user)
        except (IOError, OSError) as err:
            log.error("Error while verifying the environment: %s", err)
            sys.exit(err.errno)

        # Setup log file logging
        self.setup_logfile_logger()
        verify_log(self.config)

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
                # pylint: disable=broad-except
                try:
                    ret = mapper.provider_list()
                except (SaltCloudException, Exception,) as exc:
                    msg = "There was an error listing providers: {0}"
                    self.handle_exception(msg, exc)
                # pylint: enable=broad-except

            elif self.selected_query_option == "list_profiles":
                provider = self.options.list_profiles
                # pylint: disable=broad-except
                try:
                    ret = mapper.profile_list(provider)
                except (SaltCloudException, Exception,) as exc:
                    msg = "There was an error listing profiles: {0}"
                    self.handle_exception(msg, exc)
                # pylint: enable=broad-except

            elif self.config.get("map", None):
                log.info("Applying map from '%s'.", self.config["map"])
                # pylint: disable=broad-except
                try:
                    ret = mapper.interpolated_map(query=self.selected_query_option)
                except (SaltCloudException, Exception,) as exc:
                    msg = "There was an error with a custom map: {0}"
                    self.handle_exception(msg, exc)
                # pylint: enable=broad-except
            else:
                # pylint: disable=broad-except
                try:
                    ret = mapper.map_providers_parallel(
                        query=self.selected_query_option
                    )
                except (SaltCloudException, Exception,) as exc:
                    msg = "There was an error with a map: {0}"
                    self.handle_exception(msg, exc)
                # pylint: enable=broad-except

        elif self.options.list_locations is not None:
            # pylint: disable=broad-except
            try:
                ret = mapper.location_list(self.options.list_locations)
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error listing locations: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

        elif self.options.list_images is not None:
            # pylint: disable=broad-except
            try:
                ret = mapper.image_list(self.options.list_images)
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error listing images: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

        elif self.options.list_sizes is not None:
            # pylint: disable=broad-except
            try:
                ret = mapper.size_list(self.options.list_sizes)
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error listing sizes: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

        elif self.options.destroy and (
            self.config.get("names", None) or self.config.get("map", None)
        ):
            map_file = self.config.get("map", None)
            names = self.config.get("names", ())
            if map_file is not None:
                if names != ():
                    msg = (
                        "Supplying a mapfile, '{0}', in addition to instance names {1} "
                        "with the '--destroy' or '-d' function is not supported. "
                        "Please choose to delete either the entire map file or individual "
                        "instances.".format(map_file, names)
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
            for alias, drivers in six.iteritems(matching):
                msg += "  {0}:\n".format(alias)
                for driver, vms in six.iteritems(drivers):
                    msg += "    {0}:\n".format(driver)
                    for name in vms:
                        msg += "      {0}\n".format(name)
                        names.add(name)
            # pylint: disable=broad-except
            try:
                if self.print_confirm(msg):
                    ret = mapper.destroy(names, cached=True)
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error destroying machines: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

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
                '"{0}":\n'.format(self.options.action)
            )
            for name in names:
                if "=" in name:
                    # This is obviously not a machine name, treat it as a kwarg
                    key, value = name.split("=", 1)
                    kwargs[key] = value
                else:
                    msg += "  {0}\n".format(name)
                    machines.append(name)
            names = machines

            # pylint: disable=broad-except
            try:
                if self.print_confirm(msg):
                    ret = mapper.do_action(names, kwargs)
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error actioning machines: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

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
                    "arguments: {0}".format(args)
                )
            # pylint: disable=broad-except
            try:
                ret = mapper.do_function(
                    self.function_provider, self.function_name, kwargs
                )
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error running the function: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

        elif self.options.profile and self.config.get("names", False):
            # pylint: disable=broad-except
            try:
                ret = mapper.run_profile(self.options.profile, self.config.get("names"))
            except (SaltCloudException, Exception,) as exc:
                msg = "There was a profile error: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

        elif self.options.set_password:
            username = self.credential_username
            provider_name = "salt.cloud.provider.{0}".format(self.credential_provider)
            # TODO: check if provider is configured
            # set the password
            salt.utils.cloud.store_password_in_keyring(provider_name, username)
        elif self.config.get("map", None) and self.selected_query_option is None:
            if not mapper.rendered_map:
                sys.stderr.write("No nodes defined in this map")
                self.exit(salt.defaults.exitcodes.EX_GENERIC)
            # pylint: disable=broad-except
            try:
                ret = {}
                run_map = True

                log.info("Applying map from '%s'.", self.config["map"])
                dmap = mapper.map_data()

                msg = ""
                if "errors" in dmap:
                    # display profile errors
                    msg += "Found the following errors:\n"
                    for profile_name, error in six.iteritems(dmap["errors"]):
                        msg += "  {0}: {1}\n".format(profile_name, error)
                    sys.stderr.write(msg)
                    sys.stderr.flush()

                msg = ""
                if "existing" in dmap:
                    msg += "The following virtual machines already exist:\n"
                    for name in dmap["existing"]:
                        msg += "  {0}\n".format(name)

                if dmap["create"]:
                    msg += "The following virtual machines are set to be " "created:\n"
                    for name in dmap["create"]:
                        msg += "  {0}\n".format(name)

                if "destroy" in dmap:
                    msg += (
                        "The following virtual machines are set to be " "destroyed:\n"
                    )
                    for name in dmap["destroy"]:
                        msg += "  {0}\n".format(name)

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
                            msg = "Instance already exists, or is terminated and has the same name."
                        else:
                            msg = "Already running."
                        ret[name] = {"Message": msg}

            except (SaltCloudException, Exception,) as exc:
                msg = "There was a query error: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

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
                    "kwargs. Ex: ssh_username=larry. Remaining arguments: {0}".format(
                        args
                    )
                )

            # pylint: disable=broad-except
            try:
                ret = salt.utils.cloud.bootstrap(vm_, self.config)
            except (SaltCloudException, Exception,) as exc:
                msg = "There was an error bootstrapping the minion: {0}"
                self.handle_exception(msg, exc)
            # pylint: enable=broad-except

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
                    msg = "Error: {0}".format(msg)
                self.exit(exc.exit_code, msg.format(exc).rstrip() + "\n")
            # It's not a system exit but it's an error we can
            # handle
            self.error(msg.format(exc))
        # This is a generic exception, log it, include traceback if
        # debug logging is enabled and exit.
        # pylint: disable=str-format-in-logging
        log.error(
            msg.format(exc),
            # Show the traceback if the debug logging level is
            # enabled
            exc_info_on_loglevel=logging.DEBUG,
        )
        # pylint: enable=str-format-in-logging
        self.exit(salt.defaults.exitcodes.EX_GENERIC)
