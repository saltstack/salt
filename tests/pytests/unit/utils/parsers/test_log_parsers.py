"""
    :codeauthor: Denys Havrysh <denys.gavrysh@gmail.com>
"""

import logging
import os
import pprint

import pytest

import salt._logging
import salt.config
import salt.syspaths
import salt.utils.jid
import salt.utils.parsers
import salt.utils.platform
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


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

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self._destroy()


# <----------- START TESTS ----------->


@pytest.fixture
def root_dir(tmp_path):
    yield tmp_path / "parsers_tests_root_dir"


@pytest.fixture(
    params=[
        "master",
        "minion",
        "proxyminion",
        "syndic",
        "saltcmd",
        "saltcp",
        "saltkey",
        "saltcall",
        "saltrun",
        "saltssh",
        "saltcloud",
        "spm",
        "saltapi",
    ]
)
def log_cli_parser(request):
    return request.param


@pytest.fixture
def default_config(log_cli_parser):
    if log_cli_parser == "master":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "minion":
        return salt.config.DEFAULT_MINION_OPTS.copy()
    elif log_cli_parser == "proxyminion":
        return {
            **salt.config.DEFAULT_MINION_OPTS.copy(),
            **salt.config.DEFAULT_PROXY_MINION_OPTS.copy(),
        }
    elif log_cli_parser == "syndic":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "saltcmd":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "saltcp":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "saltkey":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "saltcall":
        return salt.config.DEFAULT_MINION_OPTS.copy()
    elif log_cli_parser == "saltrun":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "saltssh":
        return salt.config.DEFAULT_MASTER_OPTS.copy()
    elif log_cli_parser == "saltcloud":
        return {
            **salt.config.DEFAULT_MASTER_OPTS.copy(),
            **salt.config.DEFAULT_CLOUD_OPTS.copy(),
        }
    elif log_cli_parser == "spm":
        return {
            **salt.config.DEFAULT_MASTER_OPTS.copy(),
            **salt.config.DEFAULT_SPM_OPTS.copy(),
        }
    elif log_cli_parser == "saltapi":
        return {
            **salt.config.DEFAULT_MASTER_OPTS.copy(),
            **salt.config.DEFAULT_API_OPTS.copy(),
        }


@pytest.fixture
def parser(log_cli_parser):
    param_map = {
        "master": salt.utils.parsers.MasterOptionParser,
        "minion": salt.utils.parsers.MinionOptionParser,
        "proxyminion": salt.utils.parsers.ProxyMinionOptionParser,
        "syndic": salt.utils.parsers.SyndicOptionParser,
        "saltcmd": salt.utils.parsers.SaltCMDOptionParser,
        "saltcp": salt.utils.parsers.SaltCPOptionParser,
        "saltkey": salt.utils.parsers.SaltKeyOptionParser,
        "saltcall": salt.utils.parsers.SaltCallOptionParser,
        "saltrun": salt.utils.parsers.SaltRunOptionParser,
        "saltssh": salt.utils.parsers.SaltSSHOptionParser,
        "saltcloud": salt.utils.parsers.SaltCloudParser,
        "spm": salt.utils.parsers.SPMParser,
        "saltapi": salt.utils.parsers.SaltAPIParser,
    }
    return param_map[log_cli_parser]


@pytest.fixture
def config_func(log_cli_parser):
    param_map = {
        "master": "salt.config.master_config",
        "minion": "salt.config.minion_config",
        "proxyminion": "salt.config.proxy_config",
        "syndic": "salt.config.syndic_config",
        "saltcmd": "salt.config.client_config",
        "saltcp": "salt.config.master_config",
        "saltkey": "salt.config.client_config",
        "saltcall": "salt.config.minion_config",
        "saltrun": "salt.config.master_config",
        "saltssh": "salt.config.master_config",
        "saltcloud": "salt.config.cloud_config",
        "spm": "salt.config.spm_config",
        "saltapi": "salt.config.api_config",
    }
    return param_map[log_cli_parser]


@pytest.fixture
def log_file(tmp_path, logfile_config_setting_name):
    return str(tmp_path / logfile_config_setting_name)


@pytest.fixture
def args(log_cli_parser):
    if log_cli_parser in ("saltcmd", "saltssh"):
        return ["foo", "bar.baz"]
    elif log_cli_parser == "saltcp":
        return ["foo", "bar", "baz"]
    elif log_cli_parser in ("saltcall", "saltrun"):
        return ["foo.bar"]
    elif log_cli_parser == "saltcloud":
        return ["-p", "foo", "bar"]
    elif log_cli_parser == "spm":
        return ["foo", "bar"]
    return []


@pytest.fixture
def loglevel_config_setting_name():
    return "log_level"


