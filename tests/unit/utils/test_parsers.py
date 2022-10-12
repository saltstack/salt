"""
    :codeauthor: Denys Havrysh <denys.gavrysh@gmail.com>
"""

import logging
import os
import pprint
import shutil
import tempfile

import salt._logging
import salt.config
import salt.syspaths
import salt.utils.jid
import salt.utils.parsers
import salt.utils.platform
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import ANY, MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class ErrorMock:  # pylint: disable=too-few-public-methods
    """
    Error handling
    """

    def __init__(self):
        """
        init
        """
        self.msg = None

    def error(self, msg):
        """
        Capture error message
        """
        self.msg = msg


class LogImplMock:
    """
    Logger setup
    """

    def __init__(self):
        """
        init
        """
        self.log_level_console = None
        self.log_file = None
        self.log_level_logfile = None
        self.config = self.original_config = None
        logging_options = salt._logging.get_logging_options_dict()
        if logging_options:
            self.config = logging_options.copy()
            self.original_config = self.config.copy()
        self.temp_log_level = None
        self._console_handler_configured = False
        self._extended_logging_configured = False
        self._logfile_handler_configured = False
        self._real_set_logging_options_dict = salt._logging.set_logging_options_dict
        self._real_get_logging_options_dict = salt._logging.get_logging_options_dict
        self._real_setup_logfile_handler = salt._logging.setup_logfile_handler

    def _destroy(self):
        salt._logging.set_logging_options_dict.__options_dict__ = self.original_config
        salt._logging.shutdown_logfile_handler()

    def setup_temp_handler(self, log_level=None):
        """
        Set temp handler loglevel
        """
        log.debug("Setting temp handler log level to: %s", log_level)
        self.temp_log_level = log_level

    def is_console_handler_configured(self):
        log.debug("Calling is_console_handler_configured")
        return self._console_handler_configured

    def setup_console_handler(
        self, log_level="error", **kwargs
    ):  # pylint: disable=unused-argument
        """
        Set console loglevel
        """
        log.debug("Setting console handler log level to: %s", log_level)
        self.log_level_console = log_level
        self._console_handler_configured = True

    def shutdown_console_handler(self):
        log.debug("Calling shutdown_console_handler")
        self._console_handler_configured = False

    def is_extended_logging_configured(self):
        log.debug("Calling is_extended_logging_configured")
        return self._extended_logging_configured

    def setup_extended_logging(self, opts):
        """
        Set opts
        """
        log.debug("Calling setup_extended_logging")
        self._extended_logging_configured = True

    def shutdown_extended_logging(self):
        log.debug("Calling shutdown_extended_logging")
        self._extended_logging_configured = False

    def is_logfile_handler_configured(self):
        log.debug("Calling is_logfile_handler_configured")
        return self._logfile_handler_configured

    def setup_logfile_handler(
        self, log_path, log_level=None, **kwargs
    ):  # pylint: disable=unused-argument
        """
        Set logfile and loglevel
        """
        log.debug("Setting log file handler path to: %s", log_path)
        log.debug("Setting log file handler log level to: %s", log_level)
        self.log_file = log_path
        self.log_level_logfile = log_level
        self._real_setup_logfile_handler(log_path, log_level=log_level, **kwargs)
        self._logfile_handler_configured = True

    def shutdown_logfile_handler(self):
        log.debug("Calling shutdown_logfile_handler")
        self._logfile_handler_configured = False

    def get_logging_options_dict(self):
        log.debug("Calling get_logging_options_dict")
        return self.config

    def set_logging_options_dict(self, opts):
        log.debug("Calling set_logging_options_dict")
        self._real_set_logging_options_dict(opts)
        self.config = self._real_get_logging_options_dict()
        log.debug("Logging options dict:\n%s", pprint.pformat(self.config))

    def setup_log_granular_levels(self, opts):
        log.debug("Calling setup_log_granular_levels")

    def setup_logging(self):
        log.debug("Mocked setup_logging called")
        # Wether daemonizing or not, either on the main process or on a separate process
        # The log file is going to be configured.
        # The console is the only handler not configured if daemonizing

        # These routines are what happens on salt._logging.setup_logging
        opts = self.get_logging_options_dict()

        if (
            opts.get("configure_console_logger", True)
            and not self.is_console_handler_configured()
        ):
            self.setup_console_handler(
                log_level=opts["log_level"],
                log_format=opts["log_fmt_console"],
                date_format=opts["log_datefmt"],
            )
        if (
            opts.get("configure_file_logger", True)
            and not self.is_logfile_handler_configured()
        ):
            log_file_level = opts["log_level_logfile"] or opts["log_level"]
            if log_file_level != "quiet":
                self.setup_logfile_handler(
                    log_path=opts[opts["log_file_key"]],
                    log_level=log_file_level,
                    log_format=opts["log_fmt_logfile"],
                    date_format=opts["log_datefmt_logfile"],
                    max_bytes=opts["log_rotate_max_bytes"],
                    backup_count=opts["log_rotate_backup_count"],
                    user=opts["user"],
                )
        if not self.is_extended_logging_configured():
            self.setup_extended_logging(opts)
        self.setup_log_granular_levels(opts["log_granular_levels"])


