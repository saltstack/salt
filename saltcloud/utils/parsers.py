# -*- coding: utf-8 -*-
'''
    saltcloud.utils.parsers
    ~~~~~~~~~~~~~~~~~~~~~~~

    This is where the salt-cloud parser system gets setup.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.
'''
# Import python libs
import os
import sys
import optparse
from functools import partial

# Import salt libs
import salt.utils.parsers as parsers

# Import salt cloud libs
import saltcloud.config as config
import saltcloud.version as version
import saltcloud.exceptions as exceptions


class CloudConfigMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = -1000    # First options seen

    def _mixin_setup(self):
        self.master_config = {}
        self.cloud_config = {}
        self.profiles_config = {}
        self.providers_config = {}
        group = self.config_group = optparse.OptionGroup(
            self,
            'Configuration Options',
            # Include description here as a string
        )
        group.add_option(
            '-C', '--cloud-config',
            default='/etc/salt/cloud',
            help='The location of the saltcloud config file. Default: %default'
        )
        group.add_option(
            '-M', '--master-config',
            default=None,
            help='The location of the salt master config file. '
                 'Default: /etc/salt/master'
        )
        group.add_option(
            '-V', '--profiles', '--vm_config',
            dest='vm_config',
            default=None,
            help='The location of the saltcloud VM config file. '
                 'Default: /etc/salt/cloud.profiles'
        )
        group.add_option(
            '--providers-config',
            default=None,
            help='The location of the salt cloud VM providers '
                 'configuration file. Default: /etc/salt/cloud.providers'
        )
        self.add_option_group(group)

    def __assure_absolute_paths(self, name):
        # Need to check if file exists?
        optvalue = getattr(self.options, name)
        if optvalue:
            setattr(self.options, name, os.path.abspath(optvalue))

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

        # Grab data from the 4 sources (done in self.process_cloud_config)
        # 1st - Master config
        # 2nd - Override master config with salt-cloud config
        # 3rd - Include Cloud Providers
        # 4th - Include VM config
        # 5th - Override config with cli options
        # Done in parsers.MergeConfigMixIn.__merge_config_with_cli()

        # Remove log_level_logfile from config if set to None so it can be
        # equal to console log_level
        if self.config['log_level_logfile'] is None:
            self.config.pop('log_level_logfile')

        if 'DUMP_SALT_CLOUD_CONFIG' in os.environ:
            import pprint

            print('Salt cloud configuration dump(INCLUDES SENSIBLE DATA):')
            pprint.pprint(self.config)
            self.exit(0)

    def setup_config(self):
        '''
        This method needs to be defined in order for `parsers.MergeConfigMixIn`
        to do it's job.
        '''
        return {}

    def process_cloud_config(self):
        try:
            self.config = config.cloud_config(
                self.options.cloud_config,
                master_config_path=self.options.master_config,
                providers_config_path=self.options.providers_config,
                vm_config_path=self.options.vm_config
            )
        except exceptions.SaltCloudConfigError as exc:
            self.error(exc)


class ExecutionOptionsMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = 10

    def _mixin_setup(self):
        group = self.execution_group = optparse.OptionGroup(
            self,
            'Execution Options',
            # Include description here as a string
        )
        group.add_option(
            '-L', '--location',
            default=None,
            help='Specify which region to connect to.'
        )
        group.add_option(
            '-a', '--action',
            default=None,
            help='Perform an action that may be specific to this cloud '
                 'provider. This argument requires one or more instance '
                 'names to be specified.'
        )
        group.add_option(
            '-f', '--function',
            nargs=2,
            default=None,
            metavar='<FUNC-NAME> <PROVIDER>',
            help='Perform an function that may be specific to this cloud '
                 'provider, that does not apply to an instance. This '
                 'argument requires a provider to be specified (i.e.: nova).'
        )
        group.add_option(
            '-p', '--profile',
            default=None,
            help='Create an instance using the specified profile.'
        )
        group.add_option(
            '-m', '--map',
            default=None,
            help='Specify a cloud map file to use for deployment. This option '
                 'may be used alone, or in conjunction with -Q, -F, -S or -d.'
        )
        group.add_option(
            '-H', '--hard',
            default=False,
            action='store_true',
            help='Delete all VMs that are not defined in the map file. '
                 'CAUTION!!! This operation can irrevocably destroy VMs! It '
                 'must be explicitly enabled in the cloud config file.'
        )
        group.add_option(
            '-d', '--destroy',
            default=False,
            action='store_true',
            help='Destroy the specified instance(s).'
        )
        group.add_option(
            '--no-deploy',
            default=True,
            dest='deploy',
            action='store_false',
            help='Don\'t run a deploy script after instance creation.'
        )
        group.add_option(
            '-P', '--parallel',
            default=False,
            action='store_true',
            help='Build all of the specified instances in parallel.'
        )
        group.add_option(
            '-u', '--update-bootstrap',
            default=False,
            action='store_true',
            help='Update salt-bootstrap to the latest develop version on '
                 'GitHub.'
        )
        group.add_option(
            '-y', '--assume-yes',
            default=False,
            action='store_true',
            help='Default yes in answer to all confirmation questions.'
        )
        group.add_option(
            '-k', '--keep-tmp',
            default=False,
            action='store_true',
            help='Do not remove files from /tmp/ after deploy.sh finishes.'
        )
        group.add_option(
            '--show-deploy-args',
            default=False,
            action='store_true',
            help='Include the options used to deploy the minion in the data '
                 'returned.'
        )
        self.add_option_group(group)

    def process_function(self):
        if self.options.function:
            self.function_name, self.function_provider = self.options.function
            if self.function_provider.startswith('-') or \
                    '=' in self.function_provider:
                self.error(
                    '--function expects two arguments: <function-name> '
                    '<provider>'
                )


class CloudQueriesMixIn(object):
    __metaclass__ = parsers.MixInMeta
    _mixin_prio_ = 20

    selected_query_option = None

    def _mixin_setup(self):
        group = self.cloud_queries_group = optparse.OptionGroup(
            self,
            'Query Options',
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
        group.add_option(
            '--list-providers',
            default=False,
            action='store_true',
            help=('Display a list of configured providers.')
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
                    elif opt.dest == 'list_providers':
                        query = 'list_providers'
                        if self.args:
                            self.error(
                                '\'--list-providers\' does not accept any '
                                'arguments'
                            )
                    self.selected_query_option = query

            funcname = 'process_{0}'.format(option.dest)
            if not hasattr(self, funcname):
                setattr(self, funcname, partial(process, option))

    def _mixin_after_parsed(self):
        group_options_selected = filter(
            lambda option: getattr(self.options, option.dest) is not False,
            self.cloud_queries_group.option_list
        )
        if len(group_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format('/'.join([
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
            'Cloud Providers Listings',
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
            lambda option: getattr(self.options, option.dest) is not None,
            self.providers_listings_group.option_list
        )
        if len(list_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format(
                    '/'.join([
                        option.get_opt_string() for option in
                        list_options_selected
                    ])
                )
            )


class SaltCloudParser(parsers.OptionParser,
                      parsers.LogLevelMixIn,
                      parsers.MergeConfigMixIn,
                      parsers.OutputOptionsMixIn,
                      CloudConfigMixIn,
                      CloudQueriesMixIn,
                      ExecutionOptionsMixIn,
                      CloudProvidersListsMixIn):

    __metaclass__ = parsers.OptionParserMeta

    # LogLevelMixIn attributes
    _default_logging_level_ = 'info'
    _logfile_config_setting_name_ = 'log_file'
    _loglevel_config_setting_name_ = 'log_level_logfile'
    _default_logging_logfile_ = '/var/log/salt/cloud'

    VERSION = version.__version__

    def print_versions_report(self, file=sys.stdout):
        print >> file, '\n'.join(version.versions_report())
        self.exit()

    def _mixin_after_parsed(self):
        if self.args:
            self.config['names'] = self.args
