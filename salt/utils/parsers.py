# -*- coding: utf-8 -*-
"""
    salt.utils.parser
    ~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import os
import sys
import optparse
from salt import config, log, version

def _sorted(mixins_or_funcs):
    return sorted(
        mixins_or_funcs, key=lambda mf: getattr(mf, '_mixin_prio_', 1000)
    )


class MixInMeta(type):

    # This attribute here won't actually do anything. But, if you need to
    # specify an order or a dependency within the mix-ins, please define the
    # attribute on your own MixIn
    _mixin_prio_ = 0

    def __new__(cls, name, bases, attrs):
        instance = super(MixInMeta, cls).__new__(cls, name, bases, attrs)
        if not hasattr(instance, '_mixin_setup'):
            raise RuntimeError(
                "Don't subclass {0} in {1} if you're not going to use it as a "
                "salt parser mix-in.".format(cls.__name__, name)
            )
        return instance


class OptionParserMeta(MixInMeta):
    def __new__(cls, name, bases, attrs):
        instance = super(OptionParserMeta, cls).__new__(cls, name, bases, attrs)
        if not hasattr(instance, '_mixin_setup_funcs'):
            instance._mixin_setup_funcs = []
        if not hasattr(instance, '_mixin_process_funcs'):
            instance._mixin_process_funcs = []
        if not hasattr(instance, '_mixin_after_parsed_funcs'):
            instance._mixin_after_parsed_funcs = []

        for base in _sorted(bases+(instance,)):
            func = getattr(base, '_mixin_setup', None)
            if func is not None and func not in instance._mixin_setup_funcs:
                instance._mixin_setup_funcs.append(func)

            func = getattr(base, '_mixin_after_parsed', None)
            if func is not None and func not in instance._mixin_after_parsed_funcs:
                instance._mixin_after_parsed_funcs.append(func)

            # Mark process_<opt> functions with the base priority for sorting
            for func in dir(base):
                if not func.startswith('process_'):
                    continue
                func = getattr(base, func)
                if getattr(func, '_mixin_prio_', None) is not None:
                    # Function already has the attribute set, don't override it
                    continue
                func.__func__._mixin_prio_ = getattr(base, '_mixin_prio_', 1000)

        return instance


class OptionParser(optparse.OptionParser):
    usage = "%prog"

    epilog = ("You can find additional help about %prog issuing 'man %prog' "
              "or on http://docs.saltstack.org/en/latest/index.html")
    description = None

    # Private attributes
    _mixin_prio_ = 100

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("version", "%prog {0}".format(version.__version__))
        kwargs.setdefault("usage", self.usage)
        if self.description:
            kwargs.setdefault('description', self.description)

        if self.epilog:
            kwargs.setdefault('epilog', self.epilog)

        optparse.OptionParser.__init__(self, *args, **kwargs)

        if "%prog" in self.epilog:
            self.epilog = self.epilog.replace("%prog", self.get_prog_name())

    def parse_args(self, args=None, values=None):
        options, args = optparse.OptionParser.parse_args(self, args, values)
        if options.versions_report:
            self.print_versions_report()

        self.options, self.args = options, args

        # Gather and run the process_<option> functions in the proper order
        process_option_funcs = []
        for option_key in options.__dict__.keys():
            process_option_func = getattr(self, "process_%s" % option_key, None)
            if process_option_func is not None:
                process_option_funcs.append(process_option_func)

        for process_option_func in _sorted(process_option_funcs):
            process_option_func()

        # Run the functions on self._mixin_after_parsed_funcs
        for mixin_after_parsed_func in self._mixin_after_parsed_funcs:
            mixin_after_parsed_func(self)

        # Retain the standard behaviour of optparse to return options and args
        return options, args

    def _populate_option_list(self, option_list, add_help=True):
        optparse.OptionParser._populate_option_list(
            self, option_list, add_help=add_help
        )
        for mixin_setup_func in self._mixin_setup_funcs:
            mixin_setup_func(self)

    def _add_version_option(self):
        optparse.OptionParser._add_version_option(self)
        self.add_option(
            '--versions-report', action='store_true',
            help="show program's dependencies version number and exit"
        )

    def print_versions_report(self, file=sys.stdout):
        print >> file, '\n'.join(version.versions_report())
        self.exit()


class DeprecatedConfigMessage(object):
    _mixin_prio_ = -10

    def print_config_warning(self, *args, **kwargs):
        self.error(
            "The '-c/--config' option is deprecated. You should now use "
            "-c/--config-dir to point to a directory which holds all of "
            "salt's configuration files.\n"
        )

class ConfigDirMixIn(DeprecatedConfigMessage):
    __metaclass__ = MixInMeta

    def _mixin_setup(self):
        self.add_option(
            '-c', '--config-dir', default='/etc/salt',
            help=('Pass in an alternative configuration directory. Default: '
                  '%default')
        )

    def __merge_config_with_cli(self, *args):
        for option in self.option_list:
            if not option.dest:
                # --version does not have dest attribute set for example.
                # All options defined by us, even if not explicitly(by kwarg),
                # will have the dest attribute set
                continue

            value = getattr(self.options, option.dest, None)
            if value:
                self.config[option.dest] = value

    def process_config_dir(self):
        # XXX: Remove deprecation warning in next release
        if os.path.isfile(self.options.config_dir):
            self.print_config_warning()

        if hasattr(self, 'setup_config'):
            self.config = self.setup_config()
            # Add an additional function that will merge the cli options with
            # the config options and if needed override them
            self._mixin_after_parsed_funcs.append(self.__merge_config_with_cli)

    def get_config_file_path(self, configfile):
        return os.path.join(self.options.config_dir, configfile)


class DeprecatedMasterMinionMixIn(DeprecatedConfigMessage):
    __metaclass__ = MixInMeta

    def _mixin_setup(self):
        # XXX: Remove deprecated option in next release
        self.add_option(
            '--config', action="callback", callback=self.print_config_warning,
            help='DEPRECATED. Please use -c/--config-dir from now on.'
        )


class DeprecatedSyndicOptionsMixIn(DeprecatedConfigMessage):
    __metaclass__ = MixInMeta

    def _mixin_setup(self):
        # XXX: Remove deprecated option in next release
        self.add_option(
            '--master-config', '--minion-config',
            action="callback", callback=self.print_config_warning,
            help='DEPRECATED. Please use -c/--config-dir from now on.'
        )

    def process_config_dir(self, options):
        # XXX: Remove deprecation warning in next release
        if os.path.isfile(options.config_dir):
            self.print_config_warning()

        if hasattr(self, 'setup_config'):
            self.config = self.setup_config()


class LogLevelMixIn(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 10
    _skip_console_logging_config_ = False

    def _mixin_setup(self):
        if getattr(self, '_skip_console_logging_config_', False):
            return

        self.add_option(
            '-l', '--log-level',
            choices=list(log.LOG_LEVELS),
            help=('Logging log level. One of {0}. For the logfile settings see '
                  'the configuration file. Default: \'warning\'.').format(
                    ', '.join([repr(l) for l in log.SORTED_LEVEL_NAMES])
            )
        )

    def process_log_level(self):
        if not self.options.log_level:
            self.options.log_level = self.config['log_level']

        log.setup_console_logger(
            self.options.log_level,
            log_format=self.config['log_fmt_console'],
            date_format=self.config['log_datefmt']
        )

    def setup_logfile_logger(self):
        log.setup_logfile_logger(
            self.config['log_file'],
            self.config['log_level_logfile'] or self.config['log_level'],
            log_format=self.config['log_fmt_logfile'],
            date_format=self.config['log_datefmt']
        )
        for name, level in self.config['log_granular_levels'].items():
            log.set_logger_level(name, level)


class RunUserMixin(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 20

    def _mixin_setup(self):
        self.add_option(
            '-u', '--user',
            help='Specify user to run {0}'.format(self.get_prog_name())
        )


class DaemonMixIn(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 30

    def _mixin_setup(self):
        self.add_option(
            '-d', '--daemon',
            default=False,
            action='store_true',
            help='Run the {0} as a daemon'.format(self.get_prog_name())
        )

    def daemonize_if_required(self):
        if self.options.daemon:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()


class PidfileMixin(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 40

    def _mixin_setup(self):
        self.add_option(
            '--pid-file', dest='pidfile',
            default='/var/run/{0}.pid'.format(self.get_prog_name()),
            help=('Specify the location of the pidfile. Default: %default')
        )

    def set_pidfile(self):
        from salt.utils.process import set_pidfile
        set_pidfile(self.config['pidfile'])


class MasterOptionParser(OptionParser, ConfigDirMixIn, LogLevelMixIn,
                         DeprecatedMasterMinionMixIn, RunUserMixin,
                         DaemonMixIn, PidfileMixin):

    __metaclass__ = OptionParserMeta

    description = "TODO: explain what salt-master is"

    def setup_config(self):
        return config.master_config(self.get_config_file_path('master'))


class MinionOptionParser(MasterOptionParser):

    __metaclass__ = OptionParserMeta

    description = "TODO: explain what salt-minion is"

    def setup_config(self, options):
        return config.minion_config(self.get_config_file_path('minion'))


class SyndicOptionParser(OptionParser, DeprecatedSyndicOptionsMixIn,
                         ConfigDirMixIn, LogLevelMixIn, RunUserMixin,
                         DaemonMixIn, PidfileMixin):

    __metaclass__ = OptionParserMeta

    description = ("A seamless master of masters. Scale Salt to thousands of "
                   "hosts or across many different networks.")

    def setup_config(self, options):
        opts = config.master_config(self.get_config_file_path('master'))
        opts['_minion_conf_file'] = opts['conf_file']
        opts.update(config.minion_config(self.get_config_file_path('minion')))

        if 'syndic_master' not in opts:
            self.error(
                "The syndic_master needs to be configured in the salt master "
                "config, EXITING!"
            )

        from salt import utils
        # Some of the opts need to be changed to match the needed opts
        # in the minion class.
        opts['master'] = opts['syndic_master']
        opts['master_ip'] = utils.dns_check(opts['master'])

        opts['master_uri'] = 'tcp://{0}:{1}'.format(
            opts['master_ip'], str(opts['master_port'])
        )
        opts['_master_conf_file'] = opts['conf_file']
        opts.pop('conf_file')
        return opts