class ObjectView:  # pylint: disable=too-few-public-methods
    """
    Dict object view
    """

    def __init__(self, d):
        self.__dict__ = d


class ParserBase:
    """
    Unit Tests for Log Level Mixin with Salt parsers
    """

    args = []

    log_impl = None

    # Set config option names
    loglevel_config_setting_name = "log_level"
    logfile_config_setting_name = "log_file"
    logfile_loglevel_config_setting_name = (
        "log_level_logfile"  # pylint: disable=invalid-name
    )

    @classmethod
    def setUpClass(cls):
        cls.root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root_dir, ignore_errors=True)

    def setup_log(self):
        """
        Mock logger functions
        """
        testing_config = self.default_config.copy()
        testing_config["root_dir"] = self.root_dir
        for name in ("pki_dir", "cachedir"):
            testing_config[name] = name
        testing_config[self.logfile_config_setting_name] = getattr(
            self, self.logfile_config_setting_name, self.log_file
        )
        self.testing_config = testing_config
        self.addCleanup(setattr, self, "testing_config", None)

        self.log_impl = LogImplMock()
        self.addCleanup(self.log_impl._destroy)
        self.addCleanup(setattr, self, "log_impl", None)

        mocked_functions = {}
        for name in dir(self.log_impl):
            if name.startswith("_"):
                continue
            func = getattr(self.log_impl, name)
            if not callable(func):
                continue
            mocked_functions[name] = func
        patcher = patch.multiple(salt._logging, **mocked_functions)
        patcher.start()
        self.addCleanup(patcher.stop)

    # log level configuration tests

    def test_get_log_level_cli(self):
        """
        Tests that log level match command-line specified value
        """
        # Set defaults
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

        # Set log level in CLI
        log_level = "critical"
        args = ["--log-level", log_level] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
            parser.parse_args(args)

        console_log_level = getattr(parser.options, self.loglevel_config_setting_name)

        # Check console log level setting
        self.assertEqual(console_log_level, log_level)
        # Check console logger log level
        self.assertEqual(self.log_impl.log_level_console, log_level)
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(self.log_impl.temp_log_level, log_level)
        # Check log file logger log level
        self.assertEqual(self.log_impl.log_level_logfile, default_log_level)

    def test_get_log_level_config(self):
        """
        Tests that log level match the configured value
        """
        args = self.args

        # Set log level in config
        log_level = "info"
        opts = self.testing_config.copy()
        opts.update({self.loglevel_config_setting_name: log_level})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)

        console_log_level = getattr(parser.options, self.loglevel_config_setting_name)

        # Check console log level setting
        self.assertEqual(console_log_level, log_level)
        # Check console logger log level
        self.assertEqual(self.log_impl.log_level_console, log_level)
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file logger log level
        self.assertEqual(self.log_impl.log_level_logfile, log_level)

    def test_get_log_level_default(self):
        """
        Tests that log level match the default value
        """
        # Set defaults
        log_level = default_log_level = self.testing_config[
            self.loglevel_config_setting_name
        ]

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
            parser.parse_args(args)

        console_log_level = getattr(parser.options, self.loglevel_config_setting_name)

        # Check log level setting
        self.assertEqual(console_log_level, log_level)
        # Check console logger log level
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file logger
        self.assertEqual(self.log_impl.log_level_logfile, default_log_level)
        # Check help message
        self.assertIn(
            "Default: '{}'.".format(default_log_level),
            parser.get_option("--log-level").help,
        )

    # log file configuration tests

    def test_get_log_file_cli(self):
        """
        Tests that log file match command-line specified value
        """
        # Set defaults
        log_level = self.testing_config[self.loglevel_config_setting_name]

        # Set log file in CLI
        log_file = "{}_cli.log".format(self.log_file)
        args = ["--log-file", log_file] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
            parser.parse_args(args)

        log_file_option = getattr(parser.options, self.logfile_config_setting_name)

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_config_setting_name], log_file
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file setting
        self.assertEqual(log_file_option, log_file)
        # Check log file logger
        self.assertEqual(self.log_impl.log_file, log_file)

    def test_get_log_file_config(self):
        """
        Tests that log file match the configured value
        """
        # Set defaults
        log_level = self.testing_config[self.loglevel_config_setting_name]

        args = self.args

        # Set log file in config
        log_file = "{}_config.log".format(self.log_file)
        opts = self.testing_config.copy()
        opts.update({self.logfile_config_setting_name: log_file})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)

        log_file_option = getattr(parser.options, self.logfile_config_setting_name)

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_config_setting_name], log_file
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file setting
        self.assertEqual(log_file_option, log_file)
        # Check log file logger
        self.assertEqual(self.log_impl.log_file, log_file)

    def test_get_log_file_default(self):
        """
        Tests that log file match the default value
        """
        # Set defaults
        log_level = self.testing_config[self.loglevel_config_setting_name]
        log_file = self.testing_config[self.logfile_config_setting_name]
        default_log_file = self.default_config[self.logfile_config_setting_name]

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
            parser.parse_args(args)

        log_file_option = getattr(parser.options, self.logfile_config_setting_name)

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_config_setting_name], log_file
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file setting
        self.assertEqual(log_file_option, log_file)
        # Check log file logger
        self.assertEqual(self.log_impl.log_file, log_file)
        # Check help message
        self.assertIn(
            "Default: '{}'.".format(default_log_file),
            parser.get_option("--log-file").help,
        )

    # log file log level configuration tests

    def test_get_log_file_level_cli(self):
        """
        Tests that file log level match command-line specified value
        """
        # Set defaults
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

        # Set log file level in CLI
        log_level_logfile = "error"
        args = ["--log-file-level", log_level_logfile] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
            parser.parse_args(args)

        log_level_logfile_option = getattr(
            parser.options, self.logfile_loglevel_config_setting_name
        )

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, default_log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name],
            default_log_level,
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_loglevel_config_setting_name],
            log_level_logfile,
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_impl.log_level_logfile, log_level_logfile)

    def test_get_log_file_level_config(self):
        """
        Tests that log file level match the configured value
        """
        # Set defaults
        log_level = self.testing_config[self.loglevel_config_setting_name]

        args = self.args

        # Set log file level in config
        log_level_logfile = "info"
        opts = self.testing_config.copy()
        opts.update({self.logfile_loglevel_config_setting_name: log_level_logfile})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)

        log_level_logfile_option = getattr(
            parser.options, self.logfile_loglevel_config_setting_name
        )

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_loglevel_config_setting_name],
            log_level_logfile,
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_impl.log_level_logfile, log_level_logfile)

    def test_get_log_file_level_default(self):
        """
        Tests that log file level match the default value
        """
        # Set defaults
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

        log_level = default_log_level
        log_level_logfile = default_log_level

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
            parser.parse_args(args)

        log_level_logfile_option = getattr(
            parser.options, self.logfile_loglevel_config_setting_name
        )

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_loglevel_config_setting_name],
            log_level_logfile,
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_impl.log_level_logfile, log_level_logfile)
        # Check help message
        self.assertIn(
            "Default: '{}'.".format(default_log_level),
            parser.get_option("--log-file-level").help,
        )

    def test_get_console_log_level_with_file_log_level(
        self,
    ):  # pylint: disable=invalid-name
        """
        Tests that both console log level and log file level setting are working together
        """
        log_level = "critical"
        log_level_logfile = "debug"

        args = ["--log-file-level", log_level_logfile] + self.args

        opts = self.testing_config.copy()
        opts.update({self.loglevel_config_setting_name: log_level})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)

        log_level_logfile_option = getattr(
            parser.options, self.logfile_loglevel_config_setting_name
        )

        # Check console logger
        self.assertEqual(self.log_impl.log_level_console, log_level)
        # Check extended logger
        self.assertEqual(
            self.log_impl.config[self.loglevel_config_setting_name], log_level
        )
        self.assertEqual(
            self.log_impl.config[self.logfile_loglevel_config_setting_name],
            log_level_logfile,
        )
        # Check temp logger
        self.assertEqual(self.log_impl.temp_log_level, "error")
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_impl.log_level_logfile, log_level_logfile)

    def test_log_created(self):
        """
        Tests that log file is created
        """
        args = self.args
        log_file = self.log_file
        log_file_name = self.logfile_config_setting_name
        opts = self.testing_config.copy()
        opts.update({"log_file": log_file})
        if log_file_name != "log_file":
            opts.update({log_file_name: getattr(self, log_file_name)})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)

        if log_file_name == "log_file":
            self.assertGreaterEqual(os.path.getsize(log_file), 0)
        else:
            self.assertGreaterEqual(os.path.getsize(getattr(self, log_file_name)), 0)

    def test_callbacks_uniqueness(self):
        """
        Test that the callbacks are only added once, no matter
        how many instances of the parser we create
        """
        mixin_container_names = (
            "_mixin_setup_funcs",
            "_mixin_process_funcs",
            "_mixin_after_parsed_funcs",
            "_mixin_before_exit_funcs",
        )
        parser = self.parser()
        nums_1 = {}
        for cb_container in mixin_container_names:
            obj = getattr(parser, cb_container)
            nums_1[cb_container] = len(obj)

        # The next time we instantiate the parser, the counts should be equal
        parser = self.parser()
        nums_2 = {}
        for cb_container in mixin_container_names:
            obj = getattr(parser, cb_container)
            nums_2[cb_container] = len(obj)
        self.assertDictEqual(nums_1, nums_2)

    def test_verify_log_warning_logged(self):
        args = ["--log-level", "debug"] + self.args
        with TstSuiteLoggingHandler(level=logging.DEBUG) as handler:
            parser = self.parser()
            with patch(self.config_func, MagicMock(return_value=self.testing_config)):
                parser.parse_args(args)
            self.assertIn(
                "WARNING:Insecure logging configuration detected! Sensitive data may be logged.",
                handler.messages,
            )


class MasterOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Master options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_master_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.master_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.MasterOptionParser
        self.addCleanup(delattr, self, "parser")


class MinionOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Minion options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_minion_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.minion_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.MinionOptionParser
        self.addCleanup(delattr, self, "parser")


class ProxyMinionOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Proxy Minion options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_PROXY_MINION_OPTS)
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_proxy_minion_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.proxy_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.ProxyMinionOptionParser
        self.addCleanup(delattr, self, "parser")


class SyndicOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Syndic options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set config option names
        self.logfile_config_setting_name = "syndic_log_file"

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_syndic_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        syndic_log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_syndic_log",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.syndic_log_file = syndic_log_file.name
        syndic_log_file.close()
        # Function to patch
        self.config_func = "salt.config.syndic_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SyndicOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltCMDOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt CLI options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["foo", "bar.baz"]

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_cmd_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.client_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCMDOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltCPOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing salt-cp options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["foo", "bar", "baz"]

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_cp_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.master_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCPOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltKeyOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing salt-key options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set config option names
        self.logfile_config_setting_name = "key_logfile"

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_key_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        key_logfile = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_key_logfile",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.key_logfile = key_logfile.name
        key_logfile.close()
        # Function to patch
        self.config_func = "salt.config.client_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltKeyOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltCallOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Minion options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["foo.bar"]

        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_call_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.minion_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCallOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltRunOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Master options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["foo.bar"]

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_run_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.master_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltRunOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltSSHOptionParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Master options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["foo", "bar.baz"]

        # Set config option names
        self.logfile_config_setting_name = "ssh_log_file"

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_ssh_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        ssh_log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_ssh_logfile",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.ssh_log_file = ssh_log_file.name
        ssh_log_file.close()
        # Function to patch
        self.config_func = "salt.config.master_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltSSHOptionParser
        self.addCleanup(delattr, self, "parser")


class SaltCloudParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Cloud options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["-p", "foo", "bar"]

        # Set default configs
        # Cloud configs are merged with master configs in
        # config/__init__.py, so we'll do that here as well
        # As we need the 'user' key later on.
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_CLOUD_OPTS)
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_cloud_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        # Function to patch
        self.config_func = "salt.config.cloud_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCloudParser
        self.addCleanup(delattr, self, "parser")


class SPMParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Cloud options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = ["foo", "bar"]

        # Set config option names
        self.logfile_config_setting_name = "spm_logfile"

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_SPM_OPTS)
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_spm_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        spm_logfile = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_spm_logfile",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.spm_logfile = spm_logfile.name
        spm_logfile.close()
        # Function to patch
        self.config_func = "salt.config.spm_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SPMParser
        self.addCleanup(delattr, self, "parser")


class SaltAPIParserTestCase(ParserBase, TestCase):
    """
    Tests parsing Salt Cloud options
    """

    def setUp(self):
        """
        Setting up
        """
        # Set mandatory CLI options
        self.args = []

        # Set config option names
        self.logfile_config_setting_name = "api_logfile"

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_API_OPTS)
        self.addCleanup(delattr, self, "default_config")

        # Log file
        # We need to use NamedTemporaryFile because Windows won't allow deleting
        # the log file even after it has been closed: WindowsError 32
        log_file = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_salt_api_parser_test",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.log_file = log_file.name
        log_file.close()
        api_logfile = tempfile.NamedTemporaryFile(
            prefix="test_parsers_",
            suffix="_api_logfile",
            dir=RUNTIME_VARS.TMP,
            delete=True,
        )
        self.api_logfile = api_logfile.name
        api_logfile.close()
        # Function to patch
        self.config_func = "salt.config.api_config"

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltAPIParser
        self.addCleanup(delattr, self, "parser")