@pytest.fixture
def logfile_config_setting_name(log_cli_parser):
    if log_cli_parser == "syndic":
        return "syndic_log_file"
    elif log_cli_parser == "saltkey":
        return "key_logfile"
    elif log_cli_parser == "saltssh":
        return "ssh_log_file"
    elif log_cli_parser == "spm":
        return "spm_logfile"
    elif log_cli_parser == "saltapi":
        return "api_logfile"
    return "log_file"


@pytest.fixture
def logfile_loglevel_config_setting_name():
    return "log_level_logfile"


@pytest.fixture
def testing_config(default_config, root_dir, logfile_config_setting_name, log_file):
    _testing_config = default_config.copy()
    _testing_config["root_dir"] = root_dir
    for name in ("pki_dir", "cachedir"):
        _testing_config[name] = name
    _testing_config[logfile_config_setting_name] = log_file
    return _testing_config


@pytest.fixture(autouse=True)
def log_impl():
    """
    Mock logger functions
    """
    with LogImplMock() as _log_impl:
        mocked_functions = {}
        for name in dir(_log_impl):
            if name.startswith("_"):
                continue
            func = getattr(_log_impl, name)
            if not callable(func):
                continue
            mocked_functions[name] = func

        patcher = patch.multiple(salt._logging, **mocked_functions)
        with patcher:
            yield _log_impl


def test_get_log_level_cli(
    testing_config, loglevel_config_setting_name, args, parser, config_func, log_impl
):
    """
    Tests that log level match command-line specified value
    """
    # Set defaults
    default_log_level = testing_config[loglevel_config_setting_name]

    # Set log level in CLI
    log_level = "critical"
    args = ["--log-level", log_level] + args

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    console_log_level = getattr(instance.options, loglevel_config_setting_name)

    # Check console log level setting
    assert console_log_level == log_level
    # Check console logger log level
    assert log_impl.log_level_console == log_level
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.temp_log_level == log_level
    # Check log file logger log level
    assert log_impl.log_level_logfile == default_log_level


def test_get_log_level_config(
    testing_config, loglevel_config_setting_name, args, parser, config_func, log_impl
):
    """
    Tests that log level match the configured value
    """
    # Set log level in config
    log_level = "info"
    testing_config.update({loglevel_config_setting_name: log_level})

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    console_log_level = getattr(instance.options, loglevel_config_setting_name)

    # Check console log level setting
    assert console_log_level == log_level
    # Check console logger log level
    assert log_impl.log_level_console == log_level
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.temp_log_level == "error"
    # Check log file logger log level
    assert log_impl.log_level_logfile == log_level


def test_get_log_level_default(
    testing_config, loglevel_config_setting_name, args, parser, config_func, log_impl
):
    """
    Tests that log level match the default value
    """
    # Set defaults
    log_level = default_log_level = testing_config[loglevel_config_setting_name]

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    console_log_level = getattr(instance.options, loglevel_config_setting_name)

    # Check log level setting
    assert console_log_level == log_level
    # Check console logger log level
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.temp_log_level == "error"
    # Check log file logger
    assert log_impl.log_level_logfile == default_log_level
    # Check help message
    assert f"Default: '{default_log_level}'." in instance.get_option("--log-level").help


# log file configuration tests


def test_get_log_file_cli(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    log_file,
    logfile_config_setting_name,
):
    """
    Tests that log file match command-line specified value
    """
    # Set defaults
    log_level = testing_config[loglevel_config_setting_name]

    # Set log file in CLI
    log_file = f"{log_file}_cli.log"
    args = ["--log-file", log_file] + args

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_file_option = getattr(instance.options, logfile_config_setting_name)

    # Check console logger
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.config[logfile_config_setting_name] == log_file
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file setting
    assert log_file_option == log_file
    # Check log file logger
    assert log_impl.log_file == log_file


def test_get_log_file_config(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    logfile_config_setting_name,
    log_file,
):
    """
    Tests that log file match the configured value
    """
    # Set defaults
    log_level = testing_config[loglevel_config_setting_name]

    # Set log file in config
    log_file = f"{log_file}_config.log"
    testing_config.update({logfile_config_setting_name: log_file})

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_file_option = getattr(instance.options, logfile_config_setting_name)

    # Check console logger
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.config[logfile_config_setting_name] == log_file
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file setting
    assert log_file_option == log_file
    # Check log file logger
    assert log_impl.log_file == log_file


def test_get_log_file_default(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    logfile_config_setting_name,
    default_config,
):
    """
    Tests that log file match the default value
    """
    # Set defaults
    log_level = testing_config[loglevel_config_setting_name]
    log_file = testing_config[logfile_config_setting_name]
    default_log_file = default_config[logfile_config_setting_name]

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_file_option = getattr(instance.options, logfile_config_setting_name)

    # Check console logger
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.config[logfile_config_setting_name] == log_file
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file setting
    assert log_file_option == log_file
    # Check log file logger
    assert log_impl.log_file == log_file
    # Check help message
    assert f"Default: '{default_log_file}'." in instance.get_option("--log-file").help


