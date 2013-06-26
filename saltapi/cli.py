'''
CLI entry-point for salt-api
'''
# Import python libs
import sys
import logging

# Import salt libs
import salt.utils.verify
from salt.utils.parsers import (
    ConfigDirMixIn,
    DaemonMixIn,
    LogLevelMixIn,
    MergeConfigMixIn,
    OptionParser,
    OptionParserMeta,
    PidfileMixin)

# Import salt-api libs
import saltapi.client
import saltapi.config
import saltapi.version

log = logging.getLogger(__name__)


class SaltAPI(OptionParser, ConfigDirMixIn, LogLevelMixIn, PidfileMixin,
              DaemonMixIn, MergeConfigMixIn):
    '''
    The cli parser object used to fire up the salt api system.
    '''
    __metaclass__ = OptionParserMeta

    VERSION = saltapi.version.__version__

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/api'

    def setup_config(self):
        return saltapi.config.api_config(self.get_config_file_path())

    def run(self):
        '''
        Run the api
        '''
        self.parse_args()
        try:
            if self.config['verify_env']:
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith('tcp://') \
                        and not logfile.startswith('udp://') \
                        and not logfile.startswith('file://'):
                    # Logfile is not using Syslog, verify
                    salt.utils.verify.verify_files(
                        [logfile], self.config['user']
                    )
        except OSError as err:
            log.error(err)
            sys.exit(err.errno)

        self.setup_logfile_logger()
        client = saltapi.client.SaltAPIClient(self.config)
        self.daemonize_if_required()
        self.set_pidfile()
        client.run()