class DaemonMixInTestCase(TestCase):
    """
    Tests the PIDfile deletion in the DaemonMixIn.
    """

    def setUp(self):
        """
        Setting up
        """
        # Setup mixin
        self.daemon_mixin = salt.utils.parsers.DaemonMixIn()
        self.daemon_mixin.config = {}
        self.daemon_mixin.config["pidfile"] = "/some/fake.pid"

    def tearDown(self):
        """
        Tear down test
        :return:
        """
        del self.daemon_mixin

    @patch("os.unlink", MagicMock())
    @patch("os.path.isfile", MagicMock(return_value=True))
    @patch("salt.utils.parsers.log", MagicMock())
    def test_pid_file_deletion(self):
        """
        PIDfile deletion without exception.
        """
        self.daemon_mixin._mixin_before_exit()
        assert salt.utils.parsers.os.unlink.call_count == 1
        salt.utils.parsers.log.info.assert_not_called()
        salt.utils.parsers.log.debug.assert_not_called()

    @patch("os.unlink", MagicMock(side_effect=OSError()))
    @patch("os.path.isfile", MagicMock(return_value=True))
    @patch("salt.utils.parsers.log", MagicMock())
    def test_pid_deleted_oserror_as_root(self):
        """
        PIDfile deletion with exception, running as root.
        """
        if salt.utils.platform.is_windows():
            patch_args = (
                "salt.utils.win_functions.is_admin",
                MagicMock(return_value=True),
            )
        else:
            patch_args = ("os.getuid", MagicMock(return_value=0))

        with patch(*patch_args):
            self.daemon_mixin._mixin_before_exit()
            assert salt.utils.parsers.os.unlink.call_count == 1
            salt.utils.parsers.log.info.assert_called_with(
                "PIDfile(%s) could not be deleted: %s",
                format(self.daemon_mixin.config["pidfile"], ""),
                ANY,
                exc_info_on_loglevel=logging.DEBUG,
            )

    @patch("os.unlink", MagicMock(side_effect=OSError()))
    @patch("os.path.isfile", MagicMock(return_value=True))
    @patch("salt.utils.parsers.log", MagicMock())
    def test_pid_deleted_oserror_as_non_root(self):
        """
        PIDfile deletion with exception, running as non-root.
        """
        if salt.utils.platform.is_windows():
            patch_args = (
                "salt.utils.win_functions.is_admin",
                MagicMock(return_value=False),
            )
        else:
            patch_args = ("os.getuid", MagicMock(return_value=1000))

        with patch(*patch_args):
            self.daemon_mixin._mixin_before_exit()
            assert salt.utils.parsers.os.unlink.call_count == 1
            salt.utils.parsers.log.info.assert_not_called()
            salt.utils.parsers.log.debug.assert_not_called()