# log file log level configuration tests


def test_get_log_file_level_cli(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    logfile_loglevel_config_setting_name,
):
    """
    Tests that file log level match command-line specified value
    """
    # Set defaults
    default_log_level = testing_config[loglevel_config_setting_name]

    # Set log file level in CLI
    log_level_logfile = "error"
    args = ["--log-file-level", log_level_logfile] + args

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_level_logfile_option = getattr(
        instance.options, logfile_loglevel_config_setting_name
    )

    # Check console logger
    assert log_impl.log_level_console == default_log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == default_log_level
    assert log_impl.config[logfile_loglevel_config_setting_name] == log_level_logfile
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file level setting
    assert log_level_logfile_option == log_level_logfile
    # Check log file logger
    assert log_impl.log_level_logfile == log_level_logfile


def test_get_log_file_level_config(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    logfile_loglevel_config_setting_name,
):
    """
    Tests that log file level match the configured value
    """
    # Set defaults
    log_level = testing_config[loglevel_config_setting_name]

    # Set log file level in config
    log_level_logfile = "info"
    testing_config.update({logfile_loglevel_config_setting_name: log_level_logfile})

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_level_logfile_option = getattr(
        instance.options, logfile_loglevel_config_setting_name
    )

    # Check console logger
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.config[logfile_loglevel_config_setting_name] == log_level_logfile
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file level setting
    assert log_level_logfile_option == log_level_logfile
    # Check log file logger
    assert log_impl.log_level_logfile == log_level_logfile


def test_get_log_file_level_default(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    logfile_loglevel_config_setting_name,
):
    """
    Tests that log file level match the default value
    """
    # Set defaults
    default_log_level = testing_config[loglevel_config_setting_name]

    log_level = default_log_level
    log_level_logfile = default_log_level

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_level_logfile_option = getattr(
        instance.options, logfile_loglevel_config_setting_name
    )

    # Check console logger
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.config[logfile_loglevel_config_setting_name] == log_level_logfile
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file level setting
    assert log_level_logfile_option == log_level_logfile
    # Check log file logger
    assert log_impl.log_level_logfile == log_level_logfile
    # Check help message
    assert (
        f"Default: '{default_log_level}'."
        in instance.get_option("--log-file-level").help
    )


def test_get_console_log_level_with_file_log_level(
    testing_config,
    loglevel_config_setting_name,
    args,
    parser,
    config_func,
    log_impl,
    logfile_loglevel_config_setting_name,
):  # pylint: disable=invalid-name
    """
    Tests that both console log level and log file level setting are working together
    """
    log_level = "critical"
    log_level_logfile = "debug"

    args = ["--log-file-level", log_level_logfile] + args

    testing_config.update({loglevel_config_setting_name: log_level})

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    log_level_logfile_option = getattr(
        instance.options, logfile_loglevel_config_setting_name
    )

    # Check console logger
    assert log_impl.log_level_console == log_level
    # Check extended logger
    assert log_impl.config[loglevel_config_setting_name] == log_level
    assert log_impl.config[logfile_loglevel_config_setting_name] == log_level_logfile
    # Check temp logger
    assert log_impl.temp_log_level == "error"
    # Check log file level setting
    assert log_level_logfile_option == log_level_logfile
    # Check log file logger
    assert log_impl.log_level_logfile == log_level_logfile


def test_log_created(
    testing_config, args, parser, config_func, logfile_config_setting_name, log_file
):
    """
    Tests that log file is created
    """
    testing_config.update({"log_file": str(log_file)})
    log_file_name = str(log_file)
    if log_file_name.rsplit(os.sep, maxsplit=1)[-1] != "log_file":
        testing_config.update({log_file_name: str(log_file)})

    instance = parser()
    with patch(config_func, MagicMock(return_value=testing_config)):
        instance.parse_args(args)

    assert os.path.exists(str(log_file_name))


def test_callbacks_uniqueness(parser):
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
    instance = parser()
    nums_1 = {}
    for cb_container in mixin_container_names:
        obj = getattr(instance, cb_container)
        nums_1[cb_container] = len(obj)

    # The next time we instantiate the parser, the counts should be equal
    instance = parser()
    nums_2 = {}
    for cb_container in mixin_container_names:
        obj = getattr(instance, cb_container)
        nums_2[cb_container] = len(obj)
    assert nums_1 == nums_2


def test_verify_log_warning_logged(args, config_func, testing_config, parser, caplog):
    args = ["--log-level", "debug"] + args
    with caplog.at_level(logging.DEBUG):
        instance = parser()
        with patch(config_func, MagicMock(return_value=testing_config)):
            instance.parse_args(args)
        assert (
            "Insecure logging configuration detected! Sensitive data may be logged."
            in caplog.messages
        )
