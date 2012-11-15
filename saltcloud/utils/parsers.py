# -*- coding: utf-8 -*-
# vim: sw=4 ts=4 fenc=utf-8
"""
    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details
"""

# Import python libs
import os
import sys
import optparse
from functools import partial

# Import salt libs
import salt.config
from salt.utils import parsers

# Import salt cloud libs
from saltcloud import config, version


class CloudConfigMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = -1000    # First options seen

    config = {'log_level': None}

    def _mixin_setup(self):
        group = self.config_group = optparse.OptionGroup(
            self,
            "Configuration Options",
            # Include description here as a string
        )
        group.add_option(
            '-C', '--cloud-config',
            default='/etc/salt/cloud',
            help='The location of the saltcloud config file. Default: %default'
        )
        group.add_option(
            '-M', '--master-config',
            default='/etc/salt/master',
            help=('The location of the salt master config file. Default: '
                  '%default')
        )
        group.add_option(
            '-V', '--profiles', '--vm_config',
            dest='vm_config',
            default='/etc/salt/cloud.profiles',
            help=('The location of the saltcloud vm config file. Default: '
                  '%default')
        )
        self.add_option_group(group)

    def __assure_absolute_paths(self, name):
        # Need to check if file exists?
        optvalue = getattr(self.options, name)
        if optvalue:
            setattr(self.options, name, os.path.abspath(optvalue))

    def __merge_config_with_cli(self, *args):
        # Taken from https://github.com/saltstack/salt/blob/develop/salt/utils/parsers.py#L175

        # Merge parser options
        for option in self.option_list:
            if option.dest is None:
                # --version does not have dest attribute set for example.
                # All options defined by us, even if not explicitly(by kwarg),
                # will have the dest attribute set
                continue

            # Get the passed value from shell. If empty get the default one
            default = self.defaults.get(option.dest)
            value = getattr(self.options, option.dest, default)

            if option.dest not in self.config:
                # There's no value in the configuration file
                if value is not None:
                    # There's an actual value, add it to the config
                    self.config[option.dest] = value
            elif value is not None and value != default:
                # Only set the value in the config file IF it's not the default
                # value, this allows to tweak settings on the configuration
                # files bypassing the shell option flags
                self.config[option.dest] = value

        # Merge parser group options if any
        for group in self.option_groups:
            for option in group.option_list:
                if option.dest is None:
                    continue
                # Get the passed value from shell. If empty get the default one
                default = self.defaults.get(option.dest)
                value = getattr(self.options, option.dest, default)
                if option.dest not in self.config:
                    # There's no value in the configuration file
                    if value is not None:
                        # There's an actual value, add it to the config
                        self.config[option.dest] = value
                else:
                    if value is not None and value != default:
                        # Only set the value in the config file IF it's not the
                        # default value, this allows to tweak settings on the
                        # configuration files bypassing the shell option flags
                        self.config[option.dest] = value

    def _mixin_after_parsed(self):
        for option in self.config_group.option_list:
            if option.dest is None:
                # This should not happen.
                #
                # --version does not have dest attribute set for example.
                # All options defined by us, even if not explicitly(by kwarg),
                # will have the dest attribute set
                continue
            self.__assure_absolute_paths(option.dest)

        # Grab data from the 4 sources
        # 1st - Master config
        self.config.update(
            salt.config.master_config(self.options.master_config)
        )

        # 2nd Override master config with salt-cloud config
        self.config.update(config.cloud_config(self.options.cloud_config))

        ## Fix conf_file set on master config so that salt parsers don't fail
        #self.config['conf_file'] = self.options.cloud_config

        # 3rd - Override config with cli options
        self.__merge_config_with_cli()

        # 4th - Include vm config
        self.config['vm'] = config.vm_config(self.options.vm_config)

        # Remove log_level_logfile from config if set to None so it can be
        # equal to console log_level
        if self.config['log_level_logfile'] is None:
            self.config.pop('log_level_logfile')


class ExecutionOptionsMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = 10

    def _mixin_setup(self):
        group = self.execution_group = optparse.OptionGroup(
            self,
            "Execution Options",
            # Include description here as a string
        )
        group.add_option(
            '-p', '--profile',
            default='',
            help='Specify a profile to use for the vms'
        )
        group.add_option(
            '-m', '--map',
            default='',
            help='Specify a cloud map file to use for deployment'
        )
        group.add_option(
            '-H', '--hard',
            default=False,
            action='store_true',
            help=('Delete all vms that are not defined in the map file '
                  'CAUTION!!! This operation can irrevocably destroy vms!')
        )
        group.add_option(
            '-d', '--destroy',
            default=False,
            action='store_true',
            help='Specify a vm to destroy'
        )
        group.add_option(
            '-P', '--parallel',
            default=False,
            action='store_true',
            help='Build all of the specified virtual machines in parallel'
        )
        self.add_option_group(group)


class CloudQueriesMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = 20

    selected_query_option = None

    def _mixin_setup(self):
        group = self.cloud_queries_group = optparse.OptionGroup(
            self,
            "Query Options",
            # Include description here as a string
        )
        group.add_option(
            '-Q', '--query',
            default=False,
            action='store_true',
            help=('Execute a query and return some information about the '
                  'nodes running on configured cloud providers')
        )
        group.add_option(
            '-F', '--full-query',
            default=False,
            action='store_true',
            help=('Execute a query and return all information about the '
                  'nodes running on configured cloud providers')
        )
        group.add_option(
            '-S', '--select-query',
            default=False,
            action='store_true',
            help=('Execute a query and return select information about '
                  'the nodes running on configured cloud providers')
        )
        self.add_option_group(group)
        self._create_process_functions()

    def _create_process_functions(self):
        for option in self.cloud_queries_group.option_list:
            def process(opt):
                if getattr(self.options, opt.dest):
                    query = 'list_nodes'
                    if opt.dest == 'full_query':
                        query += '_full'
                    elif opt.dest == 'select_query':
                        query += '_select'
                    self.selected_query_option = query

            funcname = 'process_{0}'.format(option.dest)
            if not hasattr(self, funcname):
                setattr(self, funcname, partial(process, option))

    def _mixin_after_parsed(self):
        group_options_selected = filter(
            lambda option: getattr(self.options, option.dest) is True,
            self.cloud_queries_group.option_list
        )
        if len(group_options_selected) > 1:
            self.error(
                "The options {0} are mutually exclusive. Please only choose "
                "one of them".format('/'.join([
                    option.get_opt_string() for option in
                    group_options_selected
                ]))
            )
        self.config['selected_query_option'] = self.selected_query_option


class CloudProvidersListsMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = 30

    def _mixin_setup(self):
        group = self.providers_listings_group = optparse.OptionGroup(
            self,
            "Cloud Providers Listings",
            # Include description here as a string
        )
        group.add_option(
            '--list-locations',
            default=None,
            help=('Display a list of locations available in configured cloud '
                  'providers. Pass the cloud provider that available '
                  'locations are desired on, aka "linode", or pass "all" to '
                  'list locations for all configured cloud providers')
        )
        group.add_option(
            '--list-images',
            default=None,
            help=('Display a list of images available in configured cloud '
                  'providers. Pass the cloud provider that available images '
                  'are desired on, aka "linode", or pass "all" to list images '
                  'for all configured cloud providers')
        )
        group.add_option(
            '--list-sizes',
            default=None,
            help=('Display a list of sizes available in configured cloud '
                  'providers. Pass the cloud provider that available sizes '
                  'are desired on, aka "AWS", or pass "all" to list sizes '
                  'for all configured cloud providers')
        )
        self.add_option_group(group)

    def _mixin_after_parsed(self):
        list_options_selected = filter(
            lambda option: getattr(self.options, option.dest) is True,
            self.providers_listings_group.option_list
        )
        if len(list_options_selected) > 1:
            self.error(
                "The options {0} are mutually exclusive. Please only choose "
                "one of them".format('/'.join([
                    option.get_opt_string() for option in
                    list_options_selected
                ]))
            )


class SaltCloudParser(parsers.OptionParser,
                      parsers.LogLevelMixIn,
                      parsers.OutputOptionsWithTextMixIn,
                      CloudConfigMixIn,
                      CloudQueriesMixIn,
                      ExecutionOptionsMixIn,
                      CloudProvidersListsMixIn):

    __metaclass__ = parsers.OptionParserMeta
    _default_logging_level_ = "info"

    VERSION = version.__version__

    def print_versions_report(self, file=sys.stdout):
        print >> file, '\n'.join(version.versions_report())
        self.exit()

    def _mixin_after_parsed(self):
        if self.args:
            self.config['names'] = self.args
